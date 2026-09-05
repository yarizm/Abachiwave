"""Guards for the ``EnumString`` columns.

Every column annotated ``Mapped[SomeStrEnum]`` used to be declared as a bare
``String``: a freshly constructed object held an enum member, but a row loaded
back from the database handed out a plain ``str``. mypy trusted the annotation
and so could not flag ``.value`` on a loaded row, which failed at runtime.
"""

import ast
from pathlib import Path
from typing import NamedTuple, cast

import pytest
from sqlalchemy import String, Table, select, text
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.engine.interfaces import Dialect
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from abachiwave.core.database import Base
from abachiwave.core.types import EnumString
from abachiwave.models.audio import AudioUpload, AudioUploadKind, AudioUploadStatus
from abachiwave.models.composition import MidiAssetKind
from abachiwave.models.project import Project, ProjectStatus

MODELS_DIR = Path(__file__).resolve().parents[1] / "src" / "abachiwave" / "models"

# SQLAlchemy's dialect factories are untyped, so bind them once here.
PG_DIALECT: Dialect = postgresql.dialect()  # type: ignore[no-untyped-call]
SQLITE_DIALECT: Dialect = sqlite.dialect()


def _strenum_names() -> set[str]:
    names: set[str] = set()
    for path in MODELS_DIR.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and any(
                isinstance(base, ast.Name) and base.id == "StrEnum" for base in node.bases
            ):
                names.add(node.name)
    return names


class DeclaredEnumColumn(NamedTuple):
    filename: str
    lineno: int
    model: str
    attribute: str
    enum_name: str
    column_type: str


def _declared_enum_columns() -> list[DeclaredEnumColumn]:
    """Parse every ``x: Mapped[SomeStrEnum] = mapped_column(<type>, ...)`` declaration.

    Read from the source rather than the mapper because a bare ``String`` column
    reports ``python_type`` of ``str`` -- the very confusion under test -- so the
    mapper alone cannot tell a correct column from a broken one. Parsed as an AST
    rather than line-wise regex because most of these declarations span lines.
    """
    enum_names = _strenum_names()
    assert enum_names, "expected to find StrEnum declarations in the models package"

    declared: list[DeclaredEnumColumn] = []
    for path in sorted(MODELS_DIR.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for model in ast.walk(tree):
            if not isinstance(model, ast.ClassDef):
                continue
            for node in model.body:
                if not isinstance(node, ast.AnnAssign) or not isinstance(node.target, ast.Name):
                    continue
                annotation = node.annotation
                # Mapped[SomeEnum] -- the nullable form is Mapped[SomeEnum | None].
                if not (
                    isinstance(annotation, ast.Subscript)
                    and isinstance(annotation.value, ast.Name)
                    and annotation.value.id == "Mapped"
                ):
                    continue
                inner = annotation.slice
                enum_name = inner.id if isinstance(inner, ast.Name) else None
                if enum_name is None and isinstance(inner, ast.BinOp):
                    enum_name = inner.left.id if isinstance(inner.left, ast.Name) else None
                if enum_name is None or enum_name not in enum_names:
                    continue
                call = node.value
                if not (
                    isinstance(call, ast.Call)
                    and isinstance(call.func, ast.Name)
                    and call.func.id == "mapped_column"
                    and call.args
                ):
                    continue
                first = call.args[0]
                if isinstance(first, ast.Call) and isinstance(first.func, ast.Name):
                    column_type = first.func.id
                elif isinstance(first, ast.Name):
                    column_type = first.id
                else:
                    column_type = ast.dump(first)
                declared.append(
                    DeclaredEnumColumn(
                        path.name, node.lineno, model.name, node.target.id, enum_name, column_type
                    )
                )
    return declared


def test_no_model_annotates_an_enum_over_a_bare_string_column() -> None:
    """Source-level guard: every enum-annotated column must be declared EnumString.

    This is the guard that would have caught the original bug. It has to read the
    source, because once SQLAlchemy has built the column a bare ``String`` is
    indistinguishable from a correct one by type alone.
    """
    declared = _declared_enum_columns()
    assert len(declared) >= 20, f"expected the full set of enum columns, found {declared}"

    offenders = [
        f"{column.filename}:{column.lineno} {column.attribute}: "
        f"Mapped[{column.enum_name}] -> {column.column_type}(...)"
        for column in declared
        if column.column_type != "EnumString"
    ]
    assert offenders == [], (
        "these columns are annotated as an enum but not declared EnumString, so a "
        "loaded row will hand back str: " + "; ".join(offenders)
    )


def _mapped_tables() -> list[tuple[str, Table]]:
    """(model class name, table) for every mapper, typed so mypy can index columns."""
    return [
        (mapper.class_.__name__, cast(Table, mapper.local_table))
        for mapper in Base.registry.mappers
    ]


def test_every_declared_enum_column_is_enum_string_on_the_mapper() -> None:
    """The declarations above must survive into the built mapper as EnumString."""
    declared = _declared_enum_columns()
    by_model: dict[str, set[str]] = {}
    for declaration in declared:
        by_model.setdefault(declaration.model, set()).add(declaration.attribute)

    offenders = []
    checked = 0
    for model_name, table in _mapped_tables():
        for attribute in by_model.get(model_name, set()):
            column = table.columns[attribute]
            if isinstance(column.type, EnumString):
                checked += 1
            else:
                offenders.append(f"{table.name}.{column.name} -> {column.type!r}")
    assert offenders == [], "not EnumString on the mapper: " + ", ".join(offenders)
    assert checked == len(declared), f"verified {checked} of {len(declared)} declared columns"


def test_enum_string_ddl_matches_plain_string() -> None:
    """The stored representation is unchanged, which is why no migration is needed."""
    checked = 0
    for dialect in (PG_DIALECT, SQLITE_DIALECT):
        for _, table in _mapped_tables():
            for column in table.columns:
                column_type = column.type
                if not isinstance(column_type, EnumString):
                    continue
                rendered = column_type.compile(dialect=dialect)
                expected = String(column_type.length).compile(dialect=dialect)
                assert rendered == expected, (
                    f"{table.name}.{column.name} renders {rendered}, expected {expected}"
                )
                checked += 1
    assert checked > 0, "expected at least one EnumString column to check"


def test_columns_behind_the_known_workarounds_are_covered() -> None:
    """The specific columns whose loaded-as-str behaviour forced defensive call sites.

    ``song_spec_versions.status`` and ``generation_runs.status`` backed the two
    ``isinstance`` dances; ``audio_uploads.kind`` produced an AttributeError in the
    audio-to-MIDI run manifest.
    """
    tables = {table.name: table for _, table in _mapped_tables()}
    for table_name, column_name, expected_enum in (
        ("song_spec_versions", "status", "SongSpecStatus"),
        ("generation_runs", "status", "GenerationRunStatus"),
        ("audio_uploads", "kind", "AudioUploadKind"),
        ("midi_asset_versions", "kind", "MidiAssetKind"),
        ("projects", "status", "ProjectStatus"),
    ):
        column_type = tables[table_name].columns[column_name].type
        assert isinstance(column_type, EnumString), f"{table_name}.{column_name} is {column_type!r}"
        assert column_type.python_type.__name__ == expected_enum


async def test_loaded_row_returns_enum_member_not_str(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """The regression this whole change exists to prevent."""
    async with session_factory() as session:
        session.add(Project(id="p-enum-1", name="Enum Round Trip", status=ProjectStatus.active))
        await session.commit()

    # A fresh session guarantees the object is loaded from the database rather than
    # served out of the identity map with the value it was constructed with.
    async with session_factory() as session:
        loaded = (
            await session.execute(select(Project).where(Project.id == "p-enum-1"))
        ).scalar_one()
        assert type(loaded.status) is ProjectStatus
        assert loaded.status is ProjectStatus.active
        # The point of the exercise: this used to raise AttributeError.
        assert loaded.status.value == "active"


async def test_round_trip_stores_the_same_bytes_as_before(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Raw SQL sees the plain enum value, so existing rows stay readable."""
    async with session_factory() as session:
        session.add(Project(id="p-enum-2", name="Bytes", status=ProjectStatus.archived))
        session.add(
            AudioUpload(
                id="au-enum-1",
                project_id="p-enum-2",
                kind=AudioUploadKind.humming,
                status=AudioUploadStatus.available,
                storage_key="k",
                filename="f.wav",
                content_type="audio/wav",
                size_bytes=1,
                checksum="c",
            )
        )
        await session.commit()

    async with session_factory() as session:
        raw = (
            await session.execute(
                text("select kind, status from audio_uploads where id = :upload_id"),
                {"upload_id": "au-enum-1"},
            )
        ).one()
        assert tuple(raw) == ("humming", "available")

        raw_status = (
            await session.execute(
                text("select status from projects where id = :project_id"),
                {"project_id": "p-enum-2"},
            )
        ).scalar_one()
        assert raw_status == "archived"

        upload = (
            await session.execute(select(AudioUpload).where(AudioUpload.id == "au-enum-1"))
        ).scalar_one()
        assert type(upload.kind) is AudioUploadKind
        assert type(upload.status) is AudioUploadStatus
        assert upload.kind.value == "humming"


async def test_rows_written_as_raw_strings_load_as_enum_members(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Pre-existing rows were written by the old String column; they must still load."""
    async with session_factory() as session:
        await session.execute(
            text(
                "insert into projects (id, name, status, created_at, updated_at) "
                "values (:id, :name, :status, :now, :now)"
            ),
            {
                "id": "p-legacy",
                "name": "Legacy Row",
                "status": "archived",
                "now": "2026-01-01 00:00:00",
            },
        )
        await session.commit()

    async with session_factory() as session:
        loaded = (
            await session.execute(select(Project).where(Project.id == "p-legacy"))
        ).scalar_one()
        assert type(loaded.status) is ProjectStatus
        assert loaded.status is ProjectStatus.archived


def test_enum_string_rejects_values_outside_the_enum() -> None:
    """A value the enum does not define is corruption, and must not pass silently."""
    column_type = EnumString(MidiAssetKind, 16)
    with pytest.raises(ValueError):
        column_type.process_result_value("not_a_kind", SQLITE_DIALECT)
    with pytest.raises(ValueError):
        column_type.process_bind_param("not_a_kind", SQLITE_DIALECT)


def test_enum_string_accepts_member_or_raw_value_on_write() -> None:
    column_type = EnumString(MidiAssetKind, 16)
    assert column_type.process_bind_param(MidiAssetKind.chord, SQLITE_DIALECT) == "chord"
    assert column_type.process_bind_param("chord", SQLITE_DIALECT) == "chord"
    assert column_type.process_bind_param(None, SQLITE_DIALECT) is None
    assert column_type.process_result_value(None, SQLITE_DIALECT) is None


def test_enum_string_copy_preserves_enum_and_length() -> None:
    """SQLAlchemy copies column types internally; the enum must survive that."""
    copied = EnumString(MidiAssetKind, 16).copy()
    assert copied.enum_type is MidiAssetKind
    assert copied.length == 16
    assert copied.process_result_value("chord", SQLITE_DIALECT) is MidiAssetKind.chord


def test_distinct_enums_do_not_share_a_query_cache_key() -> None:
    """``cache_ok = True`` is only safe while the enum is part of the cache key.

    If two EnumString columns over different enums compiled to the same key,
    SQLAlchemy could reuse a cached statement and coerce a loaded value into the
    wrong enum.
    """
    same_a = EnumString(MidiAssetKind, 16)._static_cache_key
    same_b = EnumString(MidiAssetKind, 16)._static_cache_key
    other = EnumString(AudioUploadKind, 24)._static_cache_key
    assert same_a == same_b
    assert same_a != other

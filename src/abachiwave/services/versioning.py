from collections.abc import Awaitable, Callable
from uuid import UUID

from sqlalchemy import Select, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from abachiwave.core.config import get_settings
from abachiwave.core.database import Base
from abachiwave.models.project import Project

VERSION_CONFLICT_MESSAGE = "Asset version changed concurrently; retry the request"
_VERSION_CONSTRAINT_NAMES = {
    "uq_arrangement_plan_versions_project_version",
    "uq_audio_demo_versions_project_version",
    "uq_chord_progression_versions_project_version",
    "uq_lyrics_versions_project_version",
    "uq_midi_asset_versions_project_kind_version",
    "uq_song_spec_versions_project_version",
}
_SQLITE_VERSION_CONFLICT_COLUMNS = {
    "arrangement_plan_versions.project_id, arrangement_plan_versions.version_number",
    "audio_demo_versions.project_id, audio_demo_versions.version_number",
    "chord_progression_versions.project_id, chord_progression_versions.version_number",
    "lyrics_versions.project_id, lyrics_versions.version_number",
    (
        "midi_asset_versions.project_id, midi_asset_versions.kind, "
        "midi_asset_versions.version_number"
    ),
    "song_spec_versions.project_id, song_spec_versions.version_number",
}
VersionNumberLoader = Callable[[], Awaitable[int]]


class ProjectVersionLockError(RuntimeError):
    pass


class VersionWriteConflictError(RuntimeError):
    pass


def project_version_lock_statement(project_id: UUID) -> Select[tuple[str]]:
    return (
        select(Project.id)
        .where(Project.id == str(project_id))
        .with_for_update()
    )


async def lock_project_for_version_write(session: AsyncSession, project_id: UUID) -> None:
    result = await session.execute(project_version_lock_statement(project_id))
    if result.scalar_one_or_none() is None:
        raise ProjectVersionLockError("Project not found while allocating an asset version")
    bind = session.get_bind()
    if bind.dialect.name == "sqlite":
        await session.execute(
            update(Project)
            .where(Project.id == str(project_id))
            .values(updated_at=Project.updated_at)
        )


async def create_version_with_retry[VersionModel: Base](
    *,
    session: AsyncSession,
    project_id: UUID,
    load_next_version_number: VersionNumberLoader,
    build_version: Callable[[int], VersionModel],
    max_retries: int | None = None,
) -> VersionModel:
    await lock_project_for_version_write(session, project_id)
    retry_limit = (
        get_settings().version_write_max_retries if max_retries is None else max_retries
    )
    if retry_limit < 0:
        raise ValueError("max_retries must not be negative")

    for attempt in range(retry_limit + 1):
        version_number = await load_next_version_number()
        version = build_version(version_number)
        try:
            async with session.begin_nested():
                session.add(version)
                await session.flush()
        except IntegrityError as error:
            if not is_version_number_conflict(error):
                raise
            if attempt == retry_limit:
                raise VersionWriteConflictError(VERSION_CONFLICT_MESSAGE) from error
            continue
        return version

    raise AssertionError("version retry loop exited unexpectedly")


def is_version_number_conflict(error: IntegrityError) -> bool:
    diagnostic = getattr(error.orig, "diag", None)
    constraint_name = getattr(diagnostic, "constraint_name", None)
    if constraint_name in _VERSION_CONSTRAINT_NAMES:
        return True
    message = str(error.orig).lower()
    return any(columns in message for columns in _SQLITE_VERSION_CONFLICT_COLUMNS)

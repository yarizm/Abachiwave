"""add structured chord measures and events

Revision ID: 202607140003
Revises: 202607140002
Create Date: 2026-07-14
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from alembic import op

revision: str = "202607140003"
down_revision: str | None = "202607140002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "chord_progression_versions",
        sa.Column(
            "schema_version",
            sa.Integer(),
            server_default=sa.text("2"),
            nullable=False,
        ),
    )
    _backfill_structured_chords()


def downgrade() -> None:
    op.drop_column("chord_progression_versions", "schema_version")


def _backfill_structured_chords() -> None:
    chord_versions = sa.table(
        "chord_progression_versions",
        sa.column("id", sa.String(length=36)),
        sa.column("time_signature", sa.String(length=16)),
        sa.column("sections", sa.JSON()),
    )
    connection = op.get_bind()
    rows = connection.execute(
        sa.select(
            chord_versions.c.id,
            chord_versions.c.time_signature,
            chord_versions.c.sections,
        )
    ).mappings()
    for row in rows:
        beats_per_measure = _beats_per_measure(str(row["time_signature"] or "4/4"))
        migrated_sections: list[dict[str, object]] = []
        for section_index, raw_section in enumerate(row["sections"] or []):
            section = dict(raw_section) if isinstance(raw_section, dict) else {}
            if isinstance(section.get("measures"), list) and section["measures"]:
                migrated_sections.append(section)
                continue
            section_id = str(section.get("section_id") or f"section-{section_index + 1}")
            chords = [
                str(chord).strip()
                for chord in section.get("chords", [])
                if str(chord).strip()
            ]
            if not chords:
                chords = ["N.C."]
            bar_count = max(1, min(64, int(section.get("bars") or len(chords))))
            section["bars"] = bar_count
            section["chords"] = chords
            section["measures"] = [
                {
                    "measure_number": measure_number,
                    "events": [
                        {
                            "event_id": str(
                                uuid5(
                                    NAMESPACE_URL,
                                    (
                                        "abachiwave:chords:"
                                        f"{section_id}:{measure_number}:0"
                                    ),
                                )
                            ),
                            "measure": measure_number,
                            "beat": 1,
                            "duration_beats": beats_per_measure,
                            "symbol": chords[(measure_number - 1) % len(chords)],
                            "inversion": None,
                        }
                    ],
                }
                for measure_number in range(1, bar_count + 1)
            ]
            migrated_sections.append(section)
        connection.execute(
            chord_versions.update()
            .where(chord_versions.c.id == row["id"])
            .values(sections=migrated_sections)
        )


def _beats_per_measure(time_signature: str) -> int:
    numerator = time_signature.split("/", maxsplit=1)[0].strip()
    return max(1, min(32, int(numerator))) if numerator.isdigit() else 4

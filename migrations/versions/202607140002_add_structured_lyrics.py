"""add structured lyric lines

Revision ID: 202607140002
Revises: 202607140001
Create Date: 2026-07-14
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from alembic import op

revision: str = "202607140002"
down_revision: str | None = "202607140001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "lyrics_versions",
        sa.Column(
            "schema_version",
            sa.Integer(),
            server_default=sa.text("2"),
            nullable=False,
        ),
    )
    _backfill_structured_lines()


def downgrade() -> None:
    op.drop_column("lyrics_versions", "schema_version")


def _backfill_structured_lines() -> None:
    lyrics = sa.table(
        "lyrics_versions",
        sa.column("id", sa.String(length=36)),
        sa.column("sections", sa.JSON()),
    )
    connection = op.get_bind()
    rows = connection.execute(sa.select(lyrics.c.id, lyrics.c.sections)).mappings()
    for row in rows:
        migrated_sections: list[dict[str, object]] = []
        for section_index, raw_section in enumerate(row["sections"] or []):
            section = dict(raw_section) if isinstance(raw_section, dict) else {}
            section_id = str(section.get("section_id") or f"section-{section_index + 1}")
            raw_lines = section.get("lines")
            if isinstance(raw_lines, list) and raw_lines:
                lines = raw_lines
            else:
                text_lines = [
                    line.strip()
                    for line in str(section.get("text") or "").splitlines()
                    if line.strip()
                ]
                lines = [
                    {
                        "line_id": str(
                            uuid5(
                                NAMESPACE_URL,
                                f"abachiwave:lyrics:{section_id}:{line_index}",
                            )
                        ),
                        "text": line,
                        "rhyme_label": None,
                    }
                    for line_index, line in enumerate(text_lines)
                ]
            section["lines"] = lines
            section["text"] = "\n".join(
                str(line.get("text") or "").strip()
                for line in lines
                if isinstance(line, dict) and str(line.get("text") or "").strip()
            )
            migrated_sections.append(section)
        connection.execute(
            lyrics.update().where(lyrics.c.id == row["id"]).values(sections=migrated_sections)
        )

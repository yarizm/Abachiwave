"""add stable song structure and change previews

Revision ID: 202607140001
Revises: 202607130003
Create Date: 2026-07-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202607140001"
down_revision: str | None = "202607130003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "song_spec_versions",
        sa.Column(
            "structure_sections",
            sa.JSON(),
            server_default=sa.text("'[]'"),
            nullable=False,
        ),
    )
    _backfill_structure_sections()

    op.create_table(
        "structure_change_previews",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("source_song_spec_id", sa.String(length=36), nullable=False),
        sa.Column("proposed_sections", sa.JSON(), nullable=False),
        sa.Column("impact", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="pending", nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_structure_change_previews_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_song_spec_id"],
            ["song_spec_versions.id"],
            name=op.f("fk_structure_change_previews_source_song_spec_id_song_spec_versions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_structure_change_previews")),
    )
    op.create_index(
        op.f("ix_structure_change_previews_project_id"),
        "structure_change_previews",
        ["project_id"],
    )
    op.create_index(
        op.f("ix_structure_change_previews_source_song_spec_id"),
        "structure_change_previews",
        ["source_song_spec_id"],
    )
    op.create_index(
        "ix_structure_change_previews_project_created",
        "structure_change_previews",
        ["project_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_structure_change_previews_project_created",
        table_name="structure_change_previews",
    )
    op.drop_index(
        op.f("ix_structure_change_previews_source_song_spec_id"),
        table_name="structure_change_previews",
    )
    op.drop_index(
        op.f("ix_structure_change_previews_project_id"),
        table_name="structure_change_previews",
    )
    op.drop_table("structure_change_previews")
    op.drop_column("song_spec_versions", "structure_sections")


def _backfill_structure_sections() -> None:
    song_specs = sa.table(
        "song_spec_versions",
        sa.column("id", sa.String(length=36)),
        sa.column("song_structure", sa.JSON()),
        sa.column("structure_sections", sa.JSON()),
    )
    connection = op.get_bind()
    rows = connection.execute(sa.select(song_specs.c.id, song_specs.c.song_structure)).mappings()
    for row in rows:
        labels = row["song_structure"] or []
        counts: dict[str, int] = {}
        sections: list[dict[str, str]] = []
        for index, raw_label in enumerate(labels):
            label = str(raw_label).strip()
            base = "".join(
                character if character.isascii() and character.isalnum() else "-"
                for character in label.lower()
            )
            base = "-".join(part for part in base.split("-") if part) or f"section-{index + 1}"
            base = base[:56]
            counts[base] = counts.get(base, 0) + 1
            suffix = f"-{counts[base]}" if counts[base] > 1 else ""
            sections.append({"section_id": f"{base}{suffix}", "label": label})
        connection.execute(
            song_specs.update()
            .where(song_specs.c.id == row["id"])
            .values(structure_sections=sections)
        )

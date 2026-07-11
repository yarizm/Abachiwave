"""add idea intake and song spec versions

Revision ID: 202607080001
Revises: 202607070001
Create Date: 2026-07-08 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202607080001"
down_revision: str | None = "202607070001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "idea_intakes",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("idea", sa.Text(), nullable=False),
        sa.Column("answers", sa.JSON(), nullable=False),
        sa.Column("questions", sa.JSON(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default="needs_clarification",
            nullable=False,
        ),
        sa.Column(
            "generation_source",
            sa.String(length=64),
            server_default="deterministic",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_idea_intakes_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_idea_intakes")),
    )
    op.create_index(op.f("ix_idea_intakes_project_id"), "idea_intakes", ["project_id"])

    op.create_table(
        "song_spec_versions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("intake_id", sa.String(length=36), nullable=True),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=24), server_default="draft", nullable=False),
        sa.Column("parent_version_id", sa.String(length=36), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("theme", sa.Text(), nullable=True),
        sa.Column("genre", sa.JSON(), nullable=True),
        sa.Column("language", sa.String(length=32), nullable=True),
        sa.Column("tempo_bpm", sa.Integer(), nullable=True),
        sa.Column("key", sa.String(length=64), nullable=True),
        sa.Column("time_signature", sa.String(length=16), nullable=True),
        sa.Column("target_duration_seconds", sa.Integer(), nullable=True),
        sa.Column("mood_curve", sa.JSON(), nullable=True),
        sa.Column("song_structure", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["intake_id"],
            ["idea_intakes.id"],
            name=op.f("fk_song_spec_versions_intake_id_idea_intakes"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["parent_version_id"],
            ["song_spec_versions.id"],
            name=op.f("fk_song_spec_versions_parent_version_id_song_spec_versions"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_song_spec_versions_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_song_spec_versions")),
        sa.UniqueConstraint(
            "project_id",
            "version_number",
            name="uq_song_spec_versions_project_version",
        ),
    )
    op.create_index(op.f("ix_song_spec_versions_intake_id"), "song_spec_versions", ["intake_id"])
    op.create_index(op.f("ix_song_spec_versions_project_id"), "song_spec_versions", ["project_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_song_spec_versions_project_id"), table_name="song_spec_versions")
    op.drop_index(op.f("ix_song_spec_versions_intake_id"), table_name="song_spec_versions")
    op.drop_table("song_spec_versions")
    op.drop_index(op.f("ix_idea_intakes_project_id"), table_name="idea_intakes")
    op.drop_table("idea_intakes")

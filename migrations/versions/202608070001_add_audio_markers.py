"""add audio markers

Revision ID: 202608070001
Revises: 202608010001
Create Date: 2026-08-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202608070001"
down_revision: str | None = "202608010001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audio_markers",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("audio_upload_id", sa.String(length=36), nullable=False),
        sa.Column("position_seconds", sa.Float(), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("section_id", sa.String(length=128), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
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
        sa.CheckConstraint(
            "position_seconds >= 0",
            name="audio_marker_position_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["audio_upload_id"],
            ["audio_uploads.id"],
            name=op.f("fk_audio_markers_audio_upload_id_audio_uploads"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_audio_markers_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audio_markers")),
    )
    op.create_index(
        op.f("ix_audio_markers_audio_upload_id"),
        "audio_markers",
        ["audio_upload_id"],
    )
    op.create_index(
        op.f("ix_audio_markers_project_id"),
        "audio_markers",
        ["project_id"],
    )
    op.create_index(
        "ix_audio_markers_upload_position",
        "audio_markers",
        ["audio_upload_id", "position_seconds"],
    )


def downgrade() -> None:
    op.drop_index("ix_audio_markers_upload_position", table_name="audio_markers")
    op.drop_index(op.f("ix_audio_markers_project_id"), table_name="audio_markers")
    op.drop_index(op.f("ix_audio_markers_audio_upload_id"), table_name="audio_markers")
    op.drop_table("audio_markers")

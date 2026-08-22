"""add audio derivatives

Revision ID: 202608080001
Revises: 202608070001
Create Date: 2026-08-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202608080001"
down_revision: str | None = "202608070001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audio_derivatives",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("audio_upload_id", sa.String(length=36), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=64), nullable=False),
        sa.Column("format", sa.String(length=16), nullable=False),
        sa.Column("sample_rate", sa.Integer(), nullable=False),
        sa.Column("channels", sa.Integer(), nullable=False),
        sa.Column("duration_seconds", sa.Float(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("source_checksum", sa.String(length=64), nullable=False),
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
            ["audio_upload_id"],
            ["audio_uploads.id"],
            name=op.f("fk_audio_derivatives_audio_upload_id_audio_uploads"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_audio_derivatives_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audio_derivatives")),
        sa.UniqueConstraint(
            "audio_upload_id",
            "kind",
            "source_checksum",
            name="uq_audio_derivatives_upload_kind_source",
        ),
    )
    op.create_index(
        op.f("ix_audio_derivatives_audio_upload_id"),
        "audio_derivatives",
        ["audio_upload_id"],
    )
    op.create_index(
        op.f("ix_audio_derivatives_kind"),
        "audio_derivatives",
        ["kind"],
    )
    op.create_index(
        op.f("ix_audio_derivatives_project_id"),
        "audio_derivatives",
        ["project_id"],
    )
    op.create_index(
        "ix_audio_derivatives_project_created",
        "audio_derivatives",
        ["project_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_audio_derivatives_project_created", table_name="audio_derivatives")
    op.drop_index(op.f("ix_audio_derivatives_project_id"), table_name="audio_derivatives")
    op.drop_index(op.f("ix_audio_derivatives_kind"), table_name="audio_derivatives")
    op.drop_index(op.f("ix_audio_derivatives_audio_upload_id"), table_name="audio_derivatives")
    op.drop_table("audio_derivatives")

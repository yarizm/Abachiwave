"""add audio uploads and audio-to-midi linkage

Revision ID: 202607080006
Revises: 202607080005
Create Date: 2026-07-08 00:06:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202607080006"
down_revision: str | None = "202607080005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audio_uploads",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("status", sa.String(length=24), server_default="available", nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("duration_seconds", sa.Float(), nullable=False),
        sa.Column("sample_rate", sa.Integer(), nullable=False),
        sa.Column("channels", sa.Integer(), nullable=False),
        sa.Column("waveform_peaks", sa.JSON(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_audio_uploads_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audio_uploads")),
    )
    op.create_index(op.f("ix_audio_uploads_kind"), "audio_uploads", ["kind"])
    op.create_index(op.f("ix_audio_uploads_project_id"), "audio_uploads", ["project_id"])
    op.create_index(op.f("ix_audio_uploads_status"), "audio_uploads", ["status"])

    with op.batch_alter_table("midi_asset_versions") as batch_op:
        batch_op.add_column(
            sa.Column("source_audio_upload_id", sa.String(length=36), nullable=True)
        )
        batch_op.create_foreign_key(
            op.f("fk_midi_asset_versions_source_audio_upload_id_audio_uploads"),
            "audio_uploads",
            ["source_audio_upload_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index(
            op.f("ix_midi_asset_versions_source_audio_upload_id"),
            ["source_audio_upload_id"],
        )

    with op.batch_alter_table("generation_runs") as batch_op:
        batch_op.add_column(sa.Column("result_midi_asset_id", sa.String(length=36), nullable=True))
        batch_op.create_foreign_key(
            op.f("fk_generation_runs_result_midi_asset_id_midi_asset_versions"),
            "midi_asset_versions",
            ["result_midi_asset_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index(
            op.f("ix_generation_runs_result_midi_asset_id"),
            ["result_midi_asset_id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("generation_runs") as batch_op:
        batch_op.drop_index(op.f("ix_generation_runs_result_midi_asset_id"))
        batch_op.drop_constraint(
            op.f("fk_generation_runs_result_midi_asset_id_midi_asset_versions"),
            type_="foreignkey",
        )
        batch_op.drop_column("result_midi_asset_id")

    with op.batch_alter_table("midi_asset_versions") as batch_op:
        batch_op.drop_index(op.f("ix_midi_asset_versions_source_audio_upload_id"))
        batch_op.drop_constraint(
            op.f("fk_midi_asset_versions_source_audio_upload_id_audio_uploads"),
            type_="foreignkey",
        )
        batch_op.drop_column("source_audio_upload_id")

    op.drop_index(op.f("ix_audio_uploads_status"), table_name="audio_uploads")
    op.drop_index(op.f("ix_audio_uploads_project_id"), table_name="audio_uploads")
    op.drop_index(op.f("ix_audio_uploads_kind"), table_name="audio_uploads")
    op.drop_table("audio_uploads")

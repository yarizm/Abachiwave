"""add reference analysis versions

Revision ID: 202608090001
Revises: 202608080002
Create Date: 2026-08-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202608090001"
down_revision: str | None = "202608080002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "reference_analysis_versions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("audio_upload_id", sa.String(length=36), nullable=False),
        sa.Column("audio_derivative_id", sa.String(length=36), nullable=True),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("source_checksum", sa.String(length=64), nullable=False),
        sa.Column("analysis_range", sa.JSON(), nullable=False),
        sa.Column("tempo_bpm", sa.Float(), nullable=False),
        sa.Column("beat_grid", sa.JSON(), nullable=False),
        sa.Column("time_signature", sa.JSON(), nullable=False),
        sa.Column("key_candidate", sa.JSON(), nullable=False),
        sa.Column("pitch_range", sa.JSON(), nullable=False),
        sa.Column("loudness", sa.JSON(), nullable=False),
        sa.Column("structure_sections", sa.JSON(), nullable=False),
        sa.Column("chord_candidates", sa.JSON(), nullable=False),
        sa.Column("instrument_tags", sa.JSON(), nullable=False),
        sa.Column("energy_curve", sa.JSON(), nullable=False),
        sa.Column("production_features", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.JSON(), nullable=False),
        sa.Column("provider_name", sa.String(length=64), nullable=False),
        sa.Column("provider_version", sa.String(length=64), nullable=False),
        sa.Column("provider_params", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("tempo_bpm > 0", name="reference_analysis_tempo_positive"),
        sa.CheckConstraint("version_number > 0", name="reference_analysis_version_positive"),
        sa.ForeignKeyConstraint(
            ["audio_derivative_id"],
            ["audio_derivatives.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["audio_upload_id"], ["audio_uploads.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["generation_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "audio_upload_id",
            "version_number",
            name="uq_reference_analysis_upload_version",
        ),
        sa.UniqueConstraint("run_id", name="uq_reference_analysis_run"),
    )
    op.create_index(
        "ix_reference_analysis_upload_created",
        "reference_analysis_versions",
        ["audio_upload_id", "created_at"],
    )
    op.create_index(
        "ix_reference_analysis_project_created",
        "reference_analysis_versions",
        ["project_id", "created_at"],
    )
    op.create_index(
        "ix_reference_analysis_versions_audio_derivative_id",
        "reference_analysis_versions",
        ["audio_derivative_id"],
    )
    op.create_index(
        "ix_reference_analysis_versions_audio_upload_id",
        "reference_analysis_versions",
        ["audio_upload_id"],
    )
    op.create_index(
        "ix_reference_analysis_versions_project_id",
        "reference_analysis_versions",
        ["project_id"],
    )
    op.create_index(
        "ix_reference_analysis_versions_run_id",
        "reference_analysis_versions",
        ["run_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_reference_analysis_versions_run_id",
        table_name="reference_analysis_versions",
    )
    op.drop_index(
        "ix_reference_analysis_versions_project_id",
        table_name="reference_analysis_versions",
    )
    op.drop_index(
        "ix_reference_analysis_versions_audio_upload_id",
        table_name="reference_analysis_versions",
    )
    op.drop_index(
        "ix_reference_analysis_versions_audio_derivative_id",
        table_name="reference_analysis_versions",
    )
    op.drop_index(
        "ix_reference_analysis_project_created",
        table_name="reference_analysis_versions",
    )
    op.drop_index(
        "ix_reference_analysis_upload_created",
        table_name="reference_analysis_versions",
    )
    op.drop_table("reference_analysis_versions")

"""add demo generation runs and audio demo versions

Revision ID: 202607080004
Revises: 202607080003
Create Date: 2026-07-08 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202607080004"
down_revision: str | None = "202607080003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "generation_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column(
            "run_type",
            sa.String(length=32),
            server_default="demo_generation",
            nullable=False,
        ),
        sa.Column("status", sa.String(length=24), server_default="queued", nullable=False),
        sa.Column("arq_job_id", sa.String(length=128), nullable=True),
        sa.Column("input_manifest", sa.JSON(), nullable=False),
        sa.Column("provider_name", sa.String(length=64), nullable=False),
        sa.Column("provider_version", sa.String(length=64), nullable=False),
        sa.Column("provider_params", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("retry_of_run_id", sa.String(length=36), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
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
            name=op.f("fk_generation_runs_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["retry_of_run_id"],
            ["generation_runs.id"],
            name=op.f("fk_generation_runs_retry_of_run_id_generation_runs"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_generation_runs")),
    )
    op.create_index(op.f("ix_generation_runs_project_id"), "generation_runs", ["project_id"])
    op.create_index(
        op.f("ix_generation_runs_retry_of_run_id"),
        "generation_runs",
        ["retry_of_run_id"],
    )
    op.create_index(op.f("ix_generation_runs_status"), "generation_runs", ["status"])

    op.create_table(
        "audio_demo_versions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("song_spec_id", sa.String(length=36), nullable=False),
        sa.Column("lyrics_version_id", sa.String(length=36), nullable=False),
        sa.Column("chord_version_id", sa.String(length=36), nullable=False),
        sa.Column("arrangement_plan_id", sa.String(length=36), nullable=False),
        sa.Column("midi_asset_ids", sa.JSON(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=64), server_default="audio/wav", nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=False),
        sa.Column("provider_name", sa.String(length=64), nullable=False),
        sa.Column("provider_version", sa.String(length=64), nullable=False),
        sa.Column("provider_params", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["arrangement_plan_id"],
            ["arrangement_plan_versions.id"],
            name=op.f("fk_audio_demo_versions_arrangement_plan_id_arrangement_plan_versions"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["chord_version_id"],
            ["chord_progression_versions.id"],
            name=op.f("fk_audio_demo_versions_chord_version_id_chord_progression_versions"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["lyrics_version_id"],
            ["lyrics_versions.id"],
            name=op.f("fk_audio_demo_versions_lyrics_version_id_lyrics_versions"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_audio_demo_versions_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["generation_runs.id"],
            name=op.f("fk_audio_demo_versions_run_id_generation_runs"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["song_spec_id"],
            ["song_spec_versions.id"],
            name=op.f("fk_audio_demo_versions_song_spec_id_song_spec_versions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audio_demo_versions")),
        sa.UniqueConstraint(
            "project_id",
            "version_number",
            name="uq_audio_demo_versions_project_version",
        ),
    )
    op.create_index(
        op.f("ix_audio_demo_versions_arrangement_plan_id"),
        "audio_demo_versions",
        ["arrangement_plan_id"],
    )
    op.create_index(
        op.f("ix_audio_demo_versions_chord_version_id"),
        "audio_demo_versions",
        ["chord_version_id"],
    )
    op.create_index(
        op.f("ix_audio_demo_versions_lyrics_version_id"),
        "audio_demo_versions",
        ["lyrics_version_id"],
    )
    op.create_index(
        op.f("ix_audio_demo_versions_project_id"),
        "audio_demo_versions",
        ["project_id"],
    )
    op.create_index(
        op.f("ix_audio_demo_versions_run_id"),
        "audio_demo_versions",
        ["run_id"],
    )
    op.create_index(
        op.f("ix_audio_demo_versions_song_spec_id"),
        "audio_demo_versions",
        ["song_spec_id"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_audio_demo_versions_song_spec_id"),
        table_name="audio_demo_versions",
    )
    op.drop_index(op.f("ix_audio_demo_versions_run_id"), table_name="audio_demo_versions")
    op.drop_index(
        op.f("ix_audio_demo_versions_project_id"),
        table_name="audio_demo_versions",
    )
    op.drop_index(
        op.f("ix_audio_demo_versions_lyrics_version_id"),
        table_name="audio_demo_versions",
    )
    op.drop_index(
        op.f("ix_audio_demo_versions_chord_version_id"),
        table_name="audio_demo_versions",
    )
    op.drop_index(
        op.f("ix_audio_demo_versions_arrangement_plan_id"),
        table_name="audio_demo_versions",
    )
    op.drop_table("audio_demo_versions")
    op.drop_index(op.f("ix_generation_runs_status"), table_name="generation_runs")
    op.drop_index(op.f("ix_generation_runs_retry_of_run_id"), table_name="generation_runs")
    op.drop_index(op.f("ix_generation_runs_project_id"), table_name="generation_runs")
    op.drop_table("generation_runs")

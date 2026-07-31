# ruff: noqa: E501
"""add AI provider profiles, prompt versions, and generation candidates

Revision ID: 202607130002
Revises: 202607130001
Create Date: 2026-07-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202607130002"
down_revision: str | None = "202607130001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "generation_runs",
        sa.Column("provider_usage", sa.JSON(), server_default="{}", nullable=False),
    )
    op.add_column("generation_runs", sa.Column("error_code", sa.String(length=64), nullable=True))

    op.create_table(
        "provider_profiles",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("profile_key", sa.String(length=64), nullable=False),
        sa.Column("provider_name", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("capabilities", sa.JSON(), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=True),
        sa.Column("default_params", sa.JSON(), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("is_default", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("profile_key"),
    )
    op.create_table(
        "prompt_template_versions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workflow", sa.String(length=32), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("template_body", sa.Text(), nullable=False),
        sa.Column("output_schema_version", sa.String(length=32), nullable=False),
        sa.Column("change_summary", sa.Text(), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workflow", "version_number", name="uq_prompt_workflow_version"),
    )
    op.create_index(
        "ix_prompt_template_versions_workflow",
        "prompt_template_versions",
        ["workflow"],
    )
    op.create_index(
        "ix_prompt_template_versions_active",
        "prompt_template_versions",
        ["active"],
    )
    op.create_table(
        "generation_candidates",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("provider_profile_id", sa.String(length=36), nullable=True),
        sa.Column("prompt_template_version_id", sa.String(length=36), nullable=True),
        sa.Column("workflow", sa.String(length=32), nullable=False),
        sa.Column("candidate_index", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=24), server_default="pending", nullable=False),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("source_asset_ids", sa.JSON(), nullable=False),
        sa.Column("generation_params", sa.JSON(), nullable=False),
        sa.Column("provider_usage", sa.JSON(), nullable=False),
        sa.Column("selected_asset_type", sa.String(length=32), nullable=True),
        sa.Column("selected_asset_id", sa.String(length=36), nullable=True),
        sa.Column("selected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["generation_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["provider_profile_id"], ["provider_profiles.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["prompt_template_version_id"],
            ["prompt_template_versions.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "candidate_index", name="uq_candidate_run_index"),
    )
    op.create_index("ix_generation_candidates_project_id", "generation_candidates", ["project_id"])
    op.create_index("ix_generation_candidates_run_id", "generation_candidates", ["run_id"])
    op.create_index(
        "ix_generation_candidates_provider_profile_id",
        "generation_candidates",
        ["provider_profile_id"],
    )
    op.create_index(
        "ix_generation_candidates_prompt_template_version_id",
        "generation_candidates",
        ["prompt_template_version_id"],
    )
    op.create_index("ix_generation_candidates_workflow", "generation_candidates", ["workflow"])
    op.create_index("ix_generation_candidates_status", "generation_candidates", ["status"])
    op.create_index(
        "ix_generation_candidates_project_created",
        "generation_candidates",
        ["project_id", "created_at"],
    )
    op.create_table(
        "evaluation_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("sample_set", sa.String(length=120), nullable=False),
        sa.Column("provider_profile_id", sa.String(length=36), nullable=True),
        sa.Column("prompt_template_version_id", sa.String(length=36), nullable=True),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("human_scores", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["provider_profile_id"], ["provider_profiles.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["prompt_template_version_id"],
            ["prompt_template_versions.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_evaluation_runs_created_at", "evaluation_runs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_evaluation_runs_created_at", table_name="evaluation_runs")
    op.drop_table("evaluation_runs")
    op.drop_index("ix_generation_candidates_project_created", table_name="generation_candidates")
    op.drop_index("ix_generation_candidates_status", table_name="generation_candidates")
    op.drop_index("ix_generation_candidates_workflow", table_name="generation_candidates")
    op.drop_index(
        "ix_generation_candidates_prompt_template_version_id", table_name="generation_candidates"
    )
    op.drop_index(
        "ix_generation_candidates_provider_profile_id", table_name="generation_candidates"
    )
    op.drop_index("ix_generation_candidates_run_id", table_name="generation_candidates")
    op.drop_index("ix_generation_candidates_project_id", table_name="generation_candidates")
    op.drop_table("generation_candidates")
    op.drop_index("ix_prompt_template_versions_active", table_name="prompt_template_versions")
    op.drop_index("ix_prompt_template_versions_workflow", table_name="prompt_template_versions")
    op.drop_table("prompt_template_versions")
    op.drop_table("provider_profiles")
    op.drop_column("generation_runs", "error_code")
    op.drop_column("generation_runs", "provider_usage")

"""add revision requests, project events, and cancellation

Revision ID: 202607080005
Revises: 202607080004
Create Date: 2026-07-08 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202607080005"
down_revision: str | None = "202607080004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "revision_requests",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("feedback", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=24), server_default="planned", nullable=False),
        sa.Column("tasks", sa.JSON(), nullable=False),
        sa.Column("created_versions", sa.JSON(), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
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
            name=op.f("fk_revision_requests_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_revision_requests")),
    )
    op.create_index(
        op.f("ix_revision_requests_project_id"),
        "revision_requests",
        ["project_id"],
    )
    op.create_index(op.f("ix_revision_requests_status"), "revision_requests", ["status"])

    with op.batch_alter_table("lyrics_versions") as batch_op:
        batch_op.add_column(
            sa.Column("source_revision_request_id", sa.String(length=36), nullable=True),
        )
        batch_op.create_foreign_key(
            op.f("fk_lyrics_versions_source_revision_request_id_revision_requests"),
            "revision_requests",
            ["source_revision_request_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index(
            op.f("ix_lyrics_versions_source_revision_request_id"),
            ["source_revision_request_id"],
        )

    with op.batch_alter_table("midi_asset_versions") as batch_op:
        batch_op.add_column(
            sa.Column("source_revision_request_id", sa.String(length=36), nullable=True),
        )
        batch_op.create_foreign_key(
            op.f("fk_midi_asset_versions_source_revision_request_id_revision_requests"),
            "revision_requests",
            ["source_revision_request_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index(
            op.f("ix_midi_asset_versions_source_revision_request_id"),
            ["source_revision_request_id"],
        )

    with op.batch_alter_table("arrangement_plan_versions") as batch_op:
        batch_op.add_column(
            sa.Column("source_revision_request_id", sa.String(length=36), nullable=True),
        )
        batch_op.create_foreign_key(
            op.f("fk_arrangement_plan_versions_source_revision_request_id_revision_requests"),
            "revision_requests",
            ["source_revision_request_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index(
            op.f("ix_arrangement_plan_versions_source_revision_request_id"),
            ["source_revision_request_id"],
        )

    op.create_table(
        "project_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("revision_request_id", sa.String(length=36), nullable=True),
        sa.Column("generation_run_id", sa.String(length=36), nullable=True),
        sa.Column("artifact_version_id", sa.String(length=36), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["generation_run_id"],
            ["generation_runs.id"],
            name=op.f("fk_project_events_generation_run_id_generation_runs"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_project_events_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["revision_request_id"],
            ["revision_requests.id"],
            name=op.f("fk_project_events_revision_request_id_revision_requests"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_project_events")),
    )
    op.create_index(
        op.f("ix_project_events_artifact_version_id"),
        "project_events",
        ["artifact_version_id"],
    )
    op.create_index(op.f("ix_project_events_event_type"), "project_events", ["event_type"])
    op.create_index(
        op.f("ix_project_events_generation_run_id"),
        "project_events",
        ["generation_run_id"],
    )
    op.create_index(op.f("ix_project_events_project_id"), "project_events", ["project_id"])
    op.create_index(
        op.f("ix_project_events_revision_request_id"),
        "project_events",
        ["revision_request_id"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_project_events_revision_request_id"), table_name="project_events")
    op.drop_index(op.f("ix_project_events_project_id"), table_name="project_events")
    op.drop_index(op.f("ix_project_events_generation_run_id"), table_name="project_events")
    op.drop_index(op.f("ix_project_events_event_type"), table_name="project_events")
    op.drop_index(op.f("ix_project_events_artifact_version_id"), table_name="project_events")
    op.drop_table("project_events")

    with op.batch_alter_table("arrangement_plan_versions") as batch_op:
        batch_op.drop_index(op.f("ix_arrangement_plan_versions_source_revision_request_id"))
        batch_op.drop_constraint(
            op.f("fk_arrangement_plan_versions_source_revision_request_id_revision_requests"),
            type_="foreignkey",
        )
        batch_op.drop_column("source_revision_request_id")

    with op.batch_alter_table("midi_asset_versions") as batch_op:
        batch_op.drop_index(op.f("ix_midi_asset_versions_source_revision_request_id"))
        batch_op.drop_constraint(
            op.f("fk_midi_asset_versions_source_revision_request_id_revision_requests"),
            type_="foreignkey",
        )
        batch_op.drop_column("source_revision_request_id")

    with op.batch_alter_table("lyrics_versions") as batch_op:
        batch_op.drop_index(op.f("ix_lyrics_versions_source_revision_request_id"))
        batch_op.drop_constraint(
            op.f("fk_lyrics_versions_source_revision_request_id_revision_requests"),
            type_="foreignkey",
        )
        batch_op.drop_column("source_revision_request_id")

    op.drop_index(op.f("ix_revision_requests_status"), table_name="revision_requests")
    op.drop_index(op.f("ix_revision_requests_project_id"), table_name="revision_requests")
    op.drop_table("revision_requests")

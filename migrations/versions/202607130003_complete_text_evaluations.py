"""complete asynchronous text provider evaluations

Revision ID: 202607130003
Revises: 202607130002
Create Date: 2026-07-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202607130003"
down_revision: str | None = "202607130002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "evaluation_runs",
        sa.Column("workflow", sa.String(length=32), server_default="song_spec", nullable=False),
    )
    op.add_column(
        "evaluation_runs",
        sa.Column("status", sa.String(length=24), server_default="queued", nullable=False),
    )
    op.add_column("evaluation_runs", sa.Column("arq_job_id", sa.String(length=120), nullable=True))
    op.add_column(
        "evaluation_runs",
        sa.Column("sample_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column("evaluation_runs", sa.Column("error_code", sa.String(length=64), nullable=True))
    op.add_column("evaluation_runs", sa.Column("error_message", sa.Text(), nullable=True))
    op.add_column(
        "evaluation_runs", sa.Column("started_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "evaluation_runs", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "evaluation_runs",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_evaluation_runs_workflow", "evaluation_runs", ["workflow"])
    op.create_index("ix_evaluation_runs_status", "evaluation_runs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_evaluation_runs_status", table_name="evaluation_runs")
    op.drop_index("ix_evaluation_runs_workflow", table_name="evaluation_runs")
    op.drop_column("evaluation_runs", "updated_at")
    op.drop_column("evaluation_runs", "completed_at")
    op.drop_column("evaluation_runs", "started_at")
    op.drop_column("evaluation_runs", "error_message")
    op.drop_column("evaluation_runs", "error_code")
    op.drop_column("evaluation_runs", "sample_count")
    op.drop_column("evaluation_runs", "arq_job_id")
    op.drop_column("evaluation_runs", "status")
    op.drop_column("evaluation_runs", "workflow")

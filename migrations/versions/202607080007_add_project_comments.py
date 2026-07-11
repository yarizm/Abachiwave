"""add project comments

Revision ID: 202607080007
Revises: 202607080006
Create Date: 2026-07-08 00:07:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202607080007"
down_revision: str | None = "202607080006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "project_comments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("author_name", sa.String(length=120), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=24), server_default="open", nullable=False),
        sa.Column("target_type", sa.String(length=32), server_default="project", nullable=False),
        sa.Column("target_id", sa.String(length=36), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
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
            name=op.f("fk_project_comments_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_project_comments")),
    )
    op.create_index(op.f("ix_project_comments_project_id"), "project_comments", ["project_id"])
    op.create_index(op.f("ix_project_comments_status"), "project_comments", ["status"])
    op.create_index(op.f("ix_project_comments_target_id"), "project_comments", ["target_id"])
    op.create_index(op.f("ix_project_comments_target_type"), "project_comments", ["target_type"])


def downgrade() -> None:
    op.drop_index(op.f("ix_project_comments_target_type"), table_name="project_comments")
    op.drop_index(op.f("ix_project_comments_target_id"), table_name="project_comments")
    op.drop_index(op.f("ix_project_comments_status"), table_name="project_comments")
    op.drop_index(op.f("ix_project_comments_project_id"), table_name="project_comments")
    op.drop_table("project_comments")

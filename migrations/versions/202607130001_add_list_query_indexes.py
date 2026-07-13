"""add indexes for bounded project history queries

Revision ID: 202607130001
Revises: 202607080008
Create Date: 2026-07-13 00:01:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "202607130001"
down_revision: str | None = "202607080008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INDEXES = (
    ("ix_projects_created_at", "projects", ["created_at"]),
    ("ix_audio_uploads_project_created", "audio_uploads", ["project_id", "created_at"]),
    (
        "ix_project_comments_project_created",
        "project_comments",
        ["project_id", "created_at"],
    ),
    (
        "ix_revision_requests_project_created",
        "revision_requests",
        ["project_id", "created_at"],
    ),
    ("ix_project_events_project_created", "project_events", ["project_id", "created_at"]),
    (
        "ix_generation_runs_project_created",
        "generation_runs",
        ["project_id", "created_at"],
    ),
    (
        "ix_audio_demo_versions_project_created",
        "audio_demo_versions",
        ["project_id", "created_at"],
    ),
    (
        "ix_export_bundles_project_created",
        "export_bundles",
        ["project_id", "created_at"],
    ),
)


def upgrade() -> None:
    for name, table, columns in INDEXES:
        op.create_index(name, table, columns, unique=False)


def downgrade() -> None:
    for name, table, _columns in reversed(INDEXES):
        op.drop_index(name, table_name=table)

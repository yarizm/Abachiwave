"""add arrangement plans and export bundles

Revision ID: 202607080003
Revises: 202607080002
Create Date: 2026-07-08 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202607080003"
down_revision: str | None = "202607080002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "arrangement_plan_versions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("song_spec_id", sa.String(length=36), nullable=False),
        sa.Column("lyrics_version_id", sa.String(length=36), nullable=False),
        sa.Column("chord_version_id", sa.String(length=36), nullable=False),
        sa.Column("midi_asset_ids", sa.JSON(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("parent_version_id", sa.String(length=36), nullable=True),
        sa.Column("overview", sa.Text(), nullable=False),
        sa.Column("sections", sa.JSON(), nullable=False),
        sa.Column("mix_notes", sa.Text(), nullable=False),
        sa.Column("reference_notes", sa.Text(), nullable=False),
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
            ["chord_version_id"],
            ["chord_progression_versions.id"],
            name=op.f("fk_arrangement_plan_versions_chord_version_id_chord_progression_versions"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["lyrics_version_id"],
            ["lyrics_versions.id"],
            name=op.f("fk_arrangement_plan_versions_lyrics_version_id_lyrics_versions"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["parent_version_id"],
            ["arrangement_plan_versions.id"],
            name=op.f(
                "fk_arrangement_plan_versions_parent_version_id_arrangement_plan_versions"
            ),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_arrangement_plan_versions_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["song_spec_id"],
            ["song_spec_versions.id"],
            name=op.f("fk_arrangement_plan_versions_song_spec_id_song_spec_versions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_arrangement_plan_versions")),
        sa.UniqueConstraint(
            "project_id",
            "version_number",
            name="uq_arrangement_plan_versions_project_version",
        ),
    )
    op.create_index(
        op.f("ix_arrangement_plan_versions_chord_version_id"),
        "arrangement_plan_versions",
        ["chord_version_id"],
    )
    op.create_index(
        op.f("ix_arrangement_plan_versions_lyrics_version_id"),
        "arrangement_plan_versions",
        ["lyrics_version_id"],
    )
    op.create_index(
        op.f("ix_arrangement_plan_versions_project_id"),
        "arrangement_plan_versions",
        ["project_id"],
    )
    op.create_index(
        op.f("ix_arrangement_plan_versions_song_spec_id"),
        "arrangement_plan_versions",
        ["song_spec_id"],
    )

    op.create_table(
        "export_bundles",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("arrangement_plan_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=16), server_default="ready", nullable=False),
        sa.Column("manifest", sa.JSON(), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=True),
        sa.Column("filename", sa.String(length=255), nullable=True),
        sa.Column(
            "content_type",
            sa.String(length=64),
            server_default="application/zip",
            nullable=False,
        ),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("checksum", sa.String(length=64), nullable=True),
        sa.Column("download_token_hash", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
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
            ["arrangement_plan_id"],
            ["arrangement_plan_versions.id"],
            name=op.f("fk_export_bundles_arrangement_plan_id_arrangement_plan_versions"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_export_bundles_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_export_bundles")),
    )
    op.create_index(
        op.f("ix_export_bundles_arrangement_plan_id"),
        "export_bundles",
        ["arrangement_plan_id"],
    )
    op.create_index(op.f("ix_export_bundles_project_id"), "export_bundles", ["project_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_export_bundles_project_id"), table_name="export_bundles")
    op.drop_index(
        op.f("ix_export_bundles_arrangement_plan_id"),
        table_name="export_bundles",
    )
    op.drop_table("export_bundles")
    op.drop_index(
        op.f("ix_arrangement_plan_versions_song_spec_id"),
        table_name="arrangement_plan_versions",
    )
    op.drop_index(
        op.f("ix_arrangement_plan_versions_project_id"),
        table_name="arrangement_plan_versions",
    )
    op.drop_index(
        op.f("ix_arrangement_plan_versions_lyrics_version_id"),
        table_name="arrangement_plan_versions",
    )
    op.drop_index(
        op.f("ix_arrangement_plan_versions_chord_version_id"),
        table_name="arrangement_plan_versions",
    )
    op.drop_table("arrangement_plan_versions")

"""add composition asset versions

Revision ID: 202607080002
Revises: 202607080001
Create Date: 2026-07-08 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202607080002"
down_revision: str | None = "202607080001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "lyrics_versions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("song_spec_id", sa.String(length=36), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("parent_version_id", sa.String(length=36), nullable=True),
        sa.Column("sections", sa.JSON(), nullable=False),
        sa.Column("hook_candidates", sa.JSON(), nullable=False),
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
            ["parent_version_id"],
            ["lyrics_versions.id"],
            name=op.f("fk_lyrics_versions_parent_version_id_lyrics_versions"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_lyrics_versions_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["song_spec_id"],
            ["song_spec_versions.id"],
            name=op.f("fk_lyrics_versions_song_spec_id_song_spec_versions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lyrics_versions")),
        sa.UniqueConstraint(
            "project_id",
            "version_number",
            name="uq_lyrics_versions_project_version",
        ),
    )
    op.create_index(op.f("ix_lyrics_versions_project_id"), "lyrics_versions", ["project_id"])
    op.create_index(op.f("ix_lyrics_versions_song_spec_id"), "lyrics_versions", ["song_spec_id"])

    op.create_table(
        "chord_progression_versions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("song_spec_id", sa.String(length=36), nullable=False),
        sa.Column("lyrics_version_id", sa.String(length=36), nullable=True),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("parent_version_id", sa.String(length=36), nullable=True),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("tempo_bpm", sa.Integer(), nullable=False),
        sa.Column("time_signature", sa.String(length=16), nullable=False),
        sa.Column("sections", sa.JSON(), nullable=False),
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
            ["lyrics_version_id"],
            ["lyrics_versions.id"],
            name=op.f("fk_chord_progression_versions_lyrics_version_id_lyrics_versions"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["parent_version_id"],
            ["chord_progression_versions.id"],
            name=op.f("fk_chord_progression_versions_parent_version_id_chord_progression_versions"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_chord_progression_versions_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["song_spec_id"],
            ["song_spec_versions.id"],
            name=op.f("fk_chord_progression_versions_song_spec_id_song_spec_versions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_chord_progression_versions")),
        sa.UniqueConstraint(
            "project_id",
            "version_number",
            name="uq_chord_progression_versions_project_version",
        ),
    )
    op.create_index(
        op.f("ix_chord_progression_versions_lyrics_version_id"),
        "chord_progression_versions",
        ["lyrics_version_id"],
    )
    op.create_index(
        op.f("ix_chord_progression_versions_project_id"),
        "chord_progression_versions",
        ["project_id"],
    )
    op.create_index(
        op.f("ix_chord_progression_versions_song_spec_id"),
        "chord_progression_versions",
        ["song_spec_id"],
    )

    op.create_table(
        "midi_asset_versions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("song_spec_id", sa.String(length=36), nullable=False),
        sa.Column("lyrics_version_id", sa.String(length=36), nullable=True),
        sa.Column("chord_version_id", sa.String(length=36), nullable=True),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column(
            "content_type",
            sa.String(length=64),
            server_default="audio/midi",
            nullable=False,
        ),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["chord_version_id"],
            ["chord_progression_versions.id"],
            name=op.f("fk_midi_asset_versions_chord_version_id_chord_progression_versions"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["lyrics_version_id"],
            ["lyrics_versions.id"],
            name=op.f("fk_midi_asset_versions_lyrics_version_id_lyrics_versions"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_midi_asset_versions_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["song_spec_id"],
            ["song_spec_versions.id"],
            name=op.f("fk_midi_asset_versions_song_spec_id_song_spec_versions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_midi_asset_versions")),
        sa.UniqueConstraint(
            "project_id",
            "kind",
            "version_number",
            name="uq_midi_asset_versions_project_kind_version",
        ),
    )
    op.create_index(
        op.f("ix_midi_asset_versions_chord_version_id"),
        "midi_asset_versions",
        ["chord_version_id"],
    )
    op.create_index(op.f("ix_midi_asset_versions_kind"), "midi_asset_versions", ["kind"])
    op.create_index(
        op.f("ix_midi_asset_versions_lyrics_version_id"),
        "midi_asset_versions",
        ["lyrics_version_id"],
    )
    op.create_index(
        op.f("ix_midi_asset_versions_project_id"),
        "midi_asset_versions",
        ["project_id"],
    )
    op.create_index(
        op.f("ix_midi_asset_versions_song_spec_id"),
        "midi_asset_versions",
        ["song_spec_id"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_midi_asset_versions_song_spec_id"), table_name="midi_asset_versions")
    op.drop_index(op.f("ix_midi_asset_versions_project_id"), table_name="midi_asset_versions")
    op.drop_index(
        op.f("ix_midi_asset_versions_lyrics_version_id"),
        table_name="midi_asset_versions",
    )
    op.drop_index(op.f("ix_midi_asset_versions_kind"), table_name="midi_asset_versions")
    op.drop_index(op.f("ix_midi_asset_versions_chord_version_id"), table_name="midi_asset_versions")
    op.drop_table("midi_asset_versions")
    op.drop_index(
        op.f("ix_chord_progression_versions_song_spec_id"),
        table_name="chord_progression_versions",
    )
    op.drop_index(
        op.f("ix_chord_progression_versions_project_id"),
        table_name="chord_progression_versions",
    )
    op.drop_index(
        op.f("ix_chord_progression_versions_lyrics_version_id"),
        table_name="chord_progression_versions",
    )
    op.drop_table("chord_progression_versions")
    op.drop_index(op.f("ix_lyrics_versions_song_spec_id"), table_name="lyrics_versions")
    op.drop_index(op.f("ix_lyrics_versions_project_id"), table_name="lyrics_versions")
    op.drop_table("lyrics_versions")

"""add structured MIDI note events and version ancestry

Revision ID: 202608010001
Revises: 202607140003
Create Date: 2026-08-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202608010001"
down_revision: str | None = "202607140003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("midi_asset_versions") as batch_op:
        batch_op.add_column(
            sa.Column("parent_version_id", sa.String(length=36), nullable=True),
        )
        batch_op.add_column(
            sa.Column(
                "schema_version",
                sa.Integer(),
                server_default=sa.text("1"),
                nullable=False,
            )
        )
        for column_name in ("note_events", "tempo_map", "time_signature_map"):
            batch_op.add_column(
                sa.Column(
                    column_name,
                    sa.JSON(),
                    server_default=sa.text("'[]'"),
                    nullable=False,
                ),
            )
        batch_op.create_index(
            op.f("ix_midi_asset_versions_parent_version_id"),
            ["parent_version_id"],
        )
        batch_op.create_foreign_key(
            op.f("fk_midi_asset_versions_parent_version_id_midi_asset_versions"),
            "midi_asset_versions",
            ["parent_version_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("midi_asset_versions") as batch_op:
        batch_op.drop_constraint(
            op.f("fk_midi_asset_versions_parent_version_id_midi_asset_versions"),
            type_="foreignkey",
        )
        batch_op.drop_index(op.f("ix_midi_asset_versions_parent_version_id"))
        for column_name in ("time_signature_map", "tempo_map", "note_events"):
            batch_op.drop_column(column_name)
        batch_op.drop_column("schema_version")
        batch_op.drop_column("parent_version_id")

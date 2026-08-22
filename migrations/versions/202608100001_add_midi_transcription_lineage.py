"""add MIDI transcription lineage

Revision ID: 202608100001
Revises: 202608090001
Create Date: 2026-08-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202608100001"
down_revision: str | None = "202608090001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("midi_asset_versions") as batch_op:
        batch_op.add_column(
            sa.Column("source_reference_analysis_id", sa.String(length=36), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "source_provider_manifest",
                sa.JSON(),
                server_default="{}",
                nullable=False,
            )
        )
        batch_op.create_foreign_key(
            op.f(
                "fk_midi_asset_versions_source_reference_analysis_id_"
                "reference_analysis_versions"
            ),
            "reference_analysis_versions",
            ["source_reference_analysis_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index(
            op.f("ix_midi_asset_versions_source_reference_analysis_id"),
            ["source_reference_analysis_id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("midi_asset_versions") as batch_op:
        batch_op.drop_index(op.f("ix_midi_asset_versions_source_reference_analysis_id"))
        batch_op.drop_constraint(
            op.f(
                "fk_midi_asset_versions_source_reference_analysis_id_"
                "reference_analysis_versions"
            ),
            type_="foreignkey",
        )
        batch_op.drop_column("source_provider_manifest")
        batch_op.drop_column("source_reference_analysis_id")

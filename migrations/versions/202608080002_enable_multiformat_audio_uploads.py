"""enable multiformat audio uploads

Revision ID: 202608080002
Revises: 202608080001
Create Date: 2026-08-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202608080002"
down_revision: str | None = "202608080001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("audio_uploads") as batch_op:
        batch_op.add_column(
            sa.Column(
                "format",
                sa.String(length=16),
                server_default="wav",
                nullable=False,
            )
        )
        batch_op.alter_column(
            "duration_seconds",
            existing_type=sa.Float(),
            nullable=True,
        )
        batch_op.alter_column(
            "sample_rate",
            existing_type=sa.Integer(),
            nullable=True,
        )
        batch_op.alter_column(
            "channels",
            existing_type=sa.Integer(),
            nullable=True,
        )
        batch_op.alter_column(
            "waveform_peaks",
            existing_type=sa.JSON(),
            nullable=True,
        )


def downgrade() -> None:
    op.execute("UPDATE audio_uploads SET duration_seconds = 0 WHERE duration_seconds IS NULL")
    op.execute("UPDATE audio_uploads SET sample_rate = 0 WHERE sample_rate IS NULL")
    op.execute("UPDATE audio_uploads SET channels = 0 WHERE channels IS NULL")
    op.execute("UPDATE audio_uploads SET waveform_peaks = '[]' WHERE waveform_peaks IS NULL")
    with op.batch_alter_table("audio_uploads") as batch_op:
        batch_op.alter_column(
            "waveform_peaks",
            existing_type=sa.JSON(),
            nullable=False,
        )
        batch_op.alter_column(
            "channels",
            existing_type=sa.Integer(),
            nullable=False,
        )
        batch_op.alter_column(
            "sample_rate",
            existing_type=sa.Integer(),
            nullable=False,
        )
        batch_op.alter_column(
            "duration_seconds",
            existing_type=sa.Float(),
            nullable=False,
        )
        batch_op.drop_column("format")

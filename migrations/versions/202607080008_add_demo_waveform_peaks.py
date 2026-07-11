"""add waveform peaks to audio demos

Revision ID: 202607080008
Revises: 202607080007
Create Date: 2026-07-08 00:08:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202607080008"
down_revision: str | None = "202607080007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("audio_demo_versions") as batch_op:
        batch_op.add_column(
            sa.Column(
                "waveform_peaks",
                sa.JSON(),
                server_default="[]",
                nullable=False,
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("audio_demo_versions") as batch_op:
        batch_op.drop_column("waveform_peaks")

"""add historical_fee_stages (JSON) to cases

Revision ID: 0008_historical_fee_stages
Revises: 0007_retainer_snapshot_through
Create Date: 2026-02-02

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0008_historical_fee_stages"
down_revision = "0007_retainer_snapshot_through"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "cases",
        sa.Column("historical_fee_stages", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("cases", "historical_fee_stages")

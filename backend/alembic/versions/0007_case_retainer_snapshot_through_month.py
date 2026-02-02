"""add retainer_snapshot_through_month to cases

Revision ID: 0007_case_retainer_snapshot_through_month
Revises: 0006_case_name
Create Date: 2026-02-02

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007_case_retainer_snapshot_through_month"
down_revision = "0006_case_name"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "cases",
        sa.Column("retainer_snapshot_through_month", sa.Date(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("cases", "retainer_snapshot_through_month")

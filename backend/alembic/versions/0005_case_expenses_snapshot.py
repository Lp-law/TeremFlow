"""add expenses_snapshot_ils_gross to cases

Revision ID: 0005_case_expenses_snapshot
Revises: 0004_case_retainer_snapshot
Create Date: 2026-02-02

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005_case_expenses_snapshot"
down_revision = "0004_case_retainer_snapshot"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "cases",
        sa.Column("expenses_snapshot_ils_gross", sa.Numeric(12, 2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("cases", "expenses_snapshot_ils_gross")

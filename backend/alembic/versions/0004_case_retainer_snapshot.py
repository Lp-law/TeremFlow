"""add retainer_snapshot_ils_gross to cases

Revision ID: 0004_case_retainer_snapshot
Revises: 0003_case_retainer_anchor_branch
Create Date: 2026-02-02

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004_case_retainer_snapshot"
down_revision = "0003_case_retainer_anchor_branch"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "cases",
        sa.Column("retainer_snapshot_ils_gross", sa.Numeric(12, 2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("cases", "retainer_snapshot_ils_gross")

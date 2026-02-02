"""add case_name to cases

Revision ID: 0006_case_name
Revises: 0005_case_expenses_snapshot
Create Date: 2026-02-02

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006_case_name"
down_revision = "0005_case_expenses_snapshot"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "cases",
        sa.Column("case_name", sa.String(200), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("cases", "case_name")

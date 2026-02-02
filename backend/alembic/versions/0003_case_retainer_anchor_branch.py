"""add retainer_anchor_date and branch_name to cases

Revision ID: 0003_case_retainer_anchor_branch
Revises: 0002_backup_records
Create Date: 2026-02-02

"""

from __future__ import annotations

import datetime as dt

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

revision = "0003_case_retainer_anchor_branch"
down_revision = "0002_backup_records"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("cases", sa.Column("retainer_anchor_date", sa.Date(), nullable=True))
    op.add_column("cases", sa.Column("branch_name", sa.String(length=120), nullable=True))

    # Backfill retainer_anchor_date for existing rows (Jan-Jun -> July same year, Jul-Dec -> Jan next year)
    conn = op.get_bind()
    rows = conn.execute(text("SELECT id, open_date FROM cases WHERE retainer_anchor_date IS NULL")).fetchall()
    for (cid, open_date) in rows:
        if open_date:
            y, m = open_date.year, open_date.month
            anchor = dt.date(y, 7, 1) if 1 <= m <= 6 else dt.date(y + 1, 1, 1)
            conn.execute(text("UPDATE cases SET retainer_anchor_date = :a WHERE id = :i"), {"a": anchor, "i": cid})

    op.alter_column("cases", "retainer_anchor_date", nullable=False)
    op.create_index("ix_cases_retainer_anchor_date", "cases", ["retainer_anchor_date"])


def downgrade() -> None:
    op.drop_index("ix_cases_retainer_anchor_date", table_name="cases")
    op.drop_column("cases", "retainer_anchor_date")
    op.drop_column("cases", "branch_name")

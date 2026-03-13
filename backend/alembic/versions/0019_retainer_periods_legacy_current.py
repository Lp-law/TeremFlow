"""Add retainer period fields: current + legacy (start/end). Backfill from anchor and end_date.

Revision ID: 0019_retainer_periods
Revises: 0018_legacy_evidence_proofs
Create Date: 2026-02-02

- cases: retainer_current_start_date, retainer_current_end_date,
  retainer_legacy_start_date, retainer_legacy_end_date (Date, nullable).
- Backfill: retainer_anchor_date -> retainer_current_start_date,
  retainer_end_date -> retainer_current_end_date (additive only).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0019_retainer_periods"
down_revision = "0018_legacy_evidence_proofs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("cases", sa.Column("retainer_current_start_date", sa.Date(), nullable=True))
    op.add_column("cases", sa.Column("retainer_current_end_date", sa.Date(), nullable=True))
    op.add_column("cases", sa.Column("retainer_legacy_start_date", sa.Date(), nullable=True))
    op.add_column("cases", sa.Column("retainer_legacy_end_date", sa.Date(), nullable=True))

    conn = op.get_bind()
    conn.execute(
        sa.text("""
            UPDATE cases
            SET retainer_current_start_date = retainer_anchor_date
            WHERE retainer_anchor_date IS NOT NULL AND deleted_at IS NULL
        """)
    )
    conn.execute(
        sa.text("""
            UPDATE cases
            SET retainer_current_end_date = retainer_end_date
            WHERE retainer_end_date IS NOT NULL AND deleted_at IS NULL
        """)
    )


def downgrade() -> None:
    op.drop_column("cases", "retainer_legacy_end_date")
    op.drop_column("cases", "retainer_legacy_start_date")
    op.drop_column("cases", "retainer_current_end_date")
    op.drop_column("cases", "retainer_current_start_date")

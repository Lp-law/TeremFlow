"""fee_stage_rates: amount_ils as gross (including VAT, כולל מע"מ)

Revision ID: 0015_fee_stage_rates_gross
Revises: 0014_unified_model
Create Date: 2026-03-08

All fee stage amounts are now stored and used as gross (including 18% VAT).
This migration updates existing net values to gross (net * 1.18).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0015_fee_stage_rates_gross"
down_revision = "0014_unified_model"
branch_labels = None
depends_on = None

# Gross (כולל מע"מ) per code. Net was in 0010; 18% VAT => gross.
GROSS_BY_CODE = [
    ("COURT_STAGE_1_DEFENSE", "23600.00"),
    ("COURT_STAGE_2_DAMAGES", "17700.00"),
    ("COURT_STAGE_3_EVIDENCE", "17700.00"),
    ("COURT_STAGE_4_PROOFS", "17700.00"),
    ("COURT_STAGE_5_SUMMARIES", "11800.00"),
    ("AMENDED_DEFENSE_PARTIAL", "11800.00"),
    ("AMENDED_DEFENSE_FULL", "23600.00"),
    ("THIRD_PARTY_NOTICE", "11800.00"),
    ("ADDITIONAL_PROOF_HEARING", "1770.00"),
    ("DEMAND_FIX", "5900.00"),
    ("DEMAND_HOURLY", "826.00"),
    ("SMALL_CLAIMS_MANUAL", "0.00"),
    ("APPEAL", "17700.00"),
]


def upgrade() -> None:
    conn = op.get_bind()
    for code, gross in GROSS_BY_CODE:
        conn.execute(
            sa.text("UPDATE fee_stage_rates SET amount_ils = :gross WHERE code = :code"),
            {"code": code, "gross": gross},
        )


def downgrade() -> None:
    # Revert to net (gross / 1.18); approximate
    conn = op.get_bind()
    net_by_code = [
        ("COURT_STAGE_1_DEFENSE", "20000.00"),
        ("COURT_STAGE_2_DAMAGES", "15000.00"),
        ("COURT_STAGE_3_EVIDENCE", "15000.00"),
        ("COURT_STAGE_4_PROOFS", "15000.00"),
        ("COURT_STAGE_5_SUMMARIES", "10000.00"),
        ("AMENDED_DEFENSE_PARTIAL", "10000.00"),
        ("AMENDED_DEFENSE_FULL", "20000.00"),
        ("THIRD_PARTY_NOTICE", "10000.00"),
        ("ADDITIONAL_PROOF_HEARING", "1500.00"),
        ("DEMAND_FIX", "5000.00"),
        ("DEMAND_HOURLY", "700.00"),
        ("SMALL_CLAIMS_MANUAL", "0.00"),
        ("APPEAL", "15000.00"),
    ]
    for code, net in net_by_code:
        conn.execute(
            sa.text("UPDATE fee_stage_rates SET amount_ils = :net WHERE code = :code"),
            {"code": code, "net": net},
        )

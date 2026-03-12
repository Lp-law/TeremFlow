"""Fix legacy evidence/proofs rates: ראיות 5850 (5000+17%), הוכחות 11700 (10000+17%).

Revision ID: 0018_legacy_evidence_proofs
Revises: 0017_case_notes_retainer_end_vat
Create Date: 2026-02-02

- LEGACY_COURT_STAGE_3_EVIDENCE: net_ils=5000, vat_pct=0.17, amount_ils=5850
- LEGACY_COURT_STAGE_4_PROOFS: net_ils=10000, vat_pct=0.17, amount_ils=11700
Idempotent: UPDATE by code.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0018_legacy_evidence_proofs"
down_revision = "0017_case_notes_retainer_end_vat"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text("""
            UPDATE fee_stage_rates
            SET net_ils = 5000.00, vat_pct = 0.17, amount_ils = 5850.00
            WHERE code = 'LEGACY_COURT_STAGE_3_EVIDENCE'
        """)
    )
    conn.execute(
        sa.text("""
            UPDATE fee_stage_rates
            SET net_ils = 10000.00, vat_pct = 0.17, amount_ils = 11700.00
            WHERE code = 'LEGACY_COURT_STAGE_4_PROOFS'
        """)
    )


def downgrade() -> None:
    conn = op.get_bind()
    # Revert to previous (wrong) values: EVIDENCE 10000->11700, PROOFS 5000->5850
    conn.execute(
        sa.text("""
            UPDATE fee_stage_rates
            SET net_ils = 10000.00, vat_pct = 0.17, amount_ils = 11700.00
            WHERE code = 'LEGACY_COURT_STAGE_3_EVIDENCE'
        """)
    )
    conn.execute(
        sa.text("""
            UPDATE fee_stage_rates
            SET net_ils = 5000.00, vat_pct = 0.17, amount_ils = 5850.00
            WHERE code = 'LEGACY_COURT_STAGE_4_PROOFS'
        """)
    )

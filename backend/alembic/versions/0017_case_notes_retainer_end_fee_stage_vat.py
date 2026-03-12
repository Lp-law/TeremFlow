"""Add case_notes, retainer_end_date; fee_stage_rates net_ils and vat_pct (additive only).

Revision ID: 0017_case_notes_retainer_end_vat
Revises: 0016_backfill_fee_events_gross
Create Date: 2026-02-02

- cases: case_notes (Text, nullable), retainer_end_date (Date, nullable).
- fee_stage_rates: net_ils (Numeric 14,2 nullable), vat_pct (Numeric 4,4 nullable).
  When net_ils is set, gross = net_ils * (1+vat_pct); else amount_ils remains source of truth.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0017_case_notes_retainer_end_vat"
down_revision = "0016_backfill_fee_events_gross"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("cases", sa.Column("case_notes", sa.Text(), nullable=True))
    op.add_column("cases", sa.Column("retainer_end_date", sa.Date(), nullable=True))

    op.add_column("fee_stage_rates", sa.Column("net_ils", sa.Numeric(14, 2), nullable=True))
    op.add_column("fee_stage_rates", sa.Column("vat_pct", sa.Numeric(4, 4), nullable=True))

    # Insert "תיקים ישנים" (old cases) codes: net_ils + vat_pct=0.17. Gross = net * 1.17.
    # כתב הגנה 15000, תחשיב נזק 5000, ראיות 10000, הוכחות 5000, סיכומים 5000,
    # הגנה מתוקן 7500, כתב הגנה מתוקן מלא 15000, הודעת צד שלישי 7500, ישיבת הוכחות נוספת 1500
    legacy_rates = [
        ("LEGACY_COURT_STAGE_1_DEFENSE", "15000.00", "0.17"),  # כתב הגנה
        ("LEGACY_COURT_STAGE_2_DAMAGES", "5000.00", "0.17"),    # תחשיב נזק
        ("LEGACY_COURT_STAGE_3_EVIDENCE", "10000.00", "0.17"),  # ראיות
        ("LEGACY_COURT_STAGE_4_PROOFS", "5000.00", "0.17"),     # הוכחות
        ("LEGACY_COURT_STAGE_5_SUMMARIES", "5000.00", "0.17"), # סיכומים
        ("LEGACY_AMENDED_DEFENSE_PARTIAL", "7500.00", "0.17"),  # הגנה מתוקן
        ("LEGACY_AMENDED_DEFENSE_FULL", "15000.00", "0.17"),    # כתב הגנה מתוקן מלא
        ("LEGACY_THIRD_PARTY_NOTICE", "7500.00", "0.17"),       # הודעת צד שלישי
        ("LEGACY_ADDITIONAL_PROOF_HEARING", "1500.00", "0.17"), # ישיבת הוכחות נוספת
    ]
    conn = op.get_bind()
    for code, net_ils, vat_pct in legacy_rates:
        gross = round(float(net_ils) * (1 + float(vat_pct)), 2)
        conn.execute(
            sa.text("""
                INSERT INTO fee_stage_rates (code, amount_ils, is_active, net_ils, vat_pct)
                VALUES (:code, :gross, true, :net_ils, :vat_pct)
            """),
            {"code": code, "gross": str(gross), "net_ils": net_ils, "vat_pct": vat_pct},
        )


LEGACY_CODES = [
    "LEGACY_COURT_STAGE_1_DEFENSE", "LEGACY_COURT_STAGE_2_DAMAGES", "LEGACY_COURT_STAGE_3_EVIDENCE",
    "LEGACY_COURT_STAGE_4_PROOFS", "LEGACY_COURT_STAGE_5_SUMMARIES", "LEGACY_AMENDED_DEFENSE_PARTIAL",
    "LEGACY_AMENDED_DEFENSE_FULL", "LEGACY_THIRD_PARTY_NOTICE", "LEGACY_ADDITIONAL_PROOF_HEARING",
]


def downgrade() -> None:
    conn = op.get_bind()
    for code in LEGACY_CODES:
        conn.execute(sa.text("DELETE FROM fee_stage_rates WHERE code = :code"), {"code": code})
    op.drop_column("fee_stage_rates", "vat_pct")
    op.drop_column("fee_stage_rates", "net_ils")
    op.drop_column("cases", "retainer_end_date")
    op.drop_column("cases", "case_notes")

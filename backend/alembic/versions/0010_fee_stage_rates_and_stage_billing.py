"""fee_stage_rates, case legacy_fee_text/performed_fee_stage_codes, fee_event breakdown_json, APPEAL/STAGE_BILLING enum

Revision ID: 0010_fee_stage_rates
Revises: 0009_activity_log
Create Date: 2026-02-02

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0010_fee_stage_rates"
down_revision = "0009_activity_log"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # PostgreSQL only: add new enum values to feeeventtype (ignore if already present)
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        for val in ("APPEAL", "STAGE_BILLING"):
            op.execute(
                f"DO $$ BEGIN ALTER TYPE feeeventtype ADD VALUE '{val}'; EXCEPTION WHEN duplicate_object THEN NULL; END $$"
            )

    op.create_table(
        "fee_stage_rates",
        sa.Column("code", sa.String(64), primary_key=True),
        sa.Column("amount_ils", sa.Numeric(14, 2), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("effective_from", sa.Date(), nullable=True),
        sa.Column("effective_to", sa.Date(), nullable=True),
    )

    # Seed: all FeeEventType codes that have a rate + APPEAL. Amounts are gross (כולל מע"מ, 18% VAT).
    # Idempotent on PostgreSQL: UPSERT so re-running upgrade does not fail on duplicate key.
    seed = [
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
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        values_clause = ", ".join(f"(:code{i}, :amount{i}, true)" for i in range(len(seed)))
        params = {}
        for i, (code, amount) in enumerate(seed):
            params[f"code{i}"] = code
            params[f"amount{i}"] = amount
        conn.execute(
            sa.text(
                f"INSERT INTO fee_stage_rates (code, amount_ils, is_active) VALUES {values_clause} "
                "ON CONFLICT (code) DO UPDATE SET amount_ils = EXCLUDED.amount_ils, is_active = EXCLUDED.is_active"
            ),
            params,
        )
    else:
        for code, amount in seed:
            conn.execute(
                sa.text("INSERT INTO fee_stage_rates (code, amount_ils, is_active) VALUES (:code, :amount, true)"),
                {"code": code, "amount": amount},
            )

    op.add_column("cases", sa.Column("legacy_fee_text", sa.Text(), nullable=True))
    op.add_column("cases", sa.Column("performed_fee_stage_codes", sa.JSON(), nullable=True))
    op.add_column("fee_events", sa.Column("breakdown_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("fee_events", "breakdown_json")
    op.drop_column("cases", "performed_fee_stage_codes")
    op.drop_column("cases", "legacy_fee_text")
    op.drop_table("fee_stage_rates")
    # PostgreSQL: cannot remove enum values easily; leave APPEAL/STAGE_BILLING in type
    # op.execute("ALTER TYPE feeeventtype DROP VALUE 'STAGE_BILLING'")  # not supported in PG
    # op.execute("ALTER TYPE feeeventtype DROP VALUE 'APPEAL'")
    pass

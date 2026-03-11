"""Backfill fee_events: convert stored net amounts to gross (incl. VAT). Idempotent.

Revision ID: 0016_backfill_fee_events_gross
Revises: 0015_fee_stage_rates_gross
Create Date: 2026-02-02

- Single-stage fee events: if computed_amount_ils_gross equals a known net rate, set to gross.
- STAGE_BILLING events: if breakdown_json.rates contain net values, convert to gross and recompute totals.
- Excludes no events by type; soft-deleted events are updated consistently so totals stay correct
  when include_deleted is used. Normal totals exclude deleted (unchanged).
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
import json
import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

revision = "0016_backfill_fee_events_gross"
down_revision = "0015_fee_stage_rates_gross"
branch_labels = None
depends_on = None

# Known net (pre-VAT) single rates -> gross (18% VAT, ROUND_HALF_UP to 0.01).
# Only these exact net values are converted; already-gross amounts are left unchanged.
# Keys with and without .00 for DB/JSON variation.
NET_TO_GROSS = {
    "20000.00": "23600.00", "20000": "23600.00",
    "15000.00": "17700.00", "15000": "17700.00",
    "10000.00": "11800.00", "10000": "11800.00",
    "1500.00": "1770.00", "1500": "1770.00",
    "5000.00": "5900.00", "5000": "5900.00",
    "700.00": "826.00", "700": "826.00",
    "0.00": "0.00", "0": "0.00",
}

# Single-stage event_type -> (net, gross) for exact match.
SINGLE_STAGE_NET_GROSS = [
    ("COURT_STAGE_1_DEFENSE", "20000.00", "23600.00"),
    ("COURT_STAGE_2_DAMAGES", "15000.00", "17700.00"),
    ("COURT_STAGE_3_EVIDENCE", "15000.00", "17700.00"),
    ("COURT_STAGE_4_PROOFS", "15000.00", "17700.00"),
    ("COURT_STAGE_5_SUMMARIES", "10000.00", "11800.00"),
    ("AMENDED_DEFENSE_PARTIAL", "10000.00", "11800.00"),
    ("AMENDED_DEFENSE_FULL", "20000.00", "23600.00"),
    ("THIRD_PARTY_NOTICE", "10000.00", "11800.00"),
    ("ADDITIONAL_PROOF_HEARING", "1500.00", "1770.00"),
    ("DEMAND_FIX", "5000.00", "5900.00"),
    ("DEMAND_HOURLY", "700.00", "826.00"),
    ("APPEAL", "15000.00", "17700.00"),
]


def _q(s: str) -> Decimal:
    return Decimal(s).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def upgrade() -> None:
    conn = op.get_bind()

    # 1) Single-stage fee events: exact net -> gross (includes soft-deleted for consistency).
    for event_type, net, gross in SINGLE_STAGE_NET_GROSS:
        conn.execute(
            text("""
                UPDATE fee_events
                SET computed_amount_ils_gross = :gross,
                    amount_due_cash_ils_gross = :gross,
                    amount_covered_by_credit_ils_gross = 0
                WHERE event_type = :etype
                  AND computed_amount_ils_gross = :net
            """),
            {"etype": event_type, "net": net, "gross": gross},
        )

    # 2) STAGE_BILLING: convert breakdown rates net->gross and recompute totals (idempotent: only if rates look net).
    rows = conn.execute(
        text("""
            SELECT id, case_id, computed_amount_ils_gross, breakdown_json
            FROM fee_events
            WHERE event_type = 'STAGE_BILLING' AND breakdown_json IS NOT NULL
        """)
    ).fetchall()

    for (event_id, case_id, computed, raw_bj) in rows:
        if raw_bj is None:
            continue
        breakdown_json = json.loads(raw_bj) if isinstance(raw_bj, str) else raw_bj
        if not breakdown_json or "rates" not in breakdown_json:
            continue
        rates = breakdown_json.get("rates") or {}
        # Check if any rate is net (exact string match to known net).
        def _is_net(v):
            s = str(v).strip()
            return s in NET_TO_GROSS
        has_net = any(_is_net(rates.get(c)) for c in rates)
        if not has_net:
            continue

        new_rates = {}
        for code, val in rates.items():
            v = str(val).strip()
            new_rates[code] = NET_TO_GROSS.get(v, v) if v else "0.00"

        codes_selected = breakdown_json.get("codes_selected") or list(new_rates.keys())
        new_codes = breakdown_json.get("new_codes") or []
        base_total = sum(_q(new_rates.get(c, "0")) for c in codes_selected)
        delta_total = sum(_q(new_rates.get(c, "0")) for c in new_codes)
        final_delta = delta_total
        adj = breakdown_json.get("adjustment")
        if adj and adj.get("kind") == "DISCOUNT":
            try:
                final_delta = delta_total - _q(str(adj.get("amount_ils", 0)))
            except Exception:
                pass
        elif adj and adj.get("kind") not in (None, "DISCOUNT"):
            try:
                final_delta = delta_total + _q(str(adj.get("amount_ils", 0)))
            except Exception:
                pass
        final_delta = max(Decimal("0.00"), final_delta.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
        delta_total = delta_total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        new_breakdown = {**breakdown_json, "rates": {k: str(v) for k, v in new_rates.items()}}
        new_breakdown["base_total_selected"] = str(base_total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
        new_breakdown["delta_total"] = str(delta_total)
        new_breakdown["final_delta_total"] = str(final_delta)

        conn.execute(
            text("""
                UPDATE fee_events
                SET computed_amount_ils_gross = :gross,
                    amount_due_cash_ils_gross = :gross,
                    amount_covered_by_credit_ils_gross = 0,
                    breakdown_json = :bj
                WHERE id = :id
            """),
            {"id": event_id, "gross": str(final_delta), "bj": json.dumps(new_breakdown)},
        )


def downgrade() -> None:
    # Reverting backfill would require storing original net; we do not have it.
    # Downgrade is a no-op; re-run upgrade is idempotent (already-gross values are not changed).
    pass

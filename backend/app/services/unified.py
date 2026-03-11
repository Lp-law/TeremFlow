"""
Unified computation model: one consistent set of formulas across dashboard, overview, tabs, exports.
- retainer_charged_to_date_ils: theoretical (945+VAT)*months from anchor to effective_end
- fees_by_stages_ils: sum of non-deleted fee events
- expenses_total_ils: Case.expenses_total_ils_gross
- excess_remaining_ils: excess_total - retainer_charged - expenses_total (with overrides)
- fee_diff_ils: fees_by_stages - retainer_charged

Manual overrides in case.manual_overrides_json are stored as decimal strings (e.g. "1234.56")
to preserve precision; we parse them back with _parse_override_to_decimal().
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy.orm import Session

from app.models.case import Case
from app.models.fee_event import FeeEvent
from app.services.deductible import q_ils
from app.services.retainer import (
    _accrual_start_month,
    _month_start,
    add_months,
    count_charged_months,
    get_retainer_anchor_date,
    retainer_gross_for_month,
)


def _parse_override_to_decimal(raw: Any) -> Decimal | None:
    """Parse override value (stored as string or number) to Decimal. Returns None on invalid/missing."""
    if raw is None:
        return None
    try:
        if isinstance(raw, Decimal):
            return q_ils(raw)
        if isinstance(raw, str):
            s = raw.strip()
            if not s or s.lower() in ("none", "null", ""):
                return None
            return q_ils(Decimal(s))
        if isinstance(raw, (int, float)):
            return q_ils(Decimal(str(raw)))
        return None
    except (InvalidOperation, ValueError, TypeError):
        return None


def _safe_overrides(case: Case) -> dict[str, Any]:
    """Return manual_overrides_json as a dict; never return non-dict (legacy/DB can store list or string)."""
    raw = getattr(case, "manual_overrides_json", None)
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    return {}


def get_effective_end_date(case: Case) -> dt.date:
    """When frozen, retainer charged months stop at retainer_frozen_at; else today. Always returns date."""
    if getattr(case, "retainer_is_frozen", False):
        at = getattr(case, "retainer_frozen_at", None)
        if at is not None and isinstance(at, dt.date):
            return at
    return dt.date.today()


def _effective_anchor_date(case: Case) -> dt.date | None:
    """Retainer anchor date; if missing, derive from open_date. None only if both missing."""
    anchor = getattr(case, "retainer_anchor_date", None)
    if anchor is not None and isinstance(anchor, dt.date):
        return anchor
    open_date = getattr(case, "open_date", None)
    if open_date is not None and isinstance(open_date, dt.date):
        return get_retainer_anchor_date(open_date)
    return None


def charged_months_count(case: Case) -> int:
    """Number of months charged from anchor (or month after snapshot_through) to effective_end_date inclusive.
    Returns 0 if anchor/open_date missing or snapshot_through is wrong type.
    """
    anchor = _effective_anchor_date(case)
    if anchor is None:
        return 0
    snapshot_through = getattr(case, "retainer_snapshot_through_month", None)
    if snapshot_through is not None and not isinstance(snapshot_through, dt.date):
        snapshot_through = None
    effective_end = get_effective_end_date(case)
    return count_charged_months(anchor, effective_end, snapshot_through)


def retainer_charged_to_date_ils(db: Session, case: Case) -> Decimal:
    """Theoretical retainer charged = sum of monthly_gross_ils for each month from start to effective_end.
    Returns 0 if anchor/open_date missing.
    """
    overrides = _safe_overrides(case)
    parsed = _parse_override_to_decimal(overrides.get("retainer_charged_override"))
    if parsed is not None:
        return parsed
    anchor = _effective_anchor_date(case)
    if anchor is None:
        return q_ils(Decimal("0.00"))
    snapshot_through = getattr(case, "retainer_snapshot_through_month", None)
    if snapshot_through is not None and not isinstance(snapshot_through, dt.date):
        snapshot_through = None
    start = _accrual_start_month(anchor, snapshot_through)
    end = _month_start(get_effective_end_date(case))
    if start > end:
        return q_ils(Decimal("0.00"))
    total = Decimal("0.00")
    cur = start
    while cur <= end:
        total += retainer_gross_for_month(cur)
        cur = add_months(cur, 1)
    return q_ils(total)


def fees_by_stages_ils(db: Session, case: Case) -> Decimal:
    """Sum of non-deleted fee events (computed_amount_ils_gross)."""
    overrides = _safe_overrides(case)
    parsed = _parse_override_to_decimal(overrides.get("fees_by_stages_override"))
    if parsed is not None:
        return parsed
    rows = (
        db.query(FeeEvent.computed_amount_ils_gross)
        .filter(FeeEvent.case_id == case.id, FeeEvent.deleted_at.is_(None))
        .all()
    )
    total = sum(
        Decimal("0.00") if r[0] is None else Decimal(str(r[0]))
        for r in rows
    )
    return q_ils(total)


def expenses_total_ils(case: Case) -> Decimal:
    """Case-level editable total (expenses_total_ils_gross). Missing -> 0."""
    overrides = _safe_overrides(case)
    parsed = _parse_override_to_decimal(overrides.get("expenses_total_override"))
    if parsed is not None:
        return parsed
    val = getattr(case, "expenses_total_ils_gross", None)
    if val is None:
        return q_ils(Decimal("0.00"))
    try:
        return q_ils(Decimal(str(val)))
    except (InvalidOperation, ValueError, TypeError):
        return q_ils(Decimal("0.00"))


def excess_total_ils(case: Case) -> Decimal:
    """excess_total = deductible_ils_gross (with override). Missing -> 0."""
    overrides = _safe_overrides(case)
    parsed = _parse_override_to_decimal(overrides.get("excess_total_ils_override"))
    if parsed is not None:
        return parsed
    val = getattr(case, "deductible_ils_gross", None)
    if val is None:
        return q_ils(Decimal("0.00"))
    try:
        return q_ils(Decimal(str(val)))
    except (InvalidOperation, ValueError, TypeError):
        return q_ils(Decimal("0.00"))


def excess_remaining_ils(db: Session, case: Case) -> Decimal:
    """excess_remaining = excess_total - retainer_charged - expenses_total (with override)."""
    overrides = _safe_overrides(case)
    parsed = _parse_override_to_decimal(overrides.get("excess_remaining_override"))
    if parsed is not None:
        return parsed
    total = excess_total_ils(case)
    charged = retainer_charged_to_date_ils(db, case)
    exp = expenses_total_ils(case)
    rem = q_ils(total - charged - exp)
    return max(q_ils(Decimal("0.00")), rem)


def fee_diff_ils(db: Session, case: Case) -> Decimal:
    """fee_diff = fees_by_stages - retainer_charged (with override). May be negative."""
    overrides = _safe_overrides(case)
    parsed = _parse_override_to_decimal(overrides.get("fee_diff_override"))
    if parsed is not None:
        return parsed
    fees = fees_by_stages_ils(db, case)
    charged = retainer_charged_to_date_ils(db, case)
    return q_ils(fees - charged)


def get_unified_summary(db: Session, case: Case) -> dict[str, Any]:
    """All unified values for overview/deductible tab/export."""
    return {
        "retainer_charged_to_date_ils": retainer_charged_to_date_ils(db, case),
        "fees_by_stages_ils": fees_by_stages_ils(db, case),
        "expenses_total_ils": expenses_total_ils(case),
        "excess_total_ils": excess_total_ils(case),
        "excess_remaining_ils": excess_remaining_ils(db, case),
        "fee_diff_ils": fee_diff_ils(db, case),
        "charged_months_count": charged_months_count(case),
        "effective_end_date": get_effective_end_date(case).isoformat(),
    }

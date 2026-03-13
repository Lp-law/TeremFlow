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
from app.models.retainer import RetainerPayment
from app.services.deductible import q_ils
from app.services.retainer import (
    _accrual_start_month,
    _month_start,
    add_months,
    count_charged_months,
    get_retainer_anchor_date,
    is_legacy_note,
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
    """Effective end = min(today, retainer_end_date if set, retainer_frozen_at if frozen). Always returns date."""
    today = dt.date.today()
    end_date = getattr(case, "retainer_end_date", None)
    if end_date is not None and isinstance(end_date, dt.date):
        today = min(today, end_date)
    if getattr(case, "retainer_is_frozen", False):
        at = getattr(case, "retainer_frozen_at", None)
        if at is not None and isinstance(at, dt.date):
            today = min(today, at)
    return today


def _effective_anchor_date(case: Case) -> dt.date | None:
    """Retainer anchor date for charged/theoretical. None when not set (no fallback to open_date so charged=0)."""
    anchor = getattr(case, "retainer_anchor_date", None)
    if anchor is not None and isinstance(anchor, dt.date):
        return anchor
    return None


def charged_months_count(case: Case) -> int:
    """Number of months charged: current + legacy periods (from get_retainer_period_months)."""
    from app.services.retainer import get_retainer_period_months
    period_months = get_retainer_period_months(case)
    if period_months:
        return len(period_months)
    anchor = _effective_anchor_date(case)
    if anchor is None:
        return 0
    snapshot_through = getattr(case, "retainer_snapshot_through_month", None)
    if snapshot_through is not None and not isinstance(snapshot_through, dt.date):
        snapshot_through = None
    effective_end = get_effective_end_date(case)
    return count_charged_months(anchor, effective_end, snapshot_through)


def _legacy_retainer_theoretical_ils(db: Session, case_id: int) -> Decimal:
    """Legacy theoretical = 945+VAT per month for each month covered by LEGACY payments.
    A payment is LEGACY if is_legacy_note(note). We use retainer_gross_for_month(payment_date)
    so theoretical is months × official rate (VAT by month), not stored amount.
    """
    payments = db.query(RetainerPayment).filter(RetainerPayment.case_id == case_id).all()
    legacy_total = Decimal("0.00")
    for p in payments:
        if not is_legacy_note(p.note):
            continue
        month_first = _month_start(p.payment_date)
        legacy_total += retainer_gross_for_month(month_first)
    return q_ils(legacy_total)


def _regular_retainer_theoretical_ils(db: Session, case: Case) -> Decimal:
    """Theoretical from anchor to effective_end only (945+VAT per month). Excludes legacy."""
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


def retainer_charged_to_date_ils(db: Session, case: Case) -> Decimal:
    """סכום קובע = סה״כ הריטיינר ששולם (כולל ידני) — תשלומים + snapshot (ריטיינר היסטורי מייבוא).
    Override retainer_charged_override replaces the total if set.
    """
    overrides = _safe_overrides(case)
    parsed = _parse_override_to_decimal(overrides.get("retainer_charged_override"))
    if parsed is not None:
        return parsed
    from app.services.retainer import _sum_payments
    paid = _sum_payments(db, case.id)
    snapshot = getattr(case, "retainer_snapshot_ils_gross", None)
    if snapshot is not None:
        try:
            paid = q_ils(paid + Decimal(str(snapshot)))
        except (InvalidOperation, ValueError, TypeError):
            pass
    return paid


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
        (Decimal("0.00") if r[0] is None else Decimal(str(r[0])) for r in rows),
        Decimal("0.00"),
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
    """Unified values for overview/deductible/export. retainer_charged_to_date_ils = סה״כ ריטיינר ששולם (כולל ידני) from ledger."""
    overrides = _safe_overrides(case)
    override_total = _parse_override_to_decimal(overrides.get("retainer_charged_override"))
    from app.services.retainer import _sum_payments, get_total_retainer_theoretical_ils
    paid_total = _sum_payments(db, case.id)
    total = override_total if override_total is not None else paid_total
    _, total_current, total_legacy = get_total_retainer_theoretical_ils(db, case)
    return {
        "retainer_charged_to_date_ils": total,
        "retainer_regular_theoretical_ils": total_current,
        "retainer_legacy_theoretical_ils": total_legacy,
        "fees_by_stages_ils": fees_by_stages_ils(db, case),
        "expenses_total_ils": expenses_total_ils(case),
        "excess_total_ils": excess_total_ils(case),
        "excess_remaining_ils": excess_remaining_ils(db, case),
        "fee_diff_ils": fee_diff_ils(db, case),
        "charged_months_count": charged_months_count(case),
        "effective_end_date": get_effective_end_date(case).isoformat(),
    }

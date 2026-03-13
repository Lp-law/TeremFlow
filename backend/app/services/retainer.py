from __future__ import annotations

import datetime as dt
import logging
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.case import Case
from app.models.enums import CaseStatus
from app.models.fee_event import FeeEvent
from app.models.retainer import RetainerAccrual, RetainerPayment
from app.services.deductible import q_ils

RETAINER_BASE_NET_ILS = Decimal("945.00")
VAT_17_PCT = Decimal("0.17")
VAT_18_PCT = Decimal("0.18")
VAT_CUTOVER = dt.date(2025, 1, 1)  # From Jan 2025: 18%


def vat_rate_for_month(accrual_month: dt.date) -> Decimal:
    """VAT rate: 17% up to Dec 2024, 18% from Jan 2025."""
    if accrual_month < VAT_CUTOVER:
        return VAT_17_PCT
    return VAT_18_PCT


def retainer_gross_for_month(accrual_month: dt.date) -> Decimal:
    """Gross = 945 * (1 + VAT_rate). Dec 2024: 1105.65, Jan 2025: 1115.10."""
    rate = vat_rate_for_month(accrual_month)
    return q_ils(RETAINER_BASE_NET_ILS * (Decimal("1") + rate))


def is_legacy_note(note: str | None) -> bool:
    """True if note is non-null, trimmed, and starts with 'LEGACY' case-insensitive (legacy range payments)."""
    if note is None:
        return False
    s = note.strip()
    return len(s) > 0 and s.upper().startswith("LEGACY")


def _month_start(d: dt.date) -> dt.date:
    return dt.date(d.year, d.month, 1)


def add_months(d: dt.date, months: int) -> dt.date:
    y = d.year + (d.month - 1 + months) // 12
    m = (d.month - 1 + months) % 12 + 1
    return dt.date(y, m, 1)


def get_retainer_anchor_date(open_date: dt.date) -> dt.date:
    """Case opened Jan-Jun -> July same year; Jul-Dec -> January next year."""
    if 1 <= open_date.month <= 6:
        return dt.date(open_date.year, 7, 1)
    return dt.date(open_date.year + 1, 1, 1)


def get_retainer_start_month(retainer_anchor_date: dt.date) -> dt.date:
    """First accrual month = anchor date (first of month)."""
    return _month_start(retainer_anchor_date)


def _accrual_start_month(retainer_anchor_date: dt.date, snapshot_through_month: dt.date | None) -> dt.date:
    """First accrual month. If snapshot_through_month set, start from month after. Else from anchor."""
    if snapshot_through_month is not None:
        return add_months(_month_start(snapshot_through_month), 1)
    return get_retainer_start_month(retainer_anchor_date)


def count_charged_months(
    anchor_date: dt.date,
    effective_end_date: dt.date,
    snapshot_through_month: dt.date | None = None,
) -> int:
    """
    Count calendar months inclusively from start month to end month (by month boundaries).

    Rule:
    - anchor_date is treated as first-of-month (start of that month).
    - effective_end_date can be any day; we use the month containing that day as the last charged month.
    - If snapshot_through_month is set, start = first day of the month *after* snapshot_through_month.
    - Count = number of calendar months from start to end inclusive. Same month -> 1. No gap.

    Examples:
    - anchor 2024-07-01, end 2024-07-15 -> 1 (July only).
    - anchor 2024-07-01, end 2025-06-01 -> 12 (Jul'24 through Jun'25).
    - anchor 2024-07-01, end 2025-02-15 -> 8 (Jul'24 through Feb'25).
    """
    start = _accrual_start_month(_month_start(anchor_date), snapshot_through_month)
    end = _month_start(effective_end_date)
    if start > end:
        return 0
    return (end.year - start.year) * 12 + (end.month - start.month) + 1


def ensure_accruals_up_to(
    db: Session,
    *,
    case_id: int,
    retainer_anchor_date: dt.date,
    up_to: dt.date | None = None,
    snapshot_through_month: dt.date | None = None,
) -> list[RetainerAccrual]:
    """
    Ensure fixed monthly accruals exist from start month through up_to month (inclusive).
    start_month = first month after snapshot_through_month (if set), else retainer_anchor_date.
    Amount per month uses VAT: 17% up to Dec 2024, 18% from Jan 2025.
    """
    today = dt.date.today()
    up_to = _month_start(up_to or today)
    start = _accrual_start_month(retainer_anchor_date, snapshot_through_month)
    if start > up_to:
        return []

    existing = {
        a.accrual_month: a
        for a in db.query(RetainerAccrual).filter(RetainerAccrual.case_id == case_id).all()
    }
    created: list[RetainerAccrual] = []

    cur = start
    while cur <= up_to:
        if cur not in existing:
            invoice_date = cur
            due_date = invoice_date + dt.timedelta(days=60)
            amount = retainer_gross_for_month(cur)
            a = RetainerAccrual(
                case_id=case_id,
                accrual_month=cur,
                invoice_date=invoice_date,
                due_date=due_date,
                amount_ils_gross=amount,
                is_paid=False,
            )
            db.add(a)
            created.append(a)
        cur = add_months(cur, 1)

    if created:
        db.commit()
        for a in created:
            db.refresh(a)
    return created


def ensure_all_cases_accruals_up_to_now(db: Session) -> tuple[int, int]:
    """
    Roll-forward: ensure all open non-deleted cases have accruals up to effective end (today or freeze date).
    - Excludes soft-deleted cases.
    - When case is frozen, up_to = retainer_frozen_at.
    Returns (cases_scanned, accruals_added).
    """
    from app.services.unified import get_effective_end_date

    logger = logging.getLogger(__name__)
    open_cases = (
        db.query(Case)
        .filter(Case.status == CaseStatus.OPEN, Case.deleted_at.is_(None))
        .all()
    )
    total_added = 0
    processed = 0
    for c in open_cases:
        if c.retainer_snapshot_ils_gross is not None and c.retainer_snapshot_through_month is None:
            continue
        processed += 1
        snapshot_through = c.retainer_snapshot_through_month if c.retainer_snapshot_ils_gross else None
        up_to = get_effective_end_date(c)
        created = ensure_accruals_up_to(
            db,
            case_id=c.id,
            retainer_anchor_date=c.retainer_anchor_date,
            up_to=up_to,
            snapshot_through_month=snapshot_through,
        )
        total_added += len(created)
    logger.info(
        "retainer_roll_forward: cases_scanned=%d accruals_added=%d",
        processed,
        total_added,
    )
    return processed, total_added


def _sum_payments(db: Session, case_id: int) -> Decimal:
    total = (
        db.query(func.coalesce(func.sum(RetainerPayment.amount_ils_gross), 0))
        .filter(RetainerPayment.case_id == case_id)
        .scalar()
    )
    return q_ils(Decimal(str(total)))


def allocate_payments_to_accruals(db: Session, *, case_id: int) -> None:
    """
    Marks accruals as paid oldest-first based on total cash received.
    Each accrual has its own amount_ils_gross (VAT-dependent).
    """
    total_paid = _sum_payments(db, case_id)
    accruals = (
        db.query(RetainerAccrual)
        .filter(RetainerAccrual.case_id == case_id)
        .order_by(RetainerAccrual.accrual_month.asc())
        .all()
    )
    remaining = total_paid
    for a in accruals:
        amt = Decimal(str(a.amount_ils_gross))
        if remaining >= amt:
            a.is_paid = True
            remaining = q_ils(remaining - amt)
        else:
            a.is_paid = False
    db.commit()


def create_legacy_range_payments(
    db: Session,
    *,
    case_id: int,
    start_date: dt.date,
    end_date: dt.date,
    monthly_amount_ils_gross: Decimal,
    note: str | None = None,
) -> list[RetainerPayment]:
    """
    Create one RetainerPayment per month in [start_date, end_date] (inclusive by month).
    payment_date = first day of each month. note prefixed with "LEGACY: ".
    """
    start = _month_start(start_date)
    end = _month_start(end_date)
    if start > end:
        return []
    amount = q_ils(monthly_amount_ils_gross)
    note_val = ("LEGACY: " + ((note or "").strip() or "")).strip() or "LEGACY"
    created: list[RetainerPayment] = []
    cur = start
    while cur <= end:
        p = RetainerPayment(
            case_id=case_id,
            payment_date=cur,
            amount_ils_gross=amount,
            note=note_val,
        )
        db.add(p)
        created.append(p)
        cur = add_months(cur, 1)
    db.commit()
    for p in created:
        db.refresh(p)
    allocate_payments_to_accruals(db, case_id=case_id)
    return created


def retainer_summary(db: Session, *, case_id: int) -> dict[str, Decimal]:
    accrued_total = (
        db.query(func.coalesce(func.sum(RetainerAccrual.amount_ils_gross), 0))
        .filter(RetainerAccrual.case_id == case_id)
        .scalar()
    )
    paid_total = _sum_payments(db, case_id)

    applied_to_fees_total = (
        db.query(func.coalesce(func.sum(FeeEvent.amount_covered_by_credit_ils_gross), 0))
        .filter(FeeEvent.case_id == case_id)
        .scalar()
    )
    applied_to_fees_total = q_ils(Decimal(str(applied_to_fees_total)))

    fees_due_total = (
        db.query(func.coalesce(func.sum(FeeEvent.amount_due_cash_ils_gross), 0))
        .filter(FeeEvent.case_id == case_id)
        .scalar()
    )
    fees_due_total = q_ils(Decimal(str(fees_due_total)))

    credit_balance = q_ils(paid_total - applied_to_fees_total)
    if credit_balance < 0:
        credit_balance = Decimal("0.00")

    return {
        "retainer_accrued_total_ils_gross": q_ils(Decimal(str(accrued_total))),
        "retainer_paid_total_ils_gross": paid_total,
        "retainer_applied_to_fees_total_ils_gross": applied_to_fees_total,
        "retainer_credit_balance_ils_gross": credit_balance,
        "fees_due_total_ils_gross": fees_due_total,
    }


def _aggregate_payments_by_month(payments: list) -> dict[str, tuple[Decimal, str | None]]:
    """Group payments by YYYY-MM; value = (sum paid_ils, optional notes e.g. '2 תשלומים')."""
    by_month: dict[str, list[tuple[Decimal, str | None]]] = {}
    for p in payments:
        month_str = p.payment_date.strftime("%Y-%m")
        amt = q_ils(Decimal(str(p.amount_ils_gross)))
        note = (p.note or "").strip() or None
        if month_str not in by_month:
            by_month[month_str] = []
        by_month[month_str].append((amt, note))
    out = {}
    for month_str, items in by_month.items():
        total = q_ils(sum(a for a, _ in items))
        notes_parts = []
        if len(items) > 1:
            notes_parts.append(f"{len(items)} תשלומים")
        first_note = next((n for _, n in items if n), None)
        if first_note:
            notes_parts.append(first_note)
        out[month_str] = (total, notes_parts[0] if len(notes_parts) == 1 else ("; ".join(notes_parts) if notes_parts else None))
    return out


def _effective_end_for_period(
    case: Case,
    start_date: dt.date | None,
    end_date: dt.date | None,
) -> dt.date:
    """End date for a period: min(today, end_date if set, frozen_at if frozen)."""
    today = dt.date.today()
    if end_date is not None:
        today = min(today, end_date)
    if getattr(case, "retainer_is_frozen", False):
        at = getattr(case, "retainer_frozen_at", None)
        if at is not None and isinstance(at, dt.date):
            today = min(today, at)
    return today


def get_retainer_period_months(case: Case) -> list[tuple[dt.date, str]]:
    """Returns [(month_first, 'current'|'legacy'), ...] sorted by month, deduped. Both periods contribute."""
    today = dt.date.today()
    months: list[tuple[dt.date, str]] = []
    current_start = getattr(case, "retainer_current_start_date", None) or getattr(case, "retainer_anchor_date", None)
    current_end = getattr(case, "retainer_current_end_date", None) or getattr(case, "retainer_end_date", None)
    if current_start is not None and isinstance(current_start, dt.date):
        start_m = _month_start(current_start)
        end_m = _month_start(_effective_end_for_period(case, current_start, current_end))
        if start_m <= end_m:
            cur = start_m
            while cur <= end_m:
                months.append((cur, "current"))
                cur = add_months(cur, 1)
    legacy_start = getattr(case, "retainer_legacy_start_date", None)
    legacy_end = getattr(case, "retainer_legacy_end_date", None)
    if legacy_start is not None and isinstance(legacy_start, dt.date):
        start_m = _month_start(legacy_start)
        end_m = _month_start(_effective_end_for_period(case, legacy_start, legacy_end))
        if start_m <= end_m:
            cur = start_m
            while cur <= end_m:
                months.append((cur, "legacy"))
                cur = add_months(cur, 1)
    months.sort(key=lambda x: (x[0], x[1]))
    seen: set[dt.date] = set()
    out: list[tuple[dt.date, str]] = []
    for m, kind in months:
        if m not in seen:
            seen.add(m)
            out.append((m, kind))
    return out


def get_total_retainer_theoretical_ils(db: Session, case: Case) -> tuple[Decimal, Decimal, Decimal]:
    """One cumulative theoretical = current period + legacy period (same 945+VAT, different billing periods only).
    Returns (total, total_current, total_legacy). Legacy = from period dates and/or from LEGACY payments (note).
    No distinction for billing: both count as theoretical retainer."""
    period_months = get_retainer_period_months(case)
    months_already_counted: set[dt.date] = {m for m, _ in period_months}
    total = Decimal("0.00")
    total_current = Decimal("0.00")
    total_legacy = Decimal("0.00")
    for month_first, kind in period_months:
        gross = retainer_gross_for_month(month_first)
        total += gross
        if kind == "current":
            total_current += gross
        else:
            total_legacy += gross
    # Include months from LEGACY payments (note starts with LEGACY) not already in period — same theoretical
    payments = db.query(RetainerPayment).filter(RetainerPayment.case_id == case.id).all()
    for p in payments:
        if not is_legacy_note(p.note):
            continue
        month_first = _month_start(p.payment_date)
        if month_first in months_already_counted:
            continue
        months_already_counted.add(month_first)
        gross = retainer_gross_for_month(month_first)
        total += gross
        total_legacy += gross
    return (q_ils(total), q_ils(total_current), q_ils(total_legacy))


def _ledger_payments_only(db: Session, *, case_id: int) -> dict:
    """Minimal ledger when case has no retainer_anchor_date: one row per month (payments aggregated)."""
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        return None
    summary = retainer_summary(db, case_id=case_id)
    today = dt.date.today()
    rate = vat_rate_for_month(today)
    vat_pct = "18%" if rate >= Decimal("0.18") else "17%"
    config = {
        "monthly_base_net_ils": RETAINER_BASE_NET_ILS,
        "vat_pct": vat_pct,
        "monthly_gross_ils": retainer_gross_for_month(today),
    }
    anchor = getattr(case, "open_date", None) or today
    payments = (
        db.query(RetainerPayment)
        .filter(RetainerPayment.case_id == case_id)
        .order_by(RetainerPayment.payment_date.asc(), RetainerPayment.id.asc())
        .all()
    )
    paid_by_month = _aggregate_payments_by_month(payments)
    months_sorted = sorted(paid_by_month.keys())
    rows = []
    running = Decimal("0.00")
    for month_str in months_sorted:
        paid_ils, notes = paid_by_month[month_str]
        running = q_ils(running + paid_ils)
        rows.append({
            "month": month_str,
            "accrued_ils": Decimal("0"),
            "paid_ils": paid_ils,
            "running_credit_ils": running,
            "row_type": "accrual",
            "notes": notes,
        })
    charged_months_count = len(months_sorted)
    return {
        "config": config,
        "anchor_date": anchor.isoformat(),
        "snapshot_through_month": None,
        "snapshot_paid_ils": Decimal("0"),
        "current_credit_ils": summary["retainer_credit_balance_ils_gross"],
        "charged_months_count": charged_months_count,
        "retainer_paid_total_ils_gross": summary["retainer_paid_total_ils_gross"],
        "total_accrued_ils": Decimal("0"),
        "total_retainer_theoretical_ils_gross": Decimal("0"),
        "total_current_theoretical_ils": Decimal("0"),
        "total_legacy_theoretical_ils": Decimal("0"),
        "rows": rows,
    }


def build_retainer_ledger(db: Session, *, case_id: int) -> dict:
    """
    Build month-by-month ledger for display. Two periods: current + legacy. Months = union of both, chronological.
    Ledger is source of truth for total_retainer_theoretical_ils_gross (945+VAT per month).
    Returns None if case not found or deleted.
    """
    from app.services.unified import get_effective_end_date

    case = db.query(Case).filter(Case.id == case_id).first()
    if not case or getattr(case, "deleted_at", None) is not None:
        return None
    anchor = getattr(case, "retainer_anchor_date", None)
    current_start = getattr(case, "retainer_current_start_date", None) or anchor
    legacy_start = getattr(case, "retainer_legacy_start_date", None)
    if current_start is None and legacy_start is None:
        return _ledger_payments_only(db, case_id=case_id)

    effective_end = get_effective_end_date(case)
    snapshot_through = case.retainer_snapshot_through_month if case.retainer_snapshot_ils_gross else None
    snapshot_paid = q_ils(Decimal(str(case.retainer_snapshot_ils_gross or 0)))
    if current_start is not None:
        ensure_accruals_up_to(
            db,
            case_id=case_id,
            retainer_anchor_date=current_start,
            up_to=effective_end,
            snapshot_through_month=snapshot_through,
        )
    summary = retainer_summary(db, case_id=case_id)
    current_credit = summary["retainer_credit_balance_ils_gross"]
    rate = vat_rate_for_month(effective_end)
    vat_pct = "18%" if rate >= Decimal("0.18") else "17%"
    config = {
        "monthly_base_net_ils": RETAINER_BASE_NET_ILS,
        "vat_pct": vat_pct,
        "monthly_gross_ils": retainer_gross_for_month(effective_end),
    }
    accruals = (
        db.query(RetainerAccrual)
        .filter(RetainerAccrual.case_id == case_id)
        .order_by(RetainerAccrual.accrual_month.asc())
        .all()
    )
    payments = (
        db.query(RetainerPayment)
        .filter(RetainerPayment.case_id == case_id)
        .order_by(RetainerPayment.payment_date.asc(), RetainerPayment.id.asc())
        .all()
    )
    accrual_by_month: dict[str, Decimal] = {}
    for a in accruals:
        month_str = a.accrual_month.strftime("%Y-%m")
        accrual_by_month[month_str] = q_ils(Decimal(str(a.amount_ils_gross)))
    paid_by_month = _aggregate_payments_by_month(payments)

    period_months = get_retainer_period_months(case)
    month_strs = sorted({m.strftime("%Y-%m") for m, _ in period_months})
    month_to_date = {m.strftime("%Y-%m"): m for m, _ in period_months}
    for p in payments:
        if is_legacy_note(p.note):
            m = _month_start(p.payment_date)
            ms = m.strftime("%Y-%m")
            if ms not in month_to_date:
                month_to_date[ms] = m
                month_strs = sorted(set(month_strs) | {ms})
    if snapshot_paid > 0 and snapshot_through is not None:
        snap_month = snapshot_through.strftime("%Y-%m")
        if snap_month not in month_strs:
            month_strs = sorted(set(month_strs) | {snap_month})
    # Do not add months from paid_by_month: list is strictly from typed period dates (current + legacy)

    rows = []
    running = Decimal("0.00")
    for month_str in month_strs:
        accrued = accrual_by_month.get(month_str)
        if accrued is None and month_str in month_to_date:
            accrued = retainer_gross_for_month(month_to_date[month_str])
        accrued = accrued or Decimal("0")
        paid_total, notes = paid_by_month.get(month_str, (Decimal("0"), None))
        if snapshot_paid > 0 and snapshot_through is not None and snapshot_through.strftime("%Y-%m") == month_str:
            paid_total = q_ils(paid_total + snapshot_paid)
            notes = "from snapshot" if not notes else f"{notes}; from snapshot"
        running = q_ils(running + paid_total - accrued)
        row_type = "snapshot" if (snapshot_paid > 0 and snapshot_through and snapshot_through.strftime("%Y-%m") == month_str) else "accrual"
        rows.append({
            "month": month_str,
            "accrued_ils": accrued,
            "paid_ils": paid_total,
            "running_credit_ils": running,
            "row_type": row_type,
            "notes": notes,
        })

    charged_months_count = len(month_strs)
    total_paid_ils = q_ils(summary["retainer_paid_total_ils_gross"] + snapshot_paid)
    total_accrued_ils = q_ils(sum(r["accrued_ils"] for r in rows))
    total_theoretical, total_current_theoretical, total_legacy_theoretical = get_total_retainer_theoretical_ils(db, case)
    display_anchor = (current_start or anchor or case.open_date)
    return {
        "config": config,
        "anchor_date": display_anchor.isoformat() if hasattr(display_anchor, "isoformat") else str(display_anchor),
        "snapshot_through_month": snapshot_through.isoformat() if snapshot_through else None,
        "snapshot_paid_ils": snapshot_paid,
        "current_credit_ils": current_credit,
        "charged_months_count": charged_months_count,
        "retainer_paid_total_ils_gross": total_paid_ils,
        "total_accrued_ils": total_accrued_ils,
        "total_retainer_theoretical_ils_gross": total_theoretical,
        "total_current_theoretical_ils": total_current_theoretical,
        "total_legacy_theoretical_ils": total_legacy_theoretical,
        "rows": rows,
    }



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
    Roll-forward: ensure all open cases have accruals up to current month.
    - No snapshot: start from retainer_anchor_date.
    - Snapshot + through_month: start from month after through_month.
    - Snapshot without through_month: skip (backward compat).
    Returns (cases_scanned, accruals_added).
    Idempotent: ensure_accruals_up_to only creates missing months.
    """
    logger = logging.getLogger(__name__)
    today = dt.date.today()
    open_cases = db.query(Case).filter(Case.status == CaseStatus.OPEN).all()
    total_added = 0
    processed = 0
    for c in open_cases:
        if c.retainer_snapshot_ils_gross is not None and c.retainer_snapshot_through_month is None:
            continue
        processed += 1
        snapshot_through = c.retainer_snapshot_through_month if c.retainer_snapshot_ils_gross else None
        created = ensure_accruals_up_to(
            db,
            case_id=c.id,
            retainer_anchor_date=c.retainer_anchor_date,
            up_to=today,
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



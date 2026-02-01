from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.fee_event import FeeEvent
from app.models.retainer import RetainerAccrual, RetainerPayment
from app.services.deductible import q_ils

RETAINER_MONTHLY_ILS_GROSS = Decimal("945.00")


def _month_start(d: dt.date) -> dt.date:
    return dt.date(d.year, d.month, 1)


def add_months(d: dt.date, months: int) -> dt.date:
    y = d.year + (d.month - 1 + months) // 12
    m = (d.month - 1 + months) % 12 + 1
    return dt.date(y, m, 1)


def get_retainer_start_month(open_date: dt.date) -> dt.date:
    # If case opened between Jan-Jun: start month AFTER open_date
    if 1 <= open_date.month <= 6:
        return add_months(_month_start(open_date), 1)
    # If Jul-Dec: start January of NEXT year
    return dt.date(open_date.year + 1, 1, 1)


def ensure_accruals_up_to(db: Session, *, case_id: int, open_date: dt.date, up_to: dt.date | None = None) -> list[RetainerAccrual]:
    """
    Ensure fixed monthly accruals exist from start month through up_to month (inclusive).
    """
    today = dt.date.today()
    up_to = _month_start(up_to or today)
    start = get_retainer_start_month(open_date)
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
            a = RetainerAccrual(
                case_id=case_id,
                accrual_month=cur,
                invoice_date=invoice_date,
                due_date=due_date,
                amount_ils_gross=RETAINER_MONTHLY_ILS_GROSS,
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
        if remaining >= RETAINER_MONTHLY_ILS_GROSS:
            a.is_paid = True
            remaining = q_ils(remaining - RETAINER_MONTHLY_ILS_GROSS)
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



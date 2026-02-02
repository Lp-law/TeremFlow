from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.case import Case
from app.models.enums import ExpenseCategory, ExpensePayer
from app.models.expense import Expense
from app.services.deductible import deductible_remaining, q_ils, split_amount_over_deductible


def _consumed_on_deductible(db: Session, case_id: int) -> Decimal:
    total = (
        db.query(func.coalesce(func.sum(Expense.amount_ils_gross), 0))
        .filter(Expense.case_id == case_id, Expense.payer == ExpensePayer.CLIENT_DEDUCTIBLE)
        .scalar()
    )
    return Decimal(str(total))


def get_case_deductible_remaining(db: Session, case: Case) -> Decimal:
    consumed = _consumed_on_deductible(db, case.id)
    return deductible_remaining(deductible_ils_gross=Decimal(str(case.deductible_ils_gross)), consumed_on_deductible_ils_gross=consumed)


def get_case_excess_remaining(db: Session, case: Case) -> Decimal:
    """
    Excel P = M - J.
    J = retainer (past+future) + expenses (snapshot+other).
    - retainer_snapshot = past retainer; RetainerPayment = future retainer. No double count.
    - expenses_snapshot + other_expenses (Expense rows).
    """
    from app.models.retainer import RetainerPayment

    m = Decimal(str(case.deductible_ils_gross))

    retainer_paid = (
        db.query(func.coalesce(func.sum(RetainerPayment.amount_ils_gross), 0))
        .filter(RetainerPayment.case_id == case.id)
        .scalar()
    )
    retainer_paid = Decimal(str(retainer_paid))

    other_expenses = (
        db.query(func.coalesce(func.sum(Expense.amount_ils_gross), 0))
        .filter(
            Expense.case_id == case.id,
            Expense.payer == ExpensePayer.CLIENT_DEDUCTIBLE,
            Expense.category != ExpenseCategory.ATTORNEY_FEE,
        )
        .scalar()
    )
    other_expenses = Decimal(str(other_expenses))
    expenses_snapshot = Decimal(str(case.expenses_snapshot_ils_gross or 0))

    retainer_total = retainer_paid
    if case.retainer_snapshot_ils_gross is not None:
        retainer_total = q_ils(Decimal(str(case.retainer_snapshot_ils_gross)) + retainer_paid)

    j = q_ils(retainer_total + expenses_snapshot + other_expenses)
    remaining = q_ils(m - j)
    return max(Decimal("0.00"), remaining)


def list_expenses(db: Session, case_id: int) -> list[Expense]:
    return db.query(Expense).filter(Expense.case_id == case_id).order_by(Expense.expense_date.desc(), Expense.id.desc()).all()


def add_expense(db: Session, *, case_id: int, payload) -> list[Expense]:
    """
    Adds an expense, auto-splitting when it crosses deductible.

    If payload.payer is provided:
    - INSURER: full amount goes to insurer (does not consume deductible)
    - CLIENT_DEDUCTIBLE: still may be split if it would exceed remaining
    """
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")

    amt = q_ils(Decimal(str(payload.amount_ils_gross)))
    if amt <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")

    if payload.payer == ExpensePayer.INSURER:
        e = Expense(
            case_id=case_id,
            supplier_name=payload.supplier_name,
            amount_ils_gross=amt,
            service_description=payload.service_description,
            demand_received_date=payload.demand_received_date,
            expense_date=payload.expense_date,
            category=payload.category,
            payer=ExpensePayer.INSURER,
            attachment_url=payload.attachment_url,
        )
        db.add(e)
        db.commit()
        db.refresh(e)
        # If insurer is paying, mark started (if not already).
        if not case.insurer_started:
            case.insurer_started = True
            case.insurer_start_date = payload.expense_date
            db.commit()
        return [e]

    remaining = get_case_deductible_remaining(db, case)
    on_deductible, on_insurer = split_amount_over_deductible(amount_ils_gross=amt, remaining_ils_gross=remaining)

    created: list[Expense] = []
    split_id = None
    if on_insurer > 0:
        split_id = uuid.uuid4()

    if on_deductible > 0:
        e1 = Expense(
            case_id=case_id,
            supplier_name=payload.supplier_name,
            amount_ils_gross=on_deductible,
            service_description=payload.service_description,
            demand_received_date=payload.demand_received_date,
            expense_date=payload.expense_date,
            category=payload.category,
            payer=ExpensePayer.CLIENT_DEDUCTIBLE,
            attachment_url=payload.attachment_url,
            split_group_id=split_id,
            is_split_part=split_id is not None,
        )
        db.add(e1)
        created.append(e1)

    if on_insurer > 0:
        e2 = Expense(
            case_id=case_id,
            supplier_name=payload.supplier_name,
            amount_ils_gross=on_insurer,
            service_description=payload.service_description,
            demand_received_date=payload.demand_received_date,
            expense_date=payload.expense_date,
            category=payload.category,
            payer=ExpensePayer.INSURER,
            attachment_url=payload.attachment_url,
            split_group_id=split_id,
            is_split_part=True,
        )
        db.add(e2)
        created.append(e2)

        # Mark insurer started at the first split/insurer portion date.
        if not case.insurer_started:
            case.insurer_started = True
            case.insurer_start_date = payload.expense_date

    db.commit()
    for e in created:
        db.refresh(e)

    return created



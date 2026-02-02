"""Tests for excess_remaining (Excel P = M - J)."""

import datetime as dt
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.case import Case
from app.models.enums import CaseStatus, CaseType, ExpenseCategory, ExpensePayer
from app.models.expense import Expense
from app.models.retainer import RetainerPayment
from app.services.expenses import get_case_excess_remaining


def test_excess_remaining_no_payments_no_expenses(db: Session):
    """Excess = M when J=0."""
    c = Case(
        case_reference="test-excess-1",
        case_type=CaseType.COURT,
        status=CaseStatus.OPEN,
        open_date=dt.date(2025, 1, 15),
        retainer_anchor_date=dt.date(2025, 7, 1),
        branch_name=None,
        deductible_ils_gross=Decimal("10000.00"),
        insurer_started=False,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    assert get_case_excess_remaining(db, c) == Decimal("10000.00")


def test_excess_remaining_retainer_plus_other_expenses(db: Session):
    """P = M - (retainer_paid + other_expenses). M=10000, retainer=1000, other=500 -> P=8500."""
    c = Case(
        case_reference="test-excess-2",
        case_type=CaseType.COURT,
        status=CaseStatus.OPEN,
        open_date=dt.date(2025, 1, 15),
        retainer_anchor_date=dt.date(2025, 7, 1),
        branch_name=None,
        deductible_ils_gross=Decimal("10000.00"),
        insurer_started=False,
    )
    db.add(c)
    db.commit()
    db.refresh(c)

    db.add(RetainerPayment(case_id=c.id, payment_date=dt.date(2025, 8, 1), amount_ils_gross=Decimal("1000.00")))
    db.add(
        Expense(
            case_id=c.id,
            supplier_name="Expert",
            amount_ils_gross=Decimal("500.00"),
            service_description="Expert report",
            demand_received_date=dt.date(2025, 8, 1),
            expense_date=dt.date(2025, 8, 1),
            category=ExpenseCategory.EXPERT,
            payer=ExpensePayer.CLIENT_DEDUCTIBLE,
        )
    )
    db.commit()

    # J = 1000 + 500 = 1500, P = 10000 - 1500 = 8500
    assert get_case_excess_remaining(db, c) == Decimal("8500.00")


def test_excess_remaining_attorney_fee_excluded(db: Session):
    """ATTORNEY_FEE expenses do NOT reduce excess (Excel I = other expenses only)."""
    c = Case(
        case_reference="test-excess-3",
        case_type=CaseType.COURT,
        status=CaseStatus.OPEN,
        open_date=dt.date(2025, 1, 15),
        retainer_anchor_date=dt.date(2025, 7, 1),
        branch_name=None,
        deductible_ils_gross=Decimal("10000.00"),
        insurer_started=False,
    )
    db.add(c)
    db.commit()
    db.refresh(c)

    db.add(
        Expense(
            case_id=c.id,
            supplier_name="Attorney",
            amount_ils_gross=Decimal("5000.00"),
            service_description="Fee",
            demand_received_date=dt.date(2025, 8, 1),
            expense_date=dt.date(2025, 8, 1),
            category=ExpenseCategory.ATTORNEY_FEE,
            payer=ExpensePayer.CLIENT_DEDUCTIBLE,
        )
    )
    db.commit()

    # Attorney fee excluded from J, so P = 10000
    assert get_case_excess_remaining(db, c) == Decimal("10000.00")


def test_excess_remaining_never_negative(db: Session):
    """P clamped at 0."""
    c = Case(
        case_reference="test-excess-4",
        case_type=CaseType.COURT,
        status=CaseStatus.OPEN,
        open_date=dt.date(2025, 1, 15),
        retainer_anchor_date=dt.date(2025, 7, 1),
        branch_name=None,
        deductible_ils_gross=Decimal("1000.00"),
        insurer_started=False,
    )
    db.add(c)
    db.commit()
    db.refresh(c)

    db.add(RetainerPayment(case_id=c.id, payment_date=dt.date(2025, 8, 1), amount_ils_gross=Decimal("2000.00")))
    db.commit()

    assert get_case_excess_remaining(db, c) == Decimal("0.00")

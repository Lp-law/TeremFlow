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


def test_excess_with_snapshot(db: Session):
    """Case with snapshot: deductible=20000, snapshot=5000, other_expenses=3000 -> excess=12000."""
    c = Case(
        case_reference="test-excess-snapshot",
        case_type=CaseType.COURT,
        status=CaseStatus.OPEN,
        open_date=dt.date(2025, 1, 15),
        retainer_anchor_date=dt.date(2025, 7, 1),
        branch_name=None,
        deductible_ils_gross=Decimal("20000.00"),
        insurer_started=False,
        retainer_snapshot_ils_gross=Decimal("5000.00"),
    )
    db.add(c)
    db.commit()
    db.refresh(c)

    db.add(
        Expense(
            case_id=c.id,
            supplier_name="Expert",
            amount_ils_gross=Decimal("3000.00"),
            service_description="Report",
            demand_received_date=dt.date(2025, 8, 1),
            expense_date=dt.date(2025, 8, 1),
            category=ExpenseCategory.EXPERT,
            payer=ExpensePayer.CLIENT_DEDUCTIBLE,
        )
    )
    db.commit()

    # J = 3000 (other) + 5000 (snapshot) + 0 (no accruals) = 8000; P = 20000 - 8000 = 12000
    assert get_case_excess_remaining(db, c) == Decimal("12000.00")


def test_excess_without_snapshot_unchanged(db: Session):
    """Without snapshot, behavior unchanged: uses retainer_paid + other_expenses."""
    c = Case(
        case_reference="test-excess-no-snapshot",
        case_type=CaseType.COURT,
        status=CaseStatus.OPEN,
        open_date=dt.date(2025, 1, 15),
        retainer_anchor_date=dt.date(2025, 7, 1),
        branch_name=None,
        deductible_ils_gross=Decimal("10000.00"),
        insurer_started=False,
        retainer_snapshot_ils_gross=None,
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
            service_description="Report",
            demand_received_date=dt.date(2025, 8, 1),
            expense_date=dt.date(2025, 8, 1),
            category=ExpenseCategory.EXPERT,
            payer=ExpensePayer.CLIENT_DEDUCTIBLE,
        )
    )
    db.commit()

    # Same as before: J = 1000 + 500 = 1500, P = 8500
    assert get_case_excess_remaining(db, c) == Decimal("8500.00")

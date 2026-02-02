"""Tests for retainer roll-forward (ensure_all_cases_accruals_up_to_now)."""

import datetime as dt
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.case import Case
from app.models.enums import CaseStatus, CaseType
from app.models.retainer import RetainerAccrual
from app.services.alerts import run_daily_alerts
from app.services.retainer import ensure_all_cases_accruals_up_to_now


def _accrual_count(db: Session, case_id: int) -> int:
    return db.query(RetainerAccrual).filter(RetainerAccrual.case_id == case_id).count()


def _last_accrual_month(db: Session, case_id: int) -> dt.date | None:
    a = db.query(RetainerAccrual).filter(RetainerAccrual.case_id == case_id).order_by(RetainerAccrual.accrual_month.desc()).first()
    return a.accrual_month if a else None


def test_roll_forward_case_without_snapshot_creates_accruals_to_current_month(db: Session):
    """Case without snapshot created with old anchor -> after roll-forward has accruals up to current month."""
    today = dt.date.today()
    anchor = dt.date(2023, 7, 1)  # Start July 2023
    c = Case(
        case_reference="roll-fwd-1",
        case_type=CaseType.COURT,
        status=CaseStatus.OPEN,
        open_date=dt.date(2023, 1, 15),
        retainer_anchor_date=anchor,
        branch_name=None,
        deductible_ils_gross=Decimal("10000.00"),
        insurer_started=False,
        retainer_snapshot_ils_gross=None,
        expenses_snapshot_ils_gross=None,
    )
    db.add(c)
    db.commit()
    db.refresh(c)

    assert _accrual_count(db, c.id) == 0

    cases_scanned, accruals_added = ensure_all_cases_accruals_up_to_now(db)

    assert cases_scanned == 1
    assert accruals_added >= 1
    last = _last_accrual_month(db, c.id)
    assert last is not None
    # Last accrual month should be current month (first of month)
    expected_last = dt.date(today.year, today.month, 1)
    assert last == expected_last, f"expected last accrual {expected_last}, got {last}"


def test_roll_forward_case_with_snapshot_no_through_skipped(db: Session):
    """Case with retainer_snapshot but no through_month -> skipped (backward compat)."""
    c = Case(
        case_reference="roll-fwd-snapshot-no-through",
        case_type=CaseType.COURT,
        status=CaseStatus.OPEN,
        open_date=dt.date(2024, 1, 15),
        retainer_anchor_date=dt.date(2024, 7, 1),
        branch_name=None,
        deductible_ils_gross=Decimal("10000.00"),
        insurer_started=False,
        retainer_snapshot_ils_gross=Decimal("5000.00"),
        retainer_snapshot_through_month=None,
        expenses_snapshot_ils_gross=None,
    )
    db.add(c)
    db.commit()
    db.refresh(c)

    cases_scanned, accruals_added = ensure_all_cases_accruals_up_to_now(db)

    assert cases_scanned == 0
    assert accruals_added == 0
    assert _accrual_count(db, c.id) == 0


def test_roll_forward_case_with_snapshot_and_through_creates_accruals_from_next_month(db: Session):
    """Case with snapshot + through_month=2024-12 -> accruals from 2025-01 only."""
    today = dt.date.today()
    c = Case(
        case_reference="roll-fwd-snapshot-through",
        case_type=CaseType.COURT,
        status=CaseStatus.OPEN,
        open_date=dt.date(2023, 1, 15),
        retainer_anchor_date=dt.date(2023, 7, 1),
        branch_name=None,
        deductible_ils_gross=Decimal("10000.00"),
        insurer_started=False,
        retainer_snapshot_ils_gross=Decimal("85000.00"),
        retainer_snapshot_through_month=dt.date(2024, 12, 1),
        expenses_snapshot_ils_gross=None,
    )
    db.add(c)
    db.commit()
    db.refresh(c)

    assert _accrual_count(db, c.id) == 0

    cases_scanned, accruals_added = ensure_all_cases_accruals_up_to_now(db)

    assert cases_scanned == 1
    assert accruals_added >= 1
    accruals = db.query(RetainerAccrual).filter(RetainerAccrual.case_id == c.id).order_by(RetainerAccrual.accrual_month).all()
    first_month = accruals[0].accrual_month
    assert first_month == dt.date(2025, 1, 1), f"first accrual should be 2025-01, got {first_month}"
    last = _last_accrual_month(db, c.id)
    expected_last = dt.date(today.year, today.month, 1)
    assert last == expected_last


def test_roll_forward_idempotent(db: Session):
    """Double call does not add duplicate accruals."""
    c = Case(
        case_reference="roll-fwd-idem",
        case_type=CaseType.COURT,
        status=CaseStatus.OPEN,
        open_date=dt.date(2024, 1, 15),
        retainer_anchor_date=dt.date(2024, 7, 1),
        branch_name=None,
        deductible_ils_gross=Decimal("10000.00"),
        insurer_started=False,
        retainer_snapshot_ils_gross=None,
        expenses_snapshot_ils_gross=None,
    )
    db.add(c)
    db.commit()
    db.refresh(c)

    _, n1 = ensure_all_cases_accruals_up_to_now(db)
    count_after_first = _accrual_count(db, c.id)

    _, n2 = ensure_all_cases_accruals_up_to_now(db)
    count_after_second = _accrual_count(db, c.id)

    assert count_after_first == count_after_second
    assert n2 == 0


def test_run_daily_alerts_triggers_roll_forward(db: Session):
    """run_daily_alerts triggers roll-forward; case without snapshot gets accruals."""
    c = Case(
        case_reference="daily-alerts-roll",
        case_type=CaseType.COURT,
        status=CaseStatus.OPEN,
        open_date=dt.date(2024, 1, 15),
        retainer_anchor_date=dt.date(2024, 7, 1),
        branch_name=None,
        deductible_ils_gross=Decimal("10000.00"),
        insurer_started=False,
        retainer_snapshot_ils_gross=None,
        expenses_snapshot_ils_gross=None,
    )
    db.add(c)
    db.commit()
    db.refresh(c)

    assert _accrual_count(db, c.id) == 0

    result = run_daily_alerts(db)

    assert result.get("ok") is True
    assert _accrual_count(db, c.id) >= 1
    last = _last_accrual_month(db, c.id)
    assert last is not None
    today = dt.date.today()
    expected_last = dt.date(today.year, today.month, 1)
    assert last == expected_last


def test_roll_forward_idempotent_with_snapshot(db: Session):
    """Idempotency: double call with snapshot+through does not add duplicate accruals."""
    c = Case(
        case_reference="roll-fwd-idem-snapshot",
        case_type=CaseType.COURT,
        status=CaseStatus.OPEN,
        open_date=dt.date(2024, 1, 15),
        retainer_anchor_date=dt.date(2024, 7, 1),
        branch_name=None,
        deductible_ils_gross=Decimal("10000.00"),
        insurer_started=False,
        retainer_snapshot_ils_gross=Decimal("5000.00"),
        retainer_snapshot_through_month=dt.date(2024, 12, 1),
        expenses_snapshot_ils_gross=None,
    )
    db.add(c)
    db.commit()
    db.refresh(c)

    _, n1 = ensure_all_cases_accruals_up_to_now(db)
    count_after_first = _accrual_count(db, c.id)

    _, n2 = ensure_all_cases_accruals_up_to_now(db)
    count_after_second = _accrual_count(db, c.id)

    assert count_after_first == count_after_second
    assert n2 == 0

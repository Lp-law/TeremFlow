"""Regression tests: retainer ledger includes manual payments and totals."""

import datetime as dt
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

pytest.importorskip("tenacity")

from app.models.case import Case
from app.models.enums import CaseStatus, CaseType
from app.models.retainer import RetainerPayment
from app.services.cases import update_case_retainer_dates
from app.services.retainer import build_retainer_ledger
from app.services.unified import charged_months_count, get_effective_end_date


def _minimal_case(db: Session, **kwargs) -> Case:
    defaults = {
        "case_reference": "ledger-test",
        "case_name": "Ledger Test",
        "case_type": CaseType.COURT,
        "status": CaseStatus.OPEN,
        "open_date": dt.date(2024, 1, 1),
        "retainer_anchor_date": dt.date(2024, 7, 1),
        "deductible_ils_gross": Decimal("10000.00"),
        "insurer_started": False,
    }
    defaults.update(kwargs)
    c = Case(**defaults)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def test_retainer_ledger_includes_manual_payments_and_totals(db: Session):
    """Ledger has one row per month; payments in same month are aggregated into that month's paid_ils."""
    c = _minimal_case(db)
    db.add(
        RetainerPayment(
            case_id=c.id,
            payment_date=dt.date(2024, 3, 1),
            amount_ils_gross=Decimal("1105.65"),
            note="manual",
        )
    )
    db.add(
        RetainerPayment(
            case_id=c.id,
            payment_date=dt.date(2024, 4, 1),
            amount_ils_gross=Decimal("1115.10"),
            note=None,
        )
    )
    db.commit()

    data = build_retainer_ledger(db, case_id=c.id)
    assert data is not None
    assert "rows" in data
    months = [r["month"] for r in data["rows"]]
    assert len(months) == len(set(months)), "unique months only"
    march_rows = [r for r in data["rows"] if r["month"] == "2024-03"]
    april_rows = [r for r in data["rows"] if r["month"] == "2024-04"]
    assert len(march_rows) == 1 and march_rows[0]["paid_ils"] == Decimal("1105.65")
    assert len(april_rows) == 1 and april_rows[0]["paid_ils"] == Decimal("1115.10")
    assert data["retainer_paid_total_ils_gross"] == Decimal("2220.75")
    assert "total_accrued_ils" in data


def test_retainer_end_date_persists_and_caps_effective_end(db: Session):
    """PATCH retainer dates with retainer_end_date saves to DB; charged_months_count respects it."""
    c = _minimal_case(db)
    case_id = c.id
    update_case_retainer_dates(
        db,
        case_id=case_id,
        retainer_end_date=dt.date(2024, 9, 15),
        retainer_end_date_sent=True,
    )
    c = db.query(Case).filter(Case.id == case_id).first()
    assert c is not None
    assert getattr(c, "retainer_end_date", None) == dt.date(2024, 9, 15)
    assert get_effective_end_date(c) == dt.date(2024, 9, 15)
    assert charged_months_count(c) == 3  # Jul, Aug, Sep


def test_charged_months_count_anchor_jan_end_june_six_months(db: Session):
    """anchor=2024-01-01, end=2024-06-30 => 6 months (Jan through Jun inclusive)."""
    c = _minimal_case(db, retainer_anchor_date=dt.date(2024, 1, 1))
    db.refresh(c)
    setattr(c, "retainer_end_date", dt.date(2024, 6, 30))
    assert charged_months_count(c) == 6


def test_charged_months_anchor_jan_end_feb_two_months(db: Session):
    """anchor=2024-01-01, end=2024-02-01 => 2 months (Jan, Feb)."""
    c = _minimal_case(db, retainer_anchor_date=dt.date(2024, 1, 1))
    db.refresh(c)
    setattr(c, "retainer_end_date", dt.date(2024, 2, 1))
    assert charged_months_count(c) == 2


def test_ledger_february_payments_in_feb_paid_ils(db: Session):
    """Payments in February aggregate into February row only; no duplicate month row."""
    c = _minimal_case(db)
    db.add(RetainerPayment(case_id=c.id, payment_date=dt.date(2026, 2, 1), amount_ils_gross=Decimal("500"), note=None))
    db.add(RetainerPayment(case_id=c.id, payment_date=dt.date(2026, 2, 15), amount_ils_gross=Decimal("300"), note=None))
    db.commit()
    data = build_retainer_ledger(db, case_id=c.id)
    assert data is not None
    feb_rows = [r for r in data["rows"] if r["month"] == "2026-02"]
    assert len(feb_rows) == 1
    assert feb_rows[0]["paid_ils"] == Decimal("800.00")

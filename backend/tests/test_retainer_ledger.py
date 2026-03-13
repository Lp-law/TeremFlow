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
from app.services.retainer import get_total_retainer_theoretical_ils
from app.services.retainer import retainer_gross_for_month
from app.services.unified import (
    charged_months_count,
    get_effective_end_date,
    retainer_charged_to_date_ils,
)


def test_retainer_charged_includes_snapshot(db: Session):
    """סה״כ ריטיינר ששולם (כולל ידני) = תשלומים + snapshot (ריטיינר היסטורי מייבוא)."""
    c = _minimal_case(db, retainer_anchor_date=dt.date(2025, 7, 1))
    c.retainer_snapshot_ils_gross = Decimal("5900.00")
    c.retainer_snapshot_through_month = dt.date(2025, 12, 1)
    db.commit()
    db.refresh(c)
    charged = retainer_charged_to_date_ils(db, c)
    assert charged == Decimal("5900.00")
    data = build_retainer_ledger(db, case_id=c.id)
    assert data is not None
    assert data["retainer_paid_total_ils_gross"] == Decimal("5900.00")


def test_retainer_charged_zero_when_no_payments_and_no_period_dates(db: Session):
    """When no period dates (current/legacy) and no payments, retainer_charged_to_date_ils = 0."""
    c = _minimal_case(db, retainer_anchor_date=dt.date(2024, 7, 1))
    update_case_retainer_dates(
        db, case_id=c.id, retainer_end_date=dt.date(2024, 9, 30), retainer_end_date_sent=True
    )
    db.refresh(c)
    # Do not set retainer_legacy_start_date / retainer_current_start_date so charged = paid+snapshot = 0
    charged = retainer_charged_to_date_ils(db, c)
    assert charged == Decimal("0.00")


def test_retainer_charged_theoretical_when_period_dates_set_and_no_payments(db: Session):
    """When period dates (legacy) are set, retainer_charged_to_date_ils = theoretical even with no payments."""
    c = _minimal_case(db, retainer_anchor_date=dt.date(2024, 7, 1))
    setattr(c, "retainer_legacy_start_date", dt.date(2024, 3, 1))
    setattr(c, "retainer_legacy_end_date", dt.date(2024, 3, 31))
    db.commit()
    db.refresh(c)
    charged = retainer_charged_to_date_ils(db, c)
    total_theoretical, _, _ = get_total_retainer_theoretical_ils(db, c)
    assert charged == total_theoretical
    assert total_theoretical > Decimal("0")


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
    """Ledger rows follow typed period dates; payments in those months show in paid_ils."""
    c = _minimal_case(db)
    setattr(c, "retainer_legacy_start_date", dt.date(2024, 3, 1))
    setattr(c, "retainer_legacy_end_date", dt.date(2024, 4, 30))
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


def test_clearing_end_date_works(db: Session):
    """PATCH retainer dates with retainer_end_date=null clears it; effective_end becomes today (or frozen)."""
    c = _minimal_case(db)
    update_case_retainer_dates(
        db, case_id=c.id, retainer_end_date=dt.date(2024, 9, 30), retainer_end_date_sent=True
    )
    db.refresh(c)
    assert getattr(c, "retainer_end_date", None) == dt.date(2024, 9, 30)
    update_case_retainer_dates(db, case_id=c.id, retainer_end_date=None, retainer_end_date_sent=True)
    c = db.query(Case).filter(Case.id == c.id).first()
    assert c is not None
    assert getattr(c, "retainer_end_date", None) is None


def test_patch_period_end_dates_persist_and_ledger_reflects(db: Session):
    """PATCH with retainer_current_end_date and retainer_legacy_end_date persists; GET case returns them; ledger months reflect end dates."""
    c = _minimal_case(db, retainer_anchor_date=dt.date(2024, 1, 1))
    update_case_retainer_dates(
        db,
        case_id=c.id,
        retainer_current_start_date=dt.date(2024, 1, 1),
        retainer_current_end_date=dt.date(2025, 6, 30),
        retainer_legacy_start_date=dt.date(2023, 6, 1),
        retainer_legacy_end_date=dt.date(2023, 12, 31),
        current_start_sent=True,
        current_end_sent=True,
        legacy_start_sent=True,
        legacy_end_sent=True,
    )
    c = db.query(Case).filter(Case.id == c.id).first()
    assert c is not None
    assert getattr(c, "retainer_current_start_date", None) == dt.date(2024, 1, 1)
    assert getattr(c, "retainer_current_end_date", None) == dt.date(2025, 6, 30)
    assert getattr(c, "retainer_end_date", None) == dt.date(2025, 6, 30)
    assert getattr(c, "retainer_legacy_start_date", None) == dt.date(2023, 6, 1)
    assert getattr(c, "retainer_legacy_end_date", None) == dt.date(2023, 12, 31)
    data = build_retainer_ledger(db, case_id=c.id)
    assert data is not None
    month_strs = sorted([r["month"] for r in data["rows"]])
    assert "2023-06" in month_strs
    assert "2023-12" in month_strs
    assert "2024-01" in month_strs
    assert "2025-06" in month_strs
    assert data["charged_months_count"] == len(month_strs)


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


def test_ledger_paid_total_equals_overview_retainer_charged(db: Session):
    """retainer_charged_to_date_ils = סה״כ ריטיינר ששולם (כולל ידני) — must match ledger retainer_paid_total_ils_gross."""
    c = _minimal_case(db, retainer_anchor_date=dt.date(2026, 1, 1))
    db.add(RetainerPayment(case_id=c.id, payment_date=dt.date(2024, 1, 1), amount_ils_gross=Decimal("1105.65"), note="LEGACY"))
    db.add(RetainerPayment(case_id=c.id, payment_date=dt.date(2026, 2, 1), amount_ils_gross=Decimal("1115.10"), note=None))
    db.commit()
    db.refresh(c)
    data = build_retainer_ledger(db, case_id=c.id)
    assert data is not None
    paid_ledger = data.get("retainer_paid_total_ils_gross")
    assert paid_ledger is not None
    charged = retainer_charged_to_date_ils(db, c)
    assert charged == paid_ledger
    assert charged == Decimal("2220.75")


def test_retainer_charged_equals_sum_of_payments(db: Session):
    """retainer_charged_to_date_ils = סה״כ ריטיינר ששולם (כולל ידני) = sum of all retainer payments."""
    c = _minimal_case(db, retainer_anchor_date=dt.date(2024, 7, 1))
    update_case_retainer_dates(
        db, case_id=c.id, retainer_end_date=dt.date(2024, 9, 30), retainer_end_date_sent=True
    )
    db.refresh(c)
    for month in (1, 2):
        db.add(
            RetainerPayment(
                case_id=c.id,
                payment_date=dt.date(2024, month, 1),
                amount_ils_gross=Decimal("1105.65"),
                note="LEGACY: past",
            )
        )
    db.commit()
    db.refresh(c)
    charged = retainer_charged_to_date_ils(db, c)
    assert charged == Decimal("2211.30")  # 2 × 1105.65


def test_retainer_charged_equals_paid_total_eight_payments(db: Session):
    """retainer_charged_to_date_ils = sum of payments. Add 8 payments → charged = 8 × 1105.65."""
    c = _minimal_case(db, retainer_anchor_date=dt.date(2024, 7, 1))
    update_case_retainer_dates(
        db, case_id=c.id, retainer_end_date=dt.date(2024, 9, 30), retainer_end_date_sent=True
    )
    db.refresh(c)
    setattr(c, "retainer_legacy_start_date", dt.date(2024, 1, 1))
    setattr(c, "retainer_legacy_end_date", dt.date(2024, 5, 31))
    db.commit()
    db.refresh(c)
    monthly_2024 = retainer_gross_for_month(dt.date(2024, 7, 1))  # 1105.65
    for m in (1, 2, 3, 4, 5, 7, 8, 9):
        db.add(RetainerPayment(case_id=c.id, payment_date=dt.date(2024, m, 1), amount_ils_gross=monthly_2024, note="pay" if m >= 7 else "LEGACY"))
    db.commit()
    db.refresh(c)
    charged = retainer_charged_to_date_ils(db, c)
    assert charged == 8 * monthly_2024

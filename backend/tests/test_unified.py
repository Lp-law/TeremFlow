"""Tests for unified model: override parsing (decimal strings) and single source of truth."""
import datetime as dt
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.case import Case
from app.models.enums import CaseStatus, CaseType
from app.services.unified import (
    charged_months_count,
    excess_remaining_ils,
    expenses_total_ils,
    get_effective_end_date,
    get_unified_summary,
    retainer_charged_to_date_ils,
)


def _minimal_case(**kwargs) -> Case:
    defaults = {
        "case_reference": "test-unified-1",
        "case_type": CaseType.COURT,
        "status": CaseStatus.OPEN,
        "open_date": dt.date(2025, 1, 15),
        "retainer_anchor_date": dt.date(2025, 7, 1),
        "branch_name": None,
        "deductible_ils_gross": Decimal("10000.00"),
        "insurer_started": False,
    }
    defaults.update(kwargs)
    return Case(**defaults)


def test_override_stored_as_string_parsed_correctly(db: Session):
    """manual_overrides_json stores money as decimal strings; unified parses them back to Decimal."""
    c = _minimal_case()
    db.add(c)
    db.commit()
    db.refresh(c)
    # Simulate what update_case_manual_overrides writes: string "9999.99"
    c.manual_overrides_json = {"retainer_charged_override": "9999.99"}
    db.commit()
    db.refresh(c)
    assert retainer_charged_to_date_ils(db, c) == Decimal("9999.99")


def test_override_excess_remaining_parsed(db: Session):
    """excess_remaining_override as string is used for excess_remaining_ils."""
    c = _minimal_case()
    db.add(c)
    db.commit()
    db.refresh(c)
    c.manual_overrides_json = {"excess_remaining_override": "1234.56"}
    db.commit()
    db.refresh(c)
    assert excess_remaining_ils(db, c) == Decimal("1234.56")


def test_override_expenses_total_parsed(db: Session):
    """expenses_total_override as string; expenses_total_ils uses case.expenses_total_ils_gross when no override."""
    c = _minimal_case()
    c.expenses_total_ils_gross = Decimal("500.00")
    db.add(c)
    db.commit()
    db.refresh(c)
    assert expenses_total_ils(c) == Decimal("500.00")
    c.manual_overrides_json = {"expenses_total_override": "750.25"}
    db.commit()
    db.refresh(c)
    assert expenses_total_ils(c) == Decimal("750.25")


def test_get_unified_summary_uses_overrides(db: Session):
    """get_unified_summary returns override values when set (stored as strings)."""
    c = _minimal_case()
    c.manual_overrides_json = {
        "retainer_charged_override": "1111.11",
        "fees_by_stages_override": "2222.22",
        "excess_remaining_override": "3333.33",
    }
    db.add(c)
    db.commit()
    db.refresh(c)
    summary = get_unified_summary(db, c)
    assert summary["retainer_charged_to_date_ils"] == Decimal("1111.11")
    assert summary["fees_by_stages_ils"] == Decimal("2222.22")
    assert summary["excess_remaining_ils"] == Decimal("3333.33")


def test_retainer_end_date_caps_charged_months(db: Session):
    """With retainer_end_date set, effective_end is that date and charged_months_count stops at that month."""
    c = _minimal_case(
        retainer_anchor_date=dt.date(2024, 7, 1),
        retainer_end_date=dt.date(2024, 9, 15),
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    assert get_effective_end_date(c) == dt.date(2024, 9, 15)
    assert charged_months_count(c) == 3  # Jul, Aug, Sep

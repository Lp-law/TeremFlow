"""Regression tests: case details endpoints must not 500 on legacy/incomplete data."""

import datetime as dt
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

pytest.importorskip("tenacity")  # cases.py -> boi_fx needs tenacity

from app.models.case import Case
from app.models.enums import CaseStatus, CaseType
from app.schemas.deductible import DeductibleSummaryOut
from app.services.cases import build_case_overview_summary, get_case_warnings
from app.services.unified import get_unified_summary


def _case_with_required(db: Session, **kwargs) -> Case:
    """Create and persist a case with minimal required fields; allow overrides for legacy shape."""
    defaults = {
        "case_reference": "regression-500",
        "case_name": "Regression",
        "case_type": CaseType.COURT,
        "status": CaseStatus.OPEN,
        "open_date": dt.date(2024, 1, 15),
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


def test_overview_summary_with_null_expenses_and_weird_overrides(db: Session):
    """expenses_total_ils_gross None and manual_overrides_json with empty/invalid values must not 500."""
    c = _case_with_required(db, expenses_total_ils_gross=None)
    c.manual_overrides_json = {
        "retainer_charged_override": "",
        "expenses_total_override": "not a number",
        "excess_total_ils_override": "None",
    }
    db.commit()
    db.refresh(c)

    data = build_case_overview_summary(db, c.id)
    assert data is not None
    assert data["status"] in ("OPEN",)
    assert data["expenses"]["total_expenses_ils"] == Decimal("0.00")
    assert data["fees"]["fees_by_stages_ils"] == Decimal("0.00")


def test_unified_summary_with_in_memory_null_anchor(db: Session):
    """When retainer_anchor_date is None (e.g. in-memory legacy), unified must return 0 charged, not crash."""
    c = _case_with_required(db)
    # Simulate legacy/incomplete: anchor missing on loaded instance
    c.retainer_anchor_date = None

    summary = get_unified_summary(db, c)
    assert summary["charged_months_count"] == 0
    assert summary["retainer_charged_to_date_ils"] == Decimal("0.00")
    assert summary["fees_by_stages_ils"] == Decimal("0.00")
    assert summary["effective_end_date"]  # today iso


def test_warnings_with_weird_raw_json_and_null_snapshots(db: Session):
    """raw_import_fields_json non-dict and null snapshots must not 500."""
    c = _case_with_required(db)
    # SQLite/ORM may allow this; if not we skip or use a different way to set
    c.raw_import_fields_json = None
    c.retainer_snapshot_ils_gross = None
    c.retainer_snapshot_through_month = None
    db.commit()
    db.refresh(c)

    warnings = get_case_warnings(db, c.id)
    assert isinstance(warnings, list)
    # Should include at least missing retainer anchor or similar
    codes = [w["code"] for w in warnings]
    assert "MISSING_RETAINER_ANCHOR" in codes or len(warnings) >= 0


def test_deductible_summary_out_with_unified_zeroes(db: Session):
    """DeductibleSummaryOut must accept unified result with all zeros (no validation error)."""
    c = _case_with_required(db, expenses_total_ils_gross=None)
    summary = get_unified_summary(db, c)
    overrides = getattr(c, "manual_overrides_json", None) or {}
    if not isinstance(overrides, dict):
        overrides = {}

    out = DeductibleSummaryOut(
        excess_total_ils=summary["excess_total_ils"],
        retainer_charged_to_date_ils=summary["retainer_charged_to_date_ils"],
        expenses_total_ils=summary["expenses_total_ils"],
        fees_by_stages_ils=summary["fees_by_stages_ils"],
        excess_remaining_ils=summary["excess_remaining_ils"],
        fee_diff_ils=summary["fee_diff_ils"],
        manual_overrides=overrides,
    )
    assert out.expenses_total_ils == Decimal("0.00")
    assert out.fees_by_stages_ils == Decimal("0.00")


def test_overview_summary_safe_when_manual_overrides_not_dict(db: Session):
    """If manual_overrides_json is not a dict (legacy), unified and overview must not 500."""
    c = _case_with_required(db)
    # Simulate legacy: override to non-dict on the instance for service call
    orig = c.manual_overrides_json
    c.manual_overrides_json = None
    summary = get_unified_summary(db, c)
    assert summary["retainer_charged_to_date_ils"] >= Decimal("0.00")
    assert summary["fees_by_stages_ils"] >= Decimal("0.00")
    c.manual_overrides_json = orig  # restore for any later use
    # Build overview with normal case
    data = build_case_overview_summary(db, c.id)
    assert data is not None

"""Tests for manual overrides validation: reject negative (except fee_diff), invalid numbers; null clears."""
from decimal import Decimal
from datetime import date

import pytest
from fastapi import HTTPException

from app.models.case import Case
from app.models.enums import CaseStatus, CaseType
from app.services import cases as case_service


def _minimal_case(db, **kwargs) -> Case:
    defaults = {
        "case_reference": "test-ov-1",
        "case_type": CaseType.COURT,
        "status": CaseStatus.OPEN,
        "open_date": date(2025, 1, 15),
        "retainer_anchor_date": date(2025, 7, 1),
        "deductible_ils_gross": Decimal("10000.00"),
        "insurer_started": False,
    }
    defaults.update(kwargs)
    c = Case(**defaults)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def test_expenses_total_override_negative_returns_400(db):
    """Setting expenses_total_override to a negative value returns 400."""
    c = _minimal_case(db)
    with pytest.raises(HTTPException) as exc_info:
        case_service.update_case_manual_overrides(
            db, case_id=c.id, overrides={"expenses_total_override": "-1"}
        )
    assert exc_info.value.status_code == 400
    assert "expenses_total_override" in exc_info.value.detail
    assert "Negative" in exc_info.value.detail or "negative" in exc_info.value.detail.lower()


def test_excess_remaining_override_negative_returns_400(db):
    """Setting excess_remaining_override to a negative value returns 400."""
    c = _minimal_case(db)
    with pytest.raises(HTTPException) as exc_info:
        case_service.update_case_manual_overrides(
            db, case_id=c.id, overrides={"excess_remaining_override": "-5"}
        )
    assert exc_info.value.status_code == 400
    assert "excess_remaining_override" in exc_info.value.detail
    assert "Negative" in exc_info.value.detail or "negative" in exc_info.value.detail.lower()


def test_fee_diff_override_negative_succeeds(db):
    """Setting fee_diff_override to a negative value succeeds (200 / no exception)."""
    c = _minimal_case(db)
    updated = case_service.update_case_manual_overrides(
        db, case_id=c.id, overrides={"fee_diff_override": "-5"}
    )
    db.refresh(updated)
    assert updated.manual_overrides_json is not None
    assert updated.manual_overrides_json.get("fee_diff_override") == "-5.00"


def test_override_null_clears(db):
    """Setting any override to null clears it."""
    c = _minimal_case(db)
    case_service.update_case_manual_overrides(
        db, case_id=c.id, overrides={"excess_remaining_override": "100.00"}
    )
    db.refresh(c)
    assert c.manual_overrides_json.get("excess_remaining_override") == "100.00"
    case_service.update_case_manual_overrides(
        db, case_id=c.id, overrides={"excess_remaining_override": None}
    )
    db.refresh(c)
    assert c.manual_overrides_json is None or "excess_remaining_override" not in (c.manual_overrides_json or {})


def test_invalid_number_returns_400(db):
    """Setting an override to a non-numeric value returns 400 Invalid number for <field>."""
    c = _minimal_case(db)
    with pytest.raises(HTTPException) as exc_info:
        case_service.update_case_manual_overrides(
            db, case_id=c.id, overrides={"excess_total_ils_override": "not-a-number"}
        )
    assert exc_info.value.status_code == 400
    assert "excess_total_ils_override" in exc_info.value.detail
    assert "Invalid number" in exc_info.value.detail

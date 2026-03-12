"""Tests for case notes (PATCH notes, GET returns)."""
import datetime as dt
from decimal import Decimal

import pytest

from app.models.case import Case
from app.models.enums import CaseStatus, CaseType
from app.services import cases as case_service


@pytest.fixture
def a_case(db):
    c = Case(
        case_reference="notes-test-1",
        case_name="Notes test",
        case_type=CaseType.COURT,
        status=CaseStatus.OPEN,
        open_date=dt.date(2024, 1, 1),
        retainer_anchor_date=dt.date(2024, 1, 1),
        deductible_ils_gross=Decimal("5000.00"),
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def test_patch_notes_persists_and_returned_in_get(db, a_case):
    """PATCH notes persists; GET case returns case_notes."""
    case_service.update_case_notes(db, case_id=a_case.id, case_notes="הערה לבדיקה")
    db.refresh(a_case)
    out = case_service.to_case_out(db, a_case)
    assert out.get("case_notes") == "הערה לבדיקה"

    case_service.update_case_notes(db, case_id=a_case.id, case_notes="")
    db.refresh(a_case)
    out2 = case_service.to_case_out(db, a_case)
    assert out2.get("case_notes") == ""

"""Tests for Excel update-import (import_cases_from_excel_update)."""

from datetime import date
from decimal import Decimal
from io import BytesIO

import pytest
from openpyxl import Workbook

from app.models.case import Case
from app.models.enums import CaseStatus, CaseType
from app.services.cases import create_case
from app.services.import_excel import import_cases_from_excel_update


def _xlsx_bytes(header_row: list, data_rows: list[list]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.append(header_row)
    for row in data_rows:
        ws.append(row)
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


@pytest.fixture
def existing_case(db):
    """Create one case for update tests."""
    class Payload:
        case_reference = "REF-UPDATE-1"
        case_name = "Original Name"
        case_type = CaseType.COURT
        open_date = date(2024, 1, 15)
        deductible_ils_gross = Decimal("5000.00")
        branch_name = "Original Branch"

    c = create_case(db, Payload())
    return c


def test_update_existing_case_name_branch_deductible(db, existing_case):
    """Update case_name, branch_name, deductible_ils_gross via excel-update."""
    header = ["case_reference", "case_name", "branch_name", "deductible_ils_gross"]
    rows = [["REF-UPDATE-1", "Updated Name", "Updated Branch", 6000]]
    data = _xlsx_bytes(header, rows)
    result = import_cases_from_excel_update(db, data)
    assert result["updated"] == 1
    assert result["created"] == 0
    assert result["error_count"] == 0

    db.refresh(existing_case)
    assert existing_case.case_name == "Updated Name"
    assert existing_case.branch_name == "Updated Branch"
    assert existing_case.deductible_ils_gross == Decimal("6000.00")


def test_update_blank_does_not_overwrite(db, existing_case):
    """Empty cells in update file do not overwrite existing values."""
    header = ["case_reference", "case_name", "branch_name"]
    # Update branch_name; leave case_name empty -> should NOT clear case_name
    rows = [["REF-UPDATE-1", "", "New Branch Only"]]
    data = _xlsx_bytes(header, rows)
    result = import_cases_from_excel_update(db, data, overwrite_blanks=False)
    assert result["updated"] == 1

    db.refresh(existing_case)
    assert existing_case.branch_name == "New Branch Only"
    # case_name was blank in row; without overwrite_blanks we don't clear
    assert existing_case.case_name == "Original Name"


def test_update_case_not_found_row_error(db):
    """When case_reference does not exist, row is reported as error (no create)."""
    header = ["case_reference", "case_name"]
    rows = [["NONEXISTENT-REF", "Some Name"]]
    data = _xlsx_bytes(header, rows)
    result = import_cases_from_excel_update(db, data)
    assert result["updated"] == 0
    assert result["error_count"] == 1
    assert any(e["error"] == "Case not found for update" for e in result["errors"])


def test_update_invalid_value_fails_only_that_row(db, existing_case):
    """Invalid value (e.g. bad case_type) fails only that row, reported in errors."""
    header = ["case_reference", "case_type"]
    rows = [
        ["REF-UPDATE-1", "INVALID_TYPE"],
    ]
    data = _xlsx_bytes(header, rows)
    result = import_cases_from_excel_update(db, data)
    assert result["updated"] == 0
    assert result["error_count"] == 1
    assert "Invalid case_type" in result["errors"][0]["error"]

    db.refresh(existing_case)
    assert existing_case.case_type == CaseType.COURT


def test_update_legacy_fee_text(db, existing_case):
    """legacy_fee_text can be updated from Excel."""
    header = ["case_reference", "legacy_fee_text"]
    rows = [["REF-UPDATE-1", "פירוט חיוב מעודכן"]]
    data = _xlsx_bytes(header, rows)
    result = import_cases_from_excel_update(db, data)
    assert result["updated"] == 1

    db.refresh(existing_case)
    assert existing_case.legacy_fee_text == "פירוט חיוב מעודכן"


def test_update_unknown_column_stored_in_raw_import_fields(db, existing_case):
    """Excel columns not mapped to operational fields end up in raw_import_fields_json."""
    header = ["case_reference", "retainer_paid_total_ils", "case_status_text"]
    rows = [["REF-UPDATE-1", 1000, "active"]]
    data = _xlsx_bytes(header, rows)
    result = import_cases_from_excel_update(db, data)
    assert result["updated"] == 1
    assert result["error_count"] == 0

    db.refresh(existing_case)
    raw = existing_case.raw_import_fields_json or {}
    assert "retainer_paid_total_ils" in raw
    assert raw["retainer_paid_total_ils"] in (1000, 1000.0)
    assert raw.get("case_status_text") == "active"


def test_update_operational_and_raw_together(db, existing_case):
    """Operational fields update Case; unknown columns go to raw. No billing change."""
    header = ["case_reference", "case_name", "deductible_balance_ils"]
    rows = [["REF-UPDATE-1", "Name From Excel", 3000]]
    data = _xlsx_bytes(header, rows)
    result = import_cases_from_excel_update(db, data)
    assert result["updated"] == 1

    db.refresh(existing_case)
    assert existing_case.case_name == "Name From Excel"
    raw = existing_case.raw_import_fields_json or {}
    assert raw.get("deductible_balance_ils") in (3000, 3000.0)

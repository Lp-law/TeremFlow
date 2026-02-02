from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from io import BytesIO

from openpyxl import load_workbook
from sqlalchemy.orm import Session

from app.models.enums import CaseType
from app.services.cases import create_case


def _norm(s: Any) -> str:
    return str(s).strip().replace("\u200f", "").replace("\u200e", "").lower()


KNOWN_COLUMNS: dict[str, str] = {
    # case reference
    "case": "case_reference",
    "case_reference": "case_reference",
    "תיק": "case_reference",
    "מספר תיק": "case_reference",
    # case name (plaintiff / display name)
    "case_name": "case_name",
    "שם תיק": "case_name",
    # type
    "case_type": "case_type",
    "סוג תיק": "case_type",
    "סוג": "case_type",
    # open date
    "open_date": "open_date",
    "תאריך פתיחה": "open_date",
    "פתיחה": "open_date",
    # deductible
    "deductible_usd": "deductible_usd",
    "אקסס usd": "deductible_usd",
    "excess usd": "deductible_usd",
    "deductible_ils": "deductible_ils_gross",
    "deductible_ils_gross": "deductible_ils_gross",
    "אקסס שח": "deductible_ils_gross",
    "אקסס ש\"ח": "deductible_ils_gross",
    # branch (Excel column B)
    "branch": "branch_name",
    "branch_name": "branch_name",
    "סניף": "branch_name",
    # retainer anchor (Excel column C)
    "retainer_anchor": "retainer_anchor_date",
    "retainer_anchor_date": "retainer_anchor_date",
    "תאריך עוגן": "retainer_anchor_date",
    # Excel H: total retainer paid to date (snapshot)
    "h": "retainer_snapshot_ils_gross",
    "retainer_snapshot": "retainer_snapshot_ils_gross",
    "retainer_snapshot_ils_gross": "retainer_snapshot_ils_gross",
    "ריטיינר שולם": "retainer_snapshot_ils_gross",
    "total retainer": "retainer_snapshot_ils_gross",
    # Excel I: total non-attorney expenses (snapshot)
    "i": "expenses_snapshot_ils_gross",
    "expenses_snapshot": "expenses_snapshot_ils_gross",
    "expenses_snapshot_ils_gross": "expenses_snapshot_ils_gross",
    "הוצאות אחרות": "expenses_snapshot_ils_gross",
    "other expenses": "expenses_snapshot_ils_gross",
}


def _parse_date(v: Any) -> dt.date:
    if isinstance(v, dt.datetime):
        return v.date()
    if isinstance(v, dt.date):
        return v
    # try ISO
    try:
        return dt.date.fromisoformat(str(v))
    except Exception:
        raise ValueError(f"Invalid date: {v}")


def _parse_decimal_ge_zero(v: Any, field_name: str) -> Decimal | None:
    """Parse decimal >= 0. Returns None for empty/None."""
    if v is None or v == "":
        return None
    try:
        d = Decimal(str(v))
        if d < 0:
            raise ValueError(f"{field_name} must be >= 0")
        return d
    except Exception as e:
        raise ValueError(f"Invalid {field_name}: {v}") from e


def _parse_case_type(v: Any) -> CaseType:
    s = _norm(v)
    mapping = {
        "court": CaseType.COURT,
        "תיק ביהמ\"ש": CaseType.COURT,
        "תיק בית המשפט": CaseType.COURT,
        "ביהמ\"ש": CaseType.COURT,
        "demand_letter": CaseType.DEMAND_LETTER,
        "מכתב דרישה": CaseType.DEMAND_LETTER,
        "small_claims": CaseType.SMALL_CLAIMS,
        "תביעות קטנות": CaseType.SMALL_CLAIMS,
    }
    if s in mapping:
        return mapping[s]
    # try enum literal
    try:
        return CaseType(str(v))
    except Exception:
        raise ValueError(f"Invalid case_type: {v}")


def import_cases_from_excel(db: Session, file_bytes: bytes) -> dict:
    wb = load_workbook(filename=BytesIO(file_bytes), data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        raise HTTPException(status_code=400, detail="Empty Excel file")

    header = rows[0]
    col_map: dict[int, str] = {}
    for idx, name in enumerate(header):
        key = _norm(name)
        if key in KNOWN_COLUMNS:
            col_map[idx] = KNOWN_COLUMNS[key]
        else:
            # try stripping spaces (Hebrew headers can be inconsistent)
            key2 = key.replace(" ", "")
            if key2 in KNOWN_COLUMNS:
                col_map[idx] = KNOWN_COLUMNS[key2]

    required = {"case_reference", "case_type", "open_date"}
    if not required.issubset(set(col_map.values())):
        raise HTTPException(status_code=400, detail=f"Missing required columns. Need at least: {sorted(required)}")

    created = 0
    skipped_empty_rows = 0
    errors: list[dict[str, Any]] = []

    for r_i, row in enumerate(rows[1:], start=2):
        if not any(row):
            skipped_empty_rows += 1
            continue
        data: dict[str, Any] = {}
        for idx, field in col_map.items():
            data[field] = row[idx] if idx < len(row) else None
        try:
            payload = type("Obj", (), {})()
            payload.case_reference = str(data["case_reference"] or "").strip()
            if not payload.case_reference:
                raise ValueError("Missing case_reference")
            payload.case_name = (str(data.get("case_name") or "").strip() or None)
            payload.case_type = _parse_case_type(data["case_type"])
            payload.open_date = _parse_date(data["open_date"])
            payload.deductible_usd = Decimal(str(data["deductible_usd"])) if data.get("deductible_usd") not in (None, "") else None
            payload.deductible_ils_gross = (
                Decimal(str(data["deductible_ils_gross"])) if data.get("deductible_ils_gross") not in (None, "") else None
            )
            payload.branch_name = (str(data.get("branch_name") or "").strip() or None)
            payload.retainer_anchor_date = _parse_date(data["retainer_anchor_date"]) if data.get("retainer_anchor_date") not in (None, "") else None
            # Excel H, I: snapshots (>= 0)
            payload.retainer_snapshot_ils_gross = _parse_decimal_ge_zero(data.get("retainer_snapshot_ils_gross"), "retainer_snapshot_ils_gross")
            payload.expenses_snapshot_ils_gross = _parse_decimal_ge_zero(data.get("expenses_snapshot_ils_gross"), "expenses_snapshot_ils_gross")
            create_case(db, payload)
            created += 1
        except HTTPException as e:
            # Preserve meaningful API details (e.g. duplicates, BOI FX failures).
            errors.append({"row": r_i, "error": str(e.detail), "data": data})
        except Exception as e:
            errors.append({"row": r_i, "error": str(e), "data": data})

    return {
        "created": created,
        "skipped_empty_rows": skipped_empty_rows,
        "errors": errors[:50],
        "error_count": len(errors),
    }



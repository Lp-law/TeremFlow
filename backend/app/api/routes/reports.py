"""
Client report: open cases overview for client (excess, expenses, fees by stages).
JSON for UI table, Excel for download.
"""
from __future__ import annotations

import datetime as dt
import io
from decimal import Decimal

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from openpyxl import Workbook
from sqlalchemy.orm import Session

from app.api.deps import require_auth
from app.db.session import get_db
from app.models.enums import CaseStatus
from app.services import cases as case_service

router = APIRouter()


def _client_report_rows(db: Session) -> list[dict]:
    """Open cases only; each row has case_reference, case_name, excess_total_ils, excess_remaining_ils, expenses_total_ils, fees_by_stages_ils."""
    all_cases = case_service.list_cases(db)
    open_cases = [c for c in all_cases if getattr(c, "status", None) == CaseStatus.OPEN]
    rows = []
    for c in open_cases:
        ov = case_service.build_case_overview_summary(db, c.id)
        if not ov:
            continue
        ded = ov.get("deductible") or {}
        exp = ov.get("expenses") or {}
        fees = ov.get("fees") or {}
        rows.append({
            "case_reference": ov.get("case_reference") or "",
            "case_name": ov.get("case_name") or "",
            "excess_total_ils": ded.get("excess_total_ils"),
            "excess_remaining_ils": ded.get("excess_remaining_ils"),
            "expenses_total_ils": exp.get("total_expenses_ils"),
            "fees_by_stages_ils": fees.get("fees_by_stages_ils"),
        })
    return rows


def _fmt_dec(v) -> str:
    if v is None:
        return ""
    if isinstance(v, Decimal):
        return str(v)
    return str(v)


@router.get("/client-report")
def client_report_json(db: Session = Depends(get_db), _=Depends(require_auth)):
    """JSON list of open cases with excess, expenses, fees by stages (for table in UI)."""
    rows = _client_report_rows(db)
    return {"cases": rows}


@router.get("/client-report/excel")
def client_report_excel(db: Session = Depends(get_db), _=Depends(require_auth)):
    """Download client report as XLSX: open cases, excess total, excess remaining, expenses, fees by stages."""
    rows = _client_report_rows(db)
    wb = Workbook()
    ws = wb.active
    if ws is None:
        ws = wb.create_sheet("דיווח ללקוח")
    else:
        ws.title = "דיווח ללקוח"

    headers = ["שם תיק", "אקסס מלא (ש״ח)", "יתרת אקסס (ש״ח)", "הוצאות (ש״ח)", "שכר טרחה לפי שלבים (ש״ח)"]
    ws.append(headers)
    for r in rows:
        name = (r.get("case_name") or r.get("case_reference") or "").strip() or r.get("case_reference") or ""
        ws.append([
            name,
            _fmt_dec(r.get("excess_total_ils")),
            _fmt_dec(r.get("excess_remaining_ils")),
            _fmt_dec(r.get("expenses_total_ils")),
            _fmt_dec(r.get("fees_by_stages_ils")),
        ])

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    xlsx_bytes = buf.read()
    date_suffix = dt.date.today().isoformat()
    filename = f"דיווח_ללקוח_{date_suffix}.xlsx"
    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

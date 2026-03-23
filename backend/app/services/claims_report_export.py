from __future__ import annotations

import io
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from typing import Any

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH

from app.models.enums import ClaimsCategory, ClaimsFinalOutcomeType, ClaimsReportCaseStatus
from app.services.claims_reports import compute_default_narrative

CATEGORY_LABELS: dict[ClaimsCategory, str] = {
    ClaimsCategory.COURT_REPORTED_TO_INSURER: "תיקים המתנהלים בבתי משפט ודווחו לחברת הביטוח",
    ClaimsCategory.REPORTED_WITHOUT_CLAIM: "מקרים שדווחו לחברת הביטוח ללא תביעה",
    ClaimsCategory.NOT_REPORTED_TO_INSURER: "מקרים שלא דווחו לחברת הביטוח",
    ClaimsCategory.NON_MEDICAL_MALPRACTICE: "תיקים שאינם בתחום הרשלנות הרפואית",
    ClaimsCategory.OTHER: "אחר",
}

STATUS_LABELS: dict[ClaimsReportCaseStatus, str] = {
    ClaimsReportCaseStatus.OPEN: "פתוח",
    ClaimsReportCaseStatus.CLOSED: "סגור",
    ClaimsReportCaseStatus.CANNOT_ASSESS_YET: "לא ניתן להעריך בשלב זה",
    ClaimsReportCaseStatus.NO_EXPOSURE: "ללא חשיפה",
    ClaimsReportCaseStatus.REJECTED_EXPECTED: "צפי לדחייה",
    ClaimsReportCaseStatus.SETTLED: "פשרה",
    ClaimsReportCaseStatus.JUDGMENT: "פסק דין",
    ClaimsReportCaseStatus.REJECTED: "נדחה",
    ClaimsReportCaseStatus.REJECTED_WITH_COSTS: "נדחה עם הוצאות",
}

OUTCOME_LABELS: dict[ClaimsFinalOutcomeType, str] = {
    ClaimsFinalOutcomeType.SETTLEMENT: "פשרה",
    ClaimsFinalOutcomeType.JUDGMENT_FOR_PLAINTIFF: "פסק דין לטובת התובע",
    ClaimsFinalOutcomeType.CLAIM_REJECTED: "תביעה נדחתה",
    ClaimsFinalOutcomeType.CLAIM_REJECTED_WITH_COSTS: "תביעה נדחתה עם הוצאות",
    ClaimsFinalOutcomeType.CLOSED_WITHOUT_PAYMENT: "נסגר ללא תשלום",
    ClaimsFinalOutcomeType.OTHER: "אחר",
}


def _fmt_ils(v: Any) -> str:
    if v is None:
        return "—"
    try:
        d = Decimal(str(v)).quantize(Decimal("0.01"))
        return f"{d} ₪"
    except Exception:
        return str(v)


def _add_heading(doc: Document, text: str, level: int = 1) -> None:
    p = doc.add_heading(text, level=level)
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT


def _add_paragraph(doc: Document, text: str, bold: bool = False) -> None:
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run = p.add_run(text)
    run.bold = bold


def build_claims_report_docx(report, rows: list) -> tuple[bytes, str]:
    doc = Document()
    _add_heading(doc, report.title or "דו\"ח תביעות / חשיפות", 0)
    _add_paragraph(doc, f"לקוח/מוסד: {report.client_name}")
    _add_paragraph(doc, f"תאריך חתך: {report.report_cutoff_date.isoformat()}")
    if report.updated_to_date is not None:
        _add_paragraph(doc, f"מעודכן ליום: {report.updated_to_date.isoformat()}")
    _add_paragraph(doc, f"סטטוס דו\"ח: {'סופי' if str(report.status) == 'FINAL' else 'טיוטה'}")
    if report.recommended_reserve_ils is not None:
        _add_paragraph(doc, f"המלצת הפרשה: {_fmt_ils(report.recommended_reserve_ils)}", bold=True)
    if report.intro_text:
        _add_paragraph(doc, "")
        _add_paragraph(doc, report.intro_text)

    grouped = defaultdict(list)
    for row in rows:
        grouped[row.category_for_report].append(row)

    for category in ClaimsCategory:
        category_rows = grouped.get(category, [])
        if not category_rows:
            continue
        _add_paragraph(doc, "")
        _add_heading(doc, CATEGORY_LABELS.get(category, str(category)), 1)
        for idx, row in enumerate(category_rows, start=1):
            row_title = row.case_title or row.case_reference_text or f"רשומה {row.id}"
            _add_paragraph(doc, f"{idx}. {row_title}", bold=True)
            _add_paragraph(doc, f"מספר הליך/תיק: {row.proceeding_number or row.case_reference_text or '—'}")
            _add_paragraph(doc, f"סטטוס בדו\"ח: {STATUS_LABELS.get(row.report_case_status, str(row.report_case_status))}")
            if row.final_outcome_type is not None:
                _add_paragraph(doc, f"תוצאת סיום: {OUTCOME_LABELS.get(row.final_outcome_type, str(row.final_outcome_type))}")
            if row.final_outcome_amount_ils is not None:
                _add_paragraph(doc, f"סכום סיום: {_fmt_ils(row.final_outcome_amount_ils)}")
            if row.awarded_costs_to_terem_ils is not None:
                _add_paragraph(doc, f"הוצאות שנפסקו לטובת טרם: {_fmt_ils(row.awarded_costs_to_terem_ils)}")
            _add_paragraph(doc, f"השתתפות עצמית מלאה: {_fmt_ils(row.deductible_ils_gross)}")
            _add_paragraph(doc, f"שולם על חשבון: {_fmt_ils(row.amount_already_paid_on_deductible_ils)}")
            _add_paragraph(doc, f"נותר: {_fmt_ils(row.remaining_deductible_ils)}")
            _add_paragraph(doc, f"הוצאות: {_fmt_ils(row.expenses_total_ils)}")
            _add_paragraph(doc, f"שכ\"ט: {_fmt_ils(row.fees_total_ils)}")
            _add_paragraph(doc, f"חשיפה לרזרבה: {_fmt_ils(row.exposure_for_reserve_ils)}")
            narrative = row.narrative_text or compute_default_narrative(row)
            _add_paragraph(doc, f"נרטיב: {narrative}")
            if row.legal_summary_text:
                _add_paragraph(doc, f"סיכום משפטי: {row.legal_summary_text}")
            if row.status_note:
                _add_paragraph(doc, f"הערת סטטוס: {row.status_note}")
            if row.internal_notes:
                _add_paragraph(doc, f"הערות פנימיות: {row.internal_notes}")

    if report.closing_text:
        _add_paragraph(doc, "")
        _add_paragraph(doc, report.closing_text)

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    file_date = datetime.now().strftime("%Y%m%d")
    filename = f"claims_report_{report.id}_{file_date}.docx"
    return buf.read(), filename

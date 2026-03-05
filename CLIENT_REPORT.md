# Client Report — ייצוא דו״ח ללקוח

## Files changed

### Backend
- **`backend/requirements.txt`** — Added: matplotlib, python-docx, reportlab, Jinja2.
- **`backend/app/schemas/client_report.py`** — New: `ClientReportFilters`, `ClientReportBrand`, `ClientReportRequest`.
- **`backend/app/services/analytics_report.py`** — New: `_chart_closing_stage_png`, `_narrative_bullets`, `build_report_pdf`, `build_report_docx`, `build_client_report`. Uses ReportLab for PDF (RTL alignment), python-docx for DOCX, matplotlib for closing-stage bar chart.
- **`backend/app/api/routes/analytics.py`** — Extracted `compute_analytics_v2_response` (used by GET /v2 and by client-report). Added `POST /analytics/client-report` (parses body, resolves branch from branch_is_null, calls compute + build_client_report, returns file).

### Frontend
- **`frontend/src/pages/AnalyticsPage.tsx`** — Button "ייצא דו״ח ללקוח", modal wizard (template T1/T2/T3, date range default 90 days, case_type, status, branch, "רק ללא סניף", format PDF/Word, optional logo URL). On confirm: POST /analytics/client-report, download file via blob + Content-Disposition filename, toast success/error.

---

## Example request

```json
POST /analytics/client-report
Content-Type: application/json

{
  "template_id": "T1",
  "format": "pdf",
  "filters": {
    "start_date": "2025-01-01",
    "end_date": "2025-12-31",
    "case_type": null,
    "status": null,
    "branch_name": null,
    "branch_is_null": false
  },
  "brand": {
    "logo_url": null
  }
}
```

With "ללא סניף" only: `"branch_name": null, "branch_is_null": true`.

---

## Example response

- **Status:** 200 OK  
- **Headers:** `Content-Disposition: attachment; filename="client_report_T1_20260305.pdf"` (or `.docx`)  
- **Body:** Binary (PDF or DOCX). No case identifiers; no raw_import_fields_json, delete_reason, or internal IDs.

---

## PDF layout (screenshot-like description)

1. **Title (RTL):** "דו״ח סיכום פעילות" (or T2/T3 title), right-aligned.
2. **Subtitle:** Period and denominator, e.g. "תקופה: 2025-01-01 – 2025-12-31 | תיקים בפילטר: 42".
3. **מפתחות ביצוע:** Right-aligned lines: שכ״ט ממוצע לפי שלבים, שכ״ט ממוצע לפי ריטיינר, הוצאות ממוצעות לתיק, and (when applicable) שלב סיום ממוצע with denominator.
4. **סיכום:** Bullet list of auto-generated narrative sentences (X תיקים, ממוצעים, שלב שכיח, סניף עם נפח גבוה).
5. **Chart:** "התפלגות שלב סיום (תיקים סגורים)" — horizontal bar chart (matplotlib PNG), Hebrew labels.
6. **Table:** "נפח לפי סניף וסוג תיק" — columns סניף, סוג תיק, כמות.
7. **Table:** "שכ״ט ממוצע לפי סניף" — columns סניף, תיקים, שכ״ט שלבים, שכ״ט ריטיינר, הוצאות.

All text and tables use right alignment (RTL-friendly). No case IDs or internal-only fields.

---

## Brand colors + logo

- **Brand:** Request body can include `brand.logo_url`. The current implementation does not embed the logo image in the PDF/DOCX (to avoid fetching external URLs in the backend). The field is accepted for future use (e.g. download logo and embed). To add: resolve logo_url to bytes, then add an Image in ReportLab / docx and place it in the header.
- **Colors:** ReportLab uses default grey/steelblue for table header and chart. To make them configurable, extend `ClientReportBrand` with e.g. `primary_hex`, `header_bg_hex` and pass them into `build_report_pdf` / `build_report_docx`.

---

## Verification

1. **T1 PDF, last 30 days:** Run export with T1, PDF, last 30 days → open PDF → confirm RTL, KPIs and tables match Analytics page for same filters; no case IDs.
2. **DOCX:** Export T1 as Word → open DOCX → confirm tables and chart image appear, RTL alignment.
3. **Excluded data:** Compare denominator in report with Analytics v2 for same filters; confirm soft-deleted cases/events are excluded (same as v2).
4. **No identifiers:** Search PDF/DOCX for "case_id", "מזהה", "raw_import", "delete_reason" → none present.

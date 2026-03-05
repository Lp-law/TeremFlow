# Client Report — ייצוא דו״ח ללקוח

## Files changed

### Backend
- **`backend/requirements.txt`** — Added: matplotlib, python-docx, reportlab, Jinja2.
- **`backend/app/schemas/client_report.py`** — `ClientReportFilters`, `ClientReportRequest`. **`ClientReportBrand`:** `logo_base64` (preferred, no URL fetch), `primary_hex`, `accent_hex`, `header_bg_hex`, `header_text_hex`.
- **`backend/app/schemas/analytics.py`** — Added `CaseTypeFeeAverageRow` and `case_type_fee_averages` to v2 response (for T3 report).
- **`backend/app/services/analytics_report.py`** — Logo from base64 (no SSRF). Brand colors on PDF/DOCX (title, section headers, table headers, chart bars). **T1:** KPI → narrative → closing chart → branch×case_type table → branch fee table. **T2:** KPI → big branch fee table → volume table → mini insights (top branch by volume, by avg fee) → smaller chart. **T3:** KPI → case_type summary table → narrative → closing chart only when CLOSED data present.
- **`backend/app/api/routes/analytics.py`** — `compute_analytics_v2_response` now computes `case_type_fee_averages`; client-report uses `brand` with logo_base64 and hex colors.

### Frontend
- **`frontend/src/pages/AnalyticsPage.tsx`** — Report modal: template, dates, filters, format; **logo:** file upload (read as base64) or paste base64/data URL; **צבע מותג:** primary hex + header text hex pickers. Sends `brand.logo_base64`, `primary_hex`, `accent_hex`, `header_text_hex`.
- **`frontend/src/lib/types.ts`** — `ClientReportBrand`, `CaseTypeFeeAverageRow`; `AnalyticsV2Response.case_type_fee_averages`.

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
    "logo_base64": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
    "primary_hex": "#1F4E79",
    "accent_hex": "#2E75B6",
    "header_bg_hex": null,
    "header_text_hex": "#FFFFFF"
  }
}
```

- **logo_base64:** Preferred over any URL. Data URL (`data:image/...;base64,...`) or raw base64. Backend does **not** fetch external URLs (SSRF-safe).
- **primary_hex / accent_hex / header_bg_hex / header_text_hex:** Optional; defaults: primary `#1F4E79`, accent `#2E75B6`, header text `#FFFFFF`; `header_bg_hex` defaults to primary when null.
- With "ללא סניף" only: `"branch_name": null, "branch_is_null": true`.

---

## Example response

- **Status:** 200 OK  
- **Headers:** `Content-Disposition: attachment; filename="client_report_T1_20260305.pdf"` (or `.docx`)  
- **Body:** Binary (PDF or DOCX). No case identifiers; no raw_import_fields_json, delete_reason, or internal IDs.

---

## PDF layout (screenshot-like description)

- **Header:** If `brand.logo_base64` is set, logo appears **top-right** (PDF) or at **top** (DOCX). Title and period below.
- **Brand colors:** Title and section headings use `primary_hex`. Table header row uses `header_bg_hex` (default primary) and `header_text_hex` (default white). Chart bars use `primary_hex`; axis labels neutral gray; clean layout, light grid.
- All text and tables are RTL. No case IDs or internal-only fields.

### T1 — דו״ח סיכום פעילות (first page)

1. **Title bar:** "דו״ח סיכום פעילות" (brand color) + optional logo top-right.
2. **Subtitle:** "תקופה: … | תיקים בפילטר: N".
3. **מפתחות ביצוע:** שכ״ט ממוצע לפי שלבים, ריטיינר, הוצאות ממוצעות, שלב סיום ממוצע (when applicable).
4. **סיכום:** Bullet narrative (תיקים, ממוצעים, שלב שכיח, סניף נפח גבוה).
5. **Chart:** "התפלגות שלב סיום (תיקים סגורים)" — horizontal bar chart.
6. **Table:** "נפח לפי סניף וסוג תיק" (סניף, סוג תיק, כמות).
7. **Table:** "שכ״ט ממוצע לפי סניף" (סניף, תיקים, שכ״ט שלבים, ריטיינר, הוצאות).

### T2 — דו״ח סניפים (first page)

1. Title + period (same as above).
2. **מפתחות ביצוע** (same KPI row).
3. **שכ״ט ממוצע לפי סניף** — **large table first** (all branches).
4. **נפח תיקים לפי סניף וסוג תיק** — full volume table.
5. **תובנות:** Top branch by volume; top branch by avg stage fee (mini insights).
6. **התפלגות שלב סיום** — smaller chart (optional).

### T3 — דו״ח סוגי תיקים (first page)

1. Title + period.
2. **מפתחות ביצוע** (same).
3. **סיכום לפי סוג תיק** — table: סוג תיק, תיקים, שכ״ט שלבים, שכ״ט ריטיינר, הוצאות (from `case_type_fee_averages`).
4. **סיכום:** Narrative bullets.
5. **התפלגות שלב סיום** — **only when** filter/data include CLOSED cases (i.e. when `distributions.closing_stage` is non-empty).

---

## Brand colors + logo

- **Logo:** Use `brand.logo_base64` only (data URL or raw base64). Backend **does not** fetch external URLs (SSRF-safe).
- **Colors:** `primary_hex`, `accent_hex`, `header_bg_hex`, `header_text_hex` applied to PDF/DOCX title, section headers, table header row, and chart bar color.

---

## Verification

1. **T1 PDF, last 30 days:** Run export with T1, PDF, last 30 days → open PDF → confirm RTL, KPIs and tables match Analytics page for same filters; no case IDs.
2. **DOCX:** Export T1 as Word → open DOCX → confirm tables and chart image appear, RTL alignment.
3. **Excluded data:** Compare denominator in report with Analytics v2 for same filters; confirm soft-deleted cases/events are excluded (same as v2).
4. **No identifiers:** Search PDF/DOCX for "case_id", "מזהה", "raw_import", "delete_reason" → none present.

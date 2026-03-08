# Client Report — ייצוא דו״ח ללקוח

## Files changed

### Backend
- **`backend/requirements.txt`** — matplotlib, python-docx, reportlab, Jinja2.
- **`backend/app/schemas/client_report.py`** — `ClientReportFilters`, `ClientReportRequest`. **`ClientReportBrand`** optional: `primary_hex`, `accent_hex` only (no logo). Report uses fixed **Light Navy + Gold** palette when brand not provided.
- **`backend/app/schemas/analytics.py`** — `CaseTypeFeeAverageRow`, `case_type_fee_averages` in v2 response (T3).
- **`backend/app/services/analytics_report.py`** — **PDF:** Full-width title bar (navy bg, white text). Section headers: navy text + thin gold underline. Tables: header row navy/white, zebra rows subtle_gray, light borders. Chart: navy bars, max bar gold, body_text axes. **DOCX:** Navy headings + gold underline, header row shading + white text. **T1:** KPIs → narrative → closing chart → branch×case_type → branch fee table. **T2:** KPIs → big branch fee table → volume table → top-3 insights (volume, avg stage fee, avg retainer) → closing chart **only if CLOSED cases exist**. **T3:** KPIs → case_type averages table → closing chart (when CLOSED) → optional branch summary table.
- **`backend/app/api/routes/analytics.py`** — Client-report accepts optional `brand`; builds report with fixed palette (or brand overrides).

### Frontend
- **`frontend/src/pages/AnalyticsPage.tsx`** — Report modal: **template (T1/T2/T3), date range, case_type, status, branch, "רק ללא סניף", format (PDF/DOCX)**. No logo or color inputs. Request body has no `brand`.
- **`frontend/src/lib/types.ts`** — `CaseTypeFeeAverageRow`; `AnalyticsV2Response.case_type_fee_averages`.

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
  }
}
```

- **brand** is optional. If omitted, report uses fixed **Light Navy + Gold** palette. If provided: `primary_hex`, `accent_hex` only (no logo).
- For "ללא סניף" only: `"branch_name": null, "branch_is_null": true`.

---

## Example response

- **Status:** 200 OK  
- **Headers:** `Content-Disposition: attachment; filename="client_report_T1_20260305.pdf"` (or `.docx`)  
- **Body:** Binary (PDF or DOCX). No case identifiers; no raw_import_fields_json, delete_reason, or internal IDs.

---

## PDF / DOCX layout (premium Navy + Gold)

**Palette (fixed):** primary_navy `#1F3B63`, accent_gold `#C9A227`, header_bg = primary_navy, header_text `#FFFFFF`, subtle_gray `#F3F5F7`, body_text `#111827`.

- **PDF:** Full-width **title bar** at top (header_bg, header_text). **Section headers:** navy text + thin **gold underline**. **Tables:** header row navy background + white text; **zebra** rows with subtle_gray; light gray borders. **Chart:** bars primary_navy, **max bar accent_gold**; axes body_text; minimal grid.
- **DOCX:** Title in navy with thin gold line below; section headings navy + gold underline; table header row shaded navy with white text; chart image same as PDF.
- RTL throughout. No case identifiers.

### T1 — דו״ח סיכום פעילות (balanced)

1. **Title bar:** Full width, navy bg, white text: title + period.
2. **מפתחות ביצוע** (navy + gold underline): KPIs (3–4).
3. **סיכום:** Narrative bullets (3–5).
4. **התפלגות שלב סיום** + chart.
5. **נפח לפי סניף וסוג תיק** table.
6. **שכ״ט ממוצע לפי סניף** table.

### T2 — דו״ח סניפים (branch-focused)

1. Title bar + **מפתחות ביצוע** (same).
2. **שכ״ט ממוצע לפי סניף** — **BIG table first** (all branches).
3. **נפח תיקים לפי סניף וסוג תיק** table.
4. **תובנות:** Top-3: branch with highest volume; branch with highest avg stage fee; branch with highest avg retainer fee.
5. **התפלגות שלב סיום** — **only if CLOSED cases exist**; otherwise omitted.

### T3 — דו״ח סוגי תיקים (case-type focused)

1. Title bar + **מפתחות ביצוע** (same).
2. **סיכום לפי סוג תיק** — table: case_type, cases_count, avg_stage_fee_ils, avg_retainer_fee_ils, avg_expenses_ils.
3. **התפלגות שלב סיום** — only when CLOSED cases present.
4. **סיכום סניפים** — optional small table (branch, count).

---

## Brand

- **No logo** in UI or request. Backend ignores logo fields.
- **Colors:** Fixed Light Navy + Gold palette. Optional request `brand` can override `primary_hex` / `accent_hex` only.

---

## Verification

1. **T1 PDF, last 30 days:** Run export with T1, PDF, last 30 days → open PDF → confirm RTL, KPIs and tables match Analytics page for same filters; no case IDs.
2. **DOCX:** Export T1 as Word → open DOCX → confirm tables and chart image appear, RTL alignment.
3. **Excluded data:** Compare denominator in report with Analytics v2 for same filters; confirm soft-deleted cases/events are excluded (same as v2).
4. **No identifiers:** Search PDF/DOCX for "case_id", "מזהה", "raw_import", "delete_reason" → none present.

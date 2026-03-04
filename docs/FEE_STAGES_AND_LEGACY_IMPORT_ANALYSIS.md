# Fee Stages & Legacy Excel Import – Full Analysis & Options

This document answers your fact-gathering questions from the codebase and proposes solution options for importing legacy fee data (including appeal, mixed stages, free text).

---

## 1) Facts I found in the code

### 1.1 Data model & storage

| Question | Answer (with paths) |
|----------|---------------------|
| **Where are fee stages stored?** | Two places: (1) **`cases.historical_fee_stages`** – JSON column, list of strings (FeeEventType codes). (2) **`fee_events`** table – one row per billing event with `event_type` (enum), `event_date`, `quantity`, `amount_override_ils_gross`, `computed_amount_ils_gross`, retainer-credit fields. `backend/app/models/case.py` (lines 44–45), `backend/app/models/fee_event.py`. |
| **How is historical_fee_stages persisted?** | As **JSON array** on `Case` (PostgreSQL JSON / SQLite JSON). Not normalized into rows. `alembic/versions/0008_case_historical_fee_stages.py` adds `sa.Column("historical_fee_stages", sa.JSON(), nullable=True)`. |
| **Is there a “current stage” separate from historical?** | **No** separate field. The UI “שלב ההליך הנוכחי” is derived from **fee_events** only: latest `FeeEvent` by `event_date` (`CaseDetailsPage.tsx` lines 98–104). `historical_fee_stages` is **not** used for “current stage.” |
| **Are fee stages linked to billing events, invoices, or just metadata?** | **historical_fee_stages**: metadata only (display in “שלבי שכ״ט עבר”). No amounts, no dates, no retainer/billing. **fee_events**: full billing – each row has `computed_amount_ils_gross`, retainer allocation (`amount_covered_by_credit_ils_gross`, `amount_due_cash_ils_gross`). `backend/app/services/fees.py` – `compute_fee_amount`, `apply_retainer_credit`. |
| **Is there any representation of “appeal” (ערעור)?** | **No.** No enum value, no column, no flag in `Case` or `FeeEvent`. `backend/app/models/enums.py` – `FeeEventType` has no appeal. Grep for appeal/ערעור: no matches. |

### 1.2 Validation & business rules

| Question | Answer |
|----------|--------|
| **What validations run on import for historical_fee_stages?** | **Per-row.** `_parse_historical_fee_stages()` in `backend/app/services/import_excel.py` (103–115). Any **unknown code** → `ValueError` with message "קוד לא מוכר: X. קודים חוקיים: …". That row is appended to `errors`, **other rows continue**. Whole file does **not** fail. Empty/blank → `None` (no stages). |
| **Validations that restrict stages by case_type?** | **None.** Import does not check that COURT case has only court stages, etc. API `add_fee_event` (`backend/app/services/fees.py`) also does **not** check case_type. You can add DEMAND_FIX to a COURT case. |
| **What happens when a case has demand-letter stages and court stages together?** | **No special handling.** Both are stored in the same list. UI shows all in one table (“שלבי שכ״ט עבר”). Analytics (below) only looks at **fee_events** for court cases. |
| **What do stages trigger?** | **historical_fee_stages:** Only display in Case Details → Fees tab (“שלבי שכ״ט עבר (ייבוא)” – “תיעוד בלבד — אינו משפיע על קרדיט ריטיינר או תשלומים”). **fee_events:** Billing amounts (`compute_fee_amount`), retainer credit allocation (`apply_retainer_credit`), analytics “court cases end stage distribution” (highest of stages 1–5 per case). `backend/app/api/routes/analytics.py` 127–150 uses only `FeeEvent` rows, **not** `historical_fee_stages`. |

### 1.3 Import pipeline

| Question | Answer |
|----------|--------|
| **Where is Excel import implemented?** | `backend/app/services/import_excel.py` – `import_cases_from_excel(db, file_bytes)`. Called from `backend/app/api/routes/import_excel.py` – `POST /import/excel` with `UploadFile`. |
| **How are headers mapped?** | Row 0 = headers. Each cell normalized: `_norm(s)` = strip, remove RTL/LTR marks, lower. Lookup in `KNOWN_COLUMNS` dict; if not found, try key with spaces removed. Result: `col_map[column_index] = logical_field_name` (e.g. `case_reference`, `historical_fee_stages`). `import_excel.py` 146–157. |
| **How are rows parsed?** | For each data row (from row 2): build `data` dict from `col_map`; build payload object; parse each field (dates, decimals, case_type, `_parse_historical_fee_stages`); call `create_case(db, payload)`. On any exception: append `{"row": r_i, "error": str(e), "data": data}` to `errors`, continue. 166–207. |
| **Where do errors surface?** | Backend returns `{ "created", "skipped_empty_rows", "errors" (first 50), "error_count" }`. Frontend `ImportPage.tsx` shows `result` as JSON in a `<pre>`. No per-row UI (e.g. row numbers in a table). If entire request fails (e.g. missing required columns), `error` state shows `res.json().detail`. |
| **What fields can be imported besides stages?** | case_reference, case_name, case_type, open_date, deductible_usd, deductible_ils_gross, branch_name, retainer_anchor_date, retainer_snapshot_ils_gross, retainer_snapshot_through_month, expenses_snapshot_ils_gross, historical_fee_stages. No free-text column for “fee charges raw” today. |
| **Can we extend import with new columns?** | **Yes.** Add to `KNOWN_COLUMNS`, read in the row loop, attach to payload or a new Case field. New columns that are optional and not used in strict validation are safe. |

### 1.4 UI workflows

| Question | Answer |
|----------|--------|
| **Where does the user set/update stages today?** | **Live stages:** Case Details → Fees tab → “הוספת שלב שכ״ט” → `AddFeeEventModal`: event_type (dropdown of all FeeEventType), event_date, quantity, amount_override. Creates a **FeeEvent** via `POST /cases/{id}/fees/`. **Historical stages:** Only via Excel import column `historical_fee_stages`. No UI to edit them after import. |
| **Post-import editing flow?** | **None** for historical_fee_stages. No PATCH/PUT on case for stages. Only `PATCH /cases/{id}/status` (OPEN/CLOSED). `CaseCreate` schema does not include `historical_fee_stages`; only the import path passes it to `create_case`. |
| **Bulk-edit / audit / history UI?** | No bulk-edit. No audit log for case field changes (activity_log logs actions like case_create, fee_event_add, not field-level edits). |
| **Desired UX** | Not implemented; your choice: e.g. “wizard after import”, “mapping screen”, “manual entry per case”, or “parse free text at import and show in UI”. |

---

## 2) What the system can represent TODAY vs cannot

### Can represent today (no code changes)

- **Court stages 1–5** – as FeeEventType codes in `historical_fee_stages` or as `FeeEvent` rows.
- **Court extras** – AMENDED_DEFENSE_PARTIAL/FULL, THIRD_PARTY_NOTICE, ADDITIONAL_PROOF_HEARING.
- **Demand letter** – DEMAND_FIX, DEMAND_HOURLY.
- **Small claims** – SMALL_CLAIMS_MANUAL.
- **Arbitrary combination** of the above in one case (no case_type restriction).
- **Exact list** of stage codes in import (comma-separated, strict codes).

### Cannot represent today

- **Appeal (ערעור)** – no enum, no column, no flag.
- **Per-stage dates** for historical stages (historical is a list of codes only; no dates/amounts).
- **Per-stage amounts** for historical (only “תיעוד” list; amounts exist only for `FeeEvent`).
- **Free-text “פירוט חיוב שכ״ט”** – no column; cannot store or parse it without adding something.
- **Ranges** like “1–4” or **partial sets** like “1+3+4” – import expects explicit codes (e.g. COURT_STAGE_1_DEFENSE, COURT_STAGE_2_DAMAGES, …). No parser for “1–4” → list of codes.
- **Mixed timeline** (demand then court) as structured data – you can put both in the same list but there is no “phase” or order/date for historical.

---

## 3) Gaps / questions for you

1. **Appeal:** Should appeal be a **first-class stage** (new FeeEventType + same billing/retainer logic as other stages), or only **informational** (e.g. flag or note, no fixed amount)?
2. **Legacy amounts:** Do you need to **store** the legacy amounts (e.g. “46,950 ₪”) per charge line for reporting, or is “list of stages + optional note” enough?
3. **Warn vs fail:** For ambiguous or partially parseable free text (e.g. “שלב 1 + משהו לא מזוהה”) – should that row **fail** import or **succeed with warning** and store what was parsed + rest in notes?
4. **Post-import edit:** Do you want users to **edit** historical stages (or appeal/notes) from the Case Details page later, or is “set once at import” enough for now?

---

## 4) Solution options (3–5 approaches)

### Option A: Strict mapping only (no new columns, no appeal)

- **Idea:** Keep import as-is. Preprocess Excel outside the app: from “פירוט חיוב” free text, produce a column with comma-separated **strict codes** (e.g. expand “1–4” → COURT_STAGE_1_DEFENSE, …, COURT_STAGE_4_PROOFS; “הודעת צד ג’” → THIRD_PARTY_NOTICE). Appeal and unparseable text are dropped or put in case_name/notes elsewhere.
- **DB:** None.
- **API:** None.
- **UI:** None.
- **Import:** None (user supplies already-mapped column).
- **Appeal / mixed:** Appeal not represented. Mixed = same list.
- **Risks:** Manual or external script; no audit of original text; appeal lost.
- **Complexity:** Low.

### Option B: New optional columns (free text + notes), no appeal enum

- **Idea:** Add optional columns: e.g. `fee_charges_raw_text` (free text), `fee_stage_notes` (text). Import stores them on Case. No new stage codes. Parsing can be done later (or in a separate “mapping” step) and result still written into `historical_fee_stages` as today.
- **DB:** Add columns to `cases`: e.g. `fee_charges_raw_text` (Text, nullable), `fee_stage_notes` (Text, nullable). Migration.
- **API:** CaseOut (and create_case payload from import) includes new fields. No new endpoints.
- **UI:** Case Details → Fees: show “פירוט חיוב מקורי” / “הערות שלבי שכ״ט” (read-only) if present.
- **Import:** Add to KNOWN_COLUMNS (e.g. “פירוט חיוב שכ״ט עו״ד” → fee_charges_raw_text). No change to historical_fee_stages validation.
- **Appeal / mixed:** Stored only in text/notes. No structured appeal.
- **Risks:** Low. Backward compatible (columns nullable).
- **Complexity:** Low–medium.

### Option C: Parse free text at import → historical_fee_stages + notes (no DB for raw)

- **Idea:** Add one optional column “פירוט חיוב…” mapped to a single logical field. At import time, run a **parser** on that cell: extract stage codes (ranges 1–5, “הודעת צד ג’”, etc.), append to (or override) `historical_fee_stages`; put unparseable parts or “ערעור” into a **new** field `fee_stage_notes` (or keep in one notes field). No appeal enum yet.
- **DB:** One new column: e.g. `fee_stage_notes` (Text, nullable) to hold “ערעור”, “שלב 1-4”, or other parsed summary.
- **API:** CaseOut + import payload include `fee_stage_notes`.
- **UI:** Show `fee_stage_notes` in Fees tab when present.
- **Import:** New column; parser function; on parse failure either fail row or warn and store raw in notes (your choice).
- **Appeal / mixed:** Appeal as text in notes. Mixed stages in one list.
- **Risks:** Parser must be well-defined; ambiguous input needs policy (warn vs fail).
- **Complexity:** Medium.

### Option D: Add APPEAL as first-class FeeEventType + optional notes

- **Idea:** Add `APPEAL` (or `COURT_APPEAL`) to `FeeEventType`; use same fee_events/historical_fee_stages flow. Optional column `fee_stage_notes` for unparseable/extra text. Parser maps “ערעור” → APPEAL.
- **DB:** (1) New enum value in DB (if enum is DB-backed: migration to add value). (2) Optional `fee_stage_notes` on Case.
- **API:** FeeEventType in API/schemas includes new value. `compute_fee_amount`: need default amount for APPEAL (or require amount_override).
- **UI:** Add label for APPEAL in FEE_EVENT_LABEL; show in dropdown and in historical list.
- **Import:** Parser adds APPEAL to list when “ערעור” (and variants) found. Optional raw/notes column.
- **Appeal / mixed:** Appeal is a normal stage; mixed = same list.
- **Risks:** Enum migration; defining fee for appeal (fixed vs override).
- **Complexity:** Medium.

### Option E: Full legacy support (raw JSON + appeal + parser)

- **Idea:** Store original charge lines as JSON (e.g. `legacy_fee_charges_json`: list of `{ "raw": "46,950 ₪ שלב 1-4", "parsed_codes": [...], "amount_ils": 46950 }`). Add APPEAL. Parser fills `historical_fee_stages` and optionally `legacy_fee_charges_json`. UI can show both “מקור” and “מפוענח”.
- **DB:** `legacy_fee_charges_json` (JSON), `fee_stage_notes` (Text), plus APPEAL enum.
- **API:** CaseOut exposes these; import accepts optional column and parses.
- **UI:** Fees tab: historical stages (as now) + “פירוט מקורי” (from JSON) + notes.
- **Import:** One or two columns (free text + optional amount column); parser; validation policy.
- **Appeal / mixed:** Structured appeal + full fidelity of legacy text and amounts.
- **Risks:** More code and UI; JSON schema to maintain.
- **Complexity:** High.

---

## 5) Recommended approach

- **Short term (minimal, safe):**  
  **Option B** – add optional `fee_charges_raw_text` and `fee_stage_notes` on Case. Import maps “פירוט חיוב שכ״ט עו״ד” (and similar) to `fee_charges_raw_text`; leave `historical_fee_stages` as today (user or external tool fills it with strict codes). Show raw + notes in UI. No appeal enum yet; “ערעור” can go in notes.
- **Next step (if you need structured appeal and less manual mapping):**  
  **Option D** – add APPEAL to FeeEventType + parser that maps “ערעור” → APPEAL and expands “1–4” / “1+3+4” into codes. Keep Option B columns for unparseable text. So: **B + D** for appeal and parsing, without going to full JSON (Option E) unless you need per-line amounts and full audit of original lines.

---

## 6) Legacy import mapping spec (actionable)

### 6.1 Goal

Map one free-text column (e.g. “פירוט חיוב שכ״ט עו״ד”) into:

- **historical_fee_stages:** list of existing (and if you add it, APPEAL) FeeEventType codes.
- **Optional:** fee_stage_notes (e.g. “ערעור”, “שלב 1-4”, or “לא מפוענח: …”).

### 6.2 Parsing rules (to implement in parser)

- **Ranges “1–4” or “1 עד 4”:** Expand to COURT_STAGE_1_DEFENSE, COURT_STAGE_2_DAMAGES, COURT_STAGE_3_EVIDENCE, COURT_STAGE_4_PROOFS (and similarly for 1–5, 2–5, etc.).
- **Lists “1+3+4” or “1,3,4”:** Map to corresponding COURT_STAGE_* (only 1–5).
- **“שלב 4” / “stage 4”:** Single code COURT_STAGE_4_PROOFS.
- **“הודעת צד ג’” / “צד ג”:** THIRD_PARTY_NOTICE.
- **“כתב הגנה מתוקן” (partial/full):** AMENDED_DEFENSE_PARTIAL or AMENDED_DEFENSE_FULL (heuristic or default to PARTIAL).
- **“הוכחות נוספת” / “ישיבת הוכחות”:** ADDITIONAL_PROOF_HEARING.
- **“מכתב דרישה” / “דרישה” + “קבוע”:** DEMAND_FIX; + “שעתי” or “שעות”: DEMAND_HOURLY.
- **“תביעות קטנות”:** SMALL_CLAIMS_MANUAL.
- **“ערעור”:** If APPEAL exists → add APPEAL; else append to notes “ערעור”.
- **Amounts “46,950 ₪” / “46950”:** Optional: parse and store in notes or in legacy_fee_charges_json (Option E). For B/D: can ignore or put in notes as “סה״כ בעבר: X”.
- **Order:** Output list = order of first occurrence (e.g. stages 1–4 then THIRD_PARTY_NOTICE if that appears after in text).
- **Deduplication:** If same code appears twice (e.g. from “1-4” and “שלב 2”), include once (or keep first occurrence).

### 6.3 When to warn vs fail

- **Fail row:** Invalid required field (case_reference, case_type, open_date, deductible); duplicate case_reference; FX error. **Do not** fail row only because of historical_fee_stages/free text (unless you adopt “strict mode”).
- **Warn (log / add to result.errors with warning flag):** Free-text cell present but parser could not identify any stage; or “ערעור” found but no APPEAL enum. Option: still import case, put raw in fee_charges_raw_text or fee_stage_notes.
- **Succeed:** At least one code parsed, or cell empty. Empty → historical_fee_stages = None/[].

### 6.4 Examples: input string → structured output

| Input (cell) | historical_fee_stages (list) | fee_stage_notes (if used) |
|--------------|------------------------------|----------------------------|
| `46,950 ₪ שלב 1-4` | [COURT_STAGE_1_DEFENSE, COURT_STAGE_2_DAMAGES, COURT_STAGE_3_EVIDENCE, COURT_STAGE_4_PROOFS] | optional: "סה״כ 46950" |
| `52,650 ₪ שלב 1+3+4` | [COURT_STAGE_1_DEFENSE, COURT_STAGE_3_EVIDENCE, COURT_STAGE_4_PROOFS] | optional |
| `שלב 4` | [COURT_STAGE_4_PROOFS] | — |
| `35,200 ₪ שלב 1 + הודעת צד ג'` | [COURT_STAGE_1_DEFENSE, THIRD_PARTY_NOTICE] | optional |
| `שלב 1-5 + ערעור` | [COURT_STAGE_1_DEFENSE, …, COURT_STAGE_5_SUMMARIES, APPEAL] (if APPEAL exists) | or "ערעור" if no enum |
| `מכתב דרישה — קבוע` | [DEMAND_FIX] | — |
| `לא רלוונטי` (no pattern) | [] | "לא מפוענח: לא רלוונטי" (warn) |

### 6.5 Validation behavior (recommended)

- **Existing validation:** Keep strict code check for **direct** `historical_fee_stages` column: if user provides it, every code must be in VALID_FEE_EVENT_TYPES (and APPEAL if added). Per-row fail as today.
- **New “free text” column:** If column present, run parser. Parser output codes only from VALID_FEE_EVENT_TYPES (and APPEAL). Unknown tokens → notes or warn, do not add to list. Empty parse → historical_fee_stages from this column = [] and optionally notes = raw snippet.

---

## 7) File reference summary

| Topic | File(s) |
|-------|--------|
| Case model, historical_fee_stages | `backend/app/models/case.py` |
| FeeEvent model | `backend/app/models/fee_event.py` |
| FeeEventType enum | `backend/app/models/enums.py` |
| Fee amounts, add_fee_event, list_fee_events | `backend/app/services/fees.py` |
| create_case, to_case_out | `backend/app/services/cases.py` |
| Import: columns, parse, create_case | `backend/app/services/import_excel.py` |
| Import API | `backend/app/api/routes/import_excel.py` |
| Case API (create, status) | `backend/app/api/routes/cases.py` |
| Analytics stage distribution | `backend/app/api/routes/analytics.py` |
| Case schemas | `backend/app/schemas/case.py` |
| Fees tab, historical display, AddFeeEventModal | `frontend/src/pages/CaseDetailsPage.tsx` (FeesPanel, AddFeeEventModal) |
| Import page, result/error display | `frontend/src/pages/ImportPage.tsx` |
| Migration historical_fee_stages | `backend/alembic/versions/0008_case_historical_fee_stages.py` |

---

End of document. Use this with your product decisions and the chosen option (B, D, or B+D) to implement minimal, safe legacy import and optional appeal support.

# STAGE_BILLING + FeeStageRate + legacy_fee_text — Current State Audit

**Purpose:** Ground truth of what exists in code and DB today, to decide if it’s safe to deploy to Render and what (if anything) to fix first.

---

## 1) What is implemented today (ground truth)

### 1.1 DB fields

| Entity   | Field                     | Type        | Exists | Notes |
|----------|---------------------------|-------------|--------|--------|
| **Case** | `legacy_fee_text`         | `Text`      | ✅     | Nullable. From Excel "פירוט חיוב שכ״ט עו״ד". |
| **Case** | `performed_fee_stage_codes` | `JSON`   | ✅     | Nullable. List of strings. Last selection from stage-billing submit. |
| **FeeEvent** | `breakdown_json`      | `JSON`      | ✅     | Nullable. Used for `event_type=STAGE_BILLING` only. |

**Source:** Migration `0010_fee_stage_rates_and_stage_billing.py`; models `backend/app/models/case.py`, `backend/app/models/fee_event.py`.

### 1.2 Enums / constants

- **FeeEventType** (`backend/app/models/enums.py`): includes `APPEAL` and `STAGE_BILLING`.
- **APPEAL usage:**
  - **As event type:** Used in `compute_fee_amount()` in `fees.py` (hardcoded 15000) and in analytics stage ordering. You can create a single fee event with `event_type=APPEAL` via “הוספת שלב שכ״ט” (AddFeeEventModal).
  - **As stage code:** Used as a **rate code** in `fee_stage_rates` (seeded) and in the stage-billing modal (group “ערעור”). So APPEAL is both an enum value for one-off fee events and a code in the stage-billing code set. No bug, but the dual role is worth noting.
- **STAGE_BILLING:** Only created via POST `/cases/{id}/fees/stage-billing`. Amount comes from `breakdown_json`; `compute_fee_amount(STAGE_BILLING)` raises.

### 1.3 FeeStageRate model and seed

- **Table:** `fee_stage_rates`  
  **Columns:** `code` (PK, String 64), `amount_ils` (Numeric 14,2), `is_active` (Boolean, default true), `effective_from` (Date, nullable), `effective_to` (Date, nullable).  
  **Source:** `backend/app/models/fee_stage_rate.py`; migration `0010_...`.

- **Seed in migration (exact codes + amounts):**

| code                   | amount_ils |
|------------------------|------------|
| COURT_STAGE_1_DEFENSE  | 20000.00   |
| COURT_STAGE_2_DAMAGES  | 15000.00   |
| COURT_STAGE_3_EVIDENCE | 15000.00   |
| COURT_STAGE_4_PROOFS   | 15000.00   |
| COURT_STAGE_5_SUMMARIES| 10000.00   |
| AMENDED_DEFENSE_PARTIAL| 10000.00   |
| AMENDED_DEFENSE_FULL   | 20000.00   |
| THIRD_PARTY_NOTICE     | 10000.00   |
| ADDITIONAL_PROOF_HEARING | 1500.00  |
| DEMAND_FIX             | 5000.00   |
| DEMAND_HOURLY          | 700.00    |
| SMALL_CLAIMS_MANUAL    | 0.00      |
| APPEAL                 | 15000.00  |

- **Idempotency (PostgreSQL):** Seed uses `INSERT ... ON CONFLICT (code) DO UPDATE SET amount_ils = EXCLUDED.amount_ils, is_active = EXCLUDED.is_active`, so re-running upgrade is safe; existing rows are updated, missing rows inserted. Non-PostgreSQL (e.g. SQLite): plain INSERT per row; rerun can still fail on duplicate key.

### 1.4 effective_from / effective_to

- **Defined:** On `FeeStageRate` and in migration.
- **Used in logic:** **Nowhere.** `get_fee_stage_rates()` and `create_stage_billing_event()` only filter by `is_active`, not by date. Safe to ignore for current deploy.

---

## 2) API surface + request/response examples

Base URL assumed: `/api` (or as mounted). All fee/case endpoints require auth (e.g. `require_auth`).

### GET /fee-stage-rates

- **Route:** `backend/app/api/routes/fee_stage_rates.py` → mounted at `/fee-stage-rates` (router.py).
- **Auth:** Required.
- **Response:** `200` — list of `{ code: string, amount_ils: number }` (active only, ordered by code).

**Example response:**
```json
[
  { "code": "ADDITIONAL_PROOF_HEARING", "amount_ils": 1500 },
  { "code": "APPEAL", "amount_ils": 15000 },
  { "code": "COURT_STAGE_1_DEFENSE", "amount_ils": 20000 },
  ...
]
```

### GET /cases/{case_id}/fees/billed-codes

- **Route:** `backend/app/api/routes/fee_events.py` → under `/cases/{case_id}/fees`.
- **Auth:** Required.
- **Response:** `200` — list of strings (codes already billed in any STAGE_BILLING event for this case).

**Example response:**
```json
["COURT_STAGE_1_DEFENSE", "COURT_STAGE_2_DAMAGES"]
```

### POST /cases/{case_id}/fees/stage-billing

- **Route:** Same file.
- **Auth:** Required.
- **Request body:** `StageBillingCreate`:
  - `event_date`: date (YYYY-MM-DD)
  - `codes`: list of strings (min length 1) — full set of “performed to date”; only **new** codes are charged.
  - `adjustment`: optional `{ kind: "DISCOUNT" | "SURCHARGE", amount_ils: decimal >= 0, reason?: string }`. **Amount in ILS only (no percent).**
  - `confirm_zero_new_codes`: optional boolean, default false. If true, allows creating an event when there are no new codes (amount 0).

**Example request (delta-only, no adjustment):**
```json
{
  "event_date": "2024-07-01",
  "codes": ["COURT_STAGE_1_DEFENSE", "COURT_STAGE_2_DAMAGES", "APPEAL"]
}
```

**Example request (with discount):**
```json
{
  "event_date": "2024-07-01",
  "codes": ["COURT_STAGE_1_DEFENSE", "COURT_STAGE_2_DAMAGES", "APPEAL"],
  "adjustment": { "kind": "DISCOUNT", "amount_ils": 10, "reason": "הנחה" }
}
```

**Response:** `200` — `FeeEventOut` with `event_type: "STAGE_BILLING"`, `computed_amount_ils_gross`, `breakdown_json`, etc.

**Example response (excerpt):**
```json
{
  "id": 42,
  "event_type": "STAGE_BILLING",
  "event_date": "2024-07-01",
  "quantity": 1,
  "amount_override_ils_gross": null,
  "computed_amount_ils_gross": 14990,
  "amount_covered_by_credit_ils_gross": 0,
  "amount_due_cash_ils_gross": 14990,
  "breakdown_json": {
    "codes_selected": ["APPEAL", "COURT_STAGE_1_DEFENSE", "COURT_STAGE_2_DAMAGES"],
    "codes_already_billed": ["COURT_STAGE_1_DEFENSE", "COURT_STAGE_2_DAMAGES"],
    "new_codes": ["APPEAL"],
    "rates": { ... },
    "base_total_selected": "50000.00",
    "delta_total": "15000.00",
    "adjustment": { "kind": "DISCOUNT", "amount_ils": "10", "reason": "הנחה" },
    "final_delta_total": "14990.00"
  }
}
```

**Errors:**  
- `400` — At least one code required; unknown/inactive rate; no new codes to bill (unless `confirm_zero_new_codes`); discount exceeds new charges.  
- `404` — Case not found.

### Case create/import and legacy_fee_text

- **POST /cases** (create): Request body uses schema `CaseCreate` (`backend/app/schemas/case.py`). **`CaseCreate` does not include `legacy_fee_text` or `performed_fee_stage_codes`.** So the documented API does not accept them.  
- **Implementation:** `create_case()` in `cases.py` uses `getattr(payload, "legacy_fee_text", None)` (and similar for other import fields). So **import flow** (which builds a payload with `legacy_fee_text` and optionally `performed_fee_stage_codes`) does set them when creating a case. Direct API clients that add these keys to the JSON body could set them too, but they’re not part of the official Pydantic schema.
- **CaseOut / GET case:** All case read paths that use `to_case_out()` return `legacy_fee_text` and `performed_fee_stage_codes` (see `cases.py`). So **responses** include them.

---

## 3) Actual billing logic today

**Location:** `backend/app/services/fees.py` — `create_stage_billing_event()` and `get_billed_codes_for_case()`.

### 3.1 Full selected total vs delta-only

- **Delta-only.**  
  - `codes_already_billed = get_billed_codes_for_case(db, case_id)`  
  - `new_codes = [c for c in codes_selected if c not in already_billed]`  
  - `delta_total = sum(rate(c) for c in new_codes)`  
  - Event amount = adjustment applied to **delta_total** only (see below).  
  - One FeeEvent per request with `computed_amount_ils_gross = final_delta_total`.

### 3.2 How “already billed codes” is computed

- **Source:** All fee events for the case with `event_type == STAGE_BILLING` and non-null `breakdown_json`.  
- **Per event:** Union of `breakdown_json["new_codes"]` (current format) or `breakdown_json["codes"]` (legacy).  
- **Result:** Sorted list of unique codes that have ever been charged in a STAGE_BILLING event for this case.  
- **Code:** `get_billed_codes_for_case()` in `fees.py` (lines 130–146).

### 3.3 Adjustment

- **Schema:** `StageBillingAdjustment`: `kind` (DISCOUNT | SURCHARGE), `amount_ils` (required, ≥ 0), `reason` (optional). **No percent.**  
- **Calculation:**  
  - DISCOUNT: `final_delta_total = delta_total - amount_ils`. If `final_delta_total < 0` → **400** with detail `"Discount exceeds new charges"`.  
  - SURCHARGE: `final_delta_total = delta_total + amount_ils`.  
- **Stored in breakdown:** `adjustment` object with `kind`, `amount_ils`, `reason` only (no percent).

### 3.4 When user selects only already-billed codes

- **No override:** If `new_codes` is empty and `confirm_zero_new_codes` is false → **400** with detail `"No new codes to bill"`.  
- **With override:** If `confirm_zero_new_codes` is true → one STAGE_BILLING event is created with amount 0, `new_codes: []`, `delta_total: "0.00"`, `final_delta_total: "0.00"`.  
- **Persisted:** `case.performed_fee_stage_codes = codes_selected` is updated in both cases (when the request succeeds).

### 3.5 performed_fee_stage_codes

- **Set:** On every successful `create_stage_billing_event` to the **selected** list for that request (`codes_selected`).  
- **Used for billing logic:** **No.** “Already billed” is derived only from past STAGE_BILLING events’ `breakdown_json`.  
- **Used elsewhere:** Returned in CaseOut; available for future UX (e.g. pre-checking the modal). The frontend does **not** currently pre-fill the modal from `performed_fee_stage_codes`.

---

## 4) Frontend UX today (exact behavior)

### 4.1 Button location and label

- **Where:** Case detail → “שכ״ט” (fees) tab → in the “אירועי שכ״ט” card, left of “הוספת שלב שכ״ט”.  
- **Label:** **“חיוב משלבי ביצוע”** (secondary button).  
- **Action:** Opens `StageBillingModal` (`activeModal === 'stageBilling'`).

### 4.2 StageBillingModal

- **Title:** “חיוב מצטבר משלבי ביצוע”. Subtitle explains: select all performed stages to date; only stages not yet billed are charged; adjustment on the new amount is possible.
- **Data loaded on open:**  
  - GET `/fee-stage-rates` → checkboxes and amounts.  
  - GET `/cases/{id}/fees/billed-codes` → used to mark “כבר חויב” and compute `newCodes` / `deltaTotal`.
- **Grouping:** Codes are grouped as in `STAGE_BILLING_GROUPS`:  
  - שלבי בית משפט (1–5): COURT_STAGE_1_DEFENSE … COURT_STAGE_5_SUMMARIES  
  - בית משפט — נוסף: THIRD_PARTY_NOTICE, AMENDED_DEFENSE_PARTIAL, AMENDED_DEFENSE_FULL, ADDITIONAL_PROOF_HEARING  
  - מכתב דרישה: DEMAND_FIX, DEMAND_HOURLY  
  - תביעות קטנות: SMALL_CLAIMS_MANUAL  
  - ערעור: APPEAL  
- **Amounts:** Each code shows its rate from `/fee-stage-rates` next to the label (e.g. `(₪20,000)`).  
- **Totals shown:**  
  - “סה״כ נבחר (לפי תעריף)” = `baseTotalSelected` (sum of selected codes).  
  - “שלבים חדשים לחיוב” = list of new code labels + `deltaTotal`.  
  - “התאמה (אופציונלי) — סכום בש״ח בלבד”: kind (הנחה/תוספת) + one **amount (₪)** input + reason. **No percent.**  
  - “סכום לחיוב (לאחר התאמה)” = `finalDeltaTotal`.
- **Already-billed warning:** If any selected code is in `billedCodes`, an amber box says “שלבים שכבר חובו: … — לא יחויבו שוב.” and each such code has “כבר חויב” next to it.
- **When delta_total == 0:** Submit is disabled; button text shows “אין קודים חדשים לחיוב”. Optional checkbox “אישור: ליצור אירוע עם סכום 0 (תיעוד בלבד)” to allow creating a zero-amount event.
- **Submit payload:**  
  - `event_date`, `codes` (array of selected codes), `confirm_zero_new_codes` when applicable.  
  - `adjustment` only if user entered a numeric amount: `{ kind, amount_ils, reason }` (no percent).

### 4.3 FeesPanel — STAGE_BILLING events

- **Table:** Each row shows date, “שלב”, amount, כוסה בקרדיט, לתשלום, מקור.  
- **Stage column for STAGE_BILLING:** If `e.event_type === 'STAGE_BILLING'` and `e.breakdown_json` exists, label is either “חיוב מצטבר (N חדשים)” (using `new_codes.length`) or “חיוב מצטבר”. **Breakdown details (codes_selected, delta_total, adjustment) are not expanded in the table**; only the short label and amounts are shown.  
- **Source column:** “חדש” badge for all events in this list.

### 4.4 legacy_fee_text in FeesPanel

- **Placement:** If `legacyFeeText` is non-null, a **read-only** block is shown **above** the stats and the “אירועי שכ״ט” table.  
- **Title:** “פירוט חיוב שכ״ט (ייבוא)” with “לקריאה בלבד”.  
- **Content:** `legacyFeeText` in a paragraph, `whitespace-pre-wrap`.

---

## 5) Run instructions (local verification)

1. **Migrations**  
   From repo root:
   ```bash
   cd backend
   alembic upgrade head
   ```
   Expect: `0010_fee_stage_rates` applied; table `fee_stage_rates` and new columns on `cases` / `fee_events` present.

2. **Start backend + frontend**  
   - Backend: e.g. `uvicorn app.main:app --reload` (or your usual command).  
   - Frontend: e.g. `npm run dev` in `frontend/`.

3. **Create a case**  
   Use UI or:
   ```bash
   curl -X POST .../api/cases -H "Content-Type: application/json" -d '{"case_reference":"AUDIT-1","case_type":"COURT","open_date":"2024-01-01","deductible_ils_gross":5000}'
   ```

4. **First stage-billing event**  
   - Open case → שכ״ט → “חיוב משלבי ביצוע”.  
   - Select e.g. COURT_STAGE_1_DEFENSE and COURT_STAGE_2_DAMAGES.  
   - Submit.  
   **Expected:** One STAGE_BILLING event; `computed_amount_ils_gross = 35000`; `breakdown_json.new_codes` = those two; `breakdown_json.delta_total = "35000.00"`; `breakdown_json.codes_already_billed = []`. Case’s `performed_fee_stage_codes` = those two codes.

5. **Second stage-billing event (one new + one already billed)**  
   - Reopen modal.  
   - Select same two + APPEAL.  
   - Submit (no adjustment).  
   **Expected:** One new STAGE_BILLING event; `computed_amount_ils_gross = 15000` (APPEAL only); `breakdown_json.new_codes = ["APPEAL"]`; `breakdown_json.codes_already_billed` includes the two from step 4; `breakdown_json.delta_total = "15000.00"`.

6. **Check DB**  
   - `fee_events`: two rows with `event_type = 'STAGE_BILLING'`; first amount 35000, second 15000.  
   - `fee_events.breakdown_json`: has `codes_selected`, `codes_already_billed`, `new_codes`, `rates`, `base_total_selected`, `delta_total`, `adjustment` (null or object), `final_delta_total`.  
   - `cases.performed_fee_stage_codes`: after second submit, sorted list of three codes.

---

## 6) Known issues / mismatches vs desired spec

### A) What works now

- Delta-only billing: only new codes are charged; one event per request; amount = `final_delta_total`.  
- “Already billed” from STAGE_BILLING events’ `breakdown_json` (new_codes or legacy codes).  
- Adjustment: ILS only (no percent); DISCOUNT/SURCHARGE; 400 “Discount exceeds new charges” when discount > delta_total.  
- 400 “No new codes to bill” when selection is subset of already billed (unless `confirm_zero_new_codes`).  
- Breakdown persisted with all required fields; `performed_fee_stage_codes` updated on submit.  
- Frontend: base total, delta total, final total, amount-only adjustment, “אין קודים חדשים לחיוב”, billed-codes fetch and warning.  
- legacy_fee_text: stored on case (create via import), returned in CaseOut, shown read-only in FeesPanel.  
- FeeStageRate: table + seed; GET `/fee-stage-rates`; used for modal and for stage-billing computation.

### B) What’s missing / wrong

- **CaseCreate schema:** Does not include `legacy_fee_text` (or `performed_fee_stage_codes`). So OpenAPI/docs don’t show them for POST /cases. Behavior is correct for import (getattr); only documentation/consistency is lacking.  
- **Migration seed idempotency (resolved):** Migration 0010 uses UPSERT on PostgreSQL (`ON CONFLICT (code) DO UPDATE`); re-running `alembic upgrade head` after 0010 is already applied will try to INSERT the same `fee_stage_rates` rows again and fail on duplicate key. On Render, first deploy is fine; re-run of same revision can break unless you use “INSERT … ON CONFLICT DO NOTHING” or skip seed if table already has rows.  
- **APPEAL dual role:** APPEAL exists both as FeeEventType (single fee event) and as a stage code in the modal. This is intentional but can confuse: “ערעור” in the modal uses the rate from `fee_stage_rates`, not from `compute_fee_amount(APPEAL)` (they match today).

### C) Screenshots-like description of UI flow

1. Case detail → שכ״ט tab. If case has `legacy_fee_text`, a read-only “פירוט חיוב שכ״ט (ייבוא)” block appears at top.  
2. Below that: three mini-stats (סה״כ שכ״ט, כוסה בקרדיט, לתשלום).  
3. Card “אירועי שכ״ט” with two buttons: “חיוב משלבי ביצוע” (secondary) and “הוספת שלב שכ״ט” (primary).  
4. Click “חיוב משלבי ביצוע” → modal “חיוב מצטבר משלבי ביצוע” with date, grouped checkboxes (with amounts and “כבר חויב” where applicable), base total, “שלבים חדשים לחיוב” + delta total, adjustment (amount ₪ + reason only), final total. If no new codes: disabled submit + “אין קודים חדשים לחיוב” and optional zero-amount confirm.  
5. After submit, new row in table: date, “חיוב מצטבר (N חדשים)” or “חיוב מצטבר”, amount, credit, due, “חדש”. No expandable breakdown in the table.

### D) Concrete next changes before deploy (if any)

- **Optional but recommended:** Make migration 0010 seed idempotent (e.g. insert only when row for `code` does not exist, or use a one-off “seed” step that checks before insert).  
- **Optional:** Add `legacy_fee_text` (and if desired `performed_fee_stage_codes`) to `CaseCreate` so OpenAPI reflects import usage and direct API can set them consistently.  
- **No change required** for delta-only billing, adjustment (ILS only), or “No new codes” / “Discount exceeds new charges” behavior; they match the spec.

### E) Exact test plan checklist

- [ ] Migrations: `alembic upgrade head` on clean DB → 0010 applied; `fee_stage_rates` has 13 rows; cases/fee_events have new columns.  
- [ ] GET `/fee-stage-rates` → 200, list of { code, amount_ils }, includes APPEAL and COURT_STAGE_1_DEFENSE.  
- [ ] GET `/cases/{id}/fees/billed-codes` → 200, [] for new case.  
- [ ] POST stage-billing: select two codes, no adjustment → 200; one event; amount = sum of two rates; breakdown has new_codes = those two, delta_total = same sum.  
- [ ] POST stage-billing again with same two codes → 400 “No new codes to bill”.  
- [ ] POST stage-billing with same two + one new code, no adjustment → 200; amount = rate of new code only; breakdown new_codes = [new code].  
- [ ] POST stage-billing with discount amount_ils = 10 on one new code → 200; amount = rate - 10; breakdown final_delta_total correct.  
- [ ] POST stage-billing with discount > delta_total → 400, detail “Discount exceeds new charges”.  
- [ ] POST stage-billing with same codes as already billed + `confirm_zero_new_codes: true` → 200; event amount 0; new_codes [].  
- [ ] Case with legacy_fee_text from import → GET case returns it; FeesPanel shows read-only block.  
- [ ] STAGE_BILLING event in list → row shows correct amount and “חיוב מצטבר (N חדשים)”; GET /cases/{id}/fees/ returns breakdown_json for that event.

---

**Conclusion:** Behavior matches the desired spec (delta-only, adjustment ILS-only, errors and persistence). Migration 0010 seed is idempotent on PostgreSQL (UPSERT). Safe to deploy to Render after validating the test plan.

### Verifying idempotent seed locally (PostgreSQL)

1. From `backend/`: `alembic upgrade head` (ensures 0010 applied and `fee_stage_rates` seeded).
2. Run again: `alembic upgrade head` — should complete without error (no duplicate key).
3. Optionally: `alembic downgrade -1` then `alembic upgrade head` to confirm downgrade/upgrade cycle; or run `SELECT count(*) FROM fee_stage_rates;` before and after the second `upgrade head` — count stays 13, rows are updated in place.

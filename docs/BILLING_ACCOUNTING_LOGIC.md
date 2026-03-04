# TeremFlow: Billing & Accounting Logic (High-Level)

This document explains how attorney fees, deductible/excess, expenses, and retainer are intended to work end-to-end, based on the current codebase and docs. Code paths and data models are cited; items not implemented are labeled **TBD / not implemented**.

---

## A) One-Page Conceptual Model

### Entities

| Entity | Purpose |
|--------|--------|
| **Case** | One matter. Holds: deductible (ILS), FX fields if set in USD, retainer anchor/snapshots, historical_fee_stages (import-only), legacy_fee_text, performed_fee_stage_codes. |
| **FeeEvent** | One attorney-fee charge (שכ״ט). Type (stage/APPEAL/STAGE_BILLING), date, computed amount, and how much is covered by retainer vs due in cash. STAGE_BILLING stores breakdown in `breakdown_json`. |
| **Expense** | One non-attorney expense (הוצאות). Amount, category, payer (CLIENT_DEDUCTIBLE or INSURER). Can be split across deductible/insurer when it exceeds remaining deductible. |
| **RetainerAccrual** | One month’s retainer “invoice” (fixed amount per month from anchor, VAT-dependent). Tracked as accrued; `is_paid` set when payments cover it (oldest-first). |
| **RetainerPayment** | Cash received for retainer. Sum of payments = “retainer credit” applied chronologically to fee events. |

### Flows

1. **Attorney fees (שכ״ט)**  
   Created only by: (a) “הוספת שלב שכ״ט” → one FeeEvent per type/date/override, amount from `compute_fee_amount()` or override; (b) “חיוב משלבי ביצוע” → one STAGE_BILLING FeeEvent, amount = delta (new codes only) ± adjustment (ILS only). No draft state: each action creates a real, persisted FeeEvent. After any new fee or new retainer payment, **retainer credit** is reapplied: fee events ordered by `(event_date, id)`; a single pool (sum of RetainerPayment amounts) is applied in order; each event gets `amount_covered_by_credit_ils_gross` and `amount_due_cash_ils_gross` updated.

2. **Deductible (השתתפות עצמית)**  
   Stored on Case as `deductible_ils_gross` (always in ILS; if entered in USD, converted at open via BOI and stored). **Consumed only by expenses** where `payer = CLIENT_DEDUCTIBLE` (sum of such Expense amounts). **Fee events do not consume deductible.** `deductible_remaining = deductible_ils_gross - consumed_on_deductible`.

3. **Excess remaining (יתרת השתתפות עצמית – Excel P)**  
   `P = M - J`. M = `case.deductible_ils_gross`. J = retainer (snapshot + payments) + expenses (snapshot + other). “Other” = sum of Expense amounts where `payer = CLIENT_DEDUCTIBLE` and `category != ATTORNEY_FEE`. So attorney-fee expenses are excluded from J; fees are in FeeEvent, not in Expense for this formula.

4. **Expenses**  
   Recorded as Expense rows (event-based). On add, if payer = CLIENT_DEDUCTIBLE and amount would exceed deductible remaining, the amount is split: one Expense row on deductible (up to remaining), one on INSURER (rest). Expenses with payer = INSURER do not consume deductible.

5. **Retainer**  
   **Monthly accrual:** Per case, from `retainer_anchor_date` (or first month after `retainer_snapshot_through_month` if snapshot exists). Fixed 945 ILS net + VAT (17% to Dec 2024, 18% from Jan 2025) → one RetainerAccrual per month. Accruals are created by `ensure_accruals_up_to` (on case create/update and via daily roll-forward). **Payments:** RetainerPayment records; sum = credit pool. Credit is applied to **fee events only** (chronological), not to expenses. **Insufficient retainer:** No separate “debt” or “carryover” entity; each fee event has `amount_due_cash_ils_gross`; if credit runs out, later events get 0 covered and full amount due.

---

## B) Calculation Rules

- **Fees total (סה״כ שכ״ט)**  
  `sum(FeeEvent.computed_amount_ils_gross)` for the case.  
  Source: `GET /cases/{id}/fees/` → sum in frontend (`CaseDetailsPage.tsx` FeesPanel).

- **Fees covered by retainer (כוסה בקרדיט)**  
  `sum(FeeEvent.amount_covered_by_credit_ils_gross)`.  
  Source: same fee events; backend sets these in `apply_retainer_credit()`.

- **Fees due in cash (לתשלום במזומן)**  
  `sum(FeeEvent.amount_due_cash_ils_gross)`.  
  Source: same fee events.

- **Deductible remaining**  
  `deductible_ils_gross - sum(Expense.amount_ils_gross)` where `Expense.payer = CLIENT_DEDUCTIBLE`.  
  Source: `get_case_deductible_remaining()` in `expenses.py`; **not currently shown in main UI** (only excess is).

- **Excess remaining (יתרת השתתפות עצמית)**  
  `max(0, M - J)` where  
  `M = case.deductible_ils_gross`,  
  `J = retainer_total + expenses_snapshot_ils_gross + other_expenses`,  
  `retainer_total = retainer_snapshot_ils_gross + sum(RetainerPayment.amount_ils_gross)` (if snapshot set), else `sum(RetainerPayment)`,  
  `other_expenses = sum(Expense.amount_ils_gross)` where `payer = CLIENT_DEDUCTIBLE` and `category != ATTORNEY_FEE`.  
  Source: `get_case_excess_remaining()` in `expenses.py`; returned in `to_case_out()` as `excess_remaining_ils_gross`.

- **Retainer credit balance (יתרת קרדיט)**  
  `max(0, retainer_paid_total - retainer_applied_to_fees_total)`.  
  Source: `retainer_summary()` in `retainer.py` → `GET /cases/{id}/retainer/summary`.

- **Retainer applied to fees**  
  `sum(FeeEvent.amount_covered_by_credit_ils_gross)`.  
  Source: same as “fees covered by retainer”.

---

## C) What’s Implemented Today vs Missing/TBD

### Implemented

- **Fee events:** Add single fee (type, date, quantity, override); STAGE_BILLING (delta-only, ILS adjustment, breakdown, performed_fee_stage_codes).
- **Fee amounts:** Hardcoded mapping in `compute_fee_amount()`; STAGE_BILLING from `FeeStageRate` + breakdown.
- **Retainer credit application:** Chronological by `(event_date, id)`; single pool = sum(RetainerPayment); persisted on each FeeEvent (`amount_covered_by_credit_ils_gross`, `amount_due_cash_ils_gross`).
- **Retainer accruals:** Fixed monthly amount (945+VAT), per case from anchor/snapshot; roll-forward job; payments allocated to accruals oldest-first; `is_paid` on accruals.
- **Retainer payments:** Stored; after add, `allocate_payments_to_accruals` + `apply_retainer_credit`.
- **Deductible:** Stored (ILS or from USD at open); consumed only by expenses (CLIENT_DEDUCTIBLE); `get_case_deductible_remaining`.
- **Excess remaining:** `get_case_excess_remaining` (M - J) with snapshot + payments + expenses (ATTORNEY_FEE excluded); returned in CaseOut and shown in UI as “יתרת השתתפות עצמית”.
- **Expenses:** Add with payer (CLIENT_DEDUCTIBLE/INSURER); auto-split when exceeding deductible; categories include ATTORNEY_FEE (excluded from “other” in J).
- **Excel snapshots:** `retainer_snapshot_ils_gross`, `retainer_snapshot_through_month`, `expenses_snapshot_ils_gross` stored and used in excess (J) and in accrual start month; historical_fee_stages and legacy_fee_text display-only.

### Not implemented / TBD

- **Lifecycle (draft → charge → paid → closed):** No draft or “charge” state; creating a fee event is the charge. No explicit “paid” on fee events (only “covered by retainer” vs “due cash”). **TBD:** marking fees as paid, closing a case’s billing.
- **Deductible remaining in UI:** Calculated in code but not shown in case detail; only excess remaining is. **TBD:** show deductible remaining if desired.
- **Retainer insufficient:** No separate “debt” or “carryover”; just `amount_due_cash_ils_gross` per event. No automatic reminder or aging. **TBD:** if needed.
- **Expenses affecting retainer/fees:** Expenses do not reduce retainer credit; retainer only offsets fee events. **By design.**
- **Monthly “charge” of retainer:** Accruals exist (invoices/due dates); there is no automatic “charge” event that creates a fee or a payment. Payments are manual. **TBD:** if automatic monthly charge is required.

---

## D) Most Important Code Locations

| # | Path | Role |
|---|------|------|
| 1 | `backend/app/services/fees.py` | `compute_fee_amount`, `apply_credit_to_amounts`, `_retainer_paid_total`, `apply_retainer_credit`, `add_fee_event`, `create_stage_billing_event`, `get_billed_codes_for_case` |
| 2 | `backend/app/services/retainer.py` | `retainer_gross_for_month`, `get_retainer_anchor_date`, `ensure_accruals_up_to`, `allocate_payments_to_accruals`, `retainer_summary` |
| 3 | `backend/app/services/expenses.py` | `_consumed_on_deductible`, `get_case_deductible_remaining`, `get_case_excess_remaining`, `add_expense` (split over deductible) |
| 4 | `backend/app/services/deductible.py` | `deductible_remaining`, `split_amount_over_deductible` |
| 5 | `backend/app/models/case.py` | Case: deductible_ils_gross, retainer_anchor_date, retainer_snapshot_ils_gross, retainer_snapshot_through_month, expenses_snapshot_ils_gross |
| 6 | `backend/app/models/fee_event.py` | FeeEvent: event_type, computed_amount_ils_gross, amount_covered_by_credit_ils_gross, amount_due_cash_ils_gross, breakdown_json |
| 7 | `backend/app/models/expense.py` | Expense: amount_ils_gross, category, payer (CLIENT_DEDUCTIBLE / INSURER) |
| 8 | `backend/app/models/retainer.py` | RetainerAccrual (month, amount, is_paid), RetainerPayment (payment_date, amount_ils_gross) |
| 9 | `backend/app/services/cases.py` | `to_case_out()` → includes `excess_remaining_ils_gross` via `get_case_excess_remaining()` |
| 10 | `frontend/src/pages/CaseDetailsPage.tsx` | FeesPanel (totals from fee events), RetainerPanel (summary from `/retainer/summary`), Overview (excess_remaining_ils_gross, snapshots) |

---

## 1) Attorney Fees (שכר טרחה) — Detail

**What creates charges:**  
- **Single fee:** “הוספת שלב שכ״ט” → `POST /cases/{id}/fees/` with `FeeEventCreate` (event_type, event_date, quantity, amount_override_ils_gross). Amount from `compute_fee_amount()` in `fees.py` (hardcoded map) or override.  
- **Stage billing:** “חיוב משלבי ביצוע” → `POST /cases/{id}/fees/stage-billing` with codes + optional adjustment (ILS only). One FeeEvent (STAGE_BILLING); amount = delta (new codes only) ± adjustment; breakdown in `breakdown_json`; `case.performed_fee_stage_codes` updated.

**Lifecycle:**  
There is no draft/charge/paid/closed workflow. Each action creates a **real** FeeEvent. “Paid” is represented only by retainer credit (portion covered) and by `amount_due_cash_ils_gross` (remaining due). **TBD:** explicit “paid” or “closed” state if required.

**Fee events and balances:**  
- Each FeeEvent has `computed_amount_ils_gross`, `amount_covered_by_credit_ils_gross`, `amount_due_cash_ils_gross`.  
- After any new fee or retainer payment, `apply_retainer_credit(db, case_id)` runs: fee events sorted by `(event_date, id)`, credit = sum(RetainerPayment); credit applied in order; covered/due updated per event and committed.  
- Reporting: list fee events; totals = sums of the three fields above.

**STAGE_BILLING:**  
Selecting codes in the modal and submitting creates **one real** FeeEvent. Amount = sum of rates for **new** codes only (codes not already billed in prior STAGE_BILLING events), plus optional DISCOUNT/SURCHARGE in ILS. Rates from `FeeStageRate` table. No percent; discount cannot exceed new charges.

---

## 2) Deductible / Excess (השתתפות עצמית / אקסס)

**Model:**  
- Case has `deductible_ils_gross` (always stored in ILS). If user enters USD at open, BOI rate is used and result stored; `deductible_usd`, `fx_rate_usd_ils`, `fx_date_used`, `fx_source` kept for audit.

**Use in calculations:**  
- **Deductible remaining:** Threshold for expenses. `consumed = sum(Expense.amount_ils_gross)` where `payer = CLIENT_DEDUCTIBLE`. `remaining = deductible_ils_gross - consumed` (capped at 0). Used when adding an expense to split amount “on deductible” vs “on insurer”.  
- **Excess remaining (P = M - J):** M = deductible. J = what “counts against” the deductible for display: retainer (snapshot + payments) + expense snapshot + other expenses (excluding ATTORNEY_FEE category). So it is “how much of the deductible is still left to be used” in the sense of J.

**Expenses vs fees:**  
- **Expenses** (Expense rows) consume deductible when `payer = CLIENT_DEDUCTIBLE`; they are the only thing that reduces “deductible remaining”.  
- **Fees** (FeeEvent) do **not** consume deductible. They are offset by retainer credit and the rest is “due in cash”.

**Deductible balance:**  
- **Computed:** `get_case_deductible_remaining()` in `expenses.py`.  
- **Shown:** Not in main case UI today. Only “יתרת השתתפות עצמית” (excess_remaining_ils_gross) is shown, from `get_case_excess_remaining()`.

---

## 3) Expenses (הוצאות)

**Vs fees:**  
- **Fees** = attorney fees (שכ״ט), stored as FeeEvent.  
- **Expenses** = non-attorney (or attorney recorded as expense), stored as Expense; have category (EXPERT, MEDICAL_INFO, INVESTIGATOR, FEES, OTHER, or ATTORNEY_FEE) and payer (CLIENT_DEDUCTIBLE or INSURER).

**Recording:**  
- Event-based: `POST /cases/{id}/expenses` → `add_expense()`. One or two Expense rows if split.  
- **Impact on deductible:** Only `payer = CLIENT_DEDUCTIBLE` amounts are summed for `_consumed_on_deductible`.  
- **Impact on excess (J):** Sum of Expense where `payer = CLIENT_DEDUCTIBLE` and `category != ExpenseCategory.ATTORNEY_FEE` (“other” expenses). So ATTORNEY_FEE category is excluded from J (fees are in FeeEvent, not in this sum).

**Types:**  
- ExpenseCategory: ATTORNEY_FEE, EXPERT, MEDICAL_INFO, INVESTIGATOR, FEES, OTHER. All use same payer and same split logic; only ATTORNEY_FEE is excluded from “other” in `get_case_excess_remaining`.

---

## 4) Retainer (ריטיינר)

**Monthly concept:**  
- **Yes.** Stored per case: `retainer_anchor_date` (July or Jan from open_date), `retainer_snapshot_ils_gross`, `retainer_snapshot_through_month`.  
- **Amount:** Fixed 945 ILS net × (1 + VAT). VAT 17% until Dec 2024, 18% from Jan 2025 (`retainer.py`: `retainer_gross_for_month()`).  
- **When “charged”:** Not charged automatically. **Accruals** are created by `ensure_accruals_up_to` (on case create/update and daily roll-forward). Each accrual has invoice_date, due_date, amount; no automatic payment or fee event. **TBD:** if “charge” means creating an invoice or a fee.

**Payments:**  
- `RetainerPayment`: payment_date, amount_ils_gross. Sum = total retainer cash. After add payment: `allocate_payments_to_accruals` (mark accruals paid oldest-first), then `apply_retainer_credit` (reapply credit to fee events).

**Credit application:**  
- Credit = sum(RetainerPayment.amount_ils_gross). Applied **only to fee events**, in chronological order (`event_date`, `id`). Each event gets (covered, due); credit is decremented by covered amount. **Expenses are not offset by retainer.**

**Insufficient retainer:**  
- No separate “debt” entity. When credit is exhausted, later fee events get `amount_covered_by_credit_ils_gross = 0` and `amount_due_cash_ils_gross = computed_amount_ils_gross`. “Cash due” is the sum of these. No carryover or aging implemented.

---

## 5) Anchors / Snapshots from Excel

- **retainer_snapshot_ils_gross (Excel H):** “Total retainer paid to date” at import. Used in **excess (J):** `retainer_total = retainer_snapshot_ils_gross + sum(RetainerPayment)` so past + future retainer are both counted.  
- **retainer_snapshot_through_month:** Last month included in H. **Accruals** start from the **next** month (`_accrual_start_month` in `retainer.py`). If snapshot set but through_month missing, roll-forward skips the case (backward compat).  
- **expenses_snapshot_ils_gross (Excel I):** Historical non-attorney expenses. Added to J in `get_case_excess_remaining` (`expenses_snapshot + other_expenses`).  
- **historical_fee_stages:** Imported list of FeeEventType codes. **Display-only** in UI (“שלבי שכ״ט עבר”); not used in balances or retainer.  
- **legacy_fee_text:** Free text from Excel. **Display-only.**

---

## 6) Outputs & UI — Source of Truth

| Shown in UI | Source-of-truth calculation | Backend / data |
|-------------|-----------------------------|----------------|
| סה״כ שכ״ט | Sum of `FeeEvent.computed_amount_ils_gross` | `GET /cases/{id}/fees/` → frontend sum |
| כוסה בקרדיט | Sum of `FeeEvent.amount_covered_by_credit_ils_gross` | Same |
| לתשלום במזומן | Sum of `FeeEvent.amount_due_cash_ils_gross` | Same |
| יתרת השתתפות עצמית | `get_case_excess_remaining(case)` → M - J | `to_case_out()` → `excess_remaining_ils_gross` |
| נצבר (ריטיינר) | Sum of `RetainerAccrual.amount_ils_gross` | `retainer_summary()` → `retainer_accrued_total_ils_gross` |
| יתרת קרדיט | `paid_total - applied_to_fees_total` (≥ 0) | `retainer_summary()` → `retainer_credit_balance_ils_gross` |
| שכ״ט ששולם עד כה / חודש סיום / הוצאות ששולמו | Case fields | `case.retainer_snapshot_ils_gross`, `retainer_snapshot_through_month`, `expenses_snapshot_ils_gross` |

Deductible remaining is computed in code (`get_case_deductible_remaining`) but **not** currently displayed in the case UI.

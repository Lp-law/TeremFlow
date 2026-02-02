# TeremFlow — VERIFICATION & IMPORT-READINESS REPORT

**Date:** 2 February 2026  
**Mode:** Verification only (no code execution assumed)  
**Source of truth:** IMPORT_TEREMFLOW2 (CSV UTF-8) semantics per user specification

---

## STEP 1 — ARCHITECTURE VERIFICATION

### 1.1 How `retainer_snapshot_ils_gross` is used

- **Storage:** Stored on `Case`, nullable. When set, represents historical retainer (Excel Column H) paid/accrued before system usage.
- **In excess calculation:** Counts in J:  
  `J = other_expenses_total + retainer_snapshot_ils_gross + retainer_accrued_after_snapshot`
- **Behavior when snapshot exists:** `retainer_accrued_after_snapshot` = sum of `RetainerAccrual.amount_ils_gross` (system-created accruals). So for a fresh import with snapshot, retainer_after = 0.
- **Behavior when snapshot is NULL:** `retainer_accrued_after_snapshot` = sum of `RetainerPayment.amount_ils_gross` (preserves old behavior for new cases).

### 1.2 How `excess_remaining_ils_gross` is computed

```
excess_remaining = max(0, deductible_ils_gross - J)
where J = other_expenses_total + (retainer_snapshot_ils_gross or 0) + retainer_after
```

- **other_expenses_total:** Sum of `Expense.amount_ils_gross` where `payer = CLIENT_DEDUCTIBLE` and `category != ATTORNEY_FEE`.
- **retainer_after:** Sum of accruals (if snapshot exists) or payments (if no snapshot).

### 1.3 Match to Excel logic

**Excel:** `P = M − J` where `J = H + I` (H = retainer paid, I = non-attorney expenses)

**System:** `excess_remaining = M − (other_expenses + retainer_snapshot + retainer_after)`

- **retainer_snapshot** = H — correct when imported.
- **other_expenses** = I — correct when I is represented by Expense rows.
- **retainer_after** = 0 for fresh import with snapshot — correct.

**Gap:** There is no way to import I (total non-attorney expenses) as a snapshot. Today, I can only come from Expense rows. At import, we create only Cases, not Expenses, so `other_expenses_total = 0`. J is therefore understated by I, and P is overstated. **For P = M − J to match Excel, we need I in J at import time.**

---

## STEP 2 — GAP ANALYSIS AGAINST ORIGINAL GOAL

**Goal:** “No money surprises. No lost expenses. One clear picture.”

### Does the system guarantee it?

**Partially.** Gaps:

1. **Column I not imported**  
   I (total non-attorney expenses) is not imported. Excess is computed as if I = 0 for imported cases, so P is wrong and money appears “unspent.”

2. **Accruals created for imported cases**  
   `create_case` always calls `ensure_accruals_up_to`, which creates accruals from anchor through today. For imported cases with `retainer_snapshot`, those accruals overlap H. We then have both H and accruals, so J is overstated and P is understated. **When `retainer_snapshot` is set, accrual creation must be skipped at import.**

3. **Column H not wired in import**  
   `retainer_snapshot_ils_gross` exists in the model and API but is not mapped in `import_excel.py`. Column H is not imported.

4. **Anchor vs open date**  
   Import supports `retainer_anchor_date` (Column C). Logic treats anchor as the start of retainer counting, which matches the spec. `open_date` is still required; if Excel has no open date, a fallback or validation rule is needed.

---

## STEP 3 — IMPORT_TEREMFLOW2 MAPPING

| Excel Col | Meaning | API field | Model field | Status |
|-----------|---------|-----------|-------------|--------|
| A | Case ref / name | case_reference | case.case_reference | Imported |
| B | Branch / clinic | branch_name | case.branch_name | Imported |
| C | Retainer anchor date | retainer_anchor_date | case.retainer_anchor_date | Imported; **MUST validate** (date, not open_date) |
| D | Months from Jan 2025 | — | — | **Ignored** (derived in Excel) |
| E | Months up to Dec 2024 | — | — | **Ignored** (derived in Excel) |
| F | Gross retainer (18%) | — | — | **Ignored** (derived) |
| G | Gross retainer (17%) | — | — | **Ignored** (derived) |
| H | Total retainer paid to date | retainer_snapshot_ils_gross | case.retainer_snapshot_ils_gross | **NOT imported**; MUST add |
| I | Total non-attorney expenses | — | — | **NOT imported**; no field exists; MUST add (e.g. expenses_snapshot_ils_gross) |
| J | H + I | — | — | **Derived** (not stored) |
| K | Theoretical fees (stages) | — | — | **Ignored** for case import (fee events separate) |
| L | Theoretical fees | — | — | **Ignored** |
| M | Deductible / excess | deductible_ils_gross | case.deductible_ils_gross | Imported |
| N | — | — | — | Per Excel definition |
| P | Remaining excess | — | — | **Derived** (excess_remaining_ils_gross) |
| open_date | Case open date | open_date | case.open_date | Imported; may differ from C |

### Required validations

- **C (retainer_anchor_date):** Valid date; used as anchor for retainer months.
- **H (retainer_snapshot):** Non‑negative decimal; stored as snapshot, not recomputed.
- **M (deductible):** Non‑negative decimal.
- **I (if added):** Non‑negative decimal.

---

## STEP 4 — SAFE IMPORT STRATEGY

### Order of operations

1. Parse CSV/Excel; validate headers and required columns (A, B, C, M, H, I, open_date, case_type).
2. For each row:
   - Validate C, H, I, M, open_date.
   - Create Case with: case_reference, branch_name, retainer_anchor_date, open_date, deductible_ils_gross, retainer_snapshot_ils_gross, expenses_snapshot_ils_gross (once field exists).
   - **Do not** call `ensure_accruals_up_to` when `retainer_snapshot_ils_gross` is set.
3. Commit per case (or batch with rollback on error).

### Required validations

- case_reference non-empty and unique
- retainer_anchor_date valid date
- deductible_ils_gross ≥ 0
- retainer_snapshot_ils_gross ≥ 0 (if present)
- expenses_snapshot_ils_gross ≥ 0 (if field exists)
- case_type in {COURT, DEMAND_LETTER, SMALL_CLAIMS}
- open_date valid date

### Failure conditions that must abort import

- Missing required columns
- Duplicate case_reference
- Invalid date format
- Invalid numeric format or negative values where disallowed

### What must never be auto-generated during import

- **Retainer accruals** when `retainer_snapshot_ils_gross` is set (would duplicate H)
- **Retainer payments** from H (H is a snapshot, not a payment log)
- **Expense rows** from I unless we explicitly choose to split I into line items (snapshot approach is simpler)

---

## STEP 5 — FINAL VERDICT

### **B. READY WITH 1–2 FIXES**

### Fix 1 (required): Add and use `expenses_snapshot_ils_gross`

- Add `expenses_snapshot_ils_gross` (Decimal, nullable) to `Case`.
- In `get_case_excess_remaining`, use:  
  `other_expenses_total = expenses_snapshot_ils_gross OR sum(Expense rows)`  
  (snapshot overrides when present, same pattern as retainer).
- Import Column I into `expenses_snapshot_ils_gross`.
- Add migration for the new column.

### Fix 2 (required): Skip accruals when snapshot exists

- In `create_case`, when `retainer_snapshot_ils_gross` is not None, do **not** call `ensure_accruals_up_to`.
- Ensures H is not double-counted with system accruals.

### Fix 3 (required): Map Column H in import

- Add `retainer_snapshot_ils_gross` (and Hebrew equivalents) to `KNOWN_COLUMNS` in `import_excel.py`.
- Map Column H into `retainer_snapshot_ils_gross` in the import payload.

---

## Summary

| Item | Status |
|------|--------|
| retainer_snapshot in excess formula | ✓ Correct |
| excess_remaining = M − J structure | ✓ Matches when I and H are present |
| Column H import mapping | ✗ Missing |
| Column I import / expenses snapshot | ✗ Missing (no field) |
| Skip accruals when snapshot set | ✗ Not implemented |
| VAT-aware retainer amounts | ✓ Implemented |
| retainer_anchor_date support | ✓ Implemented |

**Verdict: B. READY WITH 1–2 FIXES** (three concrete fixes listed above).

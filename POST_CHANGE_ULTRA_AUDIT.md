# Post-Change Ultra Audit — TeremFlow

**Date:** 2025-02-02  
**Scope:** Backend + frontend after unified model, overrides, retainer freeze, expenses total, fee-event/case soft delete, dashboard, exports, warnings, import preview, CSRF fixes.  
**Purpose:** Regression verification and production readiness (Render prod). Audit only; no new features except fixes for discovered issues.

---

## 1) Executive verdict: **SAFE** (with one P1 fix applied)

- **Unified financial model:** Single source of truth (`get_unified_summary` / `unified_excess_remaining_ils`) is used consistently by cases list, overview-summary, deductible/summary, warnings, analytics, and case export. No legacy snapshot fields used for these totals in UI.
- **Overrides:** Stored as decimal strings in JSONB; parsing is safe; clearing via `null` works; frontend enforces non-negative for all except `fee_diff_override`. Backend does not validate non-negative for non–fee_diff overrides (P2 recommendation).
- **Retainer freeze & dates:** Freeze and PATCH dates behave correctly; accruals and charged months respect `get_effective_end_date` (freeze).
- **Expenses total:** PATCH updates `case.expenses_total_ils_gross`; unified uses it; Overview/Excess refresh after save.
- **Fees / soft delete:** Fee events exclude deleted by default; DELETE requires reason; totals and billed-codes exclude deleted.
- **Case soft delete:** List, GET, export, analytics, accrual jobs exclude deleted cases; bulk-update only affects non-deleted.
- **Security:** All mutations use `apiFetch`/`apiDownload` with `X-CSRF-Token`. **GET /admin/export-backup** was available to any authenticated user; **fixed to admin-only** (see Findings).

**Remaining risk:** Backup export loads full tables into memory (P1 note for very large DBs). Backend override validation for ≥0 (except fee_diff) is recommended (P2).

---

## 2) Findings table

| ID | Severity | Area | Finding | Reproduction | File/Function |
|----|----------|------|---------|-------------|----------------|
| F1 | P1 (fixed) | AuthZ | GET /admin/export-backup was protected only by `require_auth`; any authenticated user could download full DB backup. | As non-admin user, GET /admin/export-backup → 200 + ZIP. | `backend/app/api/routes/admin.py` — `admin_export_backup` used `require_auth`. **Fix applied:** use `require_admin`; added `require_admin` in `backend/app/api/deps.py`. |
| F2 | P2 | Overrides | Backend does not reject negative values for money overrides other than `fee_diff_override`. Frontend blocks them; API could still accept negative e.g. `excess_remaining_override`. | Send PATCH /cases/{id}/overrides with `{"excess_remaining_override": -100}` → stored. | `backend/app/services/cases.py` — `update_case_manual_overrides`; no validation. **Recommendation:** In `update_case_manual_overrides`, for keys in `_MONEY_OVERRIDE_KEYS` except `fee_diff_override`, reject if value < 0 (return 400). |
| F3 | P1 (info) | Perf | Backup export builds ZIP by loading each table fully into memory (`db.execute(select(table)).mappings().all()`). Very large DBs could cause memory pressure. | Export backup with many cases/expenses/fee_events. | `backend/app/api/routes/backups.py` — `build_backup_zip`. **Recommendation:** For scale, consider streaming rows per table or chunking; document limits. |

No P0 issues found. All other areas (unified consumers, override precedence, month counting, freeze, expenses total, fee/case soft delete, CSRF) verified as correct.

---

## 3) Recommended fixes (minimal)

### F1 — Admin-only export-backup (APPLIED)

- **File:** `backend/app/api/deps.py`  
  - Add:
    - `require_admin(user: User = Depends(require_auth)) -> User` that raises 403 if `user.role != UserRole.ADMIN`.
- **File:** `backend/app/api/routes/admin.py`  
  - Change `admin_export_backup` dependency from `require_auth` to `require_admin`; keep `require_auth` import for wipe endpoints.

### F2 — Backend override validation (optional P2)

- **File:** `backend/app/services/cases.py`  
  - In `update_case_manual_overrides`, before storing a value for `k in _MONEY_OVERRIDE_KEYS`:
    - If `k != "fee_diff_override"` and the parsed decimal `v < 0`, raise `HTTPException(400, detail="Override may not be negative")` for that key.

### F3 — Backup memory (P1 info)

- No code change in this audit. Document or add a note in config/README that full backup loads each table into memory; for very large instances, consider streaming or chunking later.

---

## 4) QA checklist (25–40 steps)

### Golden path (one case: retainer, freeze, expenses total, stage billing, fee delete, overrides, export)

1. Create or pick an open case with retainer anchor and no freeze.
2. **Retainer dates:** PATCH /cases/{id}/retainer/dates with `retainer_snapshot_through_month` (e.g. YYYY-MM-15) → verify response has normalized first-of-month; Overview “שכ״ט ששולם עד כה” and charged months update.
3. **Freeze:** POST /cases/{id}/retainer/freeze `{ "freeze": true }` → case has `retainer_is_frozen: true`, `retainer_frozen_at` set; Retainer tab shows freeze; Overview does not show “current credit”.
4. **Expenses total:** PATCH /cases/{id}/expenses/total with `expenses_total_ils_gross` → Overview “הוצאות עד כה” and “יתרת אקסס” update after refresh.
5. **Stage billing:** POST /cases/{id}/fees/stage-billing with selected codes + adjustment → new fee event; Overview “שכ״ט לפי שלבים” and “הפרש שכ״ט” update; dashboard procedure stage reflects new stage.
6. **Fee event soft delete:** DELETE /cases/{id}/fees/{eventId} with body `{ "delete_reason": "טעות" }` → 204; fee list no longer shows event (unless show-deleted); Overview and deductible summary totals decrease; procedure stage can change if was last event.
7. **Overrides:** PATCH /cases/{id}/overrides with e.g. `excess_remaining_override` → Deductible tab and Overview show override; PATCH with `excess_remaining_override: null` → override cleared, computed value shown.
8. **Export:** GET /cases/{id}/export → XLSX; Overview sheet has retainer_charged_to_date_ils, fees_by_stages_ils, fee_diff_ils, total_expenses_ils, excess_total_ils, excess_remaining_ils; Deductible sheet matches unified; Deleted Fee Events sheet lists soft-deleted events with delete_reason.

### Edge cases

9. **Empty case:** New case, no fee events, no expenses → Overview shows zeros; excess_remaining = excess_total (or 0 if no deductible); no errors.
10. **Deleted case:** Soft delete a case → GET /cases/{id} returns 404; GET /cases/{id}/export returns 404; case not in GET /cases/; not in analytics overview; direct URL in UI → 404 or redirect.
11. **Override reset:** Set override then send same key with `null` → value removed; computed value shown everywhere.
12. **Snapshot boundaries:** Case with retainer_snapshot_through_month set → charged months start month-after snapshot; retainer_charged_to_date_ils and count_charged_months match.
13. **Freeze boundary:** Frozen case → ensure_accruals_up_to and retainer_charged_to_date_ils use retainer_frozen_at as end; no accruals created after that month.
14. **CSRF:** From another origin or without cookie, send POST/PATCH/DELETE without valid X-CSRF-Token → 403 (production).
15. **Fee diff negative:** Override fee_diff to negative → stored and shown in red in Overview; other overrides negative → frontend blocks (backend does not, P2).
16. **Admin export-backup:** As non-admin user, GET /admin/export-backup → 403 after fix. As admin → 200 + ZIP.

### Regression / consistency

17. Cases list “יתרת אקסס” column matches Overview/deductible excess_remaining for same case.
18. After changing expenses total, open Deductible tab → excess_remaining matches Overview.
19. After deleting a fee event, billed-codes and stage billing modal do not include deleted event’s codes in “already billed”.
20. Bulk-update (dashboard) only updates non-deleted cases; selected case IDs that are deleted are skipped (updated_count may be less than len(case_ids)).
21. Warnings endpoint uses unified excess_total_ils for DEDUCTIBLE_ZERO check.
22. Analytics overview uses unified_excess_remaining_ils; only non-deleted cases included.
23. Retainer ledger: accruals only up to effective_end (today or freeze); no accruals past freeze.
24. Case export: single-case export uses get_case_if_not_deleted → 404 for deleted; Overview and Deductible sheets use build_case_overview_summary + get_unified_summary.

---

## 5) Key code locations (top 20)

| # | Location | Purpose |
|---|----------|--------|
| 1 | `backend/app/services/unified.py` — `get_unified_summary`, `retainer_charged_to_date_ils`, `fees_by_stages_ils`, `excess_remaining_ils`, `get_effective_end_date` | Single source of truth for financial totals and effective end (freeze). |
| 2 | `backend/app/services/cases.py` — `build_case_overview_summary` | Overview-summary endpoint payload; uses get_unified_summary. |
| 3 | `backend/app/services/cases.py` — `to_case_out` | Cases list row; uses unified_excess_remaining_ils for excess_remaining_ils_gross. |
| 4 | `backend/app/services/cases.py` — `update_case_manual_overrides`, `_MONEY_OVERRIDE_KEYS` | Override merge; decimal string storage; no negative check (P2). |
| 5 | `backend/app/services/cases.py` — `list_cases`, `get_case_if_not_deleted` | List and single-case access; exclude deleted. |
| 6 | `backend/app/services/retainer.py` — `count_charged_months`, `ensure_accruals_up_to` | Month counting; accruals up to effective_end (freeze). |
| 7 | `backend/app/services/retainer.py` — `build_retainer_ledger` | Uses get_effective_end_date for up_to. |
| 8 | `backend/app/services/cases.py` — `set_retainer_freeze`, `update_case_retainer_dates` | Freeze toggle; dates PATCH; normalize snapshot to first-of-month. |
| 9 | `backend/app/services/cases.py` — `update_case_expenses_total` | PATCH expenses total; unified uses case.expenses_total_ils_gross. |
| 10 | `backend/app/services/fees.py` — `list_fee_events(include_deleted=False)`, `soft_delete_fee_event`, `get_billed_codes_for_case` | Fee list excludes deleted; soft delete with reason; billed codes exclude deleted. |
| 11 | `backend/app/api/routes/deductible.py` — deductible summary | Uses get_unified_summary. |
| 12 | `backend/app/services/case_export.py` — `build_case_export_xlsx` | Overview + Deductible sheets from overview/unified; get_case_if_not_deleted. |
| 13 | `backend/app/services/alerts.py` | Uses unified_excess_remaining_ils; filters Case.deleted_at.is_(None). |
| 14 | `backend/app/api/routes/analytics.py` — overview | Uses unified_excess_remaining_ils; filters Case.deleted_at.is_(None). |
| 15 | `backend/app/main.py` — `_csrf_middleware`, `_CSRF_EXEMPT_PATHS` | CSRF for non-GET; exempt login/logout/import/wipe. |
| 16 | `frontend/src/lib/api.ts` — `apiFetch`, `apiDownload` | Add X-CSRF-Token for non-GET/HEAD. |
| 17 | `frontend/src/pages/CaseDetailsPage.tsx` — Overview section, DEDUCTIBLE_FIELDS, saveOverride(allowNegative) | Overview uses overview-summary only; overrides allowNegative only for fee_diff. |
| 18 | `frontend/src/pages/CasesPage.tsx` — excess column, bulk-update, delete case | excess_remaining_ils_gross from API; PATCH bulk-update; DELETE case. |
| 19 | `backend/app/api/deps.py` — `require_auth`, `require_admin` | Auth and admin-only (export-backup). |
| 20 | `backend/app/api/routes/admin.py` — `admin_export_backup` | GET backup; now uses require_admin. |

---

## Summary

- **Verdict: SAFE** for production with the applied **admin-only export-backup** fix.
- **Optional:** Backend validation for non-negative overrides (except fee_diff) and documentation/streaming for backup on very large DBs.
- **QA:** Run the golden path and edge-case checklist above to confirm behavior on Render prod.

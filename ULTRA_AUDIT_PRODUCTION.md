# TeremFlow — ULTRA Production Audit

**Date:** 2026-02-02  
**Scope:** Full audit before day-to-day office reliance on Render PRODUCTION.  
**Rules:** Audit only (no new features unless required to fix a bug). Actionable findings + exact paths + fixes + QA checklist.

---

## 1) Executive Summary

- **Fees / STAGE_BILLING:** Delta-only billing is enforced (new_codes only); discount cannot make final total negative (400); billed-codes use `new_codes` or legacy `codes`; procedure stage override is display-only; current procedure stage logic is correct and robust. Tests cover double-charge prevention and adjustment edge cases.
- **Retainer:** Accrual generation is idempotent (existing months keyed, no duplicates); snapshot + anchor logic is correct; payments and ledger rows are consistent. **Gap:** Retainer *credit applied to fees* uses only `RetainerPayment` table—snapshot is not included. Excess remaining *does* include snapshot. Confirm business rule: should snapshot count toward fee credit?
- **Expenses & Deductible:** Deductible consumed only by `payer=CLIENT_DEDUCTIBLE`; summaries and excess formula are correct; excess excludes attorney fees from J (by design). Deductible summary returns non-null numbers; no-expense cases handled.
- **Excel import:** Create requires case_reference, case_type, open_date; empty rows skipped; duplicate case_reference → 409. Update uses case_reference lookup; overwrite_blanks; update flow prefers ILS over USD when both set; create flow uses USD first when both set (preview says "ILS preferred")—minor doc/behavior inconsistency.
- **Security:** All data endpoints use `require_auth`. CSRF enforced in production for non-exempt paths; exempt: `/auth/login`, `/auth/logout`, `/import/excel`, `/admin/wipe-case-data`. Frontend sends CSRF for mutations (including import preview/run). Admin wipe requires `X-Wipe-Token`. **Finding:** `GET /admin/export-backup` is any authenticated user (no admin-only role check).
- **Backups:** Backup records created on export; logout requires backup within `backup_fresh_hours`; `my-last` uses `backup_fresh_hours`. Export loads all tables into memory—risk for very large DBs (P1).
- **Migrations:** 0010–0013 are safe (idempotent enum add, seed UPSERT, nullable columns). `start.sh` runs `alembic upgrade head` before uvicorn.
- **Verdict:** **Safe to use now** for production, with a short list of P1/P2 items to fix or confirm. No P0 blockers found; one P1 (admin export restriction) and a few P2/doc items recommended.

---

## 2) Findings (grouped by A–E, severity P0/P1/P2)

### A) Data integrity & accounting correctness

#### A1) Fees / STAGE_BILLING

| # | Finding | Severity | Location / detail |
|---|--------|----------|-------------------|
| A1.1 | Delta-only billing enforced; no double-charge by default | ✅ OK | `backend/app/services/fees.py`: `new_codes = sorted([c for c in codes_selected if c not in already_set])`; `get_billed_codes_for_case` uses union of `new_codes` or `codes` per event. |
| A1.2 | Adjustment cannot make final total negative | ✅ OK | `fees.py` ~191–197: `if final_delta_total < 0: raise HTTPException(..., "Discount exceeds new charges")`. |
| A1.3 | Billed-codes detection correct | ✅ OK | `get_billed_codes_for_case`: `charged = e.breakdown_json.get("new_codes") or e.breakdown_json.get("codes") or []`. |
| A1.4 | Stage override does not affect billing | ✅ OK | `cases.py` `_effective_procedure_stage` used only in `to_case_out` / overview for display; fee computation uses only fee_events and rates. |
| A1.5 | Current procedure stage display robust | ✅ OK | `get_latest_fee_stage_by_case_ids`: one row per case (order_by event_date.desc(), id.desc()); STAGE_BILLING uses new_codes or "STAGE_BILLING:0". |
| A1.6 | Empty new_codes / repeated submit | ✅ OK | 400 "No new codes to bill" unless `confirm_zero_new_codes`; tests in `test_stage_billing.py`. |
| A1.7 | Concurrent submissions | ⚠️ Gap | No optimistic locking or unique constraint on (case_id, event_date, event_type, breakdown hash). Two concurrent requests could create two events for same new_codes. **Recommendation:** Document as known limitation or add advisory lock/transaction. |

#### A2) Retainer

| # | Finding | Severity | Location / detail |
|---|--------|----------|-------------------|
| A2.1 | Accrual generation idempotent | ✅ OK | `retainer.py` `ensure_accruals_up_to`: `existing = {a.accrual_month: a for a in ...}`; only `if cur not in existing` creates. |
| A2.2 | Snapshot + anchor logic | ✅ OK | `_accrual_start_month`: if snapshot_through_month set, start from month after; else anchor. Ledger snapshot row and running credit include snapshot. |
| A2.3 | Credit applied to fees uses only payments | ⚠️ P2 | `fees.py` `_retainer_paid_total` and `retainer_summary` use only `RetainerPayment`. Snapshot is not applied to reduce fee cash due. Excess remaining *does* include snapshot (`expenses.py` get_case_excess_remaining). **Confirm:** Should snapshot count toward "credit" for fee allocation? If yes, fix in `_retainer_paid_total` / retainer_summary to include `case.retainer_snapshot_ils_gross` when set. |
| A2.4 | Payment note persistence | ✅ OK | `RetainerPayment.note` stored; ledger row `notes` from payment. |
| A2.5 | Ledger payment month bucketing | ✅ OK | Payments use `payment_date.strftime("%Y-%m")` as row month; no separate bucketing rule. |

#### A3) Expenses & Deductible

| # | Finding | Severity | Location / detail |
|---|--------|----------|-------------------|
| A3.1 | Deductible consumed only by CLIENT_DEDUCTIBLE | ✅ OK | `_consumed_on_deductible`: `Expense.payer == ExpensePayer.CLIENT_DEDUCTIBLE`. |
| A3.2 | Editing expense updates summaries | ✅ OK | Summaries are computed from DB each time (no cache); update_expense commits. |
| A3.3 | Excess remaining formula | ✅ OK | J = retainer_total (snapshot + payments) + expenses_snapshot + other_expenses (CLIENT_DEDUCTIBLE, category != ATTORNEY_FEE). Attorney fees excluded by design. |
| A3.4 | Deductible summary non-null / no-expense | ✅ OK | `get_deductible_summary`: total from case; consumed from query (0 if none); remaining/excess from helpers. |

#### A4) Excel import/update

| # | Finding | Severity | Location / detail |
|---|--------|----------|-------------------|
| A4.1 | Create: required columns, skip empty rows | ✅ OK | `import_excel.py`: required `case_reference`, `case_type`, `open_date`; `if not any(row): skipped_empty_rows += 1; continue`. |
| A4.2 | Create: uniqueness | ✅ OK | `create_case` raises 409 if `case_reference` exists. |
| A4.3 | Update: case_reference lookup, skip blanks | ✅ OK | `import_cases_from_excel_update`: case by ref; `if value is None and not overwrite_blanks: continue` in update_case_from_excel. |
| A4.4 | Update: prefer ILS over USD | ✅ OK | `update_case_from_excel`: `if key == "deductible_usd" and "deductible_ils_gross" in updates and updates["deductible_ils_gross"] is not None: continue`. |
| A4.5 | Create: when both USD and ILS set, USD used | ⚠️ P2 | `create_case`: `if payload.deductible_usd is not None` branch uses FX; preview says "ILS preferred when both set." **Fix:** Either document "USD preferred on create" or change create to prefer ILS when both set (match update + preview). |
| A4.6 | Preview matches real import | ✅ OK | Same `_build_col_map_and_rows`, `_parse_row_to_create_values`, `_parse_data_to_updates`, `_build_raw_from_row`. |
| A4.7 | Raw import merge, no formula dependency | ✅ OK | `merge_raw_import_fields` merges into `raw_import_fields_json`; display-only, not used in calculations. |

---

### B) Security & privacy

| # | Finding | Severity | Location / detail |
|---|--------|----------|-------------------|
| B1.1 | Endpoints enforce auth | ✅ OK | All data routes use `Depends(require_auth)` (cases, expenses, deductible, retainers, fee_events, backups, admin, import, analytics, notifications, activity). |
| B1.2 | Admin wipe restricted | ✅ OK | `admin.py` wipe: requires auth + `X-Wipe-Token` == `settings.wipe_case_data_secret`. |
| B1.3 | Admin export-backup not admin-only | 🔴 P1 | `GET /admin/export-backup`: `user=Depends(require_auth)` only. Any authenticated user can download full DB backup. **Fix:** Restrict to `user.role == UserRole.ADMIN` or equivalent. |
| B1.4 | Case export authorized | ✅ OK | `GET /cases/{case_id}/export` uses `require_auth`; no per-case ACL (any authenticated user can export any case). Acceptable if all users are trusted. |
| B2.1 | CSRF enforced in production | ✅ OK | `main.py`: production only; POST/PUT/PATCH/DELETE; path not in exempt set; when cookie present, header must match. |
| B2.2 | Frontend mutations use CSRF | ✅ OK | `api.ts`: `X-CSRF-Token` for non-GET when token present; ImportPage uses `getCsrfHeadersForMutation()` for preview and run. |
| B2.3 | Exempt paths minimal | ✅ OK | `/auth/login`, `/auth/logout`, `/import/excel`, `/admin/wipe-case-data`. Logout needs cookie; import/excel is multipart (exempt). |
| B3.1 | Export/backup no secrets in file | ✅ OK | Case export: case/overview/fees/retainer/expenses/deductible/raw; backup: table CSVs + manifest (user id/name). No JWT or secrets in content. |
| B3.2 | raw_import_fields_json | ✅ OK | Client-controlled merge; no automatic injection of tokens. Sensitive data only if user imports it. |

---

### C) Reliability & observability

| # | Finding | Severity | Location / detail |
|---|--------|----------|-------------------|
| C1.1 | Backup records created | ✅ OK | `build_backup_zip` creates `BackupRecord` and commits. |
| C1.2 | Logout uses backup (fresh_hours) | ✅ OK | `auth.py` logout: requires `X-Backup-Id`; validates record for user and `created_at` within `backup_fresh_hours`. |
| C1.3 | my-last endpoint | ✅ OK | `backups.py` `my_last_backup`: filter by `created_by_user_id`, order_by id.desc(), first. |
| C1.4 | Backup export memory | 🔴 P1 | `build_backup_zip` loads all tables with `db.execute(select(table)).mappings().all()`; no streaming. Very large DB could OOM. **Fix:** Consider streaming or row limits; or document max recommended size. |
| C2.1 | API error bodies | ✅ OK | HTTPException with detail; frontend parses `data?.detail` and shows in toast/error. |
| C2.2 | Frontend messages | ✅ OK | api.ts throws Error(detail); pages show `e?.message`. Not only "Failed to fetch" when API returns JSON. |
| C2.3 | Import/export timeouts and size | ⚠️ P2 | No explicit file size limit on import (`file.file.read()`); no timeout config called out. Render request timeout may apply. |
| C3.1 | Migrations 0010–0013 safe | ✅ OK | 0010: enum ADD VALUE with EXCEPTION; seed UPSERT; 0011–0013: nullable columns/index. |
| C3.2 | Deploy order | ✅ OK | `start.sh`: alembic upgrade head → seed → uvicorn. |
| C3.3 | Rollback / enums | ✅ OK | Downgrade 0010 does not remove enum values (commented); safe. |

---

### D) Performance

| # | Finding | Severity | Location / detail |
|---|--------|----------|-------------------|
| D1 | Cases list N+1 | ✅ OK | `list_cases` one query; `get_latest_fee_stage_by_case_ids(case_ids)` one query; `to_case_out` per case uses get_case_excess_remaining (one query per case). For hundreds of cases, N+1 on excess. **Recommendation (P2):** Batch excess if list grows large. |
| D2 | Overview summary | ✅ OK | One case load; fee_events for case; retainer_summary; expenses summary; deductible summary. Bounded by one case. |
| D3 | Retainer ledger | ✅ OK | ensure_accruals_up_to (read + possible inserts); summary; accruals + payments queries; sort in memory. Linear in months + payments. |
| D4 | Case export | ✅ OK | Same as overview + ledger + list_fee_events + list_expenses; single case. Worst case bounded by events/expenses per case. |

---

### E) UX pitfalls

| # | Finding | Severity | Location / detail |
|---|--------|----------|-------------------|
| E1 | One billing entry point | ✅ OK | Stage billing via one modal/endpoint; no duplicate UI paths. |
| E2 | Warnings useful | ✅ OK | Data quality warnings are info/warn/error with action_tab; not noisy. |
| E3 | Raw import UI | ✅ OK | Raw fields grouped and displayed; matches RAW_GROUP_ORDER and keys. |
| E4 | Export file usable | ✅ OK | Sheets: Case, Overview, Fees, Retainer, Expenses, Deductible, Raw Import; key fields present. |

---

## 3) Recommended Fixes (prioritized)

| Priority | Issue | Impact | Reproduce | Location(s) | Minimal fix | Verify |
|----------|--------|--------|-----------|-------------|-------------|--------|
| P1 | Admin export available to any authenticated user | Data leakage risk | Log in as non-admin, GET /admin/export-backup → 200 and ZIP | `backend/app/api/routes/admin.py` | Add check `if user.role != UserRole.ADMIN: raise HTTPException(403)` (or equivalent role) | Only ADMIN can GET export-backup |
| P1 | Backup export loads full DB into memory | OOM on very large DB | Export backup with many cases/expenses/fees | `backend/app/api/routes/backups.py` `build_backup_zip` | Document max recommended size; or add streaming/chunking | Export succeeds for typical size; doc in README or runbook |
| P2 | Create import: both USD and ILS set → USD used (preview says ILS preferred) | Confusing / wrong expectation | Create import with both columns set; observe FX used | `backend/app/services/cases.py` create_case; `backend/app/services/import_excel.py` preview warning | Prefer ILS when both set in create (e.g. if deductible_ils_gross not None use it, else USD) and align preview text | Create with both → ILS used; preview text matches |
| P2 | Retainer snapshot not applied to fees | Snapshot may be intended as credit | Case with retainer_snapshot_ils_gross, no payments; add fee → amount_due_cash not reduced | `backend/app/services/fees.py` _retainer_paid_total; `backend/app/services/retainer.py` retainer_summary | **Only if product confirms:** Include case.retainer_snapshot_ils_gross in "paid" for allocation and summary | Ledger and fee allocation consistent with snapshot as credit |
| P2 | Concurrent STAGE_BILLING submissions | Rare double bill | Two requests same case/codes in parallel | `backend/app/services/fees.py` create_stage_billing_event | Document or add advisory lock (e.g. SELECT FOR UPDATE on case) | No double new_codes in normal use |

---

## 4) QA Checklist (Production) — 30–50 steps

### P0 – Auth & access (5)
1. Log out; open `/cases` → redirect or 401.
2. Log in; open `/cases` → list loads.
3. Open case details → overview, fees, retainer, expenses, deductible load.
4. Log out; call GET /cases/{id}/export with session cookie removed → 401.
5. Log in as second user; export another user’s case → 200 (if no per-case ACL).

### P0 – Fees & billing (8)
6. Create case; add single fee event (e.g. COURT_STAGE_1_DEFENSE) → amount and event type correct.
7. Add STAGE_BILLING with one code → one event, delta = rate, no duplicate code.
8. Add second STAGE_BILLING with same code (no confirm_zero) → 400 "No new codes to bill".
9. Add second STAGE_BILLING with same code + confirm_zero_new_codes → 0-amount event created.
10. Add STAGE_BILLING with discount > delta_total → 400 "Discount exceeds new charges".
11. Add STAGE_BILLING with discount < delta_total → final_delta_total = delta_total - discount.
12. Set procedure_stage_override on case; check overview → display shows override; fee totals unchanged.
13. Billed-codes API for case with STAGE_BILLING → returns new_codes (or codes) from events.

### P0 – Retainer (6)
14. Case with no snapshot; open retainer tab → accruals from anchor month.
15. Case with snapshot + snapshot_through_month; open retainer → first accrual month after through_month.
16. Add retainer payment → row in ledger, running credit increases.
17. Add payment with note → note in ledger row.
18. Ensure accruals up to current month; reload → no duplicate accruals for same month.
19. Case with snapshot only (no payments); check “current credit” and fee allocation → confirm whether snapshot reduces fees (per product).

### P0 – Expenses & deductible (6)
20. Add expense with payer CLIENT_DEDUCTIBLE → deductible consumed and remaining update.
21. Add expense with payer INSURER → total expenses up; deductible consumed unchanged.
22. Edit expense amount/payer → summary and deductible remaining recalc.
23. Case with no expenses → deductible summary: consumed 0, remaining = total.
24. Deductible summary endpoint → all numeric fields non-null.
25. Excess remaining: case with retainer snapshot + payments + expenses → value matches M - J (J = retainer_total + expenses_snapshot + other_expenses).

### P0 – Import (6)
26. Create import: Excel with case_reference, case_type, open_date → cases created; empty rows skipped.
27. Create import: duplicate case_reference in sheet → 409 for duplicate row.
28. Create import: missing case_type → error for that row.
29. Update import: case_reference column present; row with existing ref → case updated; blank cells not overwritten (overwrite_blanks=false).
30. Update import: overwrite_blanks=true + blank in field → existing value cleared.
31. Update import: both deductible_usd and deductible_ils_gross set → ILS used (deductible_ils_gross wins).

### P0 – Security (4)
32. Production: POST to protected endpoint without X-CSRF-Token (with cookie) → 403.
33. Production: POST with valid X-CSRF-Token → 200/201.
34. Admin wipe without X-Wipe-Token → 403.
35. Admin wipe with correct X-Wipe-Token → 200 and data wiped.

### P1 – Backups & export (5)
36. POST /backups/export → 200; ZIP; BackupRecord created; X-Backup-Id in response.
37. GET /backups/my-last → last backup by current user; fresh_hours in body.
38. Logout without backup → 428.
39. Logout with backup ID and within fresh_hours → 200.
40. GET /admin/export-backup as non-admin (if fixed: should 403).

### P1 – Case export & warnings (4)
41. Case details → "ייצוא תיק" → file downloads; filename case_*_YYYYMMDD.xlsx.
42. Open XLSX → sheets Case, Overview, Fees, Retainer, Expenses, Deductible, Raw Import; data matches UI.
43. Case with no fees → Fees sheet has headers only.
44. Overview warnings: case missing case_name → warn; missing case_type/open_date → errors; "פתח" opens correct tab.

### P2 – Edge & doc (3)
45. Create import with both deductible_usd and deductible_ils_gross → confirm which wins (document or fix to ILS).
46. Large backup export (if applicable) → completes or document limit.
47. Two concurrent STAGE_BILLING same case/codes → document or verify behavior.

---

## 5) Files / Functions Index (top 20)

| # | Path | Purpose |
|---|------|--------|
| 1 | `backend/app/services/fees.py` | `create_stage_billing_event`, `get_billed_codes_for_case`, `apply_retainer_credit`, `_retainer_paid_total` |
| 2 | `backend/app/services/cases.py` | `create_case`, `update_case_from_excel`, `get_latest_fee_stage_by_case_ids`, `_effective_procedure_stage`, `build_case_overview_summary`, `get_case_warnings` |
| 3 | `backend/app/services/retainer.py` | `ensure_accruals_up_to`, `retainer_summary`, `build_retainer_ledger`, `_accrual_start_month` |
| 4 | `backend/app/services/expenses.py` | `_consumed_on_deductible`, `get_case_deductible_remaining`, `get_case_excess_remaining`, `get_deductible_summary`, `update_expense` |
| 5 | `backend/app/services/deductible.py` | `deductible_remaining`, `q_ils` |
| 6 | `backend/app/services/import_excel.py` | `import_cases_from_excel`, `import_cases_from_excel_update`, `preview_import_excel`, `preview_import_excel_update`, `_parse_data_to_updates`, `_build_raw_from_row` |
| 7 | `backend/app/api/routes/cases.py` | list_cases, get_case, get_case_overview_summary, get_case_warnings, export_case |
| 8 | `backend/app/api/routes/admin.py` | wipe_case_data, admin_export_backup |
| 9 | `backend/app/api/routes/backups.py` | build_backup_zip, export_backup, my_last_backup |
| 10 | `backend/app/api/deps.py` | get_current_user, require_auth |
| 11 | `backend/app/main.py` | create_app, CSRF middleware, _CSRF_EXEMPT_PATHS |
| 12 | `backend/app/api/routes/auth.py` | login (sets CSRF cookie), logout (backup check) |
| 13 | `backend/app/api/routes/import_excel.py` | import_excel_preview, import_excel, import_excel_update (all require_auth) |
| 14 | `backend/app/api/routes/fee_events.py` | list_fee_events, create_stage_billing_event, add_fee_event |
| 15 | `backend/app/models/case.py` | Case (procedure_stage_override, raw_import_fields_json, retainer_snapshot_*) |
| 16 | `backend/app/models/fee_event.py` | FeeEvent (breakdown_json) |
| 17 | `backend/alembic/versions/0010_fee_stage_rates_and_stage_billing.py` | Enum + fee_stage_rates + breakdown_json |
| 18 | `backend/start.sh` | alembic upgrade head, ensure_seeded, uvicorn |
| 19 | `frontend/src/lib/api.ts` | apiFetch, apiDownload, getCsrfHeadersForMutation, CSRF header injection |
| 20 | `frontend/src/pages/ImportPage.tsx` | Preview/run import with FormData + getCsrfHeadersForMutation |

---

## 6) Sample test data (one case for full coverage)

- **Case:** case_reference `AUDIT-1`, case_type COURT, open_date 2024-01-15, deductible_ils_gross 10000, retainer_anchor_date 2024-07-01, retainer_snapshot_ils_gross 5000, retainer_snapshot_through_month 2024-06-01.
- **Fees:** One COURT_STAGE_1_DEFENSE; one STAGE_BILLING with COURT_STAGE_2_DAMAGES (delta only).
- **Retainer:** At least one payment (e.g. 1000 ILS) with note.
- **Expenses:** One CLIENT_DEDUCTIBLE (e.g. 500), one INSURER (e.g. 200).
- **Raw import:** One column not in OPERATIONAL_FIELDS (e.g. "custom_notes") with value; legacy_fee_text optional.

Use this case for: overview summary, fees list, retainer ledger, expenses list, deductible summary, warnings, and case export; then run QA steps 6–25 and 41–44 against it.

---

**End of audit.**

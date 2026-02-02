# TeremFlow — ULTRA SYSTEM AUDIT REPORT

**Date:** 2 February 2026  
**Scope:** Production system deployed on Render  
**Mode:** Audit only — no code changes, refactors, or optimizations

---

## Executive Summary

**TeremFlow** is a case-management system for medical malpractice defense at TRM (טר״מ). The tagline: *"Every expense. Every stage. One clear picture."*

The system provides:
- **Per-case visibility** of deductible (השתתפות עצמית / access), expenses, retainer accruals, and fee events (שכ״ט)
- **Automatic expense split** when an expense crosses the remaining deductible
- **Retainer lifecycle** with Net 60 terms and credit applied to fees
- **Notifications** for deductible near exhaustion, insurer started paying, retainer due/overdue
- **Analytics** over expenses by case, payer, time, and court stage

**Alignment with original goal:** The system delivers strong visibility of money per case and clear separation between deductible/insurer/retainer/fees. Predictability is partially achieved; several gaps remain (retainer accrual roll-forward, case closure UX, edit/delete capabilities).

---

# PART 1 — ARCHITECTURE OVERVIEW

## Overall Architecture

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Frontend** | React 19, Vite 7, TypeScript, Tailwind, Recharts | SPA with RTL Hebrew UI |
| **Backend** | FastAPI (Python), SQLAlchemy 2, Alembic | REST API, business logic |
| **Database** | PostgreSQL 16 | Persistent storage |
| **Deployment** | Render | Web services + static site + cron |

### Frontend
- **Framework:** React 19 + React Router 7
- **Build:** Vite 7, outputs to `dist/`
- **Routing:** `/` → redirect; `/login`; `/dashboard`; `/cases`; `/cases/:caseId`; `/analytics`; `/import`; `/notifications`
- **Auth:** Cookie-based (JWT in HttpOnly cookie); CSRF token for production POST/PUT/PATCH/DELETE
- **API:** `fetch` with `credentials: 'include'`, `X-CSRF-Token` header for mutations

### Backend
- **Framework:** FastAPI
- **Structure:** `app/` with `api/routes/`, `services/`, `models/`, `schemas/`, `core/`
- **DB:** SQLAlchemy ORM + Alembic migrations; Postgres in production, SQLite for local dev
- **Auth:** JWT in cookie; `require_auth` dependency for protected routes

### Database
- **Tables:** `users`, `cases`, `expenses`, `retainer_accruals`, `retainer_payments`, `fee_events`, `fx_rate_cache`, `notifications`, `alert_events`, `backup_records`
- **Relations:** One case → many expenses, accruals, payments, fee_events; case → notifications (nullable FK)

### External Services
- **BOI FX:** `https://api.boi.org.il/SDMX/v2/data/EXR/RER_USD_ILS` — USD/ILS rate for deductible conversion
- **Render Cron:** Daily at 06:00 UTC, POSTs to `/tasks/daily` with `X-Tasks-Token`
- **Email:** Optional SMTP; if not configured, logs to stdout

---

## Deployment (Render)

| Service | Type | Plan | Purpose |
|---------|------|------|---------|
| `teremflow-db` | Postgres | basic-1gb | Database |
| `teremflow-api` | Web | free | FastAPI backend |
| `teremflow-frontend` | Static | — | SPA from `dist/` |
| `teremflow-daily-tasks` | Cron | — | Runs `/tasks/daily` daily |

- **Frontend ↔ Backend:** Frontend calls `VITE_API_URL` (e.g. `https://teremflow-api.onrender.com`)
- **Auth:** JWT in cookie; production uses `SameSite=None` and `Secure` for cross-origin
- **CORS:** `CORS_ORIGINS` must include exact frontend domain
- **Cron:** Must set `TASKS_DAILY_SECRET` identically on both API and Cron (Render does not sync this)

---

# PART 2 — DATA MODEL

## Case

**Purpose:** Represents a medical malpractice defense matter.

| Field | Type | Mandatory | Meaning |
|-------|------|-----------|---------|
| `id` | int | ✓ | Primary key |
| `case_reference` | string(120) | ✓ | Internal ref / patient / claim no (unique) |
| `case_type` | enum | ✓ | COURT, DEMAND_LETTER, SMALL_CLAIMS |
| `status` | enum | ✓ | OPEN, CLOSED (default OPEN) |
| `open_date` | date | ✓ | Case opening date |
| `deductible_usd` | decimal | Optional | Original deductible in USD (if provided) |
| `fx_rate_usd_ils` | decimal | Optional | FX rate used for conversion |
| `fx_date_used` | date | Optional | Date of FX rate |
| `fx_source` | string | ✓ | BOI \| IMPORTED \| MANUAL |
| `deductible_ils_gross` | decimal | ✓ | **Critical** — deductible in ILS gross (stored, used for all calculations) |
| `insurer_started` | bool | ✓ | Whether insurer has started paying |
| `insurer_start_date` | date | Optional | First date insurer paid |
| `created_at` | datetime | ✓ | Auto-set |

**At case opening (required):**
- `case_reference`, `case_type`, `open_date`
- Either `deductible_usd` or `deductible_ils_gross`

**Derived / auto:**
- `deductible_ils_gross` if `deductible_usd` provided → BOI FX lookup
- `fx_*` fields when FX is used
- `insurer_started`, `insurer_start_date` — set when first insurer expense is recorded

**Critical for correctness:**
- `deductible_ils_gross` must be correct; it drives expense split and remaining calculation.
- `case_reference` must be unique.

---

## Expense

**Purpose:** A single expense (invoice/receipt) charged to the case.

| Field | Type | Mandatory | Meaning |
|-------|------|-----------|---------|
| `id` | int | ✓ | Primary key |
| `case_id` | int | ✓ | FK to cases |
| `supplier_name` | string(120) | ✓ | Vendor name |
| `amount_ils_gross` | decimal | ✓ | Amount in ILS gross |
| `service_description` | text | ✓ | What was purchased |
| `demand_received_date` | date | ✓ | When demand was received |
| `expense_date` | date | ✓ | Expense date |
| `category` | enum | ✓ | ATTORNEY_FEE, EXPERT, MEDICAL_INFO, INVESTIGATOR, FEES, OTHER |
| `payer` | enum | ✓ | CLIENT_DEDUCTIBLE or INSURER |
| `attachment_url` | string | Optional | Link to documentation |
| `split_group_id` | UUID | Optional | Set when expense was split across deductible+insurer |
| `is_split_part` | bool | ✓ | True if this row is part of a split |
| `created_at` | datetime | ✓ | Auto-set |

**When created:** Via POST `/cases/{id}/expenses/`. Payer is either user-specified (INSURER) or auto-assigned by split logic.

**Critical:** `payer` and `amount_ils_gross` drive deductible consumption and insurer tracking.

---

## Deductible (conceptual)

**Not a table.** Computed as:
- **Consumed:** Sum of `expenses.amount_ils_gross` where `payer = CLIENT_DEDUCTIBLE`
- **Remaining:** `case.deductible_ils_gross - consumed`, clamped at 0

---

## FX Rate Cache

**Purpose:** Cache BOI USD/ILS rates by date.

| Field | Type | Meaning |
|-------|------|---------|
| `id` | int | Primary key |
| `rate_date` | date | Date of rate (unique) |
| `rate_usd_ils` | decimal | USD→ILS rate |
| `source` | string | BOI \| IMPORTED \| MANUAL |
| `fetched_at` | datetime | When cached |

---

## Retainer Accrual

**Purpose:** Fixed monthly retainer charge (945 ILS gross).

| Field | Type | Mandatory | Meaning |
|-------|------|-----------|---------|
| `id` | int | ✓ | Primary key |
| `case_id` | int | ✓ | FK to cases |
| `accrual_month` | date | ✓ | First day of month |
| `invoice_date` | date | ✓ | Same as accrual_month |
| `due_date` | date | ✓ | invoice_date + 60 days (Net 60) |
| `amount_ils_gross` | decimal | ✓ | 945.00 |
| `is_paid` | bool | ✓ | Whether allocated payment covers it |
| `created_at` | datetime | ✓ | Auto-set |

**When created:** Only at case creation via `ensure_accruals_up_to`. Not created when viewing retainer tab or by cron.

---

## Retainer Payment

**Purpose:** Cash received against retainer (cash basis).

| Field | Type | Meaning |
|-------|------|---------|
| `id` | int | Primary key |
| `case_id` | int | FK |
| `payment_date` | date | When paid |
| `amount_ils_gross` | decimal | Amount |
| `created_at` | datetime | Auto-set |

Payments allocate oldest-first to accruals; any excess becomes credit for fees.

---

## Fee Event (שכ״ט)

**Purpose:** A fee stage (court stage, demand letter, etc.).

| Field | Type | Mandatory | Meaning |
|-------|------|-----------|---------|
| `id` | int | ✓ | Primary key |
| `case_id` | int | ✓ | FK |
| `event_type` | enum | ✓ | See FeeEventType |
| `event_date` | date | ✓ | When occurred |
| `quantity` | int | ✓ | For hourly/quantity-based (default 1) |
| `amount_override_ils_gross` | decimal | Optional | Override (required for SMALL_CLAIMS_MANUAL) |
| `computed_amount_ils_gross` | decimal | ✓ | Calculated or override |
| `amount_covered_by_credit_ils_gross` | decimal | ✓ | Retainer credit applied |
| `amount_due_cash_ils_gross` | decimal | ✓ | Cash still due |
| `created_at` | datetime | ✓ | Auto-set |

**Event types:** COURT_STAGE_1..5, AMENDED_DEFENSE_*, THIRD_PARTY_NOTICE, ADDITIONAL_PROOF_HEARING, DEMAND_FIX, DEMAND_HOURLY, SMALL_CLAIMS_MANUAL.

---

## Notification / Alert

**Notification:**
- `id`, `case_id` (nullable), `type`, `title`, `message`, `severity`, `is_read`, `created_at`
- Types: DEDUCTIBLE_NEAR_EXHAUSTION, INSURER_STARTED_PAYING, RETAINER_DUE_SOON, RETAINER_OVERDUE

**AlertEvent:** Deduplication key (`type`, `key`) so same alert is not sent twice (e.g. `case:123:insurer_started`, `accrual:45:overdue`).

---

## User

**Purpose:** Authentication and backup ownership.

| Field | Type | Meaning |
|-------|------|---------|
| `id` | int | Primary key |
| `username` | string(50) | Unique |
| `password_hash` | string(255) | bcrypt |
| `role` | enum | ADMIN, USER |
| `is_active` | bool | Default true |
| `created_at` | datetime | Auto-set |

---

# PART 3 — BUSINESS LOGIC & FLOWS

## 1. Opening a New Case

**Inputs:**
- `case_reference` (unique)
- `case_type` (COURT | DEMAND_LETTER | SMALL_CLAIMS)
- `open_date`
- Either `deductible_usd` or `deductible_ils_gross`

**Automatic:**
- If `deductible_usd`: fetch BOI rate for `open_date` (or prior 10 days), compute `deductible_ils_gross`, set `fx_*`, `fx_source=BOI`
- If `deductible_ils_gross`: `fx_source=IMPORTED`, no FX call
- `ensure_accruals_up_to` creates retainer accruals from start month through current month

**Assumptions locked in:**
- Deductible in ILS is final at creation; no later FX revaluation
- Retainer start month: Jan–Jun open → next month; Jul–Dec open → next Jan
- Retainer amount fixed at 945 ILS gross

---

## 2. Adding an Expense

**Logic:**
- If `payer=INSURER`: full amount to insurer, set `insurer_started=True`, `insurer_start_date=expense_date`
- Otherwise: `split_amount_over_deductible(amount, remaining)` returns `(on_deductible, on_insurer)`
  - If split: create two Expense rows with same `split_group_id`, `is_split_part=True`
  - When `on_insurer > 0`: set `insurer_started=True`, `insurer_start_date=expense_date`

**Deductible consumed:** Sum of expenses with `payer=CLIENT_DEDUCTIBLE`.

---

## 3. Retainer Lifecycle

- **Start month:** Jan–Jun open → next month; Jul–Dec open → Jan next year
- **Net 60:** `due_date = accrual_month + 60 days`
- **Accruals:** Created only at case creation, from start month through `today`. **Gap:** No roll-forward; future months never auto-created for existing cases.
- **Payments:** Oldest accrual first; when `total_paid >= 945` for an accrual, mark `is_paid`
- **Credit:** `credit = paid_total - applied_to_fees`; applied chronologically to fee events

---

## 4. Fee (שכ״ט) Lifecycle

- **Fixed stages:** COURT_STAGE_1=20000, 2=15000, 3=15000, 4=15000, 5=10000, etc.
- **Quantity-based:** DEMAND_HOURLY (700×qty), ADDITIONAL_PROOF_HEARING (1500×qty)
- **Override:** SMALL_CLAIMS_MANUAL requires `amount_override_ils_gross`
- **Credit application:** On each new fee event, `apply_retainer_credit` runs — recalculates covered/due for all fee events in chronological order

---

## 5. Analytics

- **Filters:** Date range, case_type, payer_status (client|insurer|closed)
- **Aggregations:** Total expenses, on deductible, on insurer; per-case totals; attorney vs other; court stage distribution (highest stage per court case); monthly/quarterly/yearly time series
- **Limitation:** Court cases with no stage events are not in stage distribution

---

## 6. Notifications & Alerts

**Triggers (daily cron):**
- Insurer started paying (once per case)
- Deductible near: `remaining < 10% of deductible` OR `remaining < 20,000 ILS`
- Retainer due soon: due within 7 days, unpaid
- Retainer overdue: due_date < today, unpaid

**Deduplication:** `alert_events` table with `(type, key)` prevents repeat sends.

**Risk if ignored:** Overdue retainer and deductible exhaustion alerts can lead to missed payments or incorrect payer assumptions.

---

# PART 4 — SCREENS & UX

## Login
- Username + password; sets JWT cookie and CSRF cookie
- Hebrew RTL; placeholder hints for dev users

## Dashboard
- Backup section (last backup, download); backup required before logout
- Links: Cases, Analytics, Import, Notifications

## Cases List
- Search by reference/id; table with case_reference, type, status, deductible remaining, payer status
- Actions: New case, Export CSV, Refresh
- Create case: case_reference, case_type, open_date, deductible_ils_gross (ILS only in UI)

## Case Details
- **Overview:** Total expenses, payer status
- **Expenses:** Table; Add Expense modal (supplier, amount, dates, category, payer override)
- **Retainer:** Summary (accrued, paid, applied, credit, fees due); accruals table; payments table; Add Payment
- **Fees:** Totals; fee events table; Add Fee Event modal (type, date, quantity, override for small claims)

## Analytics
- Filters: date range, case type, payer status, time aggregation (month/quarter/year)
- KPI: total expenses, on deductible, on insurer, avg per case, cases switched, aggregate remaining
- Charts: time series, expense split (attorney vs other), top cases, court stage distribution
- Table: expenses by case with link to case

## Notifications
- List of notifications; mark as read; link to case when applicable

## Import
- Excel upload; shows created/skipped/errors (JSON)
- **Current scope:** Creates cases only; does not import expenses, retainer payments, or fee events
- Required columns: case_reference, case_type, open_date
- Optional: deductible_usd, deductible_ils_gross

### UX Safety Assessment
- **Safe:** Amounts displayed as ILS gross; confirmation on unsaved changes; backup before logout
- **Risks:** No edit/delete for expenses, fees, payments; case status (OPEN/CLOSED) cannot be changed in UI; no explicit "are you sure?" for financial actions
- **Misunderstanding:** Deductible remaining vs total deductible can be confused if not read carefully; retainer "accrued" vs "paid" needs user literacy

---

# PART 5 — ALIGNMENT WITH ORIGINAL GOAL

## 1. Does the system achieve…

| Goal | Status |
|------|--------|
| Full visibility of money per case | Yes — expenses, retainer, fees, deductible remaining all visible |
| Clear separation deductible / insurer / retainer / fees | Yes — payer, amounts, summaries are explicit |
| Predictability | Partial — retainer accruals don't roll forward; no edit/delete to fix mistakes |

## 2. Strengths
- Automatic expense split when crossing deductible
- Retainer credit applied chronologically to fees
- Notifications for key events with deduplication
- Analytics with filters and time series
- Backup + Excel import for data portability

## 3. Weaknesses / Risks
- **Retainer accruals:** Created only at case creation; no monthly roll-forward for existing cases
- **Case status:** No UI to close a case (OPEN→CLOSED)
- **No edit/delete:** Wrong expense/fee/payment cannot be corrected in-app
- **Cron secret:** `TASKS_DAILY_SECRET` must match on API and Cron (easy to misconfigure)
- **Email:** If SMTP not set, alerts only logged

## 4. Scale: "No money surprises. No lost expenses. One clear picture."

**Score: 7/10**

Visibility and structure are strong. Gaps: no accrual roll-forward, no correction workflow, and cron/email configuration risk.

---

# PART 6 — PREPARATION FOR EXCEL IMPORT

## Required for a Correct Case

| Field | Must Have | Can Be Missing | Cannot Guess |
|-------|-----------|----------------|--------------|
| `case_reference` | ✓ | | ✓ |
| `case_type` | ✓ | | ✓ |
| `open_date` | ✓ | | ✓ |
| `deductible_usd` OR `deductible_ils_gross` | One required | One can be blank | ✓ |

## Field Details

- **case_reference:** Unique; duplicates → 409
- **case_type:** Must map to COURT, DEMAND_LETTER, SMALL_CLAIMS (Hebrew headers supported)
- **open_date:** Valid date; Excel serials and ISO supported
- **deductible_ils_gross:** Use for offline/import; avoids BOI FX
- **deductible_usd:** Requires BOI FX; fails if offline

## Mapping Risks
- Hebrew column names: supported via `KNOWN_COLUMNS`; variations (spaces, RTL marks) are normalized
- Date formats: Excel date serials and ISO strings parsed; invalid dates raise
- Case type strings: must match known values or enum literal

## Typical Pitfalls
- Empty rows skipped; partial rows may error
- Duplicate `case_reference` in file → first succeeds, rest 409
- Wrong `case_type` string → validation error
- `deductible_usd` with no network → BOI failure; prefer `deductible_ils_gross` for bulk import

## Validation Before Import
- Ensure `case_reference` unique within file and vs existing DB
- Validate `case_type` against enum
- Validate dates
- Prefer ILS deductible for reliability

## Current Import Scope vs. Next Phase
- **Current:** Excel import creates **cases only** (no expenses, retainer payments, or fee events)
- **Next phase:** Excel-based import of real cases may require:
  - Multi-sheet or multi-row mapping (cases + expenses + payments + fees)
  - Ordering constraints (case before expenses)
  - Deductible/insurer split rules when importing historical expenses

---

# Appendix: Unclear Items

1. **Retainer accrual roll-forward:** Design intent is unclear — whether accruals should be created monthly by cron or only at case creation.
2. **Case closure:** PATCH exists but no UI; unclear if closing is expected in MVP.
3. **Edit/delete:** No implementation; unknown if intentional for audit trail.

---

*End of audit report*

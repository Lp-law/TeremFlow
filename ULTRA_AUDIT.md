## TeremFlow — ULTRA AUDIT (2026-01-13)

This report reflects the **current repo state** after local-hardening work to make the app runnable without Postgres (SQLite dev mode) and after updating seeded login passwords.

---

## 1) Executive Summary

**Overall status: PASS‑WITH‑FIXES**

- **Backend** is running locally on SQLite (dev-only), auth cookie flow works, core domain endpoints work in smoke tests, and **`pytest -q` passes**.
- **Frontend** builds successfully (**`npm run build` passes**).
- **Deploy readiness**: Render blueprint is mostly OK, but cron secret sync remains a real production risk (see Risk Register).

### Top 5 highest‑risk issues (current)

| Rank | Severity | Issue | Why it matters |
|---:|---|---|---|
| 1 | **High (Deployability/Correctness)** | **Render Cron secret can be missing/mismatched** (`TASKS_DAILY_SECRET` is `sync: false`) | If API + Cron don’t share the exact same value, `/tasks/daily` will 401 and **alerts/notifications won’t run**. |
| 2 | **Medium (Deployability)** | **SQLite dev mode is not migration‑backed** (uses `create_all` not Alembic) | Local SQLite schema may diverge from Postgres migration schema; great for local login/testing, but not a substitute for Postgres parity. |
| 3 | **Medium (Security)** | **Cookie auth without explicit CSRF token** (relies on `SameSite=Lax` + strict CORS) | OK for current design, but future state-changing GETs or relaxed CORS can introduce CSRF risk. |
| 4 | **Low/Medium (Auth policy)** | **Password min-length reduced to 7** to support requested credentials | This is a deliberate local change, but it weakens password policy; should be revisited if this becomes internet-facing for real users. |
| 5 | **Low (Performance)** | Frontend bundle chunk warning (>500kB) | Not a functional bug; potential future perf improvement (code splitting). |

---

## 2) Environment & Toolchain Snapshot

### Local toolchain (as run)

```text
node -v
v24.11.1

npm -v
11.6.2

python --version
Python 3.14.1
```

### Key dependency versions (observed)

**Backend**
- FastAPI: `0.115.6`
- SQLAlchemy: `2.0.39`
- Alembic: `1.14.0`

**Frontend**
- React: `19.2.0`
- react-router-dom: `7.12.0`
- Tailwind: `3.4.17`
- Vite: build showed `7.3.1`
- Recharts: `3.6.0`

---

## 3) Security Review

### Cookie settings (auth)

`backend/app/api/routes/auth.py` sets cookie:
- **HttpOnly**: ✅
- **Secure**: ✅ (only when `ENVIRONMENT=production`)
- **SameSite**: ✅ `lax`
- **Path**: ✅ `/`

Smoke test observed header like:

```text
set-cookie: teremflow_session=...; HttpOnly; Max-Age=604800; Path=/; SameSite=lax
```

### CSRF considerations (quick OWASP-ish)

- With cookie auth + `SameSite=Lax` + strict CORS, the current surface is reasonably safe.
- Recommendation (future): If you add more state-changing endpoints or cross-site embeds, consider adding CSRF tokens or switching sensitive writes to header token auth.

---

## 4) Backend Correctness Review (with smoke tests)

### Auth
- **Login**: `POST /auth/login` ✅ (returns 200 + Set-Cookie)
- **Me**: `GET /auth/me` ✅ (works with cookie jar)

**Seeded credentials (current)**
- `lior` / `lior123`
- `lidor` / `lidor123`
- `iris` / `iris 123` (includes a space)

### Cases
- `POST /cases/` ✅ when using `deductible_ils_gross` (offline-friendly).  
  Attempting to create with `deductible_usd` will call BOI FX and can fail on machines without outbound DNS/network.

### Expenses + deductible split
- `POST /cases/{id}/expenses/` ✅
- Verified split behavior when crossing remaining deductible:
  - One original expense consumed most of deductible.
  - Second expense split into **two rows** with shared `split_group_id`, with payers `CLIENT_DEDUCTIBLE` and `INSURER`.

### Retainer
- `GET /cases/{id}/retainer/accruals` returned `[]` for a case opened `2026-01-01`. This is **expected** by rule:
  - For cases opened Jan–Jun, start month is **month after open_date**, so accruals begin `2026-02-01`.
- Retainer payment credit still works:
  - Added payment 1000, summary showed credit balance 1000.

### Fees + retainer credit application
- `POST /cases/{id}/fees/` ✅
- Verified credit allocation:
  - Added `COURT_STAGE_1_DEFENSE` computed 20000.
  - Credit covered 1000, cash due 19000.

### Analytics
- `GET /analytics/overview` ✅ and returned consistent totals matching the created data.

### Alerts / tasks + notifications
- `POST /tasks/daily` ✅ with header `X-Tasks-Token: dev-tasks-secret-change-me` (local default)
- `GET /notifications/` ✅ (2 notifications generated)
- `POST /notifications/{id}/read` ✅ (read flag persisted)

---

## 5) Frontend Correctness Review (high-level)

- Build succeeded (`npm run build`).
- Main risk area for local usage is **hostname alignment** for cookies:
  - Use **`VITE_API_URL=http://localhost:8000`** (not `127.0.0.1`) to avoid cookie host mismatches during browser requests.

---

## 6) Build & Test Evidence (real outputs)

### Backend tests

```text
pytest -q
...........                                                              [100%]
```

### Frontend build

```text
npm run build
✓ built in 4.88s
(!) Some chunks are larger than 500 kB after minification...
```

---

## 7) Risk Register (recommended actions)

| ID | Severity | Component | Description | How to reproduce | Recommended fix | Fix now? |
|---|---|---|---|---|---|---|
| R1 | High | deploy | Cron + API secret mismatch risk (`render.yaml` has `TASKS_DAILY_SECRET: sync: false`) | Deploy without manually setting both env vars | Document + enforce that `TASKS_DAILY_SECRET` must be set identically in both services | Recommended |
| R2 | Medium | backend/dev | SQLite dev mode uses `create_all` not Alembic; schema parity not guaranteed | Run local on sqlite; compare with Postgres migration schema | Keep sqlite for local convenience, but add Postgres local instructions for parity testing | Optional |
| R3 | Medium | security | Cookie auth lacks explicit CSRF protection | N/A (design-level) | Consider CSRF token if app becomes public / adds more write endpoints | Optional |
| R4 | Low/Med | auth | Password min length lowered to 7 and passwords include spaces | N/A (policy) | If production accounts are introduced, revert to >= 8 and add password reset UX | Optional |
| R5 | Low | frontend | Single large JS bundle | Build output warning | Add code splitting later (dynamic import / manualChunks) | Optional |

---

## 8) Deployment Readiness (Local + Render)

### Local run checklist (recommended)

Backend:
- `DATABASE_URL=sqlite+pysqlite:///./dev.db`
- `ENVIRONMENT=development`
- Run: `python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000`

Frontend:
- `VITE_API_URL=http://localhost:8000`
- Run: `npm run dev`

### Render checklist (must-haves)

- API service:
  - `DATABASE_URL` from Render Postgres
  - `ENVIRONMENT=production`
  - `JWT_SECRET` generated (ok)
  - `CORS_ORIGINS` must include exact frontend domain
  - **`TASKS_DAILY_SECRET` must be set**
- Cron service:
  - `API_URL` correct
  - **`TASKS_DAILY_SECRET` must be set to the exact same value as API**

---

## 9) Appendix

### Key files inspected/used in audit
- `backend/app/api/routes/*`
- `backend/app/services/*` (cases/expenses/fees/retainer/alerts/boi_fx)
- `backend/app/core/config.py`, `backend/app/core/security.py`
- `frontend/src/*` (pages/lib/auth/api)
- `render.yaml`

### Notable local-hardening fixes applied prior to this report
- `backend/app/main.py`: dev-only sqlite `create_all` + seed at startup
- `backend/app/models/expense.py`: portable UUID type for sqlite
- `backend/app/db/init_db.py`: seeded passwords updated + upsert behavior
- `backend/app/schemas/auth.py` + `backend/app/core/security.py`: password min length set to 7
- `backend/alembic.ini`: fixed invalid interpolation (kept as a safe placeholder)

### CORS + cookie auth correctness

`backend/app/main.py` configures:
- `allow_credentials=True` ✅
- `allow_origins=settings.cors_origins` ✅

**Render hardening**: `backend/app/core/config.py` now parses `CORS_ORIGINS` robustly:
- single string
- comma-separated list
- JSON list

This prevents common Render misconfiguration (string env var) from breaking cookie auth CORS.

### JWT secret handling & expiry

- Secret loaded from env var `JWT_SECRET` (Render blueprint generates it) ✅
- Default expiry: 7 days (`jwt_expires_minutes`) ✅
- JWT payload contains `sub` (user id) + `exp` ✅

### `/tasks/daily` auth

`backend/app/api/routes/tasks.py` checks `X-Tasks-Token == settings.tasks_daily_secret`.

Smoke test succeeded with default local secret:

```text
POST /tasks/daily with X-Tasks-Token: dev-tasks-secret-change-me -> {"ok":true,"sent":2}
```

### OWASP-ish quick checks (CSRF & CORS)

**Current posture: acceptable but not “CSRF-hardened”**.
- Using cookie auth without CSRF token is common when relying on `SameSite=Lax` and strict CORS.
- With **SameSite=Lax**, cross-site POST requests generally won’t include cookies, reducing CSRF risk for POST endpoints.
- Risk increases if:
  - `SameSite` changes to `None`
  - any state-changing endpoints are exposed via GET
  - CORS origin list is loosened (e.g., wildcard-like patterns via proxy)

**Recommendation**: treat CSRF token addition as a medium-priority hardening item (see Risk Register).

---

## 4) Backend Correctness Review

### A) BOI FX (USD/ILS)

**What it does**
- Fetches USD/ILS rate from BOI SDMX endpoint:
  - `https://api.boi.org.il/SDMX/v2/data/EXR/RER_USD_ILS`
- Retries 3 times with exponential backoff.
- Parses SDMX-JSON to `(rate, rate_date)`.
- Caches:
  - in-memory `_mem_cache`
  - optional DB cache table `fx_rate_cache`
- Fallback: searches backward up to 10 days.

**Edge cases to test**
- Network unavailable / timeout (raises `FxLookupError` with clear message)
- Missing data for target day (fallback to prior day)
- JSON parse changes / missing keys (returns `None` and continues fallback)

**Test results**
- Unit tests pass (`pytest -q`), including fallback logic coverage.
- Live BOI network calls were avoided in smoke tests (case created via imported ILS deductible).

### B) Deductible / Expenses split

**What it does**
- Computes “consumed on deductible” as sum of expenses with `payer=CLIENT_DEDUCTIBLE`.
- Remaining is clamped at zero by `deductible_remaining(...)`.
- Adding expense:
  - If payer explicitly `INSURER`: no deductible consumption; sets `insurer_started=True`.
  - Otherwise: splits into deductible portion + insurer portion when crossing remaining deductible.
  - If split happens: assigns shared `split_group_id` and sets `insurer_started=True`, `insurer_start_date=expense_date`.

**Smoke test results**
- Case deductible: 1000
- Expense 1: 900 → single row, payer `CLIENT_DEDUCTIBLE`
- Expense 2: 200 → split into two rows (100 deductible + 100 insurer), `split_group_id` set, `insurer_started=true`.

Truncated response evidence:

```json
[
  {"amount_ils_gross":"100.00","payer":"CLIENT_DEDUCTIBLE","split_group_id":"..."},
  {"amount_ils_gross":"100.00","payer":"INSURER","split_group_id":"..."}
]
```

### C) Retainer (accrual rules + net60 + payments)

**What it does**
- Start month rule:
  - Jan–Jun open → accrual starts **next month**
  - Jul–Dec open → accrual starts **next Jan**
- `ensure_accruals_up_to` creates monthly accruals through current month, with:
  - invoice_date = accrual_month (1st)
  - due_date = invoice_date + 60 days (Net 60)
  - amount = 945.00 gross
- Payments are “cash basis” and allocate oldest-first:
  - if `total_paid >= 945` mark accrual paid, etc.

**Edge cases**
- Case opened late in month: start month logic remains month-based (not day-based).
- Payment before any accrual exists: increases credit but won’t mark accruals as paid until accruals exist.

**Smoke test result**
- Case open_date: 2026-01-01 → start month is 2026-02-01.
- Today (audit date): 2026-01-13 → accruals through Jan only ⇒ **no accruals yet**, which is correct.

```text
GET /cases/1/retainer/accruals -> []
```

Added payment still works:

```json
[{"payment_date":"2026-02-01","amount_ils_gross":"945.00"}]
```

### D) Fees (events + overrides + quantity + credit allocation)

**What it does**
- Computes fee amounts by event type:
  - fixed stage amounts
  - hourly/extra hearing multiply by quantity
  - small claims requires override (raises error if missing)
- Applies retainer credit chronologically by `(event_date asc, id asc)` allocating credit until exhausted.

**Smoke test result**
- Retainer paid: 945
- Added `COURT_STAGE_1_DEFENSE` (20000) → covered 945, due 19055
- Added `DEMAND_HOURLY` qty 2 (1400) → covered 0, due 1400 (credit exhausted)

Retainer summary confirmed:
- applied_to_fees_total = 945
- fees_due_total = 19055 + 1400 = 20455

### E) Alerts (dedupe + thresholds)

**What it does**
- Dedupe uses `alert_events` table:
  - insurer started: `case:{id}:insurer_started`
  - deductible near: `case:{id}:deductible_near`
  - retainer due soon/overdue: `accrual:{accrual_id}:...`
- Deductible near threshold: `remaining < deductible * pct` OR `remaining < abs`
- Retainer due soon: due within next 7 days and unpaid
- Retainer overdue: due_date < today and unpaid

**Smoke test result**
- Triggered `/tasks/daily` and got `sent=2`:
  - Insurer started paying
  - Deductible near exhaustion

### F) Analytics (`/analytics/overview`)

**What it does**
- Filters cases by:
  - optional `case_type`
  - optional `payer_status`: derived as `closed` if case closed else `insurer` if `insurer_started` else `client`
- Pulls expenses in date range and aggregates:
  - total, on deductible, on insurer
  - per-case totals and deductible remaining (computed live)
  - expense split: attorney vs other
  - stage distribution: highest court stage event per case (stages 1..5)
  - time series: monthly/quarterly/yearly totals

**Smoke test result**
- Response shape correct and totals consistent with inserted expenses:

```json
{
  "total_expenses_ils_gross":"1100.00",
  "total_on_deductible_ils_gross":"1000.00",
  "total_on_insurer_ils_gross":"100.00",
  "court_cases_end_stage_distribution":[{"stage":1,"count":1},...],
  "monthly":[{"period":"2026-01","total_expenses_ils_gross":"1100.00"}]
}
```

**Correctness note**: court stage distribution counts only cases with at least one stage event; court cases with no stage events are not represented (see Risk Register).

### G) Notifications

**What it does**
- Lists latest 200 notifications ordered desc by created_at/id
- Marks a notification as read via POST `/notifications/{id}/read`

**Smoke test**
- After `/tasks/daily`, `GET /notifications/` returned 2 rows.
- After marking id=1 read, re-list shows `is_read=true` for id=1.

---

## 5) Frontend Correctness Review

### Global API + auth wiring

- `frontend/src/lib/api.ts` uses `credentials: 'include'` ✅
- `AuthContext` uses:
  - POST `/auth/login`
  - GET `/auth/me`
  - POST `/auth/logout`
- Auth guard blocks private routes until `/auth/me` completes.

### Money/date formatting

- All money displayed as ILS gross with **2 decimals** via `formatILS(...)` ✅
- Dates are normalized via `formatDateYMD(...)` and `formatDateTimeShort(...)` ✅

### RTL/theme consistency

- App uses RTL (`index.html dir="rtl"`) and Heebo.
- Tailwind theme uses CSS variables; variables are stored as `R G B` to support Tailwind opacity modifiers (e.g. `bg-card/70`). ✅

### Screen-by-screen endpoint wiring

#### CaseDetails → Expenses tab
- GET `/cases/{id}`
- GET `/cases/{id}/expenses/`
- POST `/cases/{id}/expenses/` (Add Expense modal)

#### CaseDetails → Retainer tab
- GET `/cases/{id}/retainer/summary`
- GET `/cases/{id}/retainer/accruals`
- GET `/cases/{id}/retainer/payments`
- POST `/cases/{id}/retainer/payments`

#### CaseDetails → Fees tab
- GET `/cases/{id}/fees/`
- POST `/cases/{id}/fees/`

#### Analytics page
- GET `/analytics/overview` with query params:
  - `start_date`, `end_date`, optional `case_type`, and `payer_status`
- Uses Recharts for charts and links cases to `/cases/{case_id}`.

#### Notifications page
- GET `/notifications/`
- POST `/notifications/{id}/read`

### Type alignment (TS vs backend)

Backend serializes `Decimal` values as **strings** in JSON (observed in smoke tests), e.g. `"1000.00"`. Frontend types allow `string | number` for monetary fields, and formatting converts robustly. ✅

No blocking mismatches found.

---

## 6) Build & Test Evidence

### Backend unit tests

Command:

```bash
cd backend
pytest -q
```

Output (real, truncated):

```text
...........                                                              [100%]
```

Notes:
- Warnings present from `pytest-asyncio` about default loop scope + Python 3.14 deprecations; tests still pass.

### Frontend build

Command:

```bash
cd frontend
npm run build
```

Output (real, truncated):

```text
vite v7.3.1 building client environment for production...
✓ 680 modules transformed.
✓ built in 4.37s
```

**Writes**: `frontend/dist/*` artifacts were produced by Vite (expected).

---

## 7) Risk Register

| ID | Severity | Component | Description | How to reproduce | Recommended fix (precise) | Fix now? |
|---|---|---|---|---|---|---|
| R-001 | Medium | Deploy | Cron secret mismatch/absence breaks `/tasks/daily` on Render | Deploy via blueprint without manually setting secret | Render dashboard: set identical `TASKS_DAILY_SECRET` on **API + Cron**; consider a safer shared-secret mechanism if Render supports it | Yes |
| R-002 | Medium | Security | No explicit CSRF token; relies on SameSite=Lax + CORS | N/A (design) | Add CSRF token (double-submit or header token) for state-changing endpoints; keep SameSite strict | No (next hardening) |
| R-003 | Medium | Analytics | Stage distribution omits court cases with no stage events (could undercount) | Create court case with no stage events; observe it not counted | Decide desired behavior: count as “stage 0/none” or include separately; update `backend/app/api/routes/analytics.py` if needed | No (product decision) |
| R-004 | Medium | Dev/QA | Local Postgres auth failed; integration testing depends on correct local DB creds | `engine.connect()` with default URL failed due to password | Improve README with exact Postgres setup (or provide docker compose) and `.env` guidance | No (but recommended) |
| R-005 | Low/Medium | Backend | Alerts deductible remaining can go negative if data inconsistent (no clamp) | Insert expenses exceeding deductible manually | Clamp remaining at 0 in alerts display calculation (non-business-logic change is arguable; treat carefully) | No |
| R-006 | Low | Frontend | Analytics stage chart uses stage labels; no “empty state” for distribution | Court data empty | Add UI note when distribution all zeros | No |

---

## 8) Deployment Readiness (Local + Render)

### Local run checklist

**Backend**
- Ensure a DB is reachable via `DATABASE_URL` (default points to local Postgres).
- Run migrations (preferred for Postgres): `alembic upgrade head`
- Seed users: `python -c "... ensure_seeded ..."`
- Start API: `uvicorn app.main:app --reload --port 8000`

**Frontend**
- `npm install`
- set `VITE_API_URL=http://localhost:8000` in `.env`
- `npm run dev`

### Render checklist (env vars + formats)

**API service**
- `DATABASE_URL` (from Render Postgres)
- `ENVIRONMENT=production`
- `JWT_SECRET` (generated)
- `CORS_ORIGINS` (exact frontend origin; accepts single/csv/json list)
  - Example: `https://teremflow-frontend.onrender.com`
- `TASKS_DAILY_SECRET` (**manual**, must match cron)

**Cron service**
- `API_URL=https://teremflow-api.onrender.com`
- `TASKS_DAILY_SECRET` (**manual**, same as API)

### Confirm TASKS_DAILY_SECRET handling

`render.yaml` uses `sync: false` for both services, which means **Render will not auto-propagate** the value. This is secure but easy to misconfigure; treat as a deployment gating step.

---

## 9) Appendix

### Key files inspected (non-exhaustive)

**Backend**
- `backend/app/main.py`
- `backend/app/core/config.py`
- `backend/app/core/security.py`
- `backend/app/api/routes/auth.py`
- `backend/app/api/routes/cases.py`
- `backend/app/api/routes/expenses.py`
- `backend/app/api/routes/retainers.py`
- `backend/app/api/routes/fee_events.py`
- `backend/app/api/routes/analytics.py`
- `backend/app/api/routes/notifications.py`
- `backend/app/api/routes/tasks.py`
- `backend/app/services/boi_fx.py`
- `backend/app/services/cases.py`
- `backend/app/services/expenses.py`
- `backend/app/services/deductible.py`
- `backend/app/services/retainer.py`
- `backend/app/services/fees.py`
- `backend/app/services/alerts.py`
- `backend/requirements.txt`
- `render.yaml`

**Frontend**
- `frontend/src/lib/api.ts`
- `frontend/src/auth/AuthContext.tsx`
- `frontend/src/lib/types.ts`
- `frontend/src/lib/format.ts`
- `frontend/src/pages/CaseDetailsPage.tsx`
- `frontend/src/pages/AnalyticsPage.tsx`
- `frontend/src/pages/NotificationsPage.tsx`
- `frontend/src/pages/CasesPage.tsx`
- `frontend/src/pages/DashboardPage.tsx`
- `frontend/src/index.css`
- `frontend/tailwind.config.js`
- `frontend/package.json`

### Assumptions

- Phase 1 access model: all authenticated users can view all cases/notifications (no per-user authorization enforced).
- Smoke tests were executed against a **SQLite fallback DB** (`audit.db`) due to local Postgres password auth failure; production uses Postgres + Alembic migrations.



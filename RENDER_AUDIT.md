# ביקורת (Audit) התאמה להעלאה ב-Render — TeremFlow

**תאריך:** 1 בפברואר 2026  
**מסקנה:** **התוכנה מתאימה להעלאה ב-Render**, עם מספר פעולות חובה לפני/אחרי הדפלוי.

---

## 1. סיכום מנהלים

| קריטריון | סטטוס | הערות |
|----------|--------|--------|
| **תצורת Render** | ✅ | `render.yaml` קיים ומגדיר DB + API + Frontend + Cron |
| **Backend (FastAPI)** | ✅ | Python, `requirements.txt`, `start.sh`, מיגרציות Alembic |
| **Frontend (React/Vite)** | ✅ | Static Site, `npm run build`, `dist` |
| **מסד נתונים** | ✅ | Postgres 16 ב-Blueprint |
| **משתני סביבה** | ⚠️ | חובה להגדיר ידנית `TASKS_DAILY_SECRET` ב-API וב-Cron |
| **גרסת Python** | ⚠️ | מומלץ להגדיר גרסה (למשל 3.12) — ראו להלן |

**המלצה:** אפשר להעלות ל-Render. יש לבצע את הפעולות המפורטות בסעיף "פעולות חובה לפני/אחרי דפלוי".

---

## 2. מה נבדק

### 2.1 קובץ `render.yaml`

- **Databases:** Postgres 16 (`teremflow-db`) — חיבור אוטומטי ל-API דרך `DATABASE_URL`.
- **API (teremflow-api):**
  - `runtime: python`
  - `rootDir: backend`
  - `buildCommand: pip install -r requirements.txt`
  - `startCommand: bash start.sh`
  - משתנים: `DATABASE_URL` (מ-DB), `ENVIRONMENT=production`, `JWT_SECRET` (generate), `TASKS_DAILY_SECRET` (ידני), `CORS_ORIGINS`.
- **Frontend (teremflow-frontend):**
  - `runtime: static`
  - `buildCommand: npm install && npm run build`
  - `staticPublishPath: dist`
  - `VITE_API_URL` מצביע ל-API.
- **Cron (teremflow-daily-tasks):**
  - `schedule: "0 6 * * *"` (יומי 06:00 UTC)
  - קורא ל-`/tasks/daily` עם header `X-Tasks-Token`.

המבנה תואם את מה שמתועד ב-README ובעבר נבדק ב-ULTRA_AUDIT.

### 2.2 Backend

- **הפעלה:** `start.sh` מריץ `alembic upgrade head`, seed, ואז `uvicorn`.
- **תלויות:** `requirements.txt` מכיל FastAPI, uvicorn, SQLAlchemy, psycopg, alembic, pydantic, python-jose, bcrypt, openpyxl וכו' — מתאימים ל-Render.
- **פרודקשן:** ב-production אין שימוש ב-SQLite; רק Postgres + מיגרציות.
- **בריאות:** קיים endpoint `/health` — שימושי ל-Render health checks.

### 2.3 Frontend

- **Build:** `npm run build` (tsc + vite build) — מתאים ל-Static Site.
- **פלט:** `dist` — תואם ל-`staticPublishPath: dist` ב-`render.yaml`.
- **API:** משתמש ב-`VITE_API_URL` — יש להגדיר ב-Render לדומיין ה-API.

### 2.4 אבטחה ותאימות

- **CORS:** `config.py` תומך ב-CORS כ־string, רשימה מופרדת בפסיקים או JSON — מתאים למשתנה `CORS_ORIGINS` ב-Render.
- **Cookies:** HttpOnly, Secure ב-production, SameSite=Lax.
- **CSRF:** קיים middleware ל-production (cookie + header).
- **Cron:** אימות דרך `X-Tasks-Token` vs `TASKS_DAILY_SECRET`.

---

## 3. סיכונים ופעולות נדרשות

### 3.1 חובה — סוד Cron (`TASKS_DAILY_SECRET`)

ב-`render.yaml` ל-API ול-Cron מופיע `TASKS_DAILY_SECRET` עם `sync: false`, כלומר Render לא מסנכרן את הערך ביניהם.

- **סיכון:** אם לא מגדירים את אותו ערך בדיוק ב-API וב-Cron, הקריאה ל-`/tasks/daily` תקבל 401 והתראות/משימות יומיות לא ירוצו.
- **פעולה:** אחרי יצירת ה-Blueprint, ב-Dashboard של Render:
  1. ב-**teremflow-api** — להוסיף משתנה סביבה `TASKS_DAILY_SECRET` עם ערך חזק (למשל סוד אקראי).
  2. ב-**teremflow-daily-tasks** — להוסיף **אותו ערך בדיוק** ל-`TASKS_DAILY_SECRET`.

### 3.2 מומלץ — גרסת Python

- **מצב:** אין בפרויקט `runtime.txt` או `.python-version`. Render יבחר גרסת Python ברירת מחדל (למשל 3.11 או 3.13, תלוי בתאריך יצירת השירות).
- **הערה:** פיתוח מקומי עם Python 3.14 — Render עשוי עדיין לא לתמוך ב-3.14.
- **פעולה:** להוסיף root של ה-repo (או ב-`backend/` אם Render קורא משם) קובץ `.python-version` עם תוכן למשל `3.12` או `3.13`, כדי לקבוע גרסה תואמת ויציבה.

### 3.3 דומיינים ב-`render.yaml`

- **CORS_ORIGINS** ב-`render.yaml` מוגדר כ-`https://teremflow-frontend.onrender.com`.
- **VITE_API_URL** ב-frontend מוגדר כ-`https://teremflow-api.onrender.com`.

אם שמות השירותים או הדומיינים ב-Render שונים (למשל אחרי שינוי שם), יש לעדכן את המשתנים האלה בהתאם.

---

## 4. צ'קליסט דפלוי ל-Render

- [ ] חיבור הריפו ל-Render ובחירת Blueprint עם `render.yaml`.
- [ ] וידוא שה-Postgres (`teremflow-db`) נוצר ו-`DATABASE_URL` מחובר ל-API.
- [ ] הגדרת `TASKS_DAILY_SECRET` **זהה** ב-**teremflow-api** וב-**teremflow-daily-tasks**.
- [ ] עדכון `CORS_ORIGINS` ב-API אם דומיין ה-frontend שונה.
- [ ] עדכון `VITE_API_URL` ב-frontend אם דומיין ה-API שונה.
- [ ] (אופציונלי) הוספת `.python-version` (למשל `3.12`) ליציבות גרסת Python.

---

## 5. סיכום

התוכנה **מתאימה להעלאה ב-Render**: התצורה, ה-Backend, ה-Frontend וה-Cron תואמים את המודל של Render. הסיכון העיקרי הוא אי-התאמה או חוסר בהגדרת `TASKS_DAILY_SECRET` בין ה-API ל-Cron — טיפול בזה (לפי הצ'קליסט) משלים את ההתאמה לדפלוי.

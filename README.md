## TeremFlow

**TeremFlow** — “Every expense. Every stage. One clear picture.”

מערכת לניהול תיקי הגנה ברשלנות רפואית עבור טר"מ: השתתפות עצמית (אקסס), הוצאות, ריטיינר, שלבי שכ"ט, אנליטיקה והתראות.

### עקרונות

- **כל הסכומים בש״ח וכוללים מע״מ (ברוטו)**. אין פירוק נטו/מע״מ.
- UI בעברית **RTL**.
- Auth באמצעות **JWT בעוגייה httpOnly**.
- Render: FastAPI Web Service + React Static Site + Render Postgres + Cron Job שפוגע ב־`/tasks/daily`.

### מבנה ריפו

- `backend/` — FastAPI + SQLAlchemy + Alembic
- `frontend/` — React + TS + Vite + Tailwind
- `render.yaml` — תצורת Render (כולל Cron)

---

## פיתוח מקומי

### Backend

#### אפשרות מומלצת (לוקאל): SQLite (בלי Postgres)

במצב `ENVIRONMENT=development` ו־`DATABASE_URL` שמתחיל ב־`sqlite...` ה־backend:
- ייצור טבלאות אוטומטית
- יבצע seed למשתמשים

הרצה:

```bash
cd backend
export DATABASE_URL="sqlite+pysqlite:///./dev.db"   # Windows PowerShell: $env:DATABASE_URL="sqlite+pysqlite:///./dev.db"
export ENVIRONMENT="development"                    # Windows PowerShell: $env:ENVIRONMENT="development"
uvicorn app.main:app --reload --port 8000
```

#### אפשרות מלאה (לפרודקשן-פריטי): Postgres + Alembic

1) צור DB מקומי (Postgres) בשם `teremflow`.

אפשרות קלה עם Docker:

```bash
cd .
docker compose up -d
```

ואז:
- Host: `localhost`
- Port: `5432`
- User: `postgres`
- Password: `postgres`
- DB: `teremflow`

2) התקנת תלויות:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

3) קובץ env:

- בגלל הגבלות סביבתיות ב־Cursor, קבצי `.env*` עשויים להיות חסומים לעריכה/יצירה אוטומטית.
- השתמשו בקובץ `backend/env.example` כבסיס והעתיקו אותו ל־`.env` ידנית.

4) מיגרציות + seed:

```bash
export DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/teremflow"   # Windows PowerShell: $env:DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/teremflow"
export ENVIRONMENT="development"                                                       # Windows PowerShell: $env:ENVIRONMENT="development"

alembic upgrade head
python -c "from app.db.session import SessionLocal; from app.db.init_db import ensure_seeded; db=SessionLocal(); ensure_seeded(db); db.close()"
```

5) הרצת שרת:

```bash
uvicorn app.main:app --reload --port 8000
```

**משתמשים התחלתיים (לוקאל):**
- `lidor` / `lidor123`
- `iris` / `iris 123` (יש רווח)
- `lior` / `lior123`

### Frontend

```bash
cd frontend
npm install
```

Env:
- השתמשו ב־`frontend/env.example` כבסיס והעתיקו ל־`.env` (ידנית).

מומלץ בלוקאל (cookie auth): להגדיר API כ־`localhost` (לא `127.0.0.1`):

```bash
export VITE_API_URL="http://localhost:8000"   # Windows PowerShell: $env:VITE_API_URL="http://localhost:8000"
```

```bash
npm run dev
```

---

## Render Deployment

### 1) Deploy באמצעות `render.yaml`

- חברו את הריפו ל־Render.
- בחרו “Blueprint” והצביעו על `render.yaml`.
- חכו לסיום ה-build וה-deploy של כל השירותים.

המערכת תיצור:
- Postgres: `teremflow-db`
- Backend: `teremflow-api`
- Frontend: `teremflow-frontend`
- Cron: `teremflow-daily-tasks` (פוגע ב־`/tasks/daily`)

### 2) חובה אחרי הדפלוי הראשון — TASKS_DAILY_SECRET

ב-Dashboard של Render:

1. **teremflow-api** → Environment → הוסיפו משתנה:
   - **Key:** `TASKS_DAILY_SECRET`
   - **Value:** ערך סודי חזק (למשל סיסמה אקראית ארוכה)
2. **teremflow-daily-tasks** → Environment → הוסיפו **אותו ערך בדיוק**:
   - **Key:** `TASKS_DAILY_SECRET`
   - **Value:** (אותו ערך כמו ב-API)

בלי זה הקריאה ל־`/tasks/daily` תקבל 401 והתראות/משימות יומיות לא ירוצו.

### 3) משתני סביבה (יתר)

Backend:
- `DATABASE_URL` מגיע אוטומטית מה־DB
- `JWT_SECRET` נוצר אוטומטית
- `CORS_ORIGINS` — ברירת מחדל: `https://teremflow-frontend.onrender.com`. אם שיניתם שם ל-frontend, עדכנו.

Frontend:
- `VITE_API_URL` — ברירת מחדל: `https://teremflow-api.onrender.com`. אם שיניתם שם ל-API, עדכנו.

### 4) Cron

ה־Cron משתמש ב־header:
- `X-Tasks-Token: $TASKS_DAILY_SECRET`

---

## הערות על Excel Import

ב־MVP ייבוא אקסל ממומש עם `openpyxl` (ללא `pandas`) כדי להימנע מתלויות קומפילציה מקומיות ב־Windows.



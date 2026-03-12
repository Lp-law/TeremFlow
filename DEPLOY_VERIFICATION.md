# אימות דיפלוי (Deploy Verification)

## מטרה

לוודא שדיפלוי ב-Render אכן משקף את הקוד האחרון: Backend מחזיר גרסה, הפרונט מציג אותה, ומיגרציות רצות.

## מה נוסף

- **Backend:** `GET /version` (דורש התחברות) מחזיר:
  - `git_sha` — מ־`RENDER_GIT_COMMIT` או `GIT_SHA`, אחרת `"unknown"`
  - `build_time_utc` — זמן build/startup
  - `environment` — מ־`ENVIRONMENT`
  - `db_revision` — revision נוכחי מ־`alembic_version` (read-only)
  - `service`: `"teremflow-api"`
- **Frontend:** בתחתית המסך (footer) מוצג **Build: \<sha\>** — ה-sha מגיע מהבקאנד (`/version`).
- **Cache:** תגובת `/version` ו־`index.html` (meta) עם `Cache-Control: no-store, no-cache, must-revalidate` ו־`Pragma: no-cache`.
- **Startup:** ב־`start.sh` אחרי `alembic upgrade head` מודפס `DB revision after migrate: <revision>`. כישלון מיגרציה מפיל את הדיפלוי (`set -e`).

## איפה רואים את ה-SHA

- **Backend:** אחרי דיפלוי — קריאה ל־`GET https://teremflow-api.onrender.com/version` (עם cookie התחברות) מחזירה את ה־`git_sha` וה־`db_revision`.
- **Frontend:** בתחתית כל דף (Dashboard, תיקים וכו') — שורת טקסט קטנה: **Build: \<sha\>** (ה-sha של הבקאנד).

## צעדי בדיקה ידניים

1. **לאחר דיפלוי:** התחבר לאפליקציה, פתח בדפדפן:
   ```
   https://teremflow-api.onrender.com/version
   ```
   וודא ש־`git_sha` תואם ל־commit שבו דחפת (ב-Render: Build logs / RENDER_GIT_COMMIT).

2. **ב־UI:** וודא שבתחתית המסך מופיע "Build: \<sha\>" עם אותו sha.

3. **Hard refresh:** עשה Ctrl+Shift+R (או Cmd+Shift+R) ובדוק שוב — ה-sha נשאר עקבי עם `/version`.

4. **מיגרציות:** ב־Render → Logs של השירות `teremflow-api` חפש את השורה:
   ```
   DB revision after migrate: <revision>
   ```
   וודא שה-revision תואם ל־`db_revision` ב־`/version`.

## הערות

- אין Service Worker / PWA בפרונט — אין caching אגרסיבי של bundle.
- אי־הצלחה של `alembic upgrade head` ב־`start.sh` תגרום ל־exit nonzero ולדיפלוי כושל.

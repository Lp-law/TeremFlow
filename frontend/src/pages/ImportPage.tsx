import { useEffect, useState } from 'react'
import { BackButton } from '../components/BackButton'
import { API_BASE_URL } from '../lib/api'

export function ImportPage() {
  const [file, setFile] = useState<File | null>(null)
  const [result, setResult] = useState<any>(null)
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [wipeToken, setWipeToken] = useState('')
  const [wipeResult, setWipeResult] = useState<any>(null)
  const [isWiping, setIsWiping] = useState(false)
  const [dbStatus, setDbStatus] = useState<{ cases: number; clean: boolean } | null>(null)

  useEffect(() => {
    checkDbStatus()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function checkDbStatus() {
    try {
      const r = await fetch(`${API_BASE_URL}/admin/wipe-case-data-status`, { credentials: 'include' })
      if (r.ok) setDbStatus(await r.json())
    } catch {
      /* ignore */
    }
  }

  async function wipeData() {
    if (!wipeToken.trim()) {
      setError('נא להזין קוד אימות')
      return
    }
    setError(null)
    setWipeResult(null)
    setIsWiping(true)
    try {
      const r = await fetch(`${API_BASE_URL}/admin/wipe-case-data`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'X-Wipe-Token': wipeToken.trim(), 'Content-Type': 'application/json' },
      })
      if (!r.ok) {
        const d = await r.json().catch(() => ({}))
        throw new Error(d?.detail || 'שגיאה')
      }
      setWipeResult(await r.json())
      checkDbStatus()
    } catch (e: any) {
      setError(e?.message || 'שגיאה')
    } finally {
      setIsWiping(false)
    }
  }

  async function submit() {
    if (!file) return
    setError(null)
    setResult(null)
    setIsSubmitting(true)
    try {
      const form = new FormData()
      form.append('file', file)
      const res = await fetch(`${API_BASE_URL}/import/excel`, { method: 'POST', body: form, credentials: 'include' })
      if (!res.ok) {
        let detail = 'שגיאה'
        try {
          const data = await res.json()
          detail = data?.detail || detail
        } catch {
          // ignore
        }
        throw new Error(detail)
      }
      setResult(await res.json())
    } catch (e: any) {
      setError(e?.message || 'שגיאה')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen w-full px-6 py-10">
      <div className="mx-auto w-full max-w-3xl">
        <div className="flex items-center justify-between gap-4">
          <div className="text-right">
            <div className="text-2xl font-bold">ייבוא מאקסל</div>
            <div className="text-sm text-muted mt-1">MVP: יצירת תיקים לפי עמודות מוכרות</div>
          </div>
          <BackButton />
        </div>

        <div className="mt-6 card p-6 text-right">
          <div className="text-sm font-semibold text-amber-400/90">מחיקת נתונים לפני ייבוא חדש</div>
          <div className="text-xs text-muted mt-1">מוחק תיקים, אירועי שכ״ט, אקרואלים, תשלומים, הוצאות. לא מוחק משתמשים.</div>
          <div className="mt-3 flex gap-3 items-center">
            <input
              type="password"
              placeholder="קוד אימות (WIPE_CASE_DATA_SECRET)"
              value={wipeToken}
              onChange={(e) => setWipeToken(e.target.value)}
              className="input max-w-xs"
            />
            <button onClick={wipeData} disabled={!wipeToken.trim() || isWiping} className="btn btn-secondary">
              {isWiping ? 'מוחק…' : 'מחיקת כל הנתונים'}
            </button>
          </div>
          {wipeResult ? (
            <div className="mt-2 text-sm text-green-400">נמחק: {wipeResult.deleted?.cases ?? 0} תיקים</div>
          ) : null}
          <div className="mt-2">
            <button type="button" onClick={checkDbStatus} className="text-xs text-muted hover:text-primary">
              בדיקת מצב DB
            </button>
            {dbStatus !== null ? (
              <span className="mr-2 text-xs">
                {dbStatus.clean ? '✓ נקי (0 תיקים)' : `${dbStatus.cases} תיקים`}
              </span>
            ) : null}
          </div>
        </div>

        <div className="mt-6 card p-6 text-right">
          <div className="text-sm text-muted">בחרו קובץ Excel והעלו אותו לשרת.</div>
          <div className="mt-4 flex flex-col md:flex-row gap-3 md:items-center">
            <input
              type="file"
              accept=".xlsx,.xls"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
              className="block w-full text-sm text-muted file:mr-4 file:py-2 file:px-4 file:rounded-xl file:border-0 file:bg-surface file:text-text hover:file:text-primary"
            />
            <button
              onClick={submit}
              disabled={!file || isSubmitting}
              className="btn btn-primary h-12 rounded-2xl"
            >
              העלאה
            </button>
          </div>

          {error ? <div className="mt-4 text-sm text-red-300">{error}</div> : null}
          {result ? (
            <pre className="mt-4 text-xs bg-surface/50 border border-border/60 rounded-2xl p-4 overflow-auto text-left">
              {JSON.stringify(result, null, 2)}
            </pre>
          ) : null}
        </div>
      </div>
    </div>
  )
}



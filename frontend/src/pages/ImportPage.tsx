import { useState } from 'react'
import { Link } from 'react-router-dom'
import { API_BASE_URL } from '../lib/api'

export function ImportPage() {
  const [file, setFile] = useState<File | null>(null)
  const [result, setResult] = useState<any>(null)
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

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
          <Link
            to="/dashboard"
            className="btn btn-secondary"
          >
            חזרה לדשבורד
          </Link>
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



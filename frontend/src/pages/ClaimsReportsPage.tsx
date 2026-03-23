import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { BackButton } from '../components/BackButton'
import { apiFetch } from '../lib/api'
import { formatILS } from '../lib/format'
import type { ClaimsReportOut } from '../lib/types'

type CreatePayload = {
  client_name: string
  title: string
  report_cutoff_date: string
  updated_to_date: string
}

function todayYmd(): string {
  return new Date().toISOString().slice(0, 10)
}

export function ClaimsReportsPage() {
  const [items, setItems] = useState<ClaimsReportOut[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showCreate, setShowCreate] = useState(false)
  const [isCreating, setIsCreating] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)
  const [form, setForm] = useState<CreatePayload>({
    client_name: 'טרם',
    title: `דו"ח תביעות ${todayYmd()}`,
    report_cutoff_date: todayYmd(),
    updated_to_date: todayYmd(),
  })

  async function load() {
    setError(null)
    setIsLoading(true)
    try {
      const data = await apiFetch<ClaimsReportOut[]>('/claims-reports')
      setItems(data)
    } catch (e: any) {
      setError(e?.message || 'שגיאה בטעינת דו"חות')
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  async function createReport(e: React.FormEvent) {
    e.preventDefault()
    setCreateError(null)
    setIsCreating(true)
    try {
      await apiFetch('/claims-reports', {
        method: 'POST',
        body: JSON.stringify({
          client_name: form.client_name.trim() || 'טרם',
          title: form.title.trim(),
          report_cutoff_date: form.report_cutoff_date,
          updated_to_date: form.updated_to_date || null,
        }),
      })
      setShowCreate(false)
      await load()
    } catch (err: any) {
      setCreateError(err?.message || 'שגיאה ביצירת דו"ח')
    } finally {
      setIsCreating(false)
    }
  }

  async function duplicateReport(id: number) {
    try {
      await apiFetch(`/claims-reports/${id}/duplicate`, { method: 'POST' })
      await load()
    } catch (e: any) {
      setError(e?.message || 'שגיאה בשכפול דו"ח')
    }
  }

  async function deleteReport(id: number) {
    if (!window.confirm('למחוק דו"ח זה?')) return
    try {
      await apiFetch(`/claims-reports/${id}`, { method: 'DELETE' })
      await load()
    } catch (e: any) {
      setError(e?.message || 'שגיאה במחיקת דו"ח')
    }
  }

  return (
    <div className="min-h-screen w-full px-6 py-10">
      <div className="mx-auto w-full max-w-6xl">
        <div className="flex items-center justify-between gap-4">
          <div className="text-right">
            <div className="text-2xl font-bold">דו"חות תביעות / חשיפות</div>
            <div className="text-sm text-muted mt-1">ניהול דו"חות תקופתיים, רשומות מקושרות/ידניות, וייצוא Word</div>
          </div>
          <div className="flex gap-2">
            <button className="btn btn-primary" onClick={() => setShowCreate(true)}>
              דו"ח חדש
            </button>
            <BackButton />
          </div>
        </div>

        {error ? <div className="mt-4 text-sm text-red-300 text-right">{error}</div> : null}

        <div className="mt-6 card p-4 overflow-x-auto">
          {isLoading ? (
            <div className="text-right text-muted py-8">טוען...</div>
          ) : items.length === 0 ? (
            <div className="text-right text-muted py-8">אין דו"חות עדיין</div>
          ) : (
            <table className="w-full text-sm text-right">
              <thead>
                <tr className="border-b border-border/60 text-muted">
                  <th className="py-3 px-2">כותרת</th>
                  <th className="py-3 px-2">לקוח</th>
                  <th className="py-3 px-2">תאריך חתך</th>
                  <th className="py-3 px-2">סטטוס</th>
                  <th className="py-3 px-2">מספר רשומות</th>
                  <th className="py-3 px-2">המלצת הפרשה</th>
                  <th className="py-3 px-2">פעולות</th>
                </tr>
              </thead>
              <tbody>
                {items.map((r) => (
                  <tr key={r.id} className="border-b border-border/30 last:border-0">
                    <td className="py-3 px-2 font-medium">{r.title}</td>
                    <td className="py-3 px-2">{r.client_name}</td>
                    <td className="py-3 px-2">{r.report_cutoff_date}</td>
                    <td className="py-3 px-2">{r.status === 'FINAL' ? 'סופי' : 'טיוטה'}</td>
                    <td className="py-3 px-2">{r.rows_count}</td>
                    <td className="py-3 px-2">{r.recommended_reserve_ils == null ? '—' : formatILS(r.recommended_reserve_ils)}</td>
                    <td className="py-3 px-2">
                      <div className="flex gap-2 justify-end">
                        <Link className="text-primary hover:underline" to={`/claims-reports/${r.id}`}>
                          פתח
                        </Link>
                        <button className="text-primary hover:underline" onClick={() => duplicateReport(r.id)}>שכפל</button>
                        {r.status !== 'FINAL' ? (
                          <button className="text-red-300 hover:underline" onClick={() => deleteReport(r.id)}>מחק</button>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {showCreate ? (
        <div className="modal">
          <div className="modal-overlay" onClick={() => !isCreating && setShowCreate(false)} />
          <form className="modal-panel max-w-lg" onSubmit={createReport}>
            <div className="text-right">
              <div className="text-lg font-semibold">יצירת דו"ח חדש</div>
              <div className="text-sm text-muted mt-1">דו"ח חדש ייווצר במצב טיוטה</div>
            </div>
            <div className="mt-4 space-y-3">
              <div>
                <label className="block text-sm text-muted mb-1 text-right">לקוח</label>
                <input className="input w-full" value={form.client_name} onChange={(e) => setForm((p) => ({ ...p, client_name: e.target.value }))} />
              </div>
              <div>
                <label className="block text-sm text-muted mb-1 text-right">כותרת</label>
                <input className="input w-full" value={form.title} onChange={(e) => setForm((p) => ({ ...p, title: e.target.value }))} required />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm text-muted mb-1 text-right">תאריך חתך</label>
                  <input className="input w-full" type="date" value={form.report_cutoff_date} onChange={(e) => setForm((p) => ({ ...p, report_cutoff_date: e.target.value }))} required />
                </div>
                <div>
                  <label className="block text-sm text-muted mb-1 text-right">מעודכן עד</label>
                  <input className="input w-full" type="date" value={form.updated_to_date} onChange={(e) => setForm((p) => ({ ...p, updated_to_date: e.target.value }))} />
                </div>
              </div>
              {createError ? <div className="text-sm text-red-300 text-right">{createError}</div> : null}
            </div>
            <div className="mt-6 flex gap-2 justify-end">
              <button type="button" className="btn btn-secondary" onClick={() => setShowCreate(false)} disabled={isCreating}>
                ביטול
              </button>
              <button type="submit" className="btn btn-primary" disabled={isCreating}>
                {isCreating ? 'יוצר...' : 'צור דו"ח'}
              </button>
            </div>
          </form>
        </div>
      ) : null}
    </div>
  )
}

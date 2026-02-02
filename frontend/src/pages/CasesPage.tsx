import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { BackButton } from '../components/BackButton'
import { apiFetch } from '../lib/api'
import { downloadTextFile, toCsv } from '../lib/csv'
import { formatILS } from '../lib/format'
import type { CaseOut, CaseType, FeeEvent } from '../lib/types'

const FEE_EVENT_LABEL: Record<string, string> = {
  COURT_STAGE_1_DEFENSE: 'שלב 1 — כתב הגנה',
  COURT_STAGE_2_DAMAGES: 'שלב 2 — חישובי נזק',
  COURT_STAGE_3_EVIDENCE: 'שלב 3 — הגשת ראיות',
  COURT_STAGE_4_PROOFS: 'שלב 4 — הוכחות',
  COURT_STAGE_5_SUMMARIES: 'שלב 5 — סיכומים',
  AMENDED_DEFENSE_PARTIAL: 'כתב הגנה מתוקן (חלקי)',
  AMENDED_DEFENSE_FULL: 'כתב הגנה מתוקן (מלא)',
  THIRD_PARTY_NOTICE: 'הודעת צד ג׳',
  ADDITIONAL_PROOF_HEARING: 'ישיבת הוכחות נוספת',
  DEMAND_FIX: 'מכתב דרישה — קבוע',
  DEMAND_HOURLY: 'מכתב דרישה — שעתי',
  SMALL_CLAIMS_MANUAL: 'תביעות קטנות — ידני',
}

const CASE_TYPE_LABEL: Record<string, string> = {
  COURT: 'תיק ביהמ"ש',
  DEMAND_LETTER: 'מכתב דרישה',
  SMALL_CLAIMS: 'תביעות קטנות',
}

const CASE_TYPES: CaseType[] = ['COURT', 'DEMAND_LETTER', 'SMALL_CLAIMS']

type CreateCaseForm = {
  case_reference: string
  case_type: CaseType
  open_date: string
  deductible_ils_gross: string
}

const defaultCreateForm: CreateCaseForm = {
  case_reference: '',
  case_type: 'COURT',
  open_date: new Date().toISOString().slice(0, 10),
  deductible_ils_gross: '',
}

export function CasesPage() {
  const [items, setItems] = useState<CaseOut[]>([])
  const [stageByCaseId, setStageByCaseId] = useState<Record<number, string>>({})
  const [query, setQuery] = useState('')
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isExporting, setIsExporting] = useState(false)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [createForm, setCreateForm] = useState<CreateCaseForm>(defaultCreateForm)
  const [createError, setCreateError] = useState<string | null>(null)
  const [isCreating, setIsCreating] = useState(false)

  async function load() {
    setError(null)
    setIsLoading(true)
    try {
      const data = await apiFetch<CaseOut[]>('/cases/')
      setItems(data)
      const stages: Record<number, string> = {}
      await Promise.all(
        data.map(async (c) => {
          try {
            const fees = await apiFetch<FeeEvent[]>(`/cases/${c.id}/fees/`)
            if (fees.length > 0) {
              const latest = [...fees].sort(
                (a, b) => new Date(b.event_date).getTime() - new Date(a.event_date).getTime()
              )[0]
              stages[c.id] = FEE_EVENT_LABEL[latest.event_type] || latest.event_type
            }
          } catch {
            // ignore per-case fee fetch errors
          }
        })
      )
      setStageByCaseId(stages)
    } catch (e: any) {
      setError(e?.message || 'שגיאה')
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return items
    return items.filter(
      (c) =>
        c.case_reference.toLowerCase().includes(q) ||
        (c.case_name?.toLowerCase().includes(q) ?? false) ||
        String(c.id).includes(q)
    )
  }, [items, query])

  async function exportCasesCsv() {
    setError(null)
    setIsExporting(true)
    try {
      const data = await apiFetch<CaseOut[]>('/cases/')
      const rows = data.map((c) => ({
        case_name: c.case_name ?? '',
        case_reference: c.case_reference,
        retainer_snapshot_ils_gross: c.retainer_snapshot_ils_gross ?? '',
        expenses_snapshot_ils_gross: c.expenses_snapshot_ils_gross ?? '',
        excess_remaining_ils_gross: c.excess_remaining_ils_gross,
        status: c.status,
      }))

      const columns = [
        'case_name',
        'case_reference',
        'retainer_snapshot_ils_gross',
        'expenses_snapshot_ils_gross',
        'excess_remaining_ils_gross',
        'status',
      ]

      const csv = toCsv(rows, columns, ',')
      const ts = new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-')
      downloadTextFile(`teremflow-cases-${ts}.csv`, csv)
    } catch (e: any) {
      setError(e?.message || 'שגיאה')
    } finally {
      setIsExporting(false)
    }
  }

  async function createCase(e: React.FormEvent) {
    e.preventDefault()
    setCreateError(null)
    const ref = createForm.case_reference.trim()
    const amt = createForm.deductible_ils_gross.trim()
    if (!ref || ref.length < 2) {
      setCreateError('נא להזין מזהה תיק (לפחות 2 תווים)')
      return
    }
    const num = parseFloat(amt)
    if (!amt || isNaN(num) || num <= 0) {
      setCreateError('נא להזין יתרת השתתפות עצמית (ש״ח) חיובית')
      return
    }
    setIsCreating(true)
    try {
      await apiFetch<CaseOut>('/cases/', {
        method: 'POST',
        body: JSON.stringify({
          case_reference: ref,
          case_type: createForm.case_type,
          open_date: createForm.open_date,
          deductible_ils_gross: String(num),
        }),
      })
      setShowCreateModal(false)
      setCreateForm(defaultCreateForm)
      await load()
    } catch (err: any) {
      setCreateError(err?.message || 'שגיאה ביצירת תיק')
    } finally {
      setIsCreating(false)
    }
  }

  return (
    <div className="min-h-screen w-full px-6 py-10">
      <div className="mx-auto w-full max-w-6xl">
        <div className="flex items-center justify-between gap-4">
          <div className="text-right">
            <div className="text-2xl font-bold">תיקים</div>
            <div className="text-sm text-muted mt-1">חיפוש, סינון, וכניסה לפרטי תיק</div>
          </div>
          <div className="flex gap-2">
            <Link
              to="/notifications"
              className="btn btn-secondary"
            >
              התראות
            </Link>
            <BackButton />
          </div>
        </div>

        <div className="mt-6 card p-6">
          <div className="flex flex-col md:flex-row gap-3 md:items-center md:justify-between">
            <input
              className="w-full md:max-w-md h-12 rounded-xl bg-surface border border-border/70 px-4 text-text placeholder:text-placeholder outline-none focus:ring-2 focus:ring-primary/60 focus:border-primary/70"
              placeholder="חיפוש לפי שם תיק או מזהה..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <div className="flex gap-2">
              <button
                onClick={() => setShowCreateModal(true)}
                className="btn btn-primary h-12"
              >
                תיק חדש
              </button>
              <button onClick={exportCasesCsv} className="btn btn-secondary h-12" disabled={isExporting}>
                {isExporting ? 'מייצא…' : 'ייצוא לאקסל (CSV)'}
              </button>
              <button onClick={load} className="btn btn-secondary h-12">
                רענון
              </button>
            </div>
          </div>

          {error ? <div className="mt-4 text-sm text-red-300 text-right">{error}</div> : null}
          {isLoading ? <div className="mt-6 text-sm text-muted text-right">טוען...</div> : null}

          {!isLoading ? (
            <div className="mt-6 overflow-x-auto">
              <table className="w-full text-sm" dir="rtl">
                <thead className="text-muted">
                  <tr className="border-b border-border/60">
                    <th className="text-right py-3">שם התיק</th>
                    <th className="text-right py-3">שלב ההליך</th>
                    <th className="text-right py-3">שכ״ט ששולם עד כה</th>
                    <th className="text-right py-3">הוצאות ששולמו עד כה</th>
                    <th className="text-right py-3">יתרת השתתפות עצמית</th>
                    <th className="text-right py-3">סטטוס</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((c) => (
                    <tr key={c.id} className="border-b border-border/30 hover:bg-surface/30">
                      <td className="py-3">
                        <Link to={`/cases/${c.id}`} className="text-primary hover:underline">
                          {c.case_name ?? c.case_reference}
                        </Link>
                      </td>
                      <td className="py-3">{stageByCaseId[c.id] ?? 'לא הוגדר'}</td>
                      <td className="py-3">
                        {c.retainer_snapshot_ils_gross != null ? formatILS(c.retainer_snapshot_ils_gross) : '—'}
                      </td>
                      <td className="py-3">
                        {c.expenses_snapshot_ils_gross != null ? formatILS(c.expenses_snapshot_ils_gross) : '—'}
                      </td>
                      <td className="py-3">{formatILS(c.excess_remaining_ils_gross)}</td>
                      <td className="py-3">{c.status === 'OPEN' ? 'פתוח' : 'סגור'}</td>
                    </tr>
                  ))}
                  {filtered.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="py-10 text-center text-muted">
                        אין תוצאות
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>
          ) : null}
        </div>
      </div>

      {showCreateModal ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4">
          <div className="w-full max-w-lg rounded-3xl border border-border/60 bg-surface p-6 shadow-card">
            <div className="text-right">
              <div className="text-xl font-bold">תיק חדש</div>
              <div className="text-sm text-muted mt-1">מזהה תיק, סוג, תאריך פתיחה ויתרת השתתפות עצמית (ש״ח)</div>
            </div>
            <form onSubmit={createCase} className="mt-5 flex flex-col gap-4">
              <div>
                <label className="block text-sm text-muted mb-1 text-right">מזהה תיק *</label>
                <input
                  type="text"
                  className="w-full h-12 rounded-xl bg-background border border-border/70 px-4 text-text placeholder:text-placeholder outline-none focus:ring-2 focus:ring-primary/60"
                  placeholder="למשל: תיק-2026-001"
                  value={createForm.case_reference}
                  onChange={(e) => setCreateForm((f) => ({ ...f, case_reference: e.target.value }))}
                  maxLength={120}
                />
              </div>
              <div>
                <label className="block text-sm text-muted mb-1 text-right">סוג תיק</label>
                <select
                  className="w-full h-12 rounded-xl bg-background border border-border/70 px-4 text-text outline-none focus:ring-2 focus:ring-primary/60"
                  value={createForm.case_type}
                  onChange={(e) => setCreateForm((f) => ({ ...f, case_type: e.target.value as CaseType }))}
                >
                  {CASE_TYPES.map((t) => (
                    <option key={t} value={t}>
                      {CASE_TYPE_LABEL[t]}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm text-muted mb-1 text-right">תאריך פתיחה *</label>
                <input
                  type="date"
                  className="w-full h-12 rounded-xl bg-background border border-border/70 px-4 text-text outline-none focus:ring-2 focus:ring-primary/60"
                  value={createForm.open_date}
                  onChange={(e) => setCreateForm((f) => ({ ...f, open_date: e.target.value }))}
                />
              </div>
              <div>
                <label className="block text-sm text-muted mb-1 text-right">יתרת השתתפות עצמית (ש״ח ברוטו) *</label>
                <input
                  type="number"
                  step="0.01"
                  min="0.01"
                  className="w-full h-12 rounded-xl bg-background border border-border/70 px-4 text-text placeholder:text-placeholder outline-none focus:ring-2 focus:ring-primary/60"
                  placeholder="למשל: 10000"
                  value={createForm.deductible_ils_gross}
                  onChange={(e) => setCreateForm((f) => ({ ...f, deductible_ils_gross: e.target.value }))}
                />
              </div>
              {createError ? (
                <div className="text-sm text-red-300 text-right">{createError}</div>
              ) : null}
              <div className="flex gap-3 justify-end mt-2">
                <button
                  type="button"
                  onClick={() => {
                    setShowCreateModal(false)
                    setCreateError(null)
                    setCreateForm(defaultCreateForm)
                  }}
                  className="btn btn-secondary"
                  disabled={isCreating}
                >
                  ביטול
                </button>
                <button type="submit" className="btn btn-primary" disabled={isCreating}>
                  {isCreating ? 'יוצר…' : 'צור תיק'}
                </button>
              </div>
            </form>
          </div>
        </div>
      ) : null}
    </div>
  )
}



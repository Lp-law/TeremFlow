import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { BackButton } from '../components/BackButton'
import { apiFetch } from '../lib/api'
import { downloadTextFile, toCsv } from '../lib/csv'
import type { CaseOut, CaseStatus, CaseType } from '../lib/types'

/** Labels for current_procedure_stage (fee event type) in list table. */
const PROCEDURE_STAGE_LABEL: Record<string, string> = {
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
  APPEAL: 'ערעור',
  STAGE_BILLING: 'חיוב לפי שלבים',
}

const CASE_TYPE_LABEL: Record<string, string> = {
  COURT: 'תיק ביהמ"ש',
  DEMAND_LETTER: 'מכתב דרישה',
  SMALL_CLAIMS: 'תביעות קטנות',
}

/** Match stage like "COURT_STAGE_3_EVIDENCE(+2)" -> code + count suffix */
const STAGE_WITH_PLUS_RE = /^(.+)\(\+(\d+)\)$/

function formatProcedureStage(stage: string | null | undefined): string {
  if (!stage) return 'לא הוגדר'
  const plusMatch = stage.match(STAGE_WITH_PLUS_RE)
  if (plusMatch) {
    const [, code, k] = plusMatch
    const label = PROCEDURE_STAGE_LABEL[code ?? ''] ?? (code ?? '')
    return k === '0' ? label : `${label} (+${k})`
  }
  if (stage.startsWith('STAGE_BILLING:')) {
    const n = stage.slice('STAGE_BILLING:'.length)
    return `חיוב לפי שלבים (${n})`
  }
  return PROCEDURE_STAGE_LABEL[stage] ?? stage
}

const CASE_TYPES: CaseType[] = ['COURT', 'DEMAND_LETTER', 'SMALL_CLAIMS']

const STAGE_OVERRIDE_CODES = Object.keys(PROCEDURE_STAGE_LABEL) as string[]

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
  const [query, setQuery] = useState('')
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [createForm, setCreateForm] = useState<CreateCaseForm>(defaultCreateForm)
  const [createError, setCreateError] = useState<string | null>(null)
  const [isCreating, setIsCreating] = useState(false)
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set())
  const [showBulkEditModal, setShowBulkEditModal] = useState(false)
  const [bulkStatus, setBulkStatus] = useState<CaseStatus | ''>('')
  const [bulkCaseType, setBulkCaseType] = useState<CaseType | ''>('')
  const [bulkStageOverride, setBulkStageOverride] = useState<string>('') // '' = don't change, '__CLEAR__' = clear, or code
  const [bulkSaving, setBulkSaving] = useState(false)
  const [bulkError, setBulkError] = useState<string | null>(null)
  const [toast, setToast] = useState<string | null>(null)

  async function load() {
    setError(null)
    setIsLoading(true)
    try {
      const data = await apiFetch<CaseOut[]>('/cases/')
      setItems(data)
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
        (c.case_name?.toLowerCase().includes(q) ?? false)
    )
  }, [items, query])

  function exportCasesCsv() {
    setError(null)
    const rows = filtered.map((c) => ({
      case_reference: c.case_reference,
      case_name: c.case_name ?? '',
      current_procedure_stage: formatProcedureStage(c.current_procedure_stage),
      status: c.status === 'OPEN' ? 'פתוח' : c.status === 'CLOSED' ? 'סגור' : c.status,
      case_type: CASE_TYPE_LABEL[c.case_type] ?? c.case_type,
    }))
    const columns = ['case_reference', 'case_name', 'current_procedure_stage', 'status', 'case_type']
    const csv = toCsv(rows, columns, ',')
    const ts = new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-')
    downloadTextFile(`teremflow-cases-${ts}.csv`, csv)
  }

  function toggleSelect(id: number) {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  function toggleSelectAll() {
    if (selectedIds.size === filtered.length) setSelectedIds(new Set())
    else setSelectedIds(new Set(filtered.map((c) => c.id)))
  }

  async function saveBulkEdit() {
    const updates: Record<string, unknown> = {}
    if (bulkStatus) updates.status = bulkStatus
    if (bulkCaseType) updates.case_type = bulkCaseType
    if (bulkStageOverride === '__CLEAR__') updates.procedure_stage_override = null
    else if (bulkStageOverride && bulkStageOverride !== '') updates.procedure_stage_override = bulkStageOverride
    if (Object.keys(updates).length === 0) {
      setBulkError('נא לבחור לפחות שדה אחד לעדכון')
      return
    }
    setBulkError(null)
    setBulkSaving(true)
    try {
      const res = await apiFetch<{ updated_count: number }>('/cases/bulk-update', {
        method: 'PATCH',
        body: JSON.stringify({ case_ids: Array.from(selectedIds), updates }),
      })
      setShowBulkEditModal(false)
      setSelectedIds(new Set())
      setBulkStatus('')
      setBulkCaseType('')
      setBulkStageOverride('')
      setToast(`עודכנו ${res.updated_count} תיקים`)
      setTimeout(() => setToast(null), 4000)
      await load()
    } catch (e: any) {
      setBulkError(e?.message || 'שגיאה')
    } finally {
      setBulkSaving(false)
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
      {toast ? (
        <div className="fixed top-4 left-1/2 -translate-x-1/2 z-50 px-4 py-2 rounded-xl bg-primary text-bg2 shadow-lg">
          {toast}
        </div>
      ) : null}
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
            <div className="flex gap-2 flex-wrap">
              <button
                onClick={() => setShowCreateModal(true)}
                className="btn btn-primary h-12"
              >
                תיק חדש
              </button>
              <button
                onClick={() => setShowBulkEditModal(true)}
                className="btn btn-secondary h-12"
                disabled={selectedIds.size === 0}
              >
                עריכה מרובה {selectedIds.size > 0 ? `(${selectedIds.size})` : ''}
              </button>
              <button onClick={exportCasesCsv} className="btn btn-secondary h-12">
                ייצוא CSV
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
                    <th className="text-right py-3 w-10">
                      <input
                        type="checkbox"
                        checked={filtered.length > 0 && selectedIds.size === filtered.length}
                        onChange={toggleSelectAll}
                        aria-label="בחר הכל"
                      />
                    </th>
                    <th className="text-right py-3">מספר תיק</th>
                    <th className="text-right py-3">שם תיק</th>
                    <th className="text-right py-3">שלב ההליך הנוכחי</th>
                    <th className="text-right py-3">סטטוס</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((c) => (
                    <tr key={c.id} className="border-b border-border/30 hover:bg-surface/30">
                      <td className="py-3 w-10">
                        <input
                          type="checkbox"
                          checked={selectedIds.has(c.id)}
                          onChange={() => toggleSelect(c.id)}
                          aria-label={`בחר תיק ${c.case_reference}`}
                        />
                      </td>
                      <td className="py-3 text-muted text-xs">
                        {c.case_reference}
                      </td>
                      <td className="py-3">
                        <Link to={`/cases/${c.id}`} className="text-primary hover:underline font-medium">
                          {c.case_name?.trim()
                            ? `${c.case_name.trim()} ( ${c.case_reference} )`
                            : c.case_reference}
                        </Link>
                      </td>
                      <td className="py-3">
                        {formatProcedureStage(c.current_procedure_stage)}
                      </td>
                      <td className="py-3">
                        {c.status === 'OPEN' ? 'פתוח' : c.status === 'CLOSED' ? 'סגור' : 'לא הוגדר'}
                      </td>
                    </tr>
                  ))}
                  {filtered.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="py-10 text-center text-muted">
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

      {showBulkEditModal ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4">
          <div className="w-full max-w-lg rounded-3xl border border-border/60 bg-surface p-6 shadow-card">
            <div className="text-right">
              <div className="text-xl font-bold">עריכה מרובה</div>
              <div className="text-sm text-muted mt-1">נבחרו {selectedIds.size} תיקים</div>
            </div>
            <div className="mt-5 flex flex-col gap-4">
              <div>
                <label className="block text-sm text-muted mb-1 text-right">סטטוס</label>
                <select
                  className="w-full h-12 rounded-xl bg-background border border-border/70 px-4 text-text outline-none focus:ring-2 focus:ring-primary/60"
                  value={bulkStatus}
                  onChange={(e) => setBulkStatus(e.target.value as CaseStatus | '')}
                >
                  <option value="">לא לשנות</option>
                  <option value="OPEN">פתוח</option>
                  <option value="CLOSED">סגור</option>
                </select>
              </div>
              <div>
                <label className="block text-sm text-muted mb-1 text-right">סוג תיק</label>
                <select
                  className="w-full h-12 rounded-xl bg-background border border-border/70 px-4 text-text outline-none focus:ring-2 focus:ring-primary/60"
                  value={bulkCaseType}
                  onChange={(e) => setBulkCaseType(e.target.value as CaseType | '')}
                >
                  <option value="">לא לשנות</option>
                  {CASE_TYPES.map((t) => (
                    <option key={t} value={t}>
                      {CASE_TYPE_LABEL[t]}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm text-muted mb-1 text-right">שלב משפטי (דריסה ידנית)</label>
                <select
                  className="w-full h-12 rounded-xl bg-background border border-border/70 px-4 text-text outline-none focus:ring-2 focus:ring-primary/60"
                  value={bulkStageOverride}
                  onChange={(e) => setBulkStageOverride(e.target.value)}
                >
                  <option value="">לא לשנות</option>
                  <option value="__CLEAR__">נקה שלב ידני</option>
                  {STAGE_OVERRIDE_CODES.map((code) => (
                    <option key={code} value={code}>
                      {PROCEDURE_STAGE_LABEL[code] ?? code}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            {bulkError ? <div className="mt-4 text-sm text-red-300 text-right">{bulkError}</div> : null}
            <div className="flex gap-3 justify-end mt-6">
              <button
                type="button"
                onClick={() => {
                  setShowBulkEditModal(false)
                  setBulkError(null)
                }}
                className="btn btn-secondary"
                disabled={bulkSaving}
              >
                ביטול
              </button>
              <button type="button" onClick={saveBulkEdit} className="btn btn-primary" disabled={bulkSaving}>
                {bulkSaving ? 'שומר…' : 'שמור'}
              </button>
            </div>
          </div>
        </div>
      ) : null}

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



import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { BackButton } from '../components/BackButton'
import { apiDownload, apiFetch } from '../lib/api'
import { formatILS } from '../lib/format'
import type {
  CaseOut,
  ClaimsCategory,
  ClaimsFinalOutcomeType,
  ClaimsRefreshLinkedRowsOut,
  ClaimsReportCaseStatus,
  ClaimsReportDetailsOut,
  ClaimsReportOut,
  ClaimsReportRowOut,
  ClaimsRowLinkageType,
} from '../lib/types'

const CATEGORY_LABEL: Record<ClaimsCategory, string> = {
  COURT_REPORTED_TO_INSURER: 'בתי משפט + דווח לביטוח',
  REPORTED_WITHOUT_CLAIM: 'דווח ללא תביעה',
  NOT_REPORTED_TO_INSURER: 'לא דווח לביטוח',
  NON_MEDICAL_MALPRACTICE: 'לא רשלנות רפואית',
  OTHER: 'אחר',
}

const CASE_STATUS_LABEL: Record<ClaimsReportCaseStatus, string> = {
  OPEN: 'פתוח',
  CLOSED: 'סגור',
  CANNOT_ASSESS_YET: 'לא ניתן להעריך',
  NO_EXPOSURE: 'ללא חשיפה',
  REJECTED_EXPECTED: 'צפי לדחייה',
  SETTLED: 'פשרה',
  JUDGMENT: 'פסק דין',
  REJECTED: 'נדחה',
  REJECTED_WITH_COSTS: 'נדחה עם הוצאות',
}

const OUTCOME_LABEL: Record<ClaimsFinalOutcomeType, string> = {
  SETTLEMENT: 'פשרה',
  JUDGMENT_FOR_PLAINTIFF: 'פסק דין לטובת התובע',
  CLAIM_REJECTED: 'תביעה נדחתה',
  CLAIM_REJECTED_WITH_COSTS: 'תביעה נדחתה עם הוצאות',
  CLOSED_WITHOUT_PAYMENT: 'נסגר ללא תשלום',
  OTHER: 'אחר',
}

type RowForm = {
  linked_case_id: string
  linkage_type: ClaimsRowLinkageType
  case_reference_text: string
  case_title: string
  court_name: string
  proceeding_number: string
  branch_name: string
  institution_name: string
  category_for_report: ClaimsCategory
  report_case_status: ClaimsReportCaseStatus
  status_note: string
  current_risk_assessment_ils: string
  risk_assessment_text: string
  final_outcome_type: '' | ClaimsFinalOutcomeType
  final_outcome_amount_ils: string
  awarded_costs_to_terem_ils: string
  final_outcome_date: string
  final_outcome_text: string
  deductible_usd: string
  deductible_ils_gross: string
  amount_already_paid_on_deductible_ils: string
  remaining_deductible_ils: string
  expenses_total_ils: string
  fees_total_ils: string
  retainer_charged_ils: string
  exposure_for_reserve_ils: string
  narrative_text: string
  legal_summary_text: string
  internal_notes: string
  include_in_report: boolean
}

const defaultRowForm: RowForm = {
  linked_case_id: '',
  linkage_type: 'MANUAL',
  case_reference_text: '',
  case_title: '',
  court_name: '',
  proceeding_number: '',
  branch_name: '',
  institution_name: '',
  category_for_report: 'OTHER',
  report_case_status: 'OPEN',
  status_note: '',
  current_risk_assessment_ils: '',
  risk_assessment_text: '',
  final_outcome_type: '',
  final_outcome_amount_ils: '',
  awarded_costs_to_terem_ils: '',
  final_outcome_date: '',
  final_outcome_text: '',
  deductible_usd: '',
  deductible_ils_gross: '',
  amount_already_paid_on_deductible_ils: '',
  remaining_deductible_ils: '',
  expenses_total_ils: '',
  fees_total_ils: '',
  retainer_charged_ils: '',
  exposure_for_reserve_ils: '',
  narrative_text: '',
  legal_summary_text: '',
  internal_notes: '',
  include_in_report: true,
}

function numOrNull(v: string): string | null {
  const t = v.trim()
  if (!t) return null
  const n = Number(t)
  return Number.isFinite(n) ? String(n) : null
}

function formToPayload(form: RowForm) {
  return {
    linked_case_id: form.linked_case_id ? Number(form.linked_case_id) : null,
    linkage_type: form.linkage_type,
    case_reference_text: form.case_reference_text || null,
    case_title: form.case_title || null,
    court_name: form.court_name || null,
    proceeding_number: form.proceeding_number || null,
    branch_name: form.branch_name || null,
    institution_name: form.institution_name || null,
    category_for_report: form.category_for_report,
    report_case_status: form.report_case_status,
    status_note: form.status_note || null,
    current_risk_assessment_ils: numOrNull(form.current_risk_assessment_ils),
    risk_assessment_text: form.risk_assessment_text || null,
    final_outcome_type: form.final_outcome_type || null,
    final_outcome_amount_ils: numOrNull(form.final_outcome_amount_ils),
    awarded_costs_to_terem_ils: numOrNull(form.awarded_costs_to_terem_ils),
    final_outcome_date: form.final_outcome_date || null,
    final_outcome_text: form.final_outcome_text || null,
    deductible_usd: numOrNull(form.deductible_usd),
    deductible_ils_gross: numOrNull(form.deductible_ils_gross),
    amount_already_paid_on_deductible_ils: numOrNull(form.amount_already_paid_on_deductible_ils),
    remaining_deductible_ils: numOrNull(form.remaining_deductible_ils),
    expenses_total_ils: numOrNull(form.expenses_total_ils),
    fees_total_ils: numOrNull(form.fees_total_ils),
    retainer_charged_ils: numOrNull(form.retainer_charged_ils),
    exposure_for_reserve_ils: numOrNull(form.exposure_for_reserve_ils),
    narrative_text: form.narrative_text || null,
    legal_summary_text: form.legal_summary_text || null,
    internal_notes: form.internal_notes || null,
    include_in_report: form.include_in_report,
  }
}

function rowToForm(row: ClaimsReportRowOut): RowForm {
  return {
    linked_case_id: row.linked_case_id ? String(row.linked_case_id) : '',
    linkage_type: row.linkage_type,
    case_reference_text: row.case_reference_text || '',
    case_title: row.case_title || '',
    court_name: row.court_name || '',
    proceeding_number: row.proceeding_number || '',
    branch_name: row.branch_name || '',
    institution_name: row.institution_name || '',
    category_for_report: row.category_for_report,
    report_case_status: row.report_case_status,
    status_note: row.status_note || '',
    current_risk_assessment_ils: row.current_risk_assessment_ils == null ? '' : String(row.current_risk_assessment_ils),
    risk_assessment_text: row.risk_assessment_text || '',
    final_outcome_type: row.final_outcome_type || '',
    final_outcome_amount_ils: row.final_outcome_amount_ils == null ? '' : String(row.final_outcome_amount_ils),
    awarded_costs_to_terem_ils: row.awarded_costs_to_terem_ils == null ? '' : String(row.awarded_costs_to_terem_ils),
    final_outcome_date: row.final_outcome_date || '',
    final_outcome_text: row.final_outcome_text || '',
    deductible_usd: row.deductible_usd == null ? '' : String(row.deductible_usd),
    deductible_ils_gross: row.deductible_ils_gross == null ? '' : String(row.deductible_ils_gross),
    amount_already_paid_on_deductible_ils: row.amount_already_paid_on_deductible_ils == null ? '' : String(row.amount_already_paid_on_deductible_ils),
    remaining_deductible_ils: row.remaining_deductible_ils == null ? '' : String(row.remaining_deductible_ils),
    expenses_total_ils: row.expenses_total_ils == null ? '' : String(row.expenses_total_ils),
    fees_total_ils: row.fees_total_ils == null ? '' : String(row.fees_total_ils),
    retainer_charged_ils: row.retainer_charged_ils == null ? '' : String(row.retainer_charged_ils),
    exposure_for_reserve_ils: row.exposure_for_reserve_ils == null ? '' : String(row.exposure_for_reserve_ils),
    narrative_text: row.narrative_text || '',
    legal_summary_text: row.legal_summary_text || '',
    internal_notes: row.internal_notes || '',
    include_in_report: row.include_in_report,
  }
}

export function ClaimsReportDetailsPage() {
  const { reportId } = useParams()
  const id = Number(reportId)
  const [report, setReport] = useState<ClaimsReportOut | null>(null)
  const [rows, setRows] = useState<ClaimsReportRowOut[]>([])
  const [error, setError] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [filterCategory, setFilterCategory] = useState<ClaimsCategory | 'ALL'>('ALL')
  const [filterStatus, setFilterStatus] = useState<ClaimsReportCaseStatus | 'ALL'>('ALL')
  const [filterLinkage, setFilterLinkage] = useState<ClaimsRowLinkageType | 'ALL'>('ALL')

  const [showNewRow, setShowNewRow] = useState(false)
  const [newRowForm, setNewRowForm] = useState<RowForm>(defaultRowForm)
  const [isSavingRow, setIsSavingRow] = useState(false)
  const [rowFormError, setRowFormError] = useState<string | null>(null)

  const [editingRowId, setEditingRowId] = useState<number | null>(null)
  const [editRowForm, setEditRowForm] = useState<RowForm>(defaultRowForm)

  const [showImportCases, setShowImportCases] = useState(false)
  const [casesOptions, setCasesOptions] = useState<CaseOut[]>([])
  const [selectedCaseIds, setSelectedCaseIds] = useState<Set<number>>(new Set())
  const [importCategory, setImportCategory] = useState<ClaimsCategory>('OTHER')
  const [importInclude, setImportInclude] = useState(true)
  const [isImporting, setIsImporting] = useState(false)
  const [isRefreshingLinked, setIsRefreshingLinked] = useState(false)

  const isFinal = report?.status === 'FINAL'

  function fmtDateTime(v: string | null) {
    if (!v) return '—'
    return v.slice(0, 16).replace('T', ' ')
  }

  async function load() {
    setError(null)
    setIsLoading(true)
    try {
      const data = await apiFetch<ClaimsReportDetailsOut>(`/claims-reports/${id}`)
      setReport(data.report)
      setRows(data.rows)
    } catch (e: any) {
      setError(e?.message || 'שגיאה בטעינת הדו"ח')
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    if (!Number.isFinite(id)) return
    load()
  }, [id])

  const filteredRows = useMemo(() => {
    const q = search.trim().toLowerCase()
    return rows.filter((r) => {
      if (filterCategory !== 'ALL' && r.category_for_report !== filterCategory) return false
      if (filterStatus !== 'ALL' && r.report_case_status !== filterStatus) return false
      if (filterLinkage !== 'ALL' && r.linkage_type !== filterLinkage) return false
      if (!q) return true
      return (
        (r.case_title || '').toLowerCase().includes(q) ||
        (r.case_reference_text || '').toLowerCase().includes(q) ||
        (r.narrative_preview || '').toLowerCase().includes(q)
      )
    })
  }, [rows, search, filterCategory, filterStatus, filterLinkage])

  const kpis = useMemo(() => {
    const included = rows.filter((r) => r.include_in_report)
    const reserve = included.reduce((acc, r) => acc + Number(r.exposure_for_reserve_ils || 0), 0)
    return { totalRows: rows.length, includedRows: included.length, reserve }
  }, [rows])

  async function saveTopLevelReport() {
    if (!report) return
    try {
      const updated = await apiFetch<ClaimsReportOut>(`/claims-reports/${report.id}`, {
        method: 'PATCH',
        body: JSON.stringify({
          title: report.title,
          client_name: report.client_name,
          report_cutoff_date: report.report_cutoff_date,
          updated_to_date: report.updated_to_date,
          recommended_reserve_ils: report.recommended_reserve_ils,
          intro_text: report.intro_text,
          closing_text: report.closing_text,
        }),
      })
      setReport(updated)
    } catch (e: any) {
      setError(e?.message || 'שגיאה בשמירת הדו"ח')
    }
  }

  async function createRow() {
    setRowFormError(null)
    setIsSavingRow(true)
    try {
      await apiFetch(`/claims-reports/${id}/rows`, {
        method: 'POST',
        body: JSON.stringify(formToPayload(newRowForm)),
      })
      setShowNewRow(false)
      setNewRowForm(defaultRowForm)
      await load()
    } catch (e: any) {
      setRowFormError(e?.message || 'שגיאה בשמירת הרשומה')
    } finally {
      setIsSavingRow(false)
    }
  }

  async function saveEditedRow() {
    if (editingRowId == null) return
    setRowFormError(null)
    setIsSavingRow(true)
    try {
      await apiFetch(`/claims-reports/${id}/rows/${editingRowId}`, {
        method: 'PATCH',
        body: JSON.stringify(formToPayload(editRowForm)),
      })
      setEditingRowId(null)
      await load()
    } catch (e: any) {
      setRowFormError(e?.message || 'שגיאה בעדכון הרשומה')
    } finally {
      setIsSavingRow(false)
    }
  }

  async function deleteRow(rowId: number) {
    if (!window.confirm('למחוק רשומה זו?')) return
    try {
      await apiFetch(`/claims-reports/${id}/rows/${rowId}`, { method: 'DELETE' })
      await load()
    } catch (e: any) {
      setError(e?.message || 'שגיאה במחיקה')
    }
  }

  async function openImportCases() {
    setSelectedCaseIds(new Set())
    setImportCategory('OTHER')
    setImportInclude(true)
    setShowImportCases(true)
    try {
      const data = await apiFetch<CaseOut[]>('/cases')
      setCasesOptions(data)
    } catch {
      setCasesOptions([])
    }
  }

  async function importFromCases() {
    setIsImporting(true)
    try {
      await apiFetch(`/claims-reports/${id}/rows/import-from-cases`, {
        method: 'POST',
        body: JSON.stringify({
          case_ids: Array.from(selectedCaseIds),
          category_for_report: importCategory,
          include_in_report: importInclude,
        }),
      })
      setShowImportCases(false)
      await load()
    } catch (e: any) {
      setError(e?.message || 'שגיאה בייבוא מתיקים')
    } finally {
      setIsImporting(false)
    }
  }

  async function finalizeReport() {
    if (isFinal) return
    if (!window.confirm('לסמן דו"ח כ-FINAL? ניתן להמשיך לערוך גם לאחר מכן.')) return
    try {
      const fin = await apiFetch<{ id: number; status: 'DRAFT' | 'FINAL'; finalized_at: string | null }>(`/claims-reports/${id}/finalize`, {
        method: 'POST',
      })
      setReport((prev) => (prev ? { ...prev, status: fin.status, finalized_at: fin.finalized_at } : prev))
    } catch (e: any) {
      setError(e?.message || 'שגיאה בסיום דו"ח')
    }
  }

  async function exportDocx() {
    try {
      const { blob, filename } = await apiDownload(`/claims-reports/${id}/export/docx`, { method: 'POST' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename || `claims_report_${id}.docx`
      a.click()
      URL.revokeObjectURL(url)
    } catch (e: any) {
      setError(e?.message || 'שגיאה בייצוא Word')
    }
  }

  async function refreshRowFromCase(rowId: number) {
    try {
      await apiFetch(`/claims-reports/${id}/rows/${rowId}/refresh-from-case`, { method: 'POST' })
      await load()
    } catch (e: any) {
      setError(e?.message || 'שגיאה ברענון רשומה מהתיק')
    }
  }

  async function refreshAllLinkedRows() {
    setIsRefreshingLinked(true)
    try {
      const res = await apiFetch<ClaimsRefreshLinkedRowsOut>(`/claims-reports/${id}/rows/refresh-linked`, { method: 'POST' })
      await load()
      if (res.skipped_rows > 0) {
        setError(`רועננו ${res.refreshed_rows} רשומות, ודולגו ${res.skipped_rows} (תיקים חסרים/מחוקים).`)
      }
    } catch (e: any) {
      setError(e?.message || 'שגיאה ברענון רשומות מקושרות')
    } finally {
      setIsRefreshingLinked(false)
    }
  }

  if (!Number.isFinite(id)) {
    return (
      <div className="min-h-screen w-full px-6 py-10">
        <div className="mx-auto w-full max-w-4xl text-right">
          <div className="text-xl text-amber-400">מזהה דו"ח לא תקין</div>
          <BackButton />
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen w-full px-6 py-10">
      <div className="mx-auto w-full max-w-7xl">
        <div className="flex items-center justify-between gap-4">
          <div className="text-right">
            <div className="text-2xl font-bold">{report?.title || 'דו"ח תביעות / חשיפות'}</div>
            <div className="text-sm text-muted mt-1">
              סטטוס: {report?.status === 'FINAL' ? 'סופי' : 'טיוטה'} {report?.finalized_at ? `• סוכם ב-${report.finalized_at.slice(0, 16).replace('T', ' ')}` : ''}
            </div>
            <div className="text-xs text-muted mt-1">FINAL הוא סטטוס עסקי בלבד - העריכה נשארת פתוחה.</div>
          </div>
          <div className="flex gap-2">
            <Link to="/claims-reports" className="btn btn-secondary">לרשימת דו"חות</Link>
            <BackButton />
          </div>
        </div>

        {error ? <div className="mt-4 text-sm text-red-300 text-right">{error}</div> : null}
        {isLoading ? <div className="mt-6 text-right text-muted">טוען...</div> : null}

        {!isLoading && report ? (
          <>
            <div className="mt-6 card p-6">
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <Kpi title={'סה"כ רשומות'} value={String(kpis.totalRows)} />
                <Kpi title="רשומות כלולות" value={String(kpis.includedRows)} />
                <Kpi title="חשיפה מצטברת" value={formatILS(kpis.reserve)} />
                <Kpi title="המלצת הפרשה" value={report.recommended_reserve_ils == null ? '—' : formatILS(report.recommended_reserve_ils)} />
              </div>
              <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="text-right">
                  <label className="block text-sm text-muted mb-1">כותרת דו"ח</label>
                  <input className="input w-full" value={report.title} onChange={(e) => setReport((p) => (p ? { ...p, title: e.target.value } : p))} />
                </div>
                <div className="text-right">
                  <label className="block text-sm text-muted mb-1">לקוח</label>
                  <input className="input w-full" value={report.client_name} onChange={(e) => setReport((p) => (p ? { ...p, client_name: e.target.value } : p))} />
                </div>
                <div className="text-right">
                  <label className="block text-sm text-muted mb-1">תאריך חתך</label>
                  <input className="input w-full" type="date" value={report.report_cutoff_date} onChange={(e) => setReport((p) => (p ? { ...p, report_cutoff_date: e.target.value } : p))} />
                </div>
                <div className="text-right">
                  <label className="block text-sm text-muted mb-1">מעודכן עד</label>
                  <input className="input w-full" type="date" value={report.updated_to_date || ''} onChange={(e) => setReport((p) => (p ? { ...p, updated_to_date: e.target.value || null } : p))} />
                </div>
              </div>
              <div className="mt-4">
                <label className="block text-sm text-muted mb-1 text-right">פתיח</label>
                <textarea className="input w-full min-h-[90px]" value={report.intro_text || ''} onChange={(e) => setReport((p) => (p ? { ...p, intro_text: e.target.value } : p))} />
              </div>
              <div className="mt-4">
                <label className="block text-sm text-muted mb-1 text-right">סיכום/סגירה</label>
                <textarea className="input w-full min-h-[90px]" value={report.closing_text || ''} onChange={(e) => setReport((p) => (p ? { ...p, closing_text: e.target.value } : p))} />
              </div>
              <div className="mt-4 flex gap-2 justify-end">
                <button className="btn btn-primary" onClick={saveTopLevelReport}>שמור פרטי דו"ח</button>
                <button className="btn btn-secondary" onClick={exportDocx}>ייצוא Word</button>
                {!isFinal ? <button className="btn btn-secondary" onClick={finalizeReport}>סיום דו"ח (Finalize)</button> : null}
              </div>
            </div>

            <div className="mt-6 card p-4">
              <div className="flex flex-wrap gap-2 items-end justify-between">
                <div className="flex flex-wrap gap-2">
                  <input className="input h-11" placeholder="חיפוש..." value={search} onChange={(e) => setSearch(e.target.value)} />
                  <select className="input h-11" value={filterCategory} onChange={(e) => setFilterCategory(e.target.value as ClaimsCategory | 'ALL')}>
                    <option value="ALL">כל הקטגוריות</option>
                    {Object.entries(CATEGORY_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                  </select>
                  <select className="input h-11" value={filterStatus} onChange={(e) => setFilterStatus(e.target.value as ClaimsReportCaseStatus | 'ALL')}>
                    <option value="ALL">כל הסטטוסים</option>
                    {Object.entries(CASE_STATUS_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                  </select>
                  <select className="input h-11" value={filterLinkage} onChange={(e) => setFilterLinkage(e.target.value as ClaimsRowLinkageType | 'ALL')}>
                    <option value="ALL">כל הסוגים</option>
                    <option value="MANUAL">ידני</option>
                    <option value="LINKED">מקושר לתיק קיים</option>
                  </select>
                </div>
                <div className="flex gap-2">
                  <button className="btn btn-secondary" onClick={refreshAllLinkedRows} disabled={isRefreshingLinked}>
                    {isRefreshingLinked ? 'מרענן...' : 'רענון כל הרשומות המקושרות'}
                  </button>
                  <button className="btn btn-secondary" onClick={openImportCases}>הוסף מתיקים קיימים</button>
                  <button className="btn btn-primary" onClick={() => { setShowNewRow(true); setNewRowForm(defaultRowForm) }}>הוסף רשומה ידנית</button>
                </div>
              </div>
              <div className="mt-3 text-xs text-muted text-right">
                שדות מסונכרנים מהתיק: מזהה/כותרת תיק, סטטוס תיק בדו"ח, deductible/expenses/fees/retainer/exposure.
                שדות ידניים: הערכת סיכון, narrative, תוצאת סיום, include/exclude והערות.
              </div>

              <div className="mt-4 overflow-x-auto">
                <table className="w-full text-sm text-right">
                  <thead>
                    <tr className="border-b border-border/60 text-muted">
                      <th className="py-2 px-2">תיק/כותרת</th>
                      <th className="py-2 px-2">קטגוריה</th>
                      <th className="py-2 px-2">סטטוס</th>
                      <th className="py-2 px-2">סוג</th>
                      <th className="py-2 px-2">חשיפה לרזרבה</th>
                      <th className="py-2 px-2">סנכרון</th>
                      <th className="py-2 px-2">כלול בדו"ח</th>
                      <th className="py-2 px-2">פעולות</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredRows.map((r) => (
                      <tr key={r.id} className="border-b border-border/30 last:border-0">
                        <td className="py-2 px-2">
                          <div className="font-medium">{r.case_title || r.case_reference_text || `רשומה ${r.id}`}</div>
                          <div className="text-xs text-muted">{r.narrative_preview}</div>
                          <div className="text-xs text-muted mt-1">{r.linkage_type === 'LINKED' ? 'מקור: תיק קיים + שדות ידניים' : 'רשומה ידנית'}</div>
                        </td>
                        <td className="py-2 px-2">{CATEGORY_LABEL[r.category_for_report]}</td>
                        <td className="py-2 px-2">{CASE_STATUS_LABEL[r.report_case_status]}</td>
                        <td className="py-2 px-2">{r.linkage_type === 'LINKED' ? 'מקושר' : 'ידני'}</td>
                        <td className="py-2 px-2">{r.exposure_for_reserve_ils == null ? '—' : formatILS(r.exposure_for_reserve_ils)}</td>
                        <td className="py-2 px-2">
                          <div className="text-xs">sync: {fmtDateTime(r.last_synced_at)}</div>
                          <div className="text-xs text-muted">manual: {fmtDateTime(r.last_manual_update_at)}</div>
                        </td>
                        <td className="py-2 px-2">{r.include_in_report ? 'כן' : 'לא'}</td>
                        <td className="py-2 px-2">
                          <div className="flex gap-2 justify-end">
                            <button className="btn btn-secondary h-9 px-3" onClick={() => { setEditingRowId(r.id); setEditRowForm(rowToForm(r)); setRowFormError(null) }}>
                              עריכה
                            </button>
                            {r.linkage_type === 'LINKED' && r.linked_case_id ? (
                              <button className="btn btn-secondary h-9 px-3" onClick={() => refreshRowFromCase(r.id)}>
                                רענון מהתיק
                              </button>
                            ) : null}
                            <button className="btn btn-secondary h-9 px-3" onClick={() => deleteRow(r.id)}>
                              מחיקה
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {filteredRows.length === 0 ? <div className="text-right text-muted py-6">אין רשומות לתצוגה</div> : null}
              </div>
            </div>
          </>
        ) : null}
      </div>

      {showNewRow ? (
        <RowEditorModal
          title="רשומה חדשה"
          form={newRowForm}
          onChange={setNewRowForm}
          onClose={() => setShowNewRow(false)}
          onSave={createRow}
          isSaving={isSavingRow}
          error={rowFormError}
        />
      ) : null}

      {editingRowId != null ? (
        <RowEditorModal
          title={`עריכת רשומה #${editingRowId}`}
          form={editRowForm}
          onChange={setEditRowForm}
          onClose={() => setEditingRowId(null)}
          onSave={saveEditedRow}
          isSaving={isSavingRow}
          error={rowFormError}
        />
      ) : null}

      {showImportCases ? (
        <div className="modal">
          <div className="modal-overlay" onClick={() => !isImporting && setShowImportCases(false)} />
          <div className="modal-panel max-w-4xl">
            <div className="text-right">
              <div className="text-lg font-semibold">הוספת רשומות מתוך תיקים קיימים</div>
              <div className="text-sm text-muted mt-1">נוצרים rows מקושרים עם prefill מתוך נתוני התיק</div>
            </div>
            <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-3">
              <div>
                <label className="block text-sm text-muted mb-1 text-right">קטגוריה לרשומות שייווצרו</label>
                <select className="input w-full" value={importCategory} onChange={(e) => setImportCategory(e.target.value as ClaimsCategory)}>
                  {Object.entries(CATEGORY_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                </select>
              </div>
              <div className="flex items-end justify-end">
                <label className="flex items-center gap-2 text-sm">
                  <input type="checkbox" checked={importInclude} onChange={(e) => setImportInclude(e.target.checked)} />
                  לכלול בדו"ח
                </label>
              </div>
            </div>
            <div className="mt-4 max-h-[360px] overflow-auto border border-border/50 rounded-xl p-3">
              {casesOptions.map((c) => (
                <label key={c.id} className="flex items-center justify-between gap-2 py-1 border-b border-border/20 last:border-0">
                  <span className="text-sm">{c.case_name || c.case_reference} ({c.case_reference})</span>
                  <input
                    type="checkbox"
                    checked={selectedCaseIds.has(c.id)}
                    onChange={(e) => {
                      setSelectedCaseIds((prev) => {
                        const n = new Set(prev)
                        if (e.target.checked) n.add(c.id)
                        else n.delete(c.id)
                        return n
                      })
                    }}
                  />
                </label>
              ))}
              {casesOptions.length === 0 ? <div className="text-sm text-muted text-right py-4">אין תיקים זמינים</div> : null}
            </div>
            <div className="mt-6 flex gap-2 justify-end">
              <button className="btn btn-secondary" onClick={() => setShowImportCases(false)} disabled={isImporting}>ביטול</button>
              <button className="btn btn-primary" onClick={importFromCases} disabled={isImporting || selectedCaseIds.size === 0}>
                {isImporting ? 'מייבא...' : `ייבוא ${selectedCaseIds.size} תיקים`}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}

function Kpi({ title, value }: { title: string; value: string }) {
  return (
    <div className="card-soft p-4 text-right">
      <div className="text-xs text-muted">{title}</div>
      <div className="text-xl font-bold mt-1">{value}</div>
    </div>
  )
}

function RowEditorModal({
  title,
  form,
  onChange,
  onClose,
  onSave,
  isSaving,
  error,
}: {
  title: string
  form: RowForm
  onChange: (next: RowForm) => void
  onClose: () => void
  onSave: () => void
  isSaving: boolean
  error: string | null
}) {
  return (
    <div className="modal">
      <div className="modal-overlay" onClick={() => !isSaving && onClose()} />
      <div className="modal-panel max-w-5xl max-h-[92vh] overflow-auto">
        <div className="text-right">
          <div className="text-lg font-semibold">{title}</div>
        </div>
        <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-3">
          <div>
            <label className="block text-sm text-muted mb-1 text-right">סוג רשומה</label>
            <select className="input w-full" value={form.linkage_type} onChange={(e) => onChange({ ...form, linkage_type: e.target.value as ClaimsRowLinkageType })}>
              <option value="MANUAL">ידני</option>
              <option value="LINKED">מקושר לתיק קיים</option>
            </select>
          </div>
          <div>
            <label className="block text-sm text-muted mb-1 text-right">linked_case_id (אופציונלי)</label>
            <input className="input w-full" value={form.linked_case_id} onChange={(e) => onChange({ ...form, linked_case_id: e.target.value })} />
          </div>
          <div>
            <label className="block text-sm text-muted mb-1 text-right">קטגוריה</label>
            <select className="input w-full" value={form.category_for_report} onChange={(e) => onChange({ ...form, category_for_report: e.target.value as ClaimsCategory })}>
              {Object.entries(CATEGORY_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </div>

          <Field label='מזהה/מספר תיק (טקסט)' value={form.case_reference_text} onChange={(v) => onChange({ ...form, case_reference_text: v })} />
          <Field label='כותרת תיק' value={form.case_title} onChange={(v) => onChange({ ...form, case_title: v })} />
          <Field label='בית משפט' value={form.court_name} onChange={(v) => onChange({ ...form, court_name: v })} />
          <Field label='מספר הליך' value={form.proceeding_number} onChange={(v) => onChange({ ...form, proceeding_number: v })} />
          <Field label='סניף' value={form.branch_name} onChange={(v) => onChange({ ...form, branch_name: v })} />
          <Field label='מוסד/גוף' value={form.institution_name} onChange={(v) => onChange({ ...form, institution_name: v })} />

          <div>
            <label className="block text-sm text-muted mb-1 text-right">סטטוס בדו"ח</label>
            <select className="input w-full" value={form.report_case_status} onChange={(e) => onChange({ ...form, report_case_status: e.target.value as ClaimsReportCaseStatus })}>
              {Object.entries(CASE_STATUS_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </div>
          <Field label='הערת סטטוס' value={form.status_note} onChange={(v) => onChange({ ...form, status_note: v })} />
          <Field label='הערכת סיכון (₪)' value={form.current_risk_assessment_ils} onChange={(v) => onChange({ ...form, current_risk_assessment_ils: v })} />
          <Field label='טקסט הערכת סיכון' value={form.risk_assessment_text} onChange={(v) => onChange({ ...form, risk_assessment_text: v })} />

          <div>
            <label className="block text-sm text-muted mb-1 text-right">תוצאת סיום</label>
            <select className="input w-full" value={form.final_outcome_type} onChange={(e) => onChange({ ...form, final_outcome_type: e.target.value as '' | ClaimsFinalOutcomeType })}>
              <option value="">—</option>
              {Object.entries(OUTCOME_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </div>
          <Field label='סכום סיום (₪)' value={form.final_outcome_amount_ils} onChange={(v) => onChange({ ...form, final_outcome_amount_ils: v })} />
          <Field label='הוצאות לטובת טרם (₪)' value={form.awarded_costs_to_terem_ils} onChange={(v) => onChange({ ...form, awarded_costs_to_terem_ils: v })} />
          <div>
            <label className="block text-sm text-muted mb-1 text-right">תאריך סיום</label>
            <input className="input w-full" type="date" value={form.final_outcome_date} onChange={(e) => onChange({ ...form, final_outcome_date: e.target.value })} />
          </div>
          <Field label='טקסט תוצאה' value={form.final_outcome_text} onChange={(v) => onChange({ ...form, final_outcome_text: v })} />

          <Field label='deductible_usd' value={form.deductible_usd} onChange={(v) => onChange({ ...form, deductible_usd: v })} />
          <Field label='deductible_ils_gross' value={form.deductible_ils_gross} onChange={(v) => onChange({ ...form, deductible_ils_gross: v })} />
          <Field label='שולם על חשבון (₪)' value={form.amount_already_paid_on_deductible_ils} onChange={(v) => onChange({ ...form, amount_already_paid_on_deductible_ils: v })} />
          <Field label='נותר השתתפות עצמית (₪)' value={form.remaining_deductible_ils} onChange={(v) => onChange({ ...form, remaining_deductible_ils: v })} />
          <Field label='סה"כ הוצאות (₪)' value={form.expenses_total_ils} onChange={(v) => onChange({ ...form, expenses_total_ils: v })} />
          <Field label='סה"כ שכ"ט (₪)' value={form.fees_total_ils} onChange={(v) => onChange({ ...form, fees_total_ils: v })} />
          <Field label='ריטיינר מחויב (₪)' value={form.retainer_charged_ils} onChange={(v) => onChange({ ...form, retainer_charged_ils: v })} />
          <Field label='חשיפה לרזרבה (₪)' value={form.exposure_for_reserve_ils} onChange={(v) => onChange({ ...form, exposure_for_reserve_ils: v })} />
        </div>
        <div className="mt-4">
          <label className="block text-sm text-muted mb-1 text-right">נרטיב לדו"ח</label>
          <textarea className="input w-full min-h-[80px]" value={form.narrative_text} onChange={(e) => onChange({ ...form, narrative_text: e.target.value })} />
        </div>
        <div className="mt-3">
          <label className="block text-sm text-muted mb-1 text-right">סיכום משפטי</label>
          <textarea className="input w-full min-h-[80px]" value={form.legal_summary_text} onChange={(e) => onChange({ ...form, legal_summary_text: e.target.value })} />
        </div>
        <div className="mt-3">
          <label className="block text-sm text-muted mb-1 text-right">הערות פנימיות</label>
          <textarea className="input w-full min-h-[80px]" value={form.internal_notes} onChange={(e) => onChange({ ...form, internal_notes: e.target.value })} />
        </div>
        <label className="flex items-center gap-2 mt-3 justify-end text-sm">
          <input type="checkbox" checked={form.include_in_report} onChange={(e) => onChange({ ...form, include_in_report: e.target.checked })} />
          לכלול בדו"ח
        </label>
        {error ? <div className="mt-3 text-sm text-red-300 text-right">{error}</div> : null}
        <div className="mt-6 flex gap-2 justify-end">
          <button className="btn btn-secondary" onClick={onClose} disabled={isSaving}>ביטול</button>
          <button className="btn btn-primary" onClick={onSave} disabled={isSaving}>{isSaving ? 'שומר...' : 'שמור'}</button>
        </div>
      </div>
    </div>
  )
}

function Field({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <div>
      <label className="block text-sm text-muted mb-1 text-right">{label}</label>
      <input className="input w-full" value={value} onChange={(e) => onChange(e.target.value)} />
    </div>
  )
}

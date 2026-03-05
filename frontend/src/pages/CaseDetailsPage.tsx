import { useCallback, useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { BackButton } from '../components/BackButton'
import { apiDownload, apiFetch } from '../lib/api'
import { Badge } from '../components/Badge'
import { formatILS, formatDateYMD, toNumber } from '../lib/format'
import {
  RAW_GROUP_ORDER,
  formatRawValue,
  groupRawEntries,
} from '../lib/rawImportFields'
import { useUnsavedGuard } from '../lib/useUnsavedGuard'
import type {
  CaseOut,
  CaseOverviewSummary,
  CaseWarning,
  CaseWarningsResponse,
  DeductibleSummary,
  ExpenseCategory,
  ExpenseOut,
  ExpensePayer,
  ExpenseSummary,
  FeeEvent,
  RetainerLedger,
} from '../lib/types'

const CATEGORY_LABEL: Record<ExpenseCategory, string> = {
  ATTORNEY_FEE: 'שכ"ט עו"ד',
  EXPERT: 'מומחה',
  MEDICAL_INFO: 'מידע רפואי',
  INVESTIGATOR: 'חוקר',
  FEES: 'אגרות',
  OTHER: 'אחר',
}

const PAYER_LABEL: Record<ExpensePayer, string> = {
  CLIENT_DEDUCTIBLE: 'השתתפות עצמית',
  INSURER: 'מבטח',
}

const CASE_TYPE_LABEL: Record<string, string> = {
  COURT: 'תיק ביהמ"ש',
  DEMAND_LETTER: 'מכתב דרישה',
  SMALL_CLAIMS: 'תביעות קטנות',
}

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
  APPEAL: 'ערעור',
  STAGE_BILLING: 'חיוב לפי שלבים',
}

/** Format current_procedure_stage from API (code, code(+k), or STAGE_BILLING:0) for display */
function formatProcedureStage(stage: string | null | undefined): string {
  if (!stage) return 'לא הוגדר'
  const plusMatch = stage.match(/^(.+)\(\+(\d+)\)$/)
  if (plusMatch) {
    const [, code, k] = plusMatch
    const label = FEE_EVENT_LABEL[code ?? ''] ?? (code ?? '')
    return k === '0' ? label : `${label} (+${k})`
  }
  if (stage.startsWith('STAGE_BILLING:')) {
    const n = stage.slice('STAGE_BILLING:'.length)
    return `חיוב לפי שלבים (${n})`
  }
  return FEE_EVENT_LABEL[stage] ?? stage
}

export function CaseDetailsPage() {
  const { caseId } = useParams()
  const id = Number(caseId)

  const [tab, setTab] = useState<'overview' | 'expenses' | 'deductible' | 'retainer' | 'fees'>('overview')
  const [expensesInitialPayerFilter, setExpensesInitialPayerFilter] = useState<ExpensePayer | ''>('')
  const [caseItem, setCaseItem] = useState<CaseOut | null>(null)
  const [expenses, setExpenses] = useState<ExpenseOut[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  type ModalKind = 'expense' | 'retainerPayment' | 'stageBilling'
  const [activeModal, setActiveModal] = useState<ModalKind | null>(null)
  const [retainerReloadKey, setRetainerReloadKey] = useState(0)
  const [feesReloadKey, setFeesReloadKey] = useState(0)

  const [feeEvents, setFeeEvents] = useState<FeeEvent[]>([])
  const [exportLoading, setExportLoading] = useState(false)
  const [toast, setToast] = useState<string | null>(null)
  const [refreshOverviewDeductibleKey, setRefreshOverviewDeductibleKey] = useState(0)

  useEffect(() => {
    if (activeModal) {
      document.body.style.overflow = 'hidden'
      return () => {
        document.body.style.overflow = ''
      }
    }
  }, [activeModal])

  async function load() {
    setError(null)
    setIsLoading(true)
    try {
      const [c, exps, fees] = await Promise.all([
        apiFetch<CaseOut>(`/cases/${id}`),
        apiFetch<ExpenseOut[]>(`/cases/${id}/expenses/`),
        apiFetch<FeeEvent[]>(`/cases/${id}/fees/`),
      ])
      setCaseItem(c)
      setExpenses(exps)
      setFeeEvents(fees)
    } catch (e: any) {
      setError(e?.message || 'שגיאה')
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    if (!Number.isFinite(id)) return
    load()
  }, [id])

  const currentLegalStage = useMemo(() => {
    if (feeEvents.length === 0) return null
    const latest = [...feeEvents].sort(
      (a, b) => new Date(b.event_date).getTime() - new Date(a.event_date).getTime()
    )[0]
    return FEE_EVENT_LABEL[latest.event_type] ?? latest.event_type
  }, [feeEvents])

  async function handleExportCase() {
    if (!Number.isFinite(id)) return
    setExportLoading(true)
    setToast(null)
    try {
      const { blob, filename } = await apiDownload(`/cases/${id}/export`)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename || `case_${id}_export.xlsx`
      a.click()
      URL.revokeObjectURL(url)
      setToast('הורדת הקובץ החלה בהצלחה')
      setTimeout(() => setToast(null), 4000)
    } catch (e: any) {
      setToast(e?.message || 'שגיאה בייצוא תיק')
      setTimeout(() => setToast(null), 4000)
    } finally {
      setExportLoading(false)
    }
  }

  return (
    <div className="min-h-screen w-full px-6 py-10">
      <div className="mx-auto w-full max-w-6xl">
        <div className="flex items-center justify-between gap-4">
          <div className="text-right">
            <div className="text-2xl font-bold">
              {caseItem ? (caseItem.case_name ?? caseItem.case_reference) : `פרטי תיק #${id}`}
            </div>
            {caseItem?.case_name ? (
              <div className="text-sm text-muted mt-1">מזהה: {caseItem.case_reference}</div>
            ) : null}
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={handleExportCase}
              disabled={exportLoading || !caseItem}
              className="btn btn-secondary"
            >
              {exportLoading ? 'מייצא...' : 'ייצוא תיק'}
            </button>
            <BackButton />
          </div>
        </div>

        {toast ? (
          <div className="fixed top-4 left-1/2 -translate-x-1/2 z-50 px-4 py-2 rounded-xl bg-primary text-bg2 shadow-lg">
            {toast}
          </div>
        ) : null}
        {error ? <div className="mt-6 text-sm text-red-300 text-right">{error}</div> : null}
        {isLoading ? <div className="mt-6 text-sm text-muted text-right">טוען...</div> : null}

        {!isLoading && caseItem ? (
          <div className="mt-6">
            <div className="card p-6">
              <div className="flex flex-col md:flex-row gap-4 md:items-center md:justify-between">
                <div className="text-right">
                  <div className="text-lg font-semibold">{caseItem.case_reference}</div>
                </div>
                {tab === 'expenses' ? (
                  <button
                    onClick={() => setActiveModal('expense')}
                    className="btn btn-primary h-12 px-5 rounded-2xl"
                  >
                    הוסף הוצאה
                  </button>
                ) : null}
              </div>

              <div className="mt-6 flex gap-2 flex-wrap">
                <TabButton active={tab === 'overview'} onClick={() => setTab('overview')}>
                  סקירה
                </TabButton>
                <TabButton active={tab === 'expenses'} onClick={() => setTab('expenses')}>
                  הוצאות
                </TabButton>
                <TabButton active={tab === 'deductible'} onClick={() => setTab('deductible')}>
                  השתתפות עצמית / אקסס
                </TabButton>
                <TabButton active={tab === 'retainer'} onClick={() => setTab('retainer')}>
                  ריטיינר
                </TabButton>
                <TabButton active={tab === 'fees'} onClick={() => setTab('fees')}>
                  שלבי שכ"ט
                </TabButton>
              </div>
            </div>

            <div className="mt-4 card p-6">
              {tab === 'overview' ? (
                <OverviewTab
                  caseId={caseItem.id}
                  caseItem={caseItem}
                  currentLegalStage={currentLegalStage}
                  setTab={setTab}
                  refreshKey={refreshOverviewDeductibleKey}
                />
              ) : null}

              {tab === 'expenses' ? (
                <ExpensesTab
                  caseItem={caseItem}
                  expenses={expenses}
                  onReload={load}
                  onExpensesTotalSaved={() => setRefreshOverviewDeductibleKey((k) => k + 1)}
                  onToast={(msg) => {
                    setToast(msg)
                    setTimeout(() => setToast(null), 4000)
                  }}
                  initialPayerFilter={expensesInitialPayerFilter || undefined}
                  onConsumedInitialFilter={() => setExpensesInitialPayerFilter('')}
                />
              ) : null}

              {tab === 'deductible' ? (
                <DeductibleTab
                  caseId={caseItem.id}
                  refreshKey={refreshOverviewDeductibleKey}
                  onOverridesSaved={() => setRefreshOverviewDeductibleKey((k) => k + 1)}
                  onToast={(msg) => {
                    setToast(msg)
                    setTimeout(() => setToast(null), 4000)
                  }}
                  onGoToExpensesWithDeductibleFilter={() => {
                    setExpensesInitialPayerFilter('CLIENT_DEDUCTIBLE')
                    setTab('expenses')
                  }}
                />
              ) : null}

              {tab === 'retainer' ? (
                <RetainerPanel
                  caseId={caseItem.id}
                  caseItem={caseItem}
                  onOpenAddPayment={() => setActiveModal('retainerPayment')}
                  retainerReloadKey={retainerReloadKey}
                  onRetainerChange={() => setRefreshOverviewDeductibleKey((k) => k + 1)}
                  onCaseUpdated={load}
                  onToast={(msg) => {
                    setToast(msg)
                    setTimeout(() => setToast(null), 4000)
                  }}
                />
              ) : null}
              {tab === 'fees' ? (
                <FeesPanel
                  caseId={caseItem.id}
                  historicalFeeStages={caseItem.historical_fee_stages ?? []}
                  legacyFeeText={caseItem.legacy_fee_text ?? null}
                  onOpenStageBilling={() => setActiveModal('stageBilling')}
                  feesReloadKey={feesReloadKey}
                  onFeeEventDeleted={() => setRefreshOverviewDeductibleKey((k) => k + 1)}
                  onToast={(msg) => {
                    setToast(msg)
                    setTimeout(() => setToast(null), 4000)
                  }}
                />
              ) : null}
            </div>
          </div>
        ) : null}
      </div>

      {caseItem && activeModal === 'expense' ? (
        <AddExpenseModal
          caseId={caseItem.id}
          onClose={() => setActiveModal(null)}
          onSaved={async () => {
            setActiveModal(null)
            await load()
          }}
        />
      ) : null}
      {caseItem && activeModal === 'retainerPayment' ? (
        <AddRetainerPaymentModal
          caseId={caseItem.id}
          onClose={() => setActiveModal(null)}
          onSaved={async () => {
            setActiveModal(null)
            setRetainerReloadKey((k) => k + 1)
            await load()
          }}
        />
      ) : null}
      {caseItem && activeModal === 'stageBilling' ? (
        <StageBillingModal
          caseId={caseItem.id}
          onClose={() => setActiveModal(null)}
          onSaved={async () => {
            setActiveModal(null)
            setFeesReloadKey((k) => k + 1)
            await load()
          }}
        />
      ) : null}
    </div>
  )
}

function OverviewTab({
  caseId,
  caseItem,
  currentLegalStage,
  setTab,
  refreshKey = 0,
}: {
  caseId: number
  caseItem: CaseOut
  currentLegalStage: string | null
  setTab: (tab: 'overview' | 'expenses' | 'deductible' | 'retainer' | 'fees') => void
  refreshKey?: number
}) {
  const [overview, setOverview] = useState<CaseOverviewSummary | null>(null)
  const [overviewLoading, setOverviewLoading] = useState(true)
  const [overviewError, setOverviewError] = useState<string | null>(null)
  const [warnings, setWarnings] = useState<CaseWarning[]>([])
  const [warningsLoading, setWarningsLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setOverviewLoading(true)
    setOverviewError(null)
    apiFetch<CaseOverviewSummary>(`/cases/${caseId}/overview-summary`)
      .then((d) => { if (!cancelled) setOverview(d) })
      .catch((e: any) => { if (!cancelled) setOverviewError(e?.message || 'שגיאה') })
      .finally(() => { if (!cancelled) setOverviewLoading(false) })
    return () => { cancelled = true }
  }, [caseId, refreshKey])

  useEffect(() => {
    let cancelled = false
    setWarningsLoading(true)
    apiFetch<CaseWarningsResponse>(`/cases/${caseId}/warnings`)
      .then((d) => { if (!cancelled) setWarnings(d.warnings) })
      .catch(() => { if (!cancelled) setWarnings([]) })
      .finally(() => { if (!cancelled) setWarningsLoading(false) })
    return () => { cancelled = true }
  }, [caseId])

  const stageLabel = overview?.current_procedure_stage != null
    ? formatProcedureStage(overview.current_procedure_stage)
    : (currentLegalStage ?? 'לא הוגדר')

  return (
    <div className="text-right space-y-8">
      {/* Case Overview Summary — key state in ~10 seconds */}
      <section>
        <h3 className="text-sm font-semibold text-muted mb-3">סיכום תיק</h3>
        {overviewLoading ? (
          <div className="text-sm text-muted py-4">טוען סיכום...</div>
        ) : overviewError ? (
          <div className="text-sm text-amber-600 py-4">לא ניתן לטעון סיכום. נתוני התיק למטה.</div>
        ) : overview ? (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {/* Procedure stage */}
              <div className="card-soft p-4">
                <div className="text-xs text-muted mb-1">שלב הליך נוכחי</div>
                <div className="font-semibold">{stageLabel}</div>
                <div className="text-xs text-muted mt-1">סטטוס: {overview.status === 'OPEN' ? 'פתוח' : 'סגור'}</div>
                <button type="button" onClick={() => setTab('fees')} className="btn btn-secondary btn-sm mt-3">
                  לשלבי שכ״ט
                </button>
              </div>
              {/* Retainer summary + freeze */}
              <div className="card-soft p-4">
                <div className="text-xs text-muted mb-1">ריטיינר חודשי</div>
                <div className="font-semibold">{formatILS(overview.retainer.monthly_gross_ils)}</div>
                {overview.retainer.retainer_is_frozen && overview.retainer.retainer_frozen_at ? (
                  <div className="text-xs text-muted mt-1">מוקפא מאז {overview.retainer.retainer_frozen_at}</div>
                ) : null}
                <button type="button" onClick={() => setTab('retainer')} className="btn btn-secondary btn-sm mt-3">
                  לריטיינר
                </button>
              </div>
            </div>

            {/* תמונת מצב כספית — unified 6 rows */}
            <div className="mt-6">
              <h3 className="text-sm font-semibold text-muted mb-3">תמונת מצב כספית</h3>
              <dl className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                <div className="card-soft p-4">
                  <dt className="text-xs text-muted">שכ״ט ששולם עד כה (תיאורטי)</dt>
                  <dd className="mt-1 font-semibold">{formatILS(overview.retainer.retainer_charged_to_date_ils)}</dd>
                </div>
                <div className="card-soft p-4">
                  <dt className="text-xs text-muted">שכ״ט לפי שלבים</dt>
                  <dd className="mt-1 font-semibold">{formatILS(overview.fees.fees_by_stages_ils)}</dd>
                  {overview.fees.last_fee_event_date && overview.fees.last_fee_event_amount != null ? (
                    <dd className="text-xs text-muted mt-0.5">אירוע אחרון: {overview.fees.last_fee_event_date}</dd>
                  ) : null}
                </div>
                <div className="card-soft p-4">
                  <dt className="text-xs text-muted">הוצאות עד כה</dt>
                  <dd className="mt-1 font-semibold">{formatILS(overview.expenses.total_expenses_ils)}</dd>
                </div>
                <div className="card-soft p-4">
                  <dt className="text-xs text-muted">אקסס כולל</dt>
                  <dd className="mt-1 font-semibold">{formatILS(overview.deductible.excess_total_ils)}</dd>
                </div>
                <div className="card-soft p-4">
                  <dt className="text-xs text-muted">יתרת אקסס</dt>
                  <dd className="mt-1 font-semibold">{formatILS(overview.deductible.excess_remaining_ils)}</dd>
                </div>
                <div className="card-soft p-4">
                  <dt className="text-xs text-muted">הפרש שכ״ט</dt>
                  <dd className={`mt-1 font-semibold ${toNumber(overview.fees.fee_diff_ils) < 0 ? 'text-red-400' : ''}`}>
                    {formatILS(overview.fees.fee_diff_ils)}
                  </dd>
                </div>
              </dl>
              <div className="flex flex-wrap gap-2 mt-3">
                <button type="button" onClick={() => setTab('expenses')} className="btn btn-secondary btn-sm">
                  להוצאות
                </button>
                <button type="button" onClick={() => setTab('deductible')} className="btn btn-secondary btn-sm">
                  להשתתפות עצמית / אקסס
                </button>
                <button type="button" onClick={() => setTab('fees')} className="btn btn-secondary btn-sm">
                  לשלבי שכ״ט
                </button>
              </div>
            </div>
          </>
        ) : null}
      </section>

      {/* Data quality warnings — read-only; no formula or data changes */}
      <section>
        <h3 className="text-sm font-semibold text-muted mb-3">אזהרות / בדיקות תקינות</h3>
        {warningsLoading ? (
          <div className="text-sm text-muted py-2">טוען בדיקות...</div>
        ) : warnings.length === 0 ? (
          <div className="text-sm text-muted py-2">אין אזהרות.</div>
        ) : (
          <ul className="space-y-2">
            {warnings.map((w) => (
              <li
                key={w.code}
                className={`flex flex-wrap items-center gap-2 rounded px-3 py-2 text-sm ${
                  w.severity === 'error'
                    ? 'bg-red-50 text-red-800 border border-red-200'
                    : w.severity === 'warn'
                      ? 'bg-amber-50 text-amber-800 border border-amber-200'
                      : 'bg-slate-100 text-slate-700 border border-slate-200'
                }`}
              >
                <span className="font-medium">{w.title}</span>
                <span className="text-muted">—</span>
                <span>{w.details}</span>
                {w.action_tab && (
                  <button
                    type="button"
                    onClick={() => {
                      const t = w.action_tab as 'overview' | 'expenses' | 'deductible' | 'retainer' | 'fees'
                      if (['overview', 'expenses', 'deductible', 'retainer', 'fees'].includes(t)) setTab(t)
                    }}
                    className="btn btn-secondary btn-sm ms-auto"
                  >
                    פתח
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <h3 className="text-sm font-semibold text-muted mb-3">זיהוי תיק</h3>
        <dl className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-3">
          <ReadOnlyRow label="מזהה תיק" value={caseItem.case_reference} />
          <ReadOnlyRow label="שם התיק" value={caseItem.case_name ?? caseItem.case_reference} />
          <ReadOnlyRow label="סניף" value={caseItem.branch_name ?? '—'} />
          <ReadOnlyRow label="סוג תיק" value={CASE_TYPE_LABEL[caseItem.case_type] ?? caseItem.case_type} />
          <ReadOnlyRow label="סטטוס" value={caseItem.status === 'OPEN' ? 'פתוח' : 'סגור'} />
          <ReadOnlyRow label="תאריך פתיחה" value={caseItem.open_date} />
        </dl>
      </section>

      {/* Unified financial numbers are in "תמונת מצב כספית" above (from overview-summary). */}

      <section>
        <h3 className="text-sm font-semibold text-muted mb-3">מידע משפטי / תהליכי</h3>
        <dl className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-3">
          <ReadOnlyRow label="שלב ההליך הנוכחי" value={currentLegalStage ?? 'לא הוגדר'} />
          <ReadOnlyRow label="תאריך עוגן ריטיינר" value={caseItem.retainer_anchor_date} />
        </dl>
      </section>

      {caseItem.raw_import_fields_json && Object.keys(caseItem.raw_import_fields_json).length > 0 ? (
        <RawImportSection raw={caseItem.raw_import_fields_json} />
      ) : null}
    </div>
  )
}

function RawImportSection({ raw }: { raw: Record<string, unknown> }) {
  const [filterEmpty, setFilterEmpty] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [expandedGroups, setExpandedGroups] = useState<Record<string, boolean>>(() => {
    const o: Record<string, boolean> = {}
    RAW_GROUP_ORDER.forEach((g) => { o[g] = true })
    return o
  })

  const entries = useMemo(() => Object.entries(raw), [raw])
  const byGroup = useMemo(
    () => groupRawEntries(entries, filterEmpty, searchQuery),
    [entries, filterEmpty, searchQuery]
  )

  function setAllExpanded(expanded: boolean) {
    setExpandedGroups((prev) => {
      const next = { ...prev }
      RAW_GROUP_ORDER.forEach((g) => { next[g] = expanded })
      return next
    })
  }

  function toggleGroup(group: string) {
    setExpandedGroups((prev) => ({ ...prev, [group]: !prev[group] }))
  }

  async function copyValue(display: string) {
    try {
      await navigator.clipboard.writeText(display)
    } catch {
      // ignore
    }
  }

  const hasAny = RAW_GROUP_ORDER.some((g) => byGroup[g]?.length > 0)

  return (
    <section className="space-y-4">
      <h3 className="text-sm font-semibold text-muted mb-3">נתוני ייבוא גולמיים (לקריאה בלבד)</h3>

      <div className="flex flex-col sm:flex-row gap-3 flex-wrap items-start sm:items-center">
        <label className="flex items-center gap-2 cursor-pointer text-sm text-muted">
          <input
            type="checkbox"
            checked={filterEmpty}
            onChange={(e) => setFilterEmpty(e.target.checked)}
          />
          <span>הצג רק שדות עם ערך</span>
        </label>
        <input
          type="text"
          placeholder="חיפוש לפי שדה או תווית..."
          className="max-w-[220px] h-9 rounded-lg border border-border/70 bg-surface px-3 text-sm text-text placeholder:text-placeholder outline-none focus:ring-2 focus:ring-primary/50"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
        />
        <div className="flex gap-2 text-sm">
          <button
            type="button"
            onClick={() => setAllExpanded(true)}
            className="text-primary hover:underline"
          >
            הצג הכל
          </button>
          <span className="text-muted">|</span>
          <button
            type="button"
            onClick={() => setAllExpanded(false)}
            className="text-primary hover:underline"
          >
            הסתר הכל
          </button>
        </div>
      </div>

      {!hasAny ? (
        <div className="text-sm text-muted py-4">אין שדות להצגה (נסה לבטל סינון או לשנות חיפוש)</div>
      ) : (
        <div className="space-y-2">
          {RAW_GROUP_ORDER.map((group) => {
            const rows = byGroup[group] ?? []
            if (rows.length === 0) return null
            const isExpanded = expandedGroups[group] !== false
            return (
              <div key={group} className="rounded-xl border border-border/60 bg-surface/30 overflow-hidden">
                <button
                  type="button"
                  onClick={() => toggleGroup(group)}
                  className="w-full text-right flex items-center justify-between gap-2 py-3 px-4 text-sm font-semibold text-muted hover:bg-surface/50 transition-colors"
                >
                  <span>{group}</span>
                  <span className="text-lg leading-none">{isExpanded ? '▼' : '◀'}</span>
                </button>
                {isExpanded ? (
                  <div className="border-t border-border/40">
                    {rows.map(({ key, label, value }) => {
                      const display = formatRawValue(key, value)
                      return (
                        <div
                          key={key}
                          className="flex items-center justify-between gap-4 py-2 px-4 border-b border-border/30 last:border-0 text-sm"
                        >
                          <div className="min-w-0 flex-1 text-right">
                            <span className="font-medium">{label}</span>
                            <span className="text-muted mr-2">:</span>
                            <span className="text-muted">{display}</span>
                          </div>
                          <button
                            type="button"
                            onClick={() => copyValue(display)}
                            className="shrink-0 text-xs text-primary hover:underline py-1 px-2"
                            title="העתק"
                          >
                            העתק
                          </button>
                        </div>
                      )
                    })}
                  </div>
                ) : null}
              </div>
            )
          })}
        </div>
      )}
    </section>
  )
}

function ReadOnlyRow({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-muted">{label}</dt>
      <dd className="mt-0.5 font-medium">{value}</dd>
    </div>
  )
}

const DEDUCTIBLE_FIELDS: Array<{
  key: keyof DeductibleSummary
  overrideKey: string
  label: string
  allowNegative: boolean
}> = [
  { key: 'excess_total_ils', overrideKey: 'excess_total_ils_override', label: 'אקסס כולל', allowNegative: false },
  { key: 'retainer_charged_to_date_ils', overrideKey: 'retainer_charged_override', label: 'נצרך עד כה ריטיינר', allowNegative: false },
  { key: 'expenses_total_ils', overrideKey: 'expenses_total_override', label: 'הוצאות', allowNegative: false },
  { key: 'fees_by_stages_ils', overrideKey: 'fees_by_stages_override', label: 'שכ״ט לפי שלבים', allowNegative: false },
  { key: 'excess_remaining_ils', overrideKey: 'excess_remaining_override', label: 'יתרת אקסס', allowNegative: false },
  { key: 'fee_diff_ils', overrideKey: 'fee_diff_override', label: 'הפרש שכ״ט', allowNegative: true },
]

function DeductibleTab({
  caseId,
  refreshKey = 0,
  onOverridesSaved,
  onToast,
  onGoToExpensesWithDeductibleFilter,
}: {
  caseId: number
  refreshKey?: number
  onOverridesSaved?: () => void
  onToast?: (msg: string) => void
  onGoToExpensesWithDeductibleFilter: () => void
}) {
  const [summary, setSummary] = useState<DeductibleSummary | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [editingKey, setEditingKey] = useState<string | null>(null)
  const [editValue, setEditValue] = useState('')
  const [saveError, setSaveError] = useState<string | null>(null)
  const [savingKey, setSavingKey] = useState<string | null>(null)

  const loadSummary = useCallback(() => {
    setError(null)
    return apiFetch<DeductibleSummary>(`/cases/${caseId}/deductible/summary`)
      .then(setSummary)
      .catch((e: any) => setError(e?.message || 'שגיאה'))
      .finally(() => setIsLoading(false))
  }, [caseId])

  useEffect(() => {
    let cancelled = false
    setSummary(null)
    setIsLoading(true)
    apiFetch<DeductibleSummary>(`/cases/${caseId}/deductible/summary`)
      .then((s) => { if (!cancelled) setSummary(s) })
      .catch((e: any) => { if (!cancelled) setError(e?.message || 'שגיאה') })
      .finally(() => { if (!cancelled) setIsLoading(false) })
    return () => { cancelled = true }
  }, [caseId, refreshKey])

  function getValue(fieldKey: keyof DeductibleSummary): number {
    if (!summary) return 0
    const v = summary[fieldKey]
    return toNumber(v)
  }

  function isOverridden(overrideKey: string): boolean {
    return !!(summary?.manual_overrides && summary.manual_overrides[overrideKey] != null)
  }

  function startEdit(overrideKey: string, fieldKey: keyof DeductibleSummary) {
    setEditingKey(overrideKey)
    setEditValue(String(getValue(fieldKey)))
    setSaveError(null)
  }

  function cancelEdit() {
    setEditingKey(null)
    setEditValue('')
    setSaveError(null)
  }

  async function saveOverride(overrideKey: string, allowNegative: boolean) {
    const num = toNumber(editValue)
    if (!Number.isFinite(num)) {
      setSaveError('נא להזין מספר תקין')
      return
    }
    if (!allowNegative && num < 0) {
      setSaveError('נא להזין ערך גדול או שווה לאפס')
      return
    }
    setSaveError(null)
    setSavingKey(overrideKey)
    try {
      await apiFetch(`/cases/${caseId}/overrides`, {
        method: 'PATCH',
        body: JSON.stringify({ [overrideKey]: num }),
      })
      await loadSummary()
      onOverridesSaved?.()
      onToast?.('הערך נשמר')
      setEditingKey(null)
      setEditValue('')
    } catch (e: any) {
      setSaveError(e?.message || 'שגיאה בשמירה')
    } finally {
      setSavingKey(null)
    }
  }

  async function resetOverride(overrideKey: string) {
    setSavingKey(overrideKey)
    try {
      await apiFetch(`/cases/${caseId}/overrides`, {
        method: 'PATCH',
        body: JSON.stringify({ [overrideKey]: null }),
      })
      await loadSummary()
      onOverridesSaved?.()
      onToast?.('אופס לערך מחושב')
    } catch (e: any) {
      onToast?.(e?.message || 'שגיאה באיפוס')
    } finally {
      setSavingKey(null)
    }
  }

  if (isLoading) return <div className="text-right text-sm text-muted">טוען...</div>
  if (error) return <div className="text-right text-sm text-red-300">{error}</div>
  if (!summary) return null

  return (
    <div className="space-y-6 text-right">
      <div className="grid grid-cols-1 gap-3 max-w-2xl">
        {DEDUCTIBLE_FIELDS.map(({ key, overrideKey, label, allowNegative }) => {
          const value = getValue(key)
          const overridden = isOverridden(overrideKey)
          const isEditing = editingKey === overrideKey
          const isSaving = savingKey === overrideKey

          return (
            <div key={overrideKey} className="card-soft p-4 flex flex-wrap items-center gap-3 justify-between">
              <div className="min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-xs text-muted">{label}</span>
                  {overridden ? (
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-700 dark:text-amber-300">
                      ידני
                    </span>
                  ) : null}
                </div>
                {isEditing ? (
                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    <input
                      type="number"
                      step={0.01}
                      inputMode="decimal"
                      className="input w-36 py-2 text-right"
                      value={editValue}
                      onChange={(e) => setEditValue(e.target.value)}
                      dir="ltr"
                      aria-label={label}
                    />
                    <span className="text-muted">₪</span>
                    <button
                      type="button"
                      onClick={() => saveOverride(overrideKey, allowNegative)}
                      disabled={isSaving}
                      className="btn btn-primary btn-sm"
                    >
                      {isSaving ? '...' : 'שמור'}
                    </button>
                    <button type="button" onClick={cancelEdit} className="btn btn-secondary btn-sm">
                      ביטול
                    </button>
                  </div>
                ) : (
                  <div className={`font-semibold mt-0.5 ${key === 'fee_diff_ils' && value < 0 ? 'text-red-400' : ''}`}>
                    {formatILS(value)}
                  </div>
                )}
                {isEditing && saveError ? (
                  <p className="text-sm text-red-400 mt-1" role="alert">{saveError}</p>
                ) : null}
              </div>
              {!isEditing ? (
                <div className="flex items-center gap-1">
                  <button
                    type="button"
                    onClick={() => startEdit(overrideKey, key)}
                    disabled={isSaving}
                    className="p-2 rounded-lg border border-border/60 hover:bg-surface/50 text-muted hover:text-foreground disabled:opacity-50"
                    title="עריכה"
                    aria-label={`ערוך ${label}`}
                  >
                    ✎
                  </button>
                  {overridden ? (
                    <button
                      type="button"
                      onClick={() => resetOverride(overrideKey)}
                      disabled={isSaving}
                      className="p-2 rounded-lg border border-border/60 hover:bg-surface/50 text-muted hover:text-foreground disabled:opacity-50"
                      title="איפוס לערך מחושב"
                      aria-label={`איפוס ${label}`}
                    >
                      ↺
                    </button>
                  ) : null}
                </div>
              ) : null}
            </div>
          )
        })}
      </div>

      <div className="card-soft p-4 bg-muted/20 max-w-2xl">
        <p className="text-sm text-muted leading-relaxed">
          ערכים מחושבים אוטומטית. לחיצה על העיפרון מאפשרת דריסה ידנית; איפוס מחזיר לערך המחושב.
        </p>
      </div>

      <div>
        <button
          type="button"
          onClick={onGoToExpensesWithDeductibleFilter}
          className="btn btn-secondary"
        >
          לכל ההוצאות
        </button>
        <span className="mr-2 text-sm text-muted">(יפתח את לשונית הוצאות)</span>
      </div>
    </div>
  )
}

function ExpensesTab({
  caseItem,
  expenses,
  onReload,
  onExpensesTotalSaved,
  onToast,
  initialPayerFilter,
  onConsumedInitialFilter,
}: {
  caseItem: CaseOut
  expenses: ExpenseOut[]
  onReload: () => void | Promise<void>
  onExpensesTotalSaved?: () => void
  onToast?: (msg: string) => void
  initialPayerFilter?: ExpensePayer
  onConsumedInitialFilter?: () => void
}) {
  const caseId = caseItem.id
  const serverTotal = caseItem.expenses_total_ils_gross != null ? toNumber(caseItem.expenses_total_ils_gross) : 0
  const [totalInput, setTotalInput] = useState(() => String(serverTotal >= 0 ? serverTotal : 0))
  const [saveError, setSaveError] = useState<string | null>(null)
  const [isSaving, setIsSaving] = useState(false)
  const [detailOpen, setDetailOpen] = useState(false)

  // Sync input from server when case or server value changes (e.g. after reload)
  useEffect(() => {
    const v = caseItem.expenses_total_ils_gross != null ? toNumber(caseItem.expenses_total_ils_gross) : 0
    setTotalInput(String(v >= 0 ? v : 0))
  }, [caseId, caseItem.expenses_total_ils_gross])

  async function handleSaveTotal() {
    const num = toNumber(totalInput)
    if (!Number.isFinite(num) || num < 0) {
      setSaveError('נא להזין סכום גדול או שווה לאפס')
      return
    }
    setSaveError(null)
    setIsSaving(true)
    try {
      await apiFetch(`/cases/${caseId}/expenses/total`, {
        method: 'PATCH',
        body: JSON.stringify({ expenses_total_ils_gross: num }),
      })
      setTotalInput(String(num))
      await onReload()
      onExpensesTotalSaved?.()
      onToast?.('סה״כ הוצאות נשמר בהצלחה')
    } catch (e: any) {
      setSaveError(e?.message || 'שגיאה בשמירה')
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div className="space-y-6 text-right">
      {/* Primary: single editable total */}
      <section className="card-soft p-6 max-w-xl">
        <h3 className="text-lg font-semibold mb-2">סה״כ הוצאות עד כה</h3>
        <div className="flex flex-wrap items-center gap-3 gap-y-2">
          <label className="sr-only" htmlFor="expenses-total-input">סה״כ הוצאות (₪)</label>
          <input
            id="expenses-total-input"
            type="number"
            min={0}
            step={0.01}
            inputMode="decimal"
            className="input text-2xl font-semibold w-48 py-3 text-right"
            value={totalInput}
            onChange={(e) => setTotalInput(e.target.value)}
            dir="ltr"
            aria-invalid={saveError ? true : undefined}
          />
          <span className="text-xl text-muted">₪</span>
          <button
            type="button"
            onClick={handleSaveTotal}
            disabled={isSaving}
            className="btn btn-primary h-12 px-6 rounded-2xl disabled:opacity-60"
          >
            {isSaving ? 'שומר...' : 'שמור'}
          </button>
        </div>
        <p className="text-sm text-muted mt-3">
          אין צורך בפירוט; זה סכום מצטבר שמתעדכן מדי פעם.
        </p>
        {saveError ? (
          <p className="text-sm text-red-400 mt-2" role="alert">{saveError}</p>
        ) : null}
      </section>

      {/* Optional: collapsible itemized detail */}
      <section>
        <button
          type="button"
          onClick={() => setDetailOpen((o) => !o)}
          className="flex items-center gap-2 text-sm text-muted hover:text-foreground"
        >
          <span className="inline-block w-5 text-left">{detailOpen ? '▼' : '▶'}</span>
          מתקדם: פירוט הוצאות
        </button>
        {detailOpen ? (
          <ExpensesDetailTable
            caseId={caseId}
            caseItem={caseItem}
            expenses={expenses}
            onReload={onReload}
            initialPayerFilter={initialPayerFilter ?? ''}
            onConsumedInitialFilter={onConsumedInitialFilter}
          />
        ) : null}
      </section>
    </div>
  )
}

function ExpensesDetailTable({
  caseId,
  caseItem,
  expenses,
  onReload,
  initialPayerFilter,
  onConsumedInitialFilter,
}: {
  caseId: number
  caseItem: CaseOut
  expenses: ExpenseOut[]
  onReload: () => void | Promise<void>
  initialPayerFilter: ExpensePayer | ''
  onConsumedInitialFilter?: () => void
}) {
  const [summary, setSummary] = useState<ExpenseSummary | null>(null)
  const [payerFilter, setPayerFilter] = useState<ExpensePayer | ''>(initialPayerFilter)
  useEffect(() => {
    if (initialPayerFilter && onConsumedInitialFilter) {
      setPayerFilter(initialPayerFilter)
      onConsumedInitialFilter()
    }
  }, [initialPayerFilter, onConsumedInitialFilter])
  const [searchText, setSearchText] = useState('')
  const [editingExpenseId, setEditingExpenseId] = useState<number | null>(null)
  const [deletingId, setDeletingId] = useState<number | null>(null)

  const hasSnapshot =
    caseItem.expenses_snapshot_ils_gross != null && Number(caseItem.expenses_snapshot_ils_gross) > 0

  useEffect(() => {
    let cancelled = false
    apiFetch<ExpenseSummary>(`/cases/${caseId}/expenses/summary`)
      .then((s) => { if (!cancelled) setSummary(s) })
      .catch(() => { if (!cancelled) setSummary(null) })
    return () => { cancelled = true }
  }, [caseId, expenses.length])

  const filtered = useMemo(() => {
    let list = expenses
    if (payerFilter) list = list.filter((e) => e.payer === payerFilter)
    if (searchText.trim()) {
      const q = searchText.trim().toLowerCase()
      list = list.filter(
        (e) =>
          (e.supplier_name || '').toLowerCase().includes(q) ||
          (e.service_description || '').toLowerCase().includes(q)
      )
    }
    return list
  }, [expenses, payerFilter, searchText])

  async function handleDelete(e: ExpenseOut) {
    if (!window.confirm('למחוק הוצאה זו?')) return
    setDeletingId(e.id)
    try {
      await apiFetch(`/cases/${caseId}/expenses/${e.id}`, { method: 'DELETE' })
      await onReload()
    } finally {
      setDeletingId(null)
    }
  }

  return (
    <div className="mt-4 space-y-4 border border-border/40 rounded-xl p-4 bg-muted/10">
      {hasSnapshot ? (
        <div className="text-sm text-muted text-right">
          Snapshot הוצאות (מהייבוא): {formatILS(caseItem.expenses_snapshot_ils_gross)} ₪
        </div>
      ) : null}
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm text-muted">מסנן:</span>
        <button
          type="button"
          onClick={() => setPayerFilter('')}
          className={`px-3 py-1.5 rounded-lg text-sm border ${!payerFilter ? 'bg-surface border-primary/60' : 'border-border/60'}`}
        >
          הכל
        </button>
        {(Object.keys(PAYER_LABEL) as ExpensePayer[]).map((p) => (
          <button
            key={p}
            type="button"
            onClick={() => setPayerFilter(payerFilter === p ? '' : p)}
            className={`px-3 py-1.5 rounded-lg text-sm border ${payerFilter === p ? 'bg-surface border-primary/60' : 'border-border/60'}`}
          >
            {PAYER_LABEL[p]}
          </button>
        ))}
        <input
          type="text"
          placeholder="חיפוש בתיאור..."
          className="input max-w-[200px] py-1.5 text-sm"
          value={searchText}
          onChange={(e) => setSearchText(e.target.value)}
        />
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-muted">
            <tr className="border-b border-border/60">
              <th className="text-right py-3">תאריך</th>
              <th className="text-right py-3">סכום (₪)</th>
              <th className="text-right py-3">משלם</th>
              <th className="text-right py-3">תיאור/הערה</th>
              <th className="text-right py-3">פעולות</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((e) => (
              <tr key={e.id} className="border-b border-border/30 hover:bg-surface/30">
                <td className="py-3">{e.expense_date}</td>
                <td className="py-3">{formatILS(e.amount_ils_gross)}</td>
                <td className="py-3">{PAYER_LABEL[e.payer]}</td>
                <td className="py-3">
                  {[e.supplier_name, e.service_description].filter(Boolean).join(' — ') || '—'}
                </td>
                <td className="py-3">
                  <div className="flex gap-2 justify-end">
                    <button
                      type="button"
                      onClick={() => setEditingExpenseId(e.id)}
                      className="text-primary hover:underline text-sm"
                    >
                      עריכה
                    </button>
                    <button
                      type="button"
                      onClick={() => handleDelete(e)}
                      disabled={deletingId === e.id}
                      className="text-red-400 hover:underline text-sm disabled:opacity-50"
                    >
                      {deletingId === e.id ? '...' : 'מחיקה'}
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={5} className="py-10 text-center text-muted">
                  {expenses.length === 0 ? 'אין הוצאות' : 'אין תוצאות לפי המסנן'}
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
      {editingExpenseId != null ? (
        <EditExpenseModal
          caseId={caseId}
          expense={expenses.find((x) => x.id === editingExpenseId)!}
          onClose={() => setEditingExpenseId(null)}
          onSaved={async () => {
            setEditingExpenseId(null)
            await onReload()
          }}
        />
      ) : null}
    </div>
  )
}

function EditExpenseModal({
  caseId,
  expense,
  onClose,
  onSaved,
}: {
  caseId: number
  expense: ExpenseOut
  onClose: () => void
  onSaved: () => void | Promise<void>
}) {
  const [supplierName, setSupplierName] = useState(expense.supplier_name)
  const [amount, setAmount] = useState(String(expense.amount_ils_gross))
  const [serviceDescription, setServiceDescription] = useState(expense.service_description)
  const [demandReceivedDate, setDemandReceivedDate] = useState(expense.demand_received_date)
  const [expenseDate, setExpenseDate] = useState(expense.expense_date)
  const [payer, setPayer] = useState<ExpensePayer>(expense.payer)
  const [attachmentUrl, setAttachmentUrl] = useState(expense.attachment_url || '')

  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  function validate(): string | null {
    if (!supplierName.trim()) return 'נא להזין שם ספק'
    if (!amount.trim() || toNumber(amount) <= 0) return 'נא להזין סכום חיובי'
    if (!serviceDescription.trim()) return 'נא להזין תיאור'
    if (!expenseDate) return 'נא לבחור תאריך הוצאה'
    return null
  }

  async function submit() {
    const err = validate()
    if (err) {
      setError(err)
      return
    }
    setError(null)
    setIsSubmitting(true)
    try {
      await apiFetch(`/cases/${caseId}/expenses/${expense.id}`, {
        method: 'PATCH',
        body: JSON.stringify({
          supplier_name: supplierName.trim(),
          amount_ils_gross: toNumber(amount),
          service_description: serviceDescription.trim(),
          demand_received_date: demandReceivedDate,
          expense_date: expenseDate,
          payer,
          attachment_url: attachmentUrl.trim() || null,
        }),
      })
      await onSaved()
    } catch (e: any) {
      setError(e?.message || 'שגיאה')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="modal">
      <div className="modal-overlay" />
      <div className="modal-panel max-w-[640px]">
        <div className="text-right">
          <div className="text-lg font-semibold">עריכת הוצאה</div>
          <div className="text-sm text-muted mt-1">קטגוריה: {CATEGORY_LABEL[expense.category]}</div>
        </div>

        <div className="mt-5 grid grid-cols-1 md:grid-cols-2 gap-4">
          <Field label="שם הספק">
            <input className="input" value={supplierName} onChange={(e) => setSupplierName(e.target.value)} />
          </Field>
          <Field label='הסכום כולל מע"מ'>
            <input className="input" value={amount} onChange={(e) => setAmount(e.target.value)} inputMode="decimal" />
          </Field>
          <Field label="השירות שניתן" className="md:col-span-2">
            <textarea className="input h-24 py-3" value={serviceDescription} onChange={(e) => setServiceDescription(e.target.value)} />
          </Field>
          <Field label="מועד מסירת דרישת התשלום לטר״מ">
            <input className="input" type="date" value={demandReceivedDate} onChange={(e) => setDemandReceivedDate(e.target.value)} />
          </Field>
          <Field label="תאריך הוצאה">
            <input className="input" type="date" value={expenseDate} onChange={(e) => setExpenseDate(e.target.value)} />
          </Field>
          <Field label="משלם">
            <select className="input" value={payer} onChange={(e) => setPayer(e.target.value as ExpensePayer)}>
              <option value="CLIENT_DEDUCTIBLE">השתתפות עצמית</option>
              <option value="INSURER">מבטח</option>
            </select>
          </Field>
          <Field label="קישור לקובץ/תיעוד (אופציונלי)" className="md:col-span-2">
            <input className="input" value={attachmentUrl} onChange={(e) => setAttachmentUrl(e.target.value)} placeholder="https://..." dir="ltr" />
          </Field>
        </div>

        {error ? <div className="mt-4 text-sm text-red-300 text-right">{error}</div> : null}

        <div className="mt-6 flex gap-3 justify-end">
          <button type="button" onClick={onClose} className="btn btn-secondary h-12 px-5 rounded-2xl" disabled={isSubmitting}>
            ביטול
          </button>
          <button type="button" onClick={submit} disabled={isSubmitting} className="btn btn-primary h-12 px-6 rounded-2xl">
            שמירה
          </button>
        </div>
      </div>
    </div>
  )
}

function TabButton({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={[
        'h-10 px-4 rounded-xl border transition-colors',
        active ? 'bg-surface border-primary/60 text-primary' : 'bg-transparent border-border/60 text-muted hover:border-primary/40',
      ].join(' ')}
    >
      {children}
    </button>
  )
}

function AddExpenseModal({ caseId, onClose, onSaved }: { caseId: number; onClose: () => void; onSaved: () => void }) {
  const today = new Date().toISOString().slice(0, 10)

  const [supplierName, setSupplierName] = useState('')
  const [amount, setAmount] = useState('')
  const [serviceDescription, setServiceDescription] = useState('')
  const [demandReceivedDate, setDemandReceivedDate] = useState(today)
  const [expenseDate, setExpenseDate] = useState(today)
  const [category, setCategory] = useState<ExpenseCategory>('OTHER')
  const [payer, setPayer] = useState<ExpensePayer | ''>('')
  const [attachmentUrl, setAttachmentUrl] = useState('')

  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const isDirty =
    supplierName.trim() !== '' ||
    amount.trim() !== '' ||
    serviceDescription.trim() !== '' ||
    demandReceivedDate !== today ||
    expenseDate !== today ||
    category !== 'OTHER' ||
    payer !== '' ||
    attachmentUrl.trim() !== ''

  useUnsavedGuard(isDirty, 'יש שינויים שלא נשמרו. לצאת בלי לשמור?')

  function safeClose() {
    if (isDirty) {
      const ok = window.confirm('יש שינויים שלא נשמרו. לצאת בלי לשמור?')
      if (!ok) return
    }
    onClose()
  }

  function validate(): string | null {
    if (!supplierName.trim()) return 'נא להזין שם ספק'
    if (!amount.trim() || toNumber(amount) <= 0) return 'נא להזין סכום חיובי'
    if (!serviceDescription.trim()) return 'נא להזין תיאור'
    if (!expenseDate) return 'נא לבחור תאריך הוצאה'
    if (payer !== 'CLIENT_DEDUCTIBLE' && payer !== 'INSURER') return 'נא לבחור משלם (השתתפות עצמית או מבטח)'
    return null
  }

  async function submit() {
    const err = validate()
    if (err) {
      setError(err)
      return
    }
    setError(null)
    setIsSubmitting(true)
    try {
      const payload: any = {
        supplier_name: supplierName.trim(),
        amount_ils_gross: toNumber(amount),
        service_description: serviceDescription.trim(),
        demand_received_date: demandReceivedDate,
        expense_date: expenseDate,
        category,
        payer: payer as ExpensePayer,
        attachment_url: attachmentUrl.trim() || null,
      }
      await apiFetch(`/cases/${caseId}/expenses/`, { method: 'POST', body: JSON.stringify(payload) })
      onSaved()
    } catch (e: any) {
      setError(e?.message || 'שגיאה')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="modal">
      <div className="modal-overlay" />
      <div className="modal-panel max-w-[640px]">
        <div className="text-right">
          <div className="text-lg font-semibold">הוספת הוצאה</div>
          <div className="text-sm text-muted mt-1">כל הסכומים בש״ח וכוללים מע״מ (ברוטו).</div>
        </div>

        <div className="mt-5 grid grid-cols-1 md:grid-cols-2 gap-4">
          <Field label="שם הספק">
            <input className="input" value={supplierName} onChange={(e) => setSupplierName(e.target.value)} />
          </Field>
          <Field label='הסכום כולל מע"מ'>
            <input className="input" value={amount} onChange={(e) => setAmount(e.target.value)} inputMode="decimal" />
          </Field>

          <Field label="השירות שניתן" className="md:col-span-2">
            <textarea className="input h-24 py-3" value={serviceDescription} onChange={(e) => setServiceDescription(e.target.value)} />
          </Field>

            <Field label='מועד מסירת דרישת התשלום לטר״מ'>
            <input className="input" type="date" value={demandReceivedDate} onChange={(e) => setDemandReceivedDate(e.target.value)} />
          </Field>
          <Field label="תאריך הוצאה">
            <input className="input" type="date" value={expenseDate} onChange={(e) => setExpenseDate(e.target.value)} />
          </Field>

          <Field label="קטגוריה">
            <select className="input" value={category} onChange={(e) => setCategory(e.target.value as ExpenseCategory)}>
              {Object.entries(CATEGORY_LABEL).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </select>
          </Field>
          <Field label="משלם">
            <select className="input" value={payer} onChange={(e) => setPayer(e.target.value as ExpensePayer | '')}>
              <option value="">בחר משלם</option>
              <option value="CLIENT_DEDUCTIBLE">השתתפות עצמית</option>
              <option value="INSURER">מבטח</option>
            </select>
          </Field>

          <Field label="קישור לקובץ/תיעוד (אופציונלי)" className="md:col-span-2">
            <input className="input" value={attachmentUrl} onChange={(e) => setAttachmentUrl(e.target.value)} placeholder="https://..." dir="ltr" />
          </Field>
        </div>

        {error ? <div className="mt-4 text-sm text-red-300 text-right">{error}</div> : null}

        <div className="mt-6 flex gap-3 justify-end">
          <button
            onClick={safeClose}
            className="btn btn-secondary h-12 px-5 rounded-2xl"
            disabled={isSubmitting}
          >
            ביטול
          </button>
          <button
            onClick={submit}
            disabled={isSubmitting}
            className="btn btn-primary h-12 px-6 rounded-2xl"
          >
            שמירה
          </button>
        </div>
      </div>
    </div>
  )
}

function Field({
  label,
  children,
  className,
}: {
  label: string
  children: React.ReactNode
  className?: string
}) {
  return (
    <div className={['space-y-2 text-right', className || ''].join(' ')}>
      <div className="text-sm font-medium text-muted">{label}</div>
      {children}
    </div>
  )
}

function RetainerPanel({
  caseId,
  caseItem,
  onOpenAddPayment,
  retainerReloadKey,
  onRetainerChange,
  onCaseUpdated,
  onToast,
}: {
  caseId: number
  caseItem: CaseOut
  onOpenAddPayment: () => void
  retainerReloadKey: number
  onRetainerChange?: () => void
  onCaseUpdated?: () => void | Promise<void>
  onToast?: (msg: string) => void
}) {
  const [ledger, setLedger] = useState<RetainerLedger | null>(null)
  const [overview, setOverview] = useState<CaseOverviewSummary | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [anchorDate, setAnchorDate] = useState(caseItem.retainer_anchor_date?.slice(0, 10) ?? '')
  const [snapshotMonth, setSnapshotMonth] = useState(
    caseItem.retainer_snapshot_through_month ? String(caseItem.retainer_snapshot_through_month).slice(0, 7) : ''
  )
  const [datesSaveError, setDatesSaveError] = useState<string | null>(null)
  const [datesSaving, setDatesSaving] = useState(false)
  const [freezeSaving, setFreezeSaving] = useState(false)

  const isFrozen = !!caseItem.retainer_is_frozen
  const frozenAt = caseItem.retainer_frozen_at ?? null

  async function load() {
    setError(null)
    setIsLoading(true)
    try {
      const [ledgerData, overviewData] = await Promise.all([
        apiFetch<RetainerLedger>(`/cases/${caseId}/retainer/ledger`),
        apiFetch<CaseOverviewSummary>(`/cases/${caseId}/overview-summary`),
      ])
      setLedger(ledgerData)
      setOverview(overviewData)
    } catch (e: any) {
      setError(e?.message || 'שגיאה')
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    load()
    setAnchorDate(caseItem.retainer_anchor_date?.slice(0, 10) ?? '')
    setSnapshotMonth(
      caseItem.retainer_snapshot_through_month ? String(caseItem.retainer_snapshot_through_month).slice(0, 7) : ''
    )
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [caseId, retainerReloadKey])

  useEffect(() => {
    setAnchorDate(caseItem.retainer_anchor_date?.slice(0, 10) ?? '')
    setSnapshotMonth(
      caseItem.retainer_snapshot_through_month ? String(caseItem.retainer_snapshot_through_month).slice(0, 7) : ''
    )
  }, [caseItem.retainer_anchor_date, caseItem.retainer_snapshot_through_month])

  async function saveDates() {
    setDatesSaveError(null)
    setDatesSaving(true)
    try {
      const body: { retainer_anchor_date?: string; retainer_snapshot_through_month?: string } = {}
      if (anchorDate) body.retainer_anchor_date = anchorDate
      if (snapshotMonth) body.retainer_snapshot_through_month = `${snapshotMonth}-01`
      await apiFetch(`/cases/${caseId}/retainer/dates`, { method: 'PATCH', body: JSON.stringify(body) })
      await onCaseUpdated?.()
      onRetainerChange?.()
      await load()
      onToast?.('נשמר')
    } catch (e: any) {
      setDatesSaveError(e?.message || 'שגיאה בשמירה')
    } finally {
      setDatesSaving(false)
    }
  }

  async function toggleFreeze() {
    setFreezeSaving(true)
    try {
      await apiFetch(`/cases/${caseId}/retainer/freeze`, {
        method: 'POST',
        body: JSON.stringify({ freeze: !isFrozen }),
      })
      await onCaseUpdated?.()
      onRetainerChange?.()
      await load()
      onToast?.(isFrozen ? 'הקפאה בוטלה' : 'ריטיינר הוקפא')
    } catch (e: any) {
      onToast?.(e?.message || 'שגיאה')
    } finally {
      setFreezeSaving(false)
    }
  }

  if (isLoading) return <div className="text-right text-sm text-muted">טוען ריטיינר...</div>
  if (error) return <div className="text-right text-sm text-red-300">{error}</div>
  if (!ledger || !overview) return null

  const cfg = ledger.config
  const monthlyDisplay = `${formatILS(cfg.monthly_base_net_ils)} + מע״מ ${cfg.vat_pct} = ${formatILS(cfg.monthly_gross_ils)}`
  const chargedMonths = overview.retainer.charged_months_count ?? 0
  const retainerCharged = toNumber(overview.retainer.retainer_charged_to_date_ils ?? 0)

  return (
    <div className="space-y-6 text-right">
      {/* Primary: charged months + theoretical charged */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div className="card-soft p-4">
          <div className="text-xs text-muted mb-1">מספר חודשי חיוב שחויבו מעוגן</div>
          <div className="font-semibold">{chargedMonths}</div>
        </div>
        <div className="card-soft p-4">
          <div className="text-xs text-muted mb-1">שכ״ט ששולם עד כה (תיאורטי)</div>
          <div className="font-semibold">{formatILS(retainerCharged)}</div>
        </div>
      </div>

      {/* Monthly rate (read-only) */}
      <div className="card-soft p-4">
        <div className="text-xs text-muted mb-1">סכום ריטיינר חודשי</div>
        <div className="font-semibold">{monthlyDisplay}</div>
      </div>

      {/* Editable: תאריך עוגן ריטיינר */}
      <div className="card-soft p-4">
        <div className="text-xs text-muted mb-1">תאריך עוגן ריטיינר</div>
        <div className="flex flex-wrap items-center gap-2 mt-1">
          <input
            type="date"
            className="input py-2 w-40"
            value={anchorDate}
            onChange={(e) => setAnchorDate(e.target.value)}
            aria-label="תאריך עוגן ריטיינר"
          />
          <button
            type="button"
            onClick={saveDates}
            disabled={datesSaving}
            className="btn btn-primary btn-sm"
          >
            {datesSaving ? '...' : 'שמור'}
          </button>
        </div>
      </div>

      {/* Editable: Snapshot עד חודש (YYYY-MM) */}
      <div className="card-soft p-4">
        <div className="text-xs text-muted mb-1">Snapshot עד חודש (ראשון בחודש)</div>
        <div className="flex flex-wrap items-center gap-2 mt-1">
          <input
            type="month"
            className="input py-2 w-40"
            value={snapshotMonth}
            onChange={(e) => setSnapshotMonth(e.target.value)}
            aria-label="Snapshot עד חודש"
          />
          <button
            type="button"
            onClick={saveDates}
            disabled={datesSaving}
            className="btn btn-primary btn-sm"
          >
            {datesSaving ? '...' : 'שמור'}
          </button>
        </div>
      </div>
      {datesSaveError ? (
        <p className="text-sm text-red-400 text-right" role="alert">{datesSaveError}</p>
      ) : null}

      {/* Freeze toggle */}
      <div className="card-soft p-4">
        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={toggleFreeze}
            disabled={freezeSaving}
            className={isFrozen ? 'btn btn-secondary' : 'btn btn-primary'}
          >
            {freezeSaving ? '...' : isFrozen ? 'בטל הקפאה' : 'הקפא חישוב ריטיינר'}
          </button>
          {isFrozen && frozenAt ? (
            <span className="text-sm text-muted">מוקפא מאז {frozenAt}</span>
          ) : null}
        </div>
      </div>

      {/* Explanation */}
      <div className="card-soft p-4 bg-muted/20">
        <p className="text-sm text-muted leading-relaxed">
          <strong>הסבר:</strong> עוגן הריטיינר ו־Snapshot עד חודש קובעים מאיזה חודש מחושבים חודשי החיוב. כשמוקפא — החיוב לא מתקדם. לשונית זו מציגה רק את ריטיינר השכר החודשי — לא הוצאות.
        </p>
      </div>

      {/* Monthly ledger table (optional, read-only) */}
      <div className="card-soft p-5">
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div>
            <div className="font-semibold">פנקס ריטיינר חודשי</div>
            <div className="text-sm text-muted mt-1">נצבר, שולם ויתרת קרדיט לפי חודש</div>
          </div>
          <button type="button" onClick={onOpenAddPayment} className="btn btn-primary">
            הוסף תשלום ריטיינר
          </button>
        </div>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-muted">
              <tr className="border-b border-border/60">
                <th className="text-right py-3">חודש</th>
                <th className="text-right py-3">נצבר (ש״ח)</th>
                <th className="text-right py-3">שולם (ש״ח)</th>
                <th className="text-right py-3">יתרת קרדיט (ש״ח)</th>
                <th className="text-right py-3">הערות</th>
              </tr>
            </thead>
            <tbody>
              {ledger.rows.map((row, idx) => {
                const isSnapshot = row.row_type === 'snapshot'
                const isPayment = row.row_type === 'payment'
                const monthLabel = isPayment ? `${row.month} · תשלום` : row.month
                const notesDisplay = row.notes ?? '—'
                return (
                  <tr
                    key={`${row.row_type}-${row.month}-${idx}`}
                    className={`border-b border-border/30 ${isSnapshot ? 'bg-muted/20' : ''} ${isPayment ? 'bg-surface/20' : ''} hover:bg-surface/30`}
                  >
                    <td className={`py-3 ${isPayment ? 'pr-6 text-muted' : ''}`}>{monthLabel}</td>
                    <td className="py-3">{formatILS(row.accrued_ils)}</td>
                    <td className="py-3">{formatILS(row.paid_ils)}</td>
                    <td className="py-3">{formatILS(row.running_credit_ils)}</td>
                    <td className="py-3 text-muted">{notesDisplay}</td>
                  </tr>
                )
              })}
              {ledger.rows.length === 0 ? (
                <tr>
                  <td colSpan={5} className="py-8 text-center text-muted">
                    אין שורות בפנקס
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

function AddRetainerPaymentModal({ caseId, onClose, onSaved }: { caseId: number; onClose: () => void; onSaved: () => void }) {
  const today = new Date().toISOString().slice(0, 10)
  const [paymentDate, setPaymentDate] = useState(today)
  const [amount, setAmount] = useState('945.00')
  const [note, setNote] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const isDirty = paymentDate !== today || amount.trim() !== '945.00' || note.trim() !== ''
  useUnsavedGuard(isDirty, 'יש שינויים שלא נשמרו. לצאת בלי לשמור?')

  function safeClose() {
    if (isDirty) {
      const ok = window.confirm('יש שינויים שלא נשמרו. לצאת בלי לשמור?')
      if (!ok) return
    }
    onClose()
  }

  async function submit() {
    setError(null)
    setIsSubmitting(true)
    try {
      await apiFetch(`/cases/${caseId}/retainer/payments`, {
        method: 'POST',
        body: JSON.stringify({
          payment_date: paymentDate,
          amount_ils_gross: toNumber(amount),
          note: note.trim() || undefined,
        }),
      })
      onSaved()
    } catch (e: any) {
      setError(e?.message || 'שגיאה')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="modal">
      <div className="modal-overlay" />
      <div className="modal-panel max-w-[520px]">
        <div className="text-right">
          <div className="text-lg font-semibold">הוספת תשלום ריטיינר</div>
          <div className="text-sm text-muted mt-1">כל הסכומים בש״ח וכוללים מע״מ (ברוטו).</div>
        </div>

        <div className="mt-5 grid grid-cols-1 md:grid-cols-2 gap-4">
          <Field label="תאריך תשלום">
            <input className="input" type="date" value={paymentDate} onChange={(e) => setPaymentDate(e.target.value)} />
          </Field>
          <Field label='סכום (כולל מע"מ)'>
            <input className="input" value={amount} onChange={(e) => setAmount(e.target.value)} inputMode="decimal" />
          </Field>
        </div>
        <div className="mt-4">
          <Field label="הערה (אופציונלי)">
            <input className="input" value={note} onChange={(e) => setNote(e.target.value)} placeholder="הערה פנימית" />
          </Field>
        </div>

        {error ? <div className="mt-4 text-sm text-red-300 text-right">{error}</div> : null}

        <div className="mt-6 flex gap-3 justify-end">
          <button
            onClick={safeClose}
            className="btn btn-secondary h-12 px-5 rounded-2xl"
            disabled={isSubmitting}
          >
            ביטול
          </button>
          <button
            onClick={submit}
            disabled={isSubmitting}
            className="btn btn-primary h-12 px-6 rounded-2xl"
          >
            שמירה
          </button>
        </div>
      </div>
    </div>
  )
}

const STAGE_BILLING_GROUPS: { title: string; codes: string[] }[] = [
  { title: 'שלבי בית משפט (1–5)', codes: ['COURT_STAGE_1_DEFENSE', 'COURT_STAGE_2_DAMAGES', 'COURT_STAGE_3_EVIDENCE', 'COURT_STAGE_4_PROOFS', 'COURT_STAGE_5_SUMMARIES'] },
  { title: 'בית משפט — נוסף', codes: ['THIRD_PARTY_NOTICE', 'AMENDED_DEFENSE_PARTIAL', 'AMENDED_DEFENSE_FULL', 'ADDITIONAL_PROOF_HEARING'] },
  { title: 'מכתב דרישה', codes: ['DEMAND_FIX', 'DEMAND_HOURLY'] },
  { title: 'תביעות קטנות', codes: ['SMALL_CLAIMS_MANUAL'] },
  { title: 'ערעור', codes: ['APPEAL'] },
]

function FeesPanel({
  caseId,
  historicalFeeStages,
  legacyFeeText,
  onOpenStageBilling,
  feesReloadKey,
  onFeeEventDeleted,
  onToast,
}: {
  caseId: number
  historicalFeeStages: string[]
  legacyFeeText: string | null
  onOpenStageBilling: () => void
  feesReloadKey: number
  onFeeEventDeleted?: () => void
  onToast?: (msg: string) => void
}) {
  const [items, setItems] = useState<FeeEvent[]>([])
  const [unifiedSummary, setUnifiedSummary] = useState<DeductibleSummary | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [deleteModalEvent, setDeleteModalEvent] = useState<FeeEvent | null>(null)

  async function load() {
    setError(null)
    setIsLoading(true)
    try {
      const [data, summary] = await Promise.all([
        apiFetch<FeeEvent[]>(`/cases/${caseId}/fees/`),
        apiFetch<DeductibleSummary>(`/cases/${caseId}/deductible/summary`),
      ])
      setItems(data)
      setUnifiedSummary(summary)
    } catch (e: any) {
      setError(e?.message || 'שגיאה')
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [caseId, feesReloadKey])

  const feesByStages = unifiedSummary ? toNumber(unifiedSummary.fees_by_stages_ils) : 0
  const feeDiff = unifiedSummary ? toNumber(unifiedSummary.fee_diff_ils) : 0

  if (isLoading) return <div className="text-right text-sm text-muted">טוען אירועי שכ״ט...</div>
  if (error) return <div className="text-right text-sm text-red-300">{error}</div>

  const hasHistorical = historicalFeeStages.length > 0

  return (
    <div className="space-y-6">
      {legacyFeeText ? (
        <div className="card-soft p-5">
          <div className="text-right mb-2">
            <div className="font-semibold">פירוט חיוב שכ״ט (ייבוא)</div>
            <div className="text-sm text-muted mt-1">לקריאה בלבד</div>
          </div>
          <p className="text-sm text-right whitespace-pre-wrap">{legacyFeeText}</p>
        </div>
      ) : null}
      {hasHistorical ? (
        <div className="card-soft p-5">
          <div className="text-right mb-4">
            <div className="font-semibold">שלבי שכ״ט עבר (ייבוא)</div>
            <div className="text-sm text-muted mt-1">תיעוד בלבד — אינו משפיע על קרדיט ריטיינר או תשלומים</div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-muted">
                <tr className="border-b border-border/60">
                  <th className="text-right py-3">תאריך</th>
                  <th className="text-right py-3">שלב</th>
                  <th className="text-right py-3">סכום</th>
                  <th className="text-right py-3">מקור</th>
                </tr>
              </thead>
              <tbody>
                {historicalFeeStages.map((eventType, i) => (
                  <tr key={`hist-${i}`} className="border-b border-border/30 bg-muted/20">
                    <td className="py-3">—</td>
                    <td className="py-3">{FEE_EVENT_LABEL[eventType] ?? eventType}</td>
                    <td className="py-3">—</td>
                    <td className="py-3">
                      <Badge label="עבר" variant="info" />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}

      {hasHistorical ? (
        <h3 className="text-sm font-semibold text-muted">שלבי שכ״ט עתידיים</h3>
      ) : null}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <MiniStat title="סה״כ שכ״ט" value={formatILS(feesByStages)} />
        <MiniStat
          title="כוסה בקרדיט"
          value={formatILS(feeDiff)}
          valueClassName={feeDiff < 0 ? 'text-red-400' : undefined}
        />
      </div>

      <div className="card-soft p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="text-right">
            <div className="font-semibold">אירועי שכ״ט</div>
            <div className="text-sm text-muted mt-1">בחרו שלבים שבוצעו — יחויבו רק שלבים חדשים (דלתא). המערכת מקצה קרדיט ריטיינר לפי סדר כרונולוגי</div>
          </div>
          <button type="button" onClick={onOpenStageBilling} className="btn btn-primary">
            חיוב משלבי ביצוע
          </button>
        </div>

        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-muted">
              <tr className="border-b border-border/60">
                <th className="text-right py-3">תאריך</th>
                <th className="text-right py-3">שלב</th>
                <th className="text-right py-3">סכום</th>
                <th className="text-right py-3">כוסה בקרדיט</th>
                <th className="text-right py-3">מקור</th>
                <th className="text-right py-3 w-12">מחיקה</th>
              </tr>
            </thead>
            <tbody>
              {items.map((e) => (
                <tr key={e.id} className="border-b border-border/30 hover:bg-surface/30">
                  <td className="py-3">{formatDateYMD(e.event_date)}</td>
                  <td className="py-3">
                    {e.event_type === 'STAGE_BILLING' && e.breakdown_json
                      ? (() => {
                          const codes = e.breakdown_json.new_codes ?? e.breakdown_json.codes ?? []
                          return codes.length ? `${FEE_EVENT_LABEL[e.event_type]} (${codes.length} חדשים)` : FEE_EVENT_LABEL[e.event_type]
                        })()
                      : FEE_EVENT_LABEL[e.event_type] || e.event_type}
                  </td>
                  <td className="py-3">{formatILS(e.computed_amount_ils_gross)}</td>
                  <td className="py-3">{formatILS(e.amount_covered_by_credit_ils_gross)}</td>
                  <td className="py-3">
                    <Badge label="חדש" variant="success" />
                  </td>
                  <td className="py-3">
                    <button
                      type="button"
                      onClick={() => setDeleteModalEvent(e)}
                      className="p-1.5 rounded text-muted hover:bg-red-500/20 hover:text-red-400"
                      title="מחיקת אירוע (רכה)"
                      aria-label="מחק אירוע"
                    >
                      🗑️
                    </button>
                  </td>
                </tr>
              ))}
              {items.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-8 text-center text-muted">
                    אין אירועים
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </div>

      {deleteModalEvent ? (
        <DeleteFeeEventModal
          caseId={caseId}
          event={deleteModalEvent}
          onClose={() => setDeleteModalEvent(null)}
          onDeleted={async () => {
            setDeleteModalEvent(null)
            await load()
            onFeeEventDeleted?.()
            onToast?.('אירוע השכ״ט נמחק')
          }}
        />
      ) : null}
    </div>
  )
}

function DeleteFeeEventModal({
  caseId,
  event,
  onClose,
  onDeleted,
}: {
  caseId: number
  event: FeeEvent
  onClose: () => void
  onDeleted: () => void | Promise<void>
}) {
  const [reason, setReason] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  async function handleDelete() {
    const trimmed = reason.trim()
    if (trimmed.length === 0) {
      setError('נא להזין סיבת המחיקה (חובה)')
      return
    }
    if (trimmed.length > 500) {
      setError('סיבת המחיקה עד 500 תווים')
      return
    }
    setError(null)
    setIsSubmitting(true)
    try {
      await apiFetch(`/cases/${caseId}/fees/${event.id}`, {
        method: 'DELETE',
        body: JSON.stringify({ delete_reason: trimmed }),
      })
      await onDeleted()
      onClose()
    } catch (e: any) {
      setError(e?.message || 'שגיאה במחיקה')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="modal">
      <div className="modal-overlay" />
      <div className="modal-panel max-w-md">
        <div className="text-right">
          <div className="text-lg font-semibold">מחיקת אירוע שכ״ט</div>
          <p className="text-sm text-muted mt-2">
            האירוע יוסר מהחישובים אך יישמר לאנליטיקה.
          </p>
        </div>
        <div className="mt-4">
          <label htmlFor="delete-reason" className="block text-sm text-muted mb-1 text-right">
            סיבת המחיקה (חובה, 1–500 תווים)
          </label>
          <textarea
            id="delete-reason"
            className="input w-full min-h-[80px] py-2 text-right"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            maxLength={500}
            placeholder="למשל: הזנה כפולה"
            dir="auto"
          />
          {error ? (
            <p className="text-sm text-red-400 mt-2 text-right" role="alert">{error}</p>
          ) : null}
        </div>
        <div className="mt-6 flex gap-3 justify-end">
          <button
            type="button"
            onClick={onClose}
            className="btn btn-secondary"
            disabled={isSubmitting}
          >
            בטל
          </button>
          <button
            type="button"
            onClick={handleDelete}
            disabled={isSubmitting}
            className="btn bg-red-600 hover:bg-red-700 text-white"
          >
            {isSubmitting ? 'מוחק...' : 'מחק'}
          </button>
        </div>
      </div>
    </div>
  )
}

type RateRow = { code: string; amount_ils: number }

function StageBillingModal({ caseId, onClose, onSaved }: { caseId: number; onClose: () => void; onSaved: () => void }) {
  const today = new Date().toISOString().slice(0, 10)
  const [eventDate, setEventDate] = useState(today)
  const [selectedCodes, setSelectedCodes] = useState<Set<string>>(new Set())
  const [adjustmentKind, setAdjustmentKind] = useState<'DISCOUNT' | 'SURCHARGE'>('DISCOUNT')
  const [adjustmentAmount, setAdjustmentAmount] = useState('')
  const [adjustmentReason, setAdjustmentReason] = useState('')

  const [rates, setRates] = useState<RateRow[]>([])
  const [billedCodes, setBilledCodes] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    Promise.all([
      apiFetch<RateRow[]>('/fee-stage-rates'),
      apiFetch<string[]>(`/cases/${caseId}/fees/billed-codes`),
    ])
      .then(([r, b]) => {
        if (!cancelled) {
          setRates(r)
          setBilledCodes(b)
        }
      })
      .catch((e: any) => {
        if (!cancelled) setError(e?.message || 'שגיאה')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [caseId])

  const rateByCode = useMemo(() => {
    const m: Record<string, number> = {}
    rates.forEach((r) => { m[r.code] = r.amount_ils })
    return m
  }, [rates])

  const billedSet = useMemo(() => new Set(billedCodes), [billedCodes])
  const newCodes = useMemo(() => Array.from(selectedCodes).filter((c) => !billedSet.has(c)), [selectedCodes, billedSet])
  const alreadyBilledSelected = useMemo(() => Array.from(selectedCodes).filter((c) => billedSet.has(c)), [selectedCodes, billedSet])

  const baseTotalSelected = useMemo(() => {
    return Array.from(selectedCodes).reduce((sum, code) => sum + (rateByCode[code] ?? 0), 0)
  }, [selectedCodes, rateByCode])

  const deltaTotal = useMemo(() => {
    return newCodes.reduce((sum, code) => sum + (rateByCode[code] ?? 0), 0)
  }, [newCodes, rateByCode])

  const adjustmentValue = useMemo(() => {
    const amt = parseFloat(adjustmentAmount)
    return !Number.isNaN(amt) && amt >= 0 ? amt : 0
  }, [adjustmentAmount])

  const finalDeltaTotal = useMemo(() => {
    if (adjustmentValue <= 0) return deltaTotal
    if (adjustmentKind === 'DISCOUNT') return Math.max(0, deltaTotal - adjustmentValue)
    return deltaTotal + adjustmentValue
  }, [deltaTotal, adjustmentKind, adjustmentValue])

  const noNewCodes = newCodes.length === 0
  const [confirmZeroNewCodes, setConfirmZeroNewCodes] = useState(false)

  function toggleCode(code: string) {
    setSelectedCodes((prev) => {
      const next = new Set(prev)
      if (next.has(code)) next.delete(code)
      else next.add(code)
      return next
    })
  }

  async function submit() {
    if (selectedCodes.size === 0) {
      setError('נא לבחור לפחות שלב אחד (בוצעו עד כה)')
      return
    }
    if (noNewCodes && !confirmZeroNewCodes) {
      setError('אין קודים חדשים לחיוב')
      return
    }
    setError(null)
    setIsSubmitting(true)
    try {
      const payload: any = {
        event_date: eventDate,
        codes: Array.from(selectedCodes),
        confirm_zero_new_codes: noNewCodes && confirmZeroNewCodes,
      }
      if (adjustmentAmount.trim() !== '' && !Number.isNaN(parseFloat(adjustmentAmount))) {
        payload.adjustment = {
          kind: adjustmentKind,
          amount_ils: parseFloat(adjustmentAmount),
          reason: adjustmentReason.trim(),
        }
      }
      await apiFetch(`/cases/${caseId}/fees/stage-billing`, { method: 'POST', body: JSON.stringify(payload) })
      onSaved()
    } catch (e: any) {
      setError(e?.message || 'שגיאה')
    } finally {
      setIsSubmitting(false)
    }
  }

  if (loading) {
    return (
      <div className="modal">
        <div className="modal-overlay" />
        <div className="modal-panel max-w-[680px]">
          <div className="text-right text-muted">טוען...</div>
        </div>
      </div>
    )
  }

  return (
    <div className="modal">
      <div className="modal-overlay" onClick={onClose} />
      <div className="modal-panel max-w-[800px] max-h-[90vh] overflow-y-auto">
        <div className="text-right">
          <div className="text-lg font-semibold">חיוב מצטבר משלבי ביצוע</div>
          <div className="text-sm text-muted mt-1">בחרו את כל השלבים שבוצעו עד כה. יחויבו רק שלבים שעדיין לא חובו. אפשר להוסיף הנחה או תוספת על הסכום החדש.</div>
        </div>

        <div className="mt-4">
          <Field label="תאריך אירוע">
            <input className="input w-full max-w-[200px]" type="date" value={eventDate} onChange={(e) => setEventDate(e.target.value)} />
          </Field>
        </div>

        <div className="mt-5 space-y-4">
          {STAGE_BILLING_GROUPS.map((group) => (
            <div key={group.title} className="border border-border/50 rounded-xl p-4">
              <div className="text-sm font-semibold text-muted mb-3">{group.title}</div>
              <div className="flex flex-wrap gap-4">
                {group.codes.map((code) => {
                  const amount = rateByCode[code]
                  const isBilled = billedCodes.includes(code)
                  const selected = selectedCodes.has(code)
                  return (
                    <label key={code} className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={selected}
                        onChange={() => toggleCode(code)}
                      />
                      <span>{FEE_EVENT_LABEL[code] ?? code}</span>
                      {amount != null && <span className="text-muted text-sm">({formatILS(amount)})</span>}
                      {isBilled && selected && <span className="text-amber-400 text-xs">כבר חויב</span>}
                    </label>
                  )
                })}
              </div>
            </div>
          ))}
        </div>

        {alreadyBilledSelected.length > 0 ? (
          <div className="mt-4 p-3 rounded-xl bg-amber-500/10 border border-amber-500/30 text-right text-sm text-amber-200">
            שלבים שכבר חובו: {alreadyBilledSelected.map((c) => FEE_EVENT_LABEL[c] ?? c).join(', ')} — לא יחויבו שוב.
          </div>
        ) : null}

        <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="text-right p-4 rounded-xl bg-surface/50">
            <div className="text-sm text-muted">סה״כ נבחר (לפי תעריף)</div>
            <div className="text-xl font-bold mt-1">{formatILS(baseTotalSelected)}</div>
          </div>
          <div className="text-right p-4 rounded-xl bg-surface/50">
            <div className="text-sm text-muted">שלבים חדשים לחיוב</div>
            <div className="text-sm mt-1">
              {newCodes.length === 0 ? (
                <span className="text-muted">אין — כולם כבר חובו</span>
              ) : (
                newCodes.map((c) => FEE_EVENT_LABEL[c] ?? c).join(' • ')
              )}
            </div>
            <div className="text-lg font-bold mt-2">{formatILS(deltaTotal)}</div>
          </div>
          <div className="space-y-3">
            <div className="text-sm font-semibold text-muted">התאמה (אופציונלי) — סכום בש״ח בלבד</div>
            <select className="input" value={adjustmentKind} onChange={(e) => setAdjustmentKind(e.target.value as 'DISCOUNT' | 'SURCHARGE')}>
              <option value="DISCOUNT">הנחה</option>
              <option value="SURCHARGE">תוספת</option>
            </select>
            <input
              className="input"
              type="number"
              min={0}
              step={0.01}
              placeholder="סכום (₪)"
              value={adjustmentAmount}
              onChange={(e) => setAdjustmentAmount(e.target.value)}
            />
            <input
              className="input"
              placeholder="סיבת ההתאמה"
              value={adjustmentReason}
              onChange={(e) => setAdjustmentReason(e.target.value)}
            />
          </div>
        </div>

        <div className="mt-4 p-4 rounded-xl border border-primary/40 bg-primary/5 text-right">
          <div className="text-sm text-muted">סכום לחיוב (לאחר התאמה)</div>
          <div className="text-2xl font-bold mt-1">{formatILS(finalDeltaTotal)}</div>
        </div>

        {noNewCodes ? (
          <div className="mt-4 p-3 rounded-xl bg-amber-500/10 border border-amber-500/30 text-right text-sm">
            <p className="text-amber-200 mb-2">אין קודים חדשים לחיוב</p>
            <label className="flex items-center gap-2 justify-end cursor-pointer">
              <input type="checkbox" checked={confirmZeroNewCodes} onChange={(e) => setConfirmZeroNewCodes(e.target.checked)} />
              <span>אישור: ליצור אירוע עם סכום 0 (תיעוד בלבד)</span>
            </label>
          </div>
        ) : null}

        {error ? <div className="mt-4 text-sm text-red-300 text-right">{error}</div> : null}

        <div className="mt-6 flex gap-3 justify-end">
          <button type="button" onClick={onClose} className="btn btn-secondary" disabled={isSubmitting}>ביטול</button>
          <button
            type="button"
            onClick={submit}
            className="btn btn-primary"
            disabled={isSubmitting || selectedCodes.size === 0 || (noNewCodes && !confirmZeroNewCodes)}
            title={noNewCodes ? 'אין קודים חדשים לחיוב' : finalDeltaTotal > 0 ? `חיוב ${formatILS(finalDeltaTotal)} (שלבים חדשים בלבד)` : undefined}
          >
            {isSubmitting
              ? 'שומר…'
              : noNewCodes && !confirmZeroNewCodes
                ? 'אין קודים חדשים לחיוב'
                : noNewCodes && confirmZeroNewCodes
                  ? 'יצירת אירוע 0 ש״ח (תיעוד)'
                  : `חיוב ${formatILS(finalDeltaTotal)} (שלבים חדשים בלבד)`}
          </button>
        </div>
      </div>
    </div>
  )
}

function MiniStat({
  title,
  value,
  valueClassName,
}: {
  title: string
  value: string
  valueClassName?: string
}) {
  return (
    <div className="rounded-2xl border border-border/60 bg-card/40 p-4 text-right">
      <div className="text-xs text-muted">{title}</div>
      <div className={`mt-1 text-lg font-bold ${valueClassName ?? ''}`}>{value}</div>
    </div>
  )
}



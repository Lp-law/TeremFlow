import { useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { BackButton } from '../components/BackButton'
import { apiFetch } from '../lib/api'
import { Badge } from '../components/Badge'
import { formatILS, formatDateYMD, isOverdue, toNumber } from '../lib/format'
import {
  RAW_GROUP_ORDER,
  formatRawValue,
  groupRawEntries,
} from '../lib/rawImportFields'
import { useUnsavedGuard } from '../lib/useUnsavedGuard'
import type {
  CaseOut,
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
            <BackButton />
          </div>
        </div>

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
                  caseItem={caseItem}
                  currentLegalStage={currentLegalStage}
                />
              ) : null}

              {tab === 'expenses' ? (
                <ExpensesTab
                  caseItem={caseItem}
                  expenses={expenses}
                  onReload={load}
                  initialPayerFilter={expensesInitialPayerFilter || undefined}
                  onConsumedInitialFilter={() => setExpensesInitialPayerFilter('')}
                />
              ) : null}

              {tab === 'deductible' ? (
                <DeductibleTab
                  caseId={caseItem.id}
                  onGoToExpensesWithDeductibleFilter={() => {
                    setExpensesInitialPayerFilter('CLIENT_DEDUCTIBLE')
                    setTab('expenses')
                  }}
                />
              ) : null}

              {tab === 'retainer' ? (
                <RetainerPanel
                  caseId={caseItem.id}
                  onOpenAddPayment={() => setActiveModal('retainerPayment')}
                  retainerReloadKey={retainerReloadKey}
                />
              ) : null}
              {tab === 'fees' ? (
                <FeesPanel
                  caseId={caseItem.id}
                  historicalFeeStages={caseItem.historical_fee_stages ?? []}
                  legacyFeeText={caseItem.legacy_fee_text ?? null}
                  onOpenStageBilling={() => setActiveModal('stageBilling')}
                  feesReloadKey={feesReloadKey}
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

function OverviewTab({ caseItem, currentLegalStage }: { caseItem: CaseOut; currentLegalStage: string | null }) {
  return (
    <div className="text-right space-y-8">
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

      <section>
        <h3 className="text-sm font-semibold text-muted mb-3">תמונת מצב כספית (לקריאה בלבד)</h3>
        <dl className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-3">
          <ReadOnlyRow label="השתתפות עצמית (ברוטו)" value={formatILS(caseItem.deductible_ils_gross)} />
          <ReadOnlyRow label="שכ״ט ששולם עד כה" value={caseItem.retainer_snapshot_ils_gross != null ? formatILS(caseItem.retainer_snapshot_ils_gross) : '—'} />
          <ReadOnlyRow
            label="חודש סיום snapshot"
            value={caseItem.retainer_snapshot_through_month ?? '—'}
          />
          <ReadOnlyRow label="הוצאות ששולמו עד כה" value={caseItem.expenses_snapshot_ils_gross != null ? formatILS(caseItem.expenses_snapshot_ils_gross) : '—'} />
          <ReadOnlyRow label="יתרת השתתפות עצמית" value={formatILS(caseItem.excess_remaining_ils_gross)} />
        </dl>
      </section>

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

function DeductibleTab({
  caseId,
  onGoToExpensesWithDeductibleFilter,
}: {
  caseId: number
  onGoToExpensesWithDeductibleFilter: () => void
}) {
  const [summary, setSummary] = useState<DeductibleSummary | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setError(null)
    setSummary(null)
    apiFetch<DeductibleSummary>(`/cases/${caseId}/deductible/summary`)
      .then((s) => { if (!cancelled) setSummary(s) })
      .catch((e: any) => { if (!cancelled) setError(e?.message || 'שגיאה') })
      .finally(() => { if (!cancelled) setIsLoading(false) })
    return () => { cancelled = true }
  }, [caseId])

  if (isLoading) return <div className="text-right text-sm text-muted">טוען...</div>
  if (error) return <div className="text-right text-sm text-red-300">{error}</div>
  if (!summary) return null

  const hasExcess = summary.excess_remaining_ils != null

  return (
    <div className="space-y-6">
      <div className={`grid grid-cols-1 sm:grid-cols-3 gap-3 ${hasExcess ? 'sm:grid-cols-4' : ''}`}>
        <div className="card-soft p-4">
          <div className="text-xs text-muted mb-1">אקסס כולל</div>
          <div className="font-semibold">{formatILS(summary.deductible_total_ils)}</div>
        </div>
        <div className="card-soft p-4">
          <div className="text-xs text-muted mb-1">נצרך עד כה</div>
          <div className="font-semibold">{formatILS(summary.deductible_consumed_ils)}</div>
        </div>
        <div className="card-soft p-4">
          <div className="text-xs text-muted mb-1">יתרה</div>
          <div className="font-semibold">{formatILS(summary.deductible_remaining_ils)}</div>
        </div>
        {hasExcess ? (
          <div className="card-soft p-4">
            <div className="text-xs text-muted mb-1">יתרת אקסס</div>
            <div className="font-semibold">{formatILS(summary.excess_remaining_ils)}</div>
          </div>
        ) : null}
      </div>

      <div className="card-soft p-4 bg-muted/20">
        <p className="text-sm text-right text-muted leading-relaxed">
          רק הוצאות שמסומנות &quot;השתתפות עצמית&quot; נוגסות באקסס. שכ״ט וריטיינר לא.
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
        <span className="mr-2 text-sm text-muted">(יפתח את לשונית הוצאות עם מסנן השתתפות עצמית)</span>
      </div>
    </div>
  )
}

function ExpensesTab({
  caseItem,
  expenses,
  onReload,
  initialPayerFilter,
  onConsumedInitialFilter,
}: {
  caseItem: CaseOut
  expenses: ExpenseOut[]
  onReload: () => void | Promise<void>
  initialPayerFilter?: ExpensePayer
  onConsumedInitialFilter?: () => void
}) {
  const [summary, setSummary] = useState<ExpenseSummary | null>(null)
  const [payerFilter, setPayerFilter] = useState<ExpensePayer | ''>(initialPayerFilter ?? '')
  useEffect(() => {
    if (initialPayerFilter && onConsumedInitialFilter) {
      setPayerFilter(initialPayerFilter)
      onConsumedInitialFilter()
    }
  }, [initialPayerFilter, onConsumedInitialFilter])
  const [searchText, setSearchText] = useState('')
  const [editingExpenseId, setEditingExpenseId] = useState<number | null>(null)
  const [deletingId, setDeletingId] = useState<number | null>(null)

  const caseId = caseItem.id
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

  const totalDisplay = summary ? formatILS(summary.total_expenses_ils) : '—'
  const deductibleDisplay = summary ? formatILS(summary.deductible_consumed_by_expenses_ils) : '—'
  const otherDisplay = summary ? formatILS(summary.other_expenses_ils) : '—'

  return (
    <div className="space-y-6">
      {/* Summary cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div className="card-soft p-4">
          <div className="text-xs text-muted mb-1">סה״כ הוצאות</div>
          <div className="font-semibold">{totalDisplay}</div>
        </div>
        <div className="card-soft p-4">
          <div className="text-xs text-muted mb-1">נוגס בהשתתפות עצמית</div>
          <div className="font-semibold">{deductibleDisplay}</div>
        </div>
        <div className="card-soft p-4">
          <div className="text-xs text-muted mb-1">הוצאות אחרות</div>
          <div className="font-semibold">{otherDisplay}</div>
        </div>
      </div>

      {/* Snapshot (read-only from import) */}
      {hasSnapshot ? (
        <div className="card-soft p-4 bg-muted/20">
          <div className="text-sm text-right text-muted">
            Snapshot הוצאות (מהייבוא): {formatILS(caseItem.expenses_snapshot_ils_gross)} ₪
          </div>
        </div>
      ) : null}

      {/* Filter chips + search */}
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

      {/* Table */}
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
  onOpenAddPayment,
  retainerReloadKey,
}: {
  caseId: number
  onOpenAddPayment: () => void
  retainerReloadKey: number
}) {
  const [ledger, setLedger] = useState<RetainerLedger | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  async function load() {
    setError(null)
    setIsLoading(true)
    try {
      const data = await apiFetch<RetainerLedger>(`/cases/${caseId}/retainer/ledger`)
      setLedger(data)
    } catch (e: any) {
      setError(e?.message || 'שגיאה')
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [caseId, retainerReloadKey])

  if (isLoading) return <div className="text-right text-sm text-muted">טוען ריטיינר...</div>
  if (error) return <div className="text-right text-sm text-red-300">{error}</div>
  if (!ledger) return null

  const cfg = ledger.config
  const monthlyDisplay = `${formatILS(cfg.monthly_base_net_ils)} + מע״מ ${cfg.vat_pct} = ${formatILS(cfg.monthly_gross_ils)}`

  return (
    <div className="space-y-6">
      {/* Header summary cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
        <div className="card-soft p-4">
          <div className="text-xs text-muted mb-1">סכום ריטיינר חודשי</div>
          <div className="font-semibold">{monthlyDisplay}</div>
        </div>
        <div className="card-soft p-4">
          <div className="text-xs text-muted mb-1">עוגן חישוב</div>
          <div className="font-semibold">{ledger.anchor_date}</div>
        </div>
        <div className="card-soft p-4">
          <div className="text-xs text-muted mb-1">Snapshot עד חודש</div>
          <div className="font-semibold">
            {ledger.snapshot_through_month ? String(ledger.snapshot_through_month).slice(0, 7) : 'לא הוגדר'}
          </div>
        </div>
        <div className="card-soft p-4">
          <div className="text-xs text-muted mb-1">Snapshot שולם</div>
          <div className="font-semibold">{formatILS(ledger.snapshot_paid_ils)}</div>
        </div>
        <div className="card-soft p-4">
          <div className="text-xs text-muted mb-1">קרדיט ריטיינר נוכחי</div>
          <div className="font-semibold">{formatILS(ledger.current_credit_ils)}</div>
        </div>
      </div>

      {/* Explanation block */}
      <div className="card-soft p-4 bg-muted/20">
        <p className="text-sm text-right text-muted leading-relaxed">
          <strong>הסבר:</strong> ה־Snapshot מייצג סכום ריטיינר ששולם עבור תקופה שקדמה למערכת. מהחודש שאחרי &quot;Snapshot עד חודש&quot; מחושבים אקרואלים חודשיים. לשונית זו מציגה רק את ריטיינר השכר החודשי — לא הוצאות.
        </p>
      </div>

      {/* Monthly ledger table */}
      <div className="card-soft p-5">
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div className="text-right">
            <div className="font-semibold">פנקס ריטיינר חודשי</div>
            <div className="text-sm text-muted mt-1">נצבר, שולם ויתרת קרדיט לפי חודש</div>
          </div>
          <button onClick={onOpenAddPayment} className="btn btn-primary">
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
}: {
  caseId: number
  historicalFeeStages: string[]
  legacyFeeText: string | null
  onOpenStageBilling: () => void
  feesReloadKey: number
}) {
  const [items, setItems] = useState<FeeEvent[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  async function load() {
    setError(null)
    setIsLoading(true)
    try {
      const data = await apiFetch<FeeEvent[]>(`/cases/${caseId}/fees/`)
      setItems(data)
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

  const totals = useMemo(() => {
    const total = items.reduce((s, e) => s + toNumber(e.computed_amount_ils_gross), 0)
    const covered = items.reduce((s, e) => s + toNumber(e.amount_covered_by_credit_ils_gross), 0)
    const due = items.reduce((s, e) => s + toNumber(e.amount_due_cash_ils_gross), 0)
    return { total, covered, due }
  }, [items])

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

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <MiniStat title="סה״כ שכ״ט" value={formatILS(totals.total)} />
        <MiniStat title="כוסה בקרדיט" value={formatILS(totals.covered)} />
        <MiniStat title="לתשלום במזומן" value={formatILS(totals.due)} />
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
                <th className="text-right py-3">לתשלום</th>
                <th className="text-right py-3">מקור</th>
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
                  <td className="py-3">{formatILS(e.amount_due_cash_ils_gross)}</td>
                  <td className="py-3">
                    <Badge label="חדש" variant="success" />
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

function MiniStat({ title, value }: { title: string; value: string }) {
  return (
    <div className="rounded-2xl border border-border/60 bg-card/40 p-4 text-right">
      <div className="text-xs text-muted">{title}</div>
      <div className="mt-1 text-lg font-bold">{value}</div>
    </div>
  )
}



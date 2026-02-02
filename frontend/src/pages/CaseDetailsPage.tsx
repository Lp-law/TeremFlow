import { useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { BackButton } from '../components/BackButton'
import { apiFetch } from '../lib/api'
import { Badge } from '../components/Badge'
import { formatILS, formatDateYMD, isOverdue, toNumber } from '../lib/format'
import { useUnsavedGuard } from '../lib/useUnsavedGuard'
import type {
  CaseOut,
  ExpenseCategory,
  ExpenseOut,
  ExpensePayer,
  FeeEvent,
  FeeEventType,
  RetainerAccrual,
  RetainerPayment,
  RetainerSummary,
} from '../lib/types'

const CATEGORY_LABEL: Record<ExpenseCategory, string> = {
  ATTORNEY_FEE: 'שכ"ט עו"ד',
  EXPERT: 'מומחה',
  MEDICAL_INFO: 'מידע רפואי',
  INVESTIGATOR: 'חוקר',
  FEES: 'אגרות',
  OTHER: 'אחר',
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
}

export function CaseDetailsPage() {
  const { caseId } = useParams()
  const id = Number(caseId)

  const [tab, setTab] = useState<'overview' | 'expenses' | 'retainer' | 'fees'>('overview')
  const [caseItem, setCaseItem] = useState<CaseOut | null>(null)
  const [expenses, setExpenses] = useState<ExpenseOut[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  type ModalKind = 'expense' | 'retainerPayment' | 'feeEvent'
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
                    הוספת הוצאה חדשה
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
                <ExpensesTab caseItem={caseItem} expenses={expenses} />
              ) : null}

              {tab === 'retainer' ? (
                <RetainerPanel
                  caseId={caseItem.id}
                  retainerAnchorDate={caseItem.retainer_anchor_date}
                  retainerSnapshotIlsGross={caseItem.retainer_snapshot_ils_gross}
                  onOpenAddPayment={() => setActiveModal('retainerPayment')}
                  retainerReloadKey={retainerReloadKey}
                />
              ) : null}
              {tab === 'fees' ? (
                <FeesPanel
                  caseId={caseItem.id}
                  onOpenAddFeeStage={() => setActiveModal('feeEvent')}
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
      {caseItem && activeModal === 'feeEvent' ? (
        <AddFeeEventModal
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
    </div>
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

function ExpensesTab({ caseItem, expenses }: { caseItem: CaseOut; expenses: ExpenseOut[] }) {
  const hasHistorical =
    caseItem.expenses_snapshot_ils_gross != null && Number(caseItem.expenses_snapshot_ils_gross) > 0

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="text-muted">
          <tr className="border-b border-border/60">
            <th className="text-right py-3">תאריך</th>
            <th className="text-right py-3">תיאור</th>
            <th className="text-right py-3">סכום (כולל מע״מ)</th>
            <th className="text-right py-3">מקור</th>
          </tr>
        </thead>
        <tbody>
          {hasHistorical ? (
            <tr className="border-b border-border/30 bg-muted/20">
              <td className="py-3">—</td>
              <td className="py-3">הוצאות עבר (ייבוא)</td>
              <td className="py-3">{formatILS(caseItem.expenses_snapshot_ils_gross)}</td>
              <td className="py-3">
                <Badge label="עבר" variant="info" />
              </td>
            </tr>
          ) : null}
          {expenses.map((e) => (
            <tr key={e.id} className="border-b border-border/30 hover:bg-surface/30">
              <td className="py-3">{e.expense_date}</td>
              <td className="py-3">
                {e.supplier_name}
                {e.service_description ? ` — ${e.service_description}` : ''}
              </td>
              <td className="py-3">{formatILS(e.amount_ils_gross)}</td>
              <td className="py-3">
                <Badge label="חדש" variant="success" />
              </td>
            </tr>
          ))}
          {!hasHistorical && expenses.length === 0 ? (
            <tr>
              <td colSpan={4} className="py-10 text-center text-muted">
                אין הוצאות
              </td>
            </tr>
          ) : null}
        </tbody>
      </table>
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

  async function submit() {
    setError(null)
    setIsSubmitting(true)
    try {
      const payload: any = {
        supplier_name: supplierName,
        amount_ils_gross: Number(amount),
        service_description: serviceDescription,
        demand_received_date: demandReceivedDate,
        expense_date: expenseDate,
        category,
        attachment_url: attachmentUrl || null,
      }
      if (payer) payload.payer = payer
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
          <Field label="משלם (אופציונלי)">
            <select className="input" value={payer} onChange={(e) => setPayer(e.target.value as any)}>
              <option value="">אוטומטי לפי יתרת השתתפות עצמית</option>
              <option value="CLIENT_DEDUCTIBLE">השתתפות עצמית</option>
              <option value="INSURER">המבטח</option>
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
  retainerAnchorDate,
  retainerSnapshotIlsGross,
  onOpenAddPayment,
  retainerReloadKey,
}: {
  caseId: number
  retainerAnchorDate: string
  retainerSnapshotIlsGross: string | number | null
  onOpenAddPayment: () => void
  retainerReloadKey: number
}) {
  const [summary, setSummary] = useState<RetainerSummary | null>(null)
  const [accruals, setAccruals] = useState<RetainerAccrual[]>([])
  const [payments, setPayments] = useState<RetainerPayment[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const hasHistoricalSnapshot =
    retainerSnapshotIlsGross != null && Number(retainerSnapshotIlsGross) > 0

  async function load() {
    setError(null)
    setIsLoading(true)
    try {
      const [s, a, p] = await Promise.all([
        apiFetch<RetainerSummary>(`/cases/${caseId}/retainer/summary`),
        apiFetch<RetainerAccrual[]>(`/cases/${caseId}/retainer/accruals`),
        apiFetch<RetainerPayment[]>(`/cases/${caseId}/retainer/payments`),
      ])
      setSummary(s)
      setAccruals(a)
      setPayments(p)
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

  const retainerStartMonth = retainerAnchorDate ? String(retainerAnchorDate).slice(0, 7) : null

  return (
    <div className="space-y-6">
      {hasHistoricalSnapshot ? (
        <div className="card-soft p-5">
          <div className="text-right mb-4">
            <div className="font-semibold">ריטיינר עבר (ייבוא)</div>
            <div className="text-sm text-muted mt-1">סכום היסטורי — לקריאה בלבד, אינו משפיע על אקרואלים או תשלומים</div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-muted">
                <tr className="border-b border-border/60">
                  <th className="text-right py-3">תאריך</th>
                  <th className="text-right py-3">תיאור</th>
                  <th className="text-right py-3">סכום</th>
                  <th className="text-right py-3">מקור</th>
                </tr>
              </thead>
              <tbody>
                <tr className="border-b border-border/30 bg-muted/20">
                  <td className="py-3">—</td>
                  <td className="py-3">ריטיינר עבר (ייבוא)</td>
                  <td className="py-3">{formatILS(retainerSnapshotIlsGross)}</td>
                  <td className="py-3">
                    <Badge label="עבר" variant="info" />
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      ) : null}

      {hasHistoricalSnapshot ? (
        <h3 className="text-sm font-semibold text-muted">ריטיינר עתידי — אקרואלים ותשלומים</h3>
      ) : null}

      {summary ? (
        <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
          <MiniStat title="נצבר" value={formatILS(summary.retainer_accrued_total_ils_gross)} />
          <MiniStat title="שולם" value={formatILS(summary.retainer_paid_total_ils_gross)} />
          <MiniStat title="כוסה לשכ״ט" value={formatILS(summary.retainer_applied_to_fees_total_ils_gross)} />
          <MiniStat title="יתרת קרדיט" value={formatILS(summary.retainer_credit_balance_ils_gross)} />
          <MiniStat title="שכ״ט לתשלום" value={formatILS(summary.fees_due_total_ils_gross)} />
        </div>
      ) : null}

      <div className="card-soft p-5">
        <div className="flex items-center justify-between gap-3">
          <div className="text-right">
            <div className="font-semibold">אקרואלים</div>
            <div className="text-sm text-muted mt-1">נטו 60 (תאריך חשבונית = 1 בחודש האקרואל)</div>
          </div>
        </div>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-muted">
              <tr className="border-b border-border/60">
                <th className="text-right py-3">חודש</th>
                <th className="text-right py-3">תאריך חשבונית</th>
                <th className="text-right py-3">תאריך יעד</th>
                <th className="text-right py-3">סכום</th>
                <th className="text-right py-3">סטטוס</th>
              </tr>
            </thead>
            <tbody>
              {accruals.map((a) => {
                const overdue = isOverdue(formatDateYMD(a.due_date), a.is_paid)
                return (
                  <tr key={a.id} className={`border-b border-border/30 ${overdue ? 'bg-red-500/10' : 'hover:bg-surface/30'}`}>
                    <td className="py-3">{formatDateYMD(a.accrual_month).slice(0, 7)}</td>
                    <td className="py-3">{formatDateYMD(a.invoice_date)}</td>
                    <td className="py-3">{formatDateYMD(a.due_date)}</td>
                    <td className="py-3">{formatILS(a.amount_ils_gross)}</td>
                    <td className="py-3">
                      {a.is_paid ? <Badge label="שולם" variant="success" /> : overdue ? <Badge label="באיחור" variant="danger" /> : <Badge label="טרם שולם" variant="warning" />}
                    </td>
                  </tr>
                )
              })}
              {accruals.length === 0 ? (
                <tr>
                  <td colSpan={5} className="py-8 text-center text-muted">
                    אין אקרואלים{retainerStartMonth ? ` — הצטברות מתחילה בחודש ${retainerStartMonth}` : ''}
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card-soft p-5">
        <div className="flex items-center justify-between gap-3">
          <div className="text-right">
            <div className="font-semibold">תשלומים</div>
            <div className="text-sm text-muted mt-1">תשלומים מגדילים קרדיט (cash basis)</div>
          </div>
          <button
            onClick={onOpenAddPayment}
            className="btn btn-primary"
          >
            הוספת תשלום ריטיינר
          </button>
        </div>

        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-muted">
              <tr className="border-b border-border/60">
                <th className="text-right py-3">תאריך תשלום</th>
                <th className="text-right py-3">סכום</th>
              </tr>
            </thead>
            <tbody>
              {payments.map((p) => (
                <tr key={p.id} className="border-b border-border/30 hover:bg-surface/30">
                  <td className="py-3">{formatDateYMD(p.payment_date)}</td>
                  <td className="py-3">{formatILS(p.amount_ils_gross)}</td>
                </tr>
              ))}
              {payments.length === 0 ? (
                <tr>
                  <td colSpan={2} className="py-8 text-center text-muted">
                    אין תשלומים
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
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const isDirty = paymentDate !== today || amount.trim() !== '945.00'
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
        body: JSON.stringify({ payment_date: paymentDate, amount_ils_gross: toNumber(amount) }),
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

type HistoricalFeeStage = { event_date: string; event_type: string; amount_ils_gross: string | number }

function FeesPanel({
  caseId,
  onOpenAddFeeStage,
  feesReloadKey,
}: {
  caseId: number
  onOpenAddFeeStage: () => void
  feesReloadKey: number
}) {
  const [items, setItems] = useState<FeeEvent[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const historicalFeeStages: HistoricalFeeStage[] = []

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
                {historicalFeeStages.map((h, i) => (
                  <tr key={`hist-${i}`} className="border-b border-border/30 bg-muted/20">
                    <td className="py-3">{h.event_date}</td>
                    <td className="py-3">{FEE_EVENT_LABEL[h.event_type] ?? h.event_type}</td>
                    <td className="py-3">{formatILS(h.amount_ils_gross)}</td>
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
        <div className="flex items-center justify-between gap-3">
          <div className="text-right">
            <div className="font-semibold">אירועי שכ״ט</div>
            <div className="text-sm text-muted mt-1">המערכת מקצה קרדיט ריטיינר לפי סדר כרונולוגי</div>
          </div>
          <button
            onClick={onOpenAddFeeStage}
            className="btn btn-primary"
          >
            הוספת שלב שכ״ט
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
                  <td className="py-3">{FEE_EVENT_LABEL[e.event_type] || e.event_type}</td>
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

function AddFeeEventModal({ caseId, onClose, onSaved }: { caseId: number; onClose: () => void; onSaved: () => void }) {
  const today = new Date().toISOString().slice(0, 10)
  const [eventType, setEventType] = useState<FeeEventType>('COURT_STAGE_1_DEFENSE')
  const [eventDate, setEventDate] = useState(today)
  const [quantity, setQuantity] = useState(1)
  const [amountOverride, setAmountOverride] = useState('')
  const [showAdvanced, setShowAdvanced] = useState(false)

  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const needsQty = eventType === 'DEMAND_HOURLY' || eventType === 'ADDITIONAL_PROOF_HEARING'
  const needsOverride = eventType === 'SMALL_CLAIMS_MANUAL'

  const isDirty =
    eventType !== 'COURT_STAGE_1_DEFENSE' ||
    eventDate !== today ||
    quantity !== 1 ||
    amountOverride.trim() !== '' ||
    showAdvanced !== false

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
      const payload: any = {
        event_type: eventType,
        event_date: eventDate,
        quantity: needsQty ? quantity : 1,
      }
      if (needsOverride) payload.amount_override_ils_gross = toNumber(amountOverride)
      else if (showAdvanced && amountOverride.trim()) payload.amount_override_ils_gross = toNumber(amountOverride)
      await apiFetch(`/cases/${caseId}/fees/`, { method: 'POST', body: JSON.stringify(payload) })
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
      <div className="modal-panel max-w-[680px]">
        <div className="text-right">
          <div className="text-lg font-semibold">הוספת אירוע שכ״ט</div>
          <div className="text-sm text-muted mt-1">הסכומים בש״ח וכוללים מע״מ (ברוטו).</div>
        </div>

        <div className="mt-5 grid grid-cols-1 md:grid-cols-2 gap-4">
          <Field label="סוג אירוע">
            <select className="input" value={eventType} onChange={(e) => setEventType(e.target.value as FeeEventType)}>
              {Object.entries(FEE_EVENT_LABEL).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </select>
          </Field>
          <Field label="תאריך אירוע">
            <input className="input" type="date" value={eventDate} onChange={(e) => setEventDate(e.target.value)} />
          </Field>

          <Field label="כמות" className={needsQty ? '' : 'opacity-60'}>
            <input
              className="input"
              type="number"
              min={1}
              value={needsQty ? quantity : 1}
              disabled={!needsQty}
              onChange={(e) => setQuantity(Math.max(1, Number(e.target.value)))}
            />
          </Field>

          <Field label='סכום ידני (כולל מע״מ)' className={!needsOverride && !showAdvanced ? 'hidden' : ''}>
            <input
              className="input"
              value={amountOverride}
              onChange={(e) => setAmountOverride(e.target.value)}
              inputMode="decimal"
              placeholder={needsOverride ? 'נדרש עבור תביעות קטנות' : 'אופציונלי'}
            />
          </Field>
        </div>

        {!needsOverride ? (
          <div className="mt-4 text-right">
            <button
              type="button"
              onClick={() => setShowAdvanced((s) => !s)}
              className="text-sm text-primary hover:underline"
            >
              {showAdvanced ? 'הסתר אפשרויות מתקדמות' : 'אפשרויות מתקדמות (אופציונלי)'}
            </button>
          </div>
        ) : null}

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
            disabled={isSubmitting || (needsOverride && !amountOverride.trim())}
            className="btn btn-primary h-12 px-6 rounded-2xl"
          >
            שמירה
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



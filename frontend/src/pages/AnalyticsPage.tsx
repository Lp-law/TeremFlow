import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { BackButton } from '../components/BackButton'
import { Bar, BarChart, CartesianGrid, Legend, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { apiFetch } from '../lib/api'
import { formatILS, formatDateYMD, toNumber } from '../lib/format'
import type { AnalyticsOverviewResponse, CaseType } from '../lib/types'

const CASE_TYPE_LABEL: Record<string, string> = {
  COURT: 'תיק ביהמ"ש',
  DEMAND_LETTER: 'מכתב דרישה',
  SMALL_CLAIMS: 'תביעות קטנות',
}

function lastNDaysRange(n: number): { start: string; end: string } {
  const end = new Date()
  const start = new Date()
  start.setDate(end.getDate() - n)
  return { start: formatDateYMD(start), end: formatDateYMD(end) }
}

export function AnalyticsPage() {
  const initial = lastNDaysRange(90)
  const [startDate, setStartDate] = useState(initial.start)
  const [endDate, setEndDate] = useState(initial.end)
  const [caseType, setCaseType] = useState<'all' | CaseType>('all')
  const [payerStatus, setPayerStatus] = useState<'all' | 'client' | 'insurer' | 'closed'>('all')
  const [compareMode, setCompareMode] = useState<'month' | 'quarter' | 'year'>('month')

  const [data, setData] = useState<AnalyticsOverviewResponse | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function run() {
    setError(null)
    setIsLoading(true)
    try {
      const qs = new URLSearchParams()
      qs.set('start_date', startDate)
      qs.set('end_date', endDate)
      if (caseType !== 'all') qs.set('case_type', caseType)
      qs.set('payer_status', payerStatus)

      const res = await apiFetch<AnalyticsOverviewResponse>(`/analytics/overview?${qs.toString()}`)
      setData(res)
    } catch (e: any) {
      setError(e?.message || 'שגיאה')
    } finally {
      setIsLoading(false)
    }
  }

  const timeSeries = useMemo(() => {
    if (!data) return []
    const arr = compareMode === 'month' ? data.monthly : compareMode === 'quarter' ? data.quarterly : data.yearly
    return arr.map((p) => ({ period: p.period, total: toNumber(p.total_expenses_ils_gross) }))
  }, [data, compareMode])

  const splitChart = useMemo(() => {
    const attorney = toNumber((data?.expense_split as any)?.attorney ?? 0)
    const other = toNumber((data?.expense_split as any)?.other ?? 0)
    const total = Math.max(0, attorney + other)
    return [
      { name: 'שכ״ט עו״ד', value: attorney, pct: total > 0 ? (attorney / total) * 100 : 0 },
      { name: 'הוצאות אחרות', value: other, pct: total > 0 ? (other / total) * 100 : 0 },
    ]
  }, [data])

  const topCasesSplit = useMemo(() => {
    const rows = (data?.expenses_by_case || []).slice()
    rows.sort((a, b) => toNumber(b.total_expenses_ils_gross) - toNumber(a.total_expenses_ils_gross))
    return rows.slice(0, 10).map((r) => ({
      case_reference: r.case_reference,
      attorney: toNumber(r.attorney_fees_expenses_ils_gross),
      other: toNumber(r.other_expenses_ils_gross),
      total: toNumber(r.total_expenses_ils_gross),
    }))
  }, [data])

  const stageChart = useMemo(() => {
    const arr = data?.court_cases_end_stage_distribution || []
    return arr.map((x) => ({ stage: `שלב ${x.stage}`, count: x.count }))
  }, [data])

  return (
    <div className="min-h-screen w-full px-6 py-10">
      <div className="mx-auto w-full max-w-6xl">
        <div className="flex items-center justify-between gap-4">
          <div className="text-right">
            <div className="text-2xl font-bold">אנליטיקה</div>
            <div className="text-sm text-muted mt-1">פילוחים, טבלאות והשוואות זמן</div>
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
          <div className="grid grid-cols-1 md:grid-cols-6 gap-4">
            <div className="space-y-2 text-right">
              <div className="text-sm font-medium text-muted">מתאריך</div>
              <input className="input h-12" type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
            </div>
            <div className="space-y-2 text-right">
              <div className="text-sm font-medium text-muted">עד תאריך</div>
              <input className="input h-12" type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
            </div>
            <div className="space-y-2 text-right">
              <div className="text-sm font-medium text-muted">סוג תיק</div>
              <select className="input h-12" value={caseType} onChange={(e) => setCaseType(e.target.value as any)}>
                <option value="all">הכל</option>
                <option value="COURT">{CASE_TYPE_LABEL.COURT}</option>
                <option value="DEMAND_LETTER">{CASE_TYPE_LABEL.DEMAND_LETTER}</option>
                <option value="SMALL_CLAIMS">{CASE_TYPE_LABEL.SMALL_CLAIMS}</option>
              </select>
            </div>
            <div className="space-y-2 text-right">
              <div className="text-sm font-medium text-muted">מצב משלם</div>
              <select className="input h-12" value={payerStatus} onChange={(e) => setPayerStatus(e.target.value as any)}>
                <option value="all">הכל</option>
                <option value="client">השתתפות עצמית</option>
                <option value="insurer">המבטח</option>
                <option value="closed">סגור</option>
              </select>
            </div>
            <div className="space-y-2 text-right">
              <div className="text-sm font-medium text-muted">השוואה לפי</div>
              <select className="input h-12" value={compareMode} onChange={(e) => setCompareMode(e.target.value as any)}>
                <option value="month">חודשים</option>
                <option value="quarter">רבעונים</option>
                <option value="year">שנים</option>
              </select>
            </div>
            <div className="flex items-end">
              <button
                onClick={run}
                disabled={isLoading}
                className="btn btn-primary w-full h-12 rounded-2xl"
              >
                הפעל
              </button>
            </div>
          </div>

          {error ? <div className="mt-4 text-sm text-red-300 text-right">{error}</div> : null}
          {isLoading ? <div className="mt-4 text-sm text-muted text-right">טוען...</div> : null}
        </div>

        {data ? (
          <div className="mt-6 space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-6 gap-3">
              <Kpi title="סה״כ הוצאות" value={formatILS(data.total_expenses_ils_gross)} />
              <Kpi title="על השתתפות עצמית" value={formatILS(data.total_on_deductible_ils_gross)} />
              <Kpi title="על המבטח" value={formatILS(data.total_on_insurer_ils_gross)} />
              <Kpi title="ממוצע לתיק" value={formatILS(data.average_expenses_per_case_ils_gross)} />
              <Kpi title="תיקים שהתחלפו" value={String(data.cases_switched_to_insurer_count)} />
              <Kpi title="יתרת השתתפות (פתוחים)" value={formatILS(data.aggregate_remaining_deductible_open_cases_ils_gross)} />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
              <ChartCard title={compareMode === 'month' ? 'מגמת הוצאות חודשית' : compareMode === 'quarter' ? 'מגמת הוצאות רבעונית' : 'מגמת הוצאות שנתית'}>
                <div className="h-[260px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={timeSeries}>
                      <CartesianGrid stroke="rgb(var(--border) / 0.30)" />
                      <XAxis dataKey="period" stroke="rgb(var(--muted) / 0.9)" />
                      <YAxis stroke="rgb(var(--muted) / 0.9)" />
                      <Tooltip formatter={(v: any) => formatILS(v)} labelFormatter={(l: any) => `תקופה: ${l}`} />
                      <Bar dataKey="total" fill="rgb(var(--primary) / 0.90)" radius={[10, 10, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </ChartCard>

              <ChartCard title="פילוח הוצאות: שכ״ט עו״ד מול אחרות">
                <div className="h-[260px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Tooltip
                        formatter={(v: any, _name: any, props: any) => {
                          const pct = props?.payload?.pct ?? 0
                          return `${formatILS(v)} (${Number(pct).toFixed(1)}%)`
                        }}
                      />
                      <Legend />
                      <Pie data={splitChart} dataKey="value" nameKey="name" outerRadius={92} stroke="rgb(var(--bg) / 0.35)" />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              </ChartCard>

              <ChartCard title="טופ תיקים — פילוח שכ״ט מול אחרות">
                <div className="h-[260px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={topCasesSplit} layout="vertical" margin={{ left: 24 }}>
                      <CartesianGrid stroke="rgb(var(--border) / 0.30)" />
                      <XAxis type="number" stroke="rgb(var(--muted) / 0.9)" />
                      <YAxis type="category" dataKey="case_reference" stroke="rgb(var(--muted) / 0.9)" width={88} />
                      <Tooltip
                        formatter={(v: any, name: any, props: any) => {
                          const total = props?.payload?.total ?? 0
                          const pct = total > 0 ? (Number(v) / total) * 100 : 0
                          const label = name === 'attorney' ? 'שכ״ט עו״ד' : 'הוצאות אחרות'
                          return `${label}: ${formatILS(v)} (${pct.toFixed(1)}%)`
                        }}
                        labelFormatter={(l: any) => `תיק: ${l}`}
                      />
                      <Legend formatter={(v: any) => (v === 'attorney' ? 'שכ״ט עו״ד' : 'הוצאות אחרות')} />
                      <Bar dataKey="attorney" stackId="a" fill="rgb(var(--primary) / 0.92)" radius={[8, 0, 0, 8]} />
                      <Bar dataKey="other" stackId="a" fill="rgb(var(--surface) / 0.85)" radius={[0, 8, 8, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </ChartCard>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
              <ChartCard title='תיקי ביהמ"ש — הסתיימו באיזה שלב'>
                <div className="h-[260px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={stageChart}>
                      <CartesianGrid stroke="rgb(var(--border) / 0.30)" />
                      <XAxis dataKey="stage" stroke="rgb(var(--muted) / 0.9)" />
                      <YAxis stroke="rgb(var(--muted) / 0.9)" allowDecimals={false} />
                      <Tooltip labelFormatter={(l: any) => `שלב: ${l}`} />
                      <Bar dataKey="count" fill="rgb(var(--primary) / 0.90)" radius={[10, 10, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </ChartCard>

              <div className="lg:col-span-2 card p-6">
              <div className="text-right">
                <div className="text-lg font-semibold">הוצאות לפי תיק</div>
                <div className="text-sm text-muted mt-1">סכומים (₪) + אחוז שכ״ט מתוך סה״כ הוצאות לתיק</div>
              </div>

              <div className="mt-4 overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="text-muted">
                    <tr className="border-b border-border/60">
                      <th className="text-right py-3">תיק</th>
                      <th className="text-right py-3">סוג</th>
                      <th className="text-right py-3">סטטוס</th>
                      <th className="text-right py-3">מצב משלם</th>
                      <th className="text-right py-3">סה״כ</th>
                      <th className="text-right py-3">שכ״ט</th>
                      <th className="text-right py-3">אחרות</th>
                      <th className="text-right py-3">% שכ״ט</th>
                      <th className="text-right py-3">יתרת השתתפות</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.expenses_by_case.map((r) => {
                      const total = toNumber(r.total_expenses_ils_gross)
                      const pctAttorney = total > 0 ? (toNumber(r.attorney_fees_expenses_ils_gross) / total) * 100 : 0
                      return (
                        <tr key={r.case_id} className="border-b border-border/30 hover:bg-surface/30">
                          <td className="py-3">
                            <Link to={`/cases/${r.case_id}`} className="text-primary hover:underline">
                              {r.case_reference}
                            </Link>
                            <div className="text-xs text-muted">#{r.case_id}</div>
                          </td>
                          <td className="py-3">{CASE_TYPE_LABEL[r.case_type] || r.case_type}</td>
                          <td className="py-3">{r.status === 'OPEN' ? 'פתוח' : 'סגור'}</td>
                          <td className="py-3">{r.payer_status === 'insurer' ? 'המבטח' : r.payer_status === 'client' ? 'השתתפות עצמית' : 'סגור'}</td>
                          <td className="py-3">{formatILS(r.total_expenses_ils_gross)}</td>
                          <td className="py-3">{formatILS(r.attorney_fees_expenses_ils_gross)}</td>
                          <td className="py-3">{formatILS(r.other_expenses_ils_gross)}</td>
                          <td className="py-3">{pctAttorney.toFixed(1)}%</td>
                          <td className="py-3">{formatILS(r.deductible_remaining_ils_gross)}</td>
                        </tr>
                      )
                    })}
                    {data.expenses_by_case.length === 0 ? (
                      <tr>
                        <td colSpan={9} className="py-10 text-center text-muted">
                          אין נתונים
                        </td>
                      </tr>
                    ) : null}
                  </tbody>
                </table>
              </div>
            </div>
            </div>
          </div>
        ) : (
          <div className="mt-6 card p-6 text-right text-sm text-muted">
            בחרו טווח תאריכים והפעילו כדי להציג KPI, גרפים וטבלת תיקים.
          </div>
        )}
      </div>
    </div>
  )
}

function Kpi({ title, value }: { title: string; value: string }) {
  return (
    <div className="rounded-2xl border border-border/60 bg-card/40 p-4 text-right">
      <div className="text-xs text-muted">{title}</div>
      <div className="mt-1 text-lg font-bold">{value}</div>
    </div>
  )
}

function ChartCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="card p-6">
      <div className="text-right">
        <div className="text-lg font-semibold">{title}</div>
      </div>
      <div className="mt-4">{children}</div>
    </div>
  )
}



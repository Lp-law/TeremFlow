import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { BackButton } from '../components/BackButton'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { apiDownload, apiFetch } from '../lib/api'
import { formatILS, formatDateYMD } from '../lib/format'
import type { AnalyticsV2Response } from '../lib/types'

const CASE_TYPE_LABEL: Record<string, string> = {
  COURT: 'תיק ביהמ"ש',
  DEMAND_LETTER: 'מכתב דרישה',
  SMALL_CLAIMS: 'תביעות קטנות',
}

const STATUS_LABEL: Record<string, string> = {
  OPEN: 'פתוח',
  CLOSED: 'סגור',
  ALL: 'הכל',
}

function lastNDaysRange(n: number): { start: string; end: string } {
  const end = new Date()
  const start = new Date()
  start.setDate(end.getDate() - n)
  return { start: formatDateYMD(start), end: formatDateYMD(end) }
}

const REPORT_TEMPLATES: { id: string; label: string }[] = [
  { id: 'T1', label: 'דו"ח סיכום פעילות' },
  { id: 'T2', label: 'דו"ח סניפים' },
  { id: 'T3', label: 'דו"ח סוגי תיקים' },
]

export function AnalyticsPage() {
  const initial = lastNDaysRange(365)
  const [startDate, setStartDate] = useState(initial.start)
  const [endDate, setEndDate] = useState(initial.end)
  const [caseType, setCaseType] = useState<string>('ALL')
  const [status, setStatus] = useState<string>('ALL')
  const [branchName, setBranchName] = useState<string>('ALL')

  const [branches, setBranches] = useState<(string | null)[]>([])
  const [data, setData] = useState<AnalyticsV2Response | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [splitByCaseType, setSplitByCaseType] = useState(false)
  const [reportModalOpen, setReportModalOpen] = useState(false)
  const [reportLoading, setReportLoading] = useState(false)
  const [reportToast, setReportToast] = useState<string | null>(null)
  const reportDefaultRange = lastNDaysRange(90)
  const [reportStart, setReportStart] = useState(reportDefaultRange.start)
  const [reportEnd, setReportEnd] = useState(reportDefaultRange.end)
  const [reportTemplate, setReportTemplate] = useState('T1')
  const [reportCaseType, setReportCaseType] = useState<string>('')
  const [reportStatus, setReportStatus] = useState<string>('')
  const [reportBranch, setReportBranch] = useState<string>('')
  const [reportBranchNull, setReportBranchNull] = useState(false)
  const [reportFormat, setReportFormat] = useState<'pdf' | 'docx'>('pdf')

  useEffect(() => {
    apiFetch<(string | null)[]>('/analytics/v2/branches').then(setBranches).catch(() => setBranches([]))
  }, [])

  async function run() {
    setError(null)
    setIsLoading(true)
    try {
      const qs = new URLSearchParams()
      qs.set('start_date', startDate)
      qs.set('end_date', endDate)
      if (caseType !== 'ALL') qs.set('case_type', caseType)
      if (status !== 'ALL') qs.set('status', status)
      if (branchName !== 'ALL') qs.set('branch_name', branchName)

      const res = await apiFetch<AnalyticsV2Response>(`/analytics/v2?${qs.toString()}`)
      setData(res)
    } catch (e: any) {
      setError(e?.message || 'שגיאה')
    } finally {
      setIsLoading(false)
    }
  }

  const closingStageChartData = data?.distributions.closing_stage?.map((r) => ({
    name: r.label,
    count: r.count,
    pct: r.pct,
  })) ?? []

  async function exportClientReport() {
    setReportLoading(true)
    setReportToast(null)
    try {
      const branch_name = reportBranchNull ? null : (reportBranch || null)
      const body = {
        template_id: reportTemplate,
        format: reportFormat,
        filters: {
          start_date: reportStart,
          end_date: reportEnd,
          case_type: reportCaseType || null,
          status: reportStatus || null,
          branch_name: branch_name,
          branch_is_null: reportBranchNull || null,
        },
      }
      const { blob, filename } = await apiDownload('/analytics/client-report', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename || `client_report_${reportTemplate}_${reportFormat}.${reportFormat}`
      a.click()
      URL.revokeObjectURL(url)
      setReportToast('הדו״ח הורד בהצלחה')
      setTimeout(() => setReportToast(null), 4000)
      setReportModalOpen(false)
    } catch (e: any) {
      setReportToast(e?.message || 'שגיאה בייצוא הדו״ח')
    } finally {
      setReportLoading(false)
    }
  }

  return (
    <div className="min-h-screen w-full px-6 py-10">
      <div className="mx-auto w-full max-w-6xl">
        <div className="flex items-center justify-between gap-4">
          <div className="text-right">
            <div className="text-2xl font-bold">אנליטיקה</div>
            <div className="text-sm text-muted mt-1">פילטרים לפי תיק (תאריך פתיחה), מודל מאוחד</div>
          </div>
          <div className="flex gap-2 items-center">
            <button
              type="button"
              onClick={() => setReportModalOpen(true)}
              className="btn btn-secondary"
            >
              ייצא דו״ח ללקוח
            </button>
            <Link to="/notifications" className="btn btn-secondary">
              התראות
            </Link>
            <BackButton />
          </div>
        </div>

        {reportToast ? (
          <div className="mt-3 py-2 px-4 rounded-lg bg-surface/80 text-right text-sm">
            {reportToast}
          </div>
        ) : null}

        {reportModalOpen ? (
          <div className="modal">
            <div className="modal-overlay" onClick={() => !reportLoading && setReportModalOpen(false)} />
            <div className="modal-panel max-w-md">
              <div className="text-right">
                <div className="text-lg font-semibold">ייצוא דו״ח ללקוח</div>
                <div className="text-sm text-muted mt-1">בחר תבנית, טווח תאריכים ומבנה קובץ</div>
              </div>
              <div className="mt-4 space-y-4">
                <div>
                  <label className="block text-sm text-muted mb-1 text-right">תבנית</label>
                  <select className="input w-full" value={reportTemplate} onChange={(e) => setReportTemplate(e.target.value)}>
                    {REPORT_TEMPLATES.map((t) => (
                      <option key={t.id} value={t.id}>{t.label}</option>
                    ))}
                  </select>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-sm text-muted mb-1 text-right">מתאריך</label>
                    <input className="input w-full" type="date" value={reportStart} onChange={(e) => setReportStart(e.target.value)} />
                  </div>
                  <div>
                    <label className="block text-sm text-muted mb-1 text-right">עד תאריך</label>
                    <input className="input w-full" type="date" value={reportEnd} onChange={(e) => setReportEnd(e.target.value)} />
                  </div>
                </div>
                <div>
                  <label className="block text-sm text-muted mb-1 text-right">סוג תיק</label>
                  <select className="input w-full" value={reportCaseType} onChange={(e) => setReportCaseType(e.target.value)}>
                    <option value="">הכל</option>
                    <option value="COURT">{CASE_TYPE_LABEL.COURT}</option>
                    <option value="DEMAND_LETTER">{CASE_TYPE_LABEL.DEMAND_LETTER}</option>
                    <option value="SMALL_CLAIMS">{CASE_TYPE_LABEL.SMALL_CLAIMS}</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm text-muted mb-1 text-right">סטטוס</label>
                  <select className="input w-full" value={reportStatus} onChange={(e) => setReportStatus(e.target.value)}>
                    <option value="">הכל</option>
                    <option value="OPEN">{STATUS_LABEL.OPEN}</option>
                    <option value="CLOSED">{STATUS_LABEL.CLOSED}</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm text-muted mb-1 text-right">סניף</label>
                  <select className="input w-full" value={reportBranch} onChange={(e) => setReportBranch(e.target.value)} disabled={reportBranchNull}>
                    <option value="">הכל</option>
                    {branches.map((b) => (
                      <option key={b === null ? '__NULL__' : b!} value={b === null ? '' : b!}>
                        {b === null ? 'ללא סניף' : b}
                      </option>
                    ))}
                  </select>
                  <label className="flex items-center gap-2 mt-1 justify-end text-sm">
                    <input type="checkbox" checked={reportBranchNull} onChange={(e) => setReportBranchNull(e.target.checked)} />
                    רק ללא סניף
                  </label>
                </div>
                <div>
                  <label className="block text-sm text-muted mb-1 text-right">פורמט</label>
                  <select className="input w-full" value={reportFormat} onChange={(e) => setReportFormat(e.target.value as 'pdf' | 'docx')}>
                    <option value="pdf">PDF</option>
                    <option value="docx">Word (DOCX)</option>
                  </select>
                </div>
              </div>
              <div className="mt-6 flex gap-2 justify-end">
                <button type="button" className="btn btn-secondary" onClick={() => setReportModalOpen(false)} disabled={reportLoading}>
                  ביטול
                </button>
                <button type="button" className="btn btn-primary" onClick={exportClientReport} disabled={reportLoading}>
                  {reportLoading ? 'מכין דו״ח…' : 'ייצא והורד'}
                </button>
              </div>
            </div>
          </div>
        ) : null}

        <div className="mt-6 card p-6">
          <div className="grid grid-cols-1 md:grid-cols-6 gap-4">
            <div className="space-y-2 text-right">
              <div className="text-sm font-medium text-muted">תאריך פתיחה (מתאריך)</div>
              <input className="input h-12" type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
            </div>
            <div className="space-y-2 text-right">
              <div className="text-sm font-medium text-muted">תאריך פתיחה (עד)</div>
              <input className="input h-12" type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
            </div>
            <div className="space-y-2 text-right">
              <div className="text-sm font-medium text-muted">סוג תיק</div>
              <select className="input h-12" value={caseType} onChange={(e) => setCaseType(e.target.value)}>
                <option value="ALL">הכל</option>
                <option value="COURT">{CASE_TYPE_LABEL.COURT}</option>
                <option value="DEMAND_LETTER">{CASE_TYPE_LABEL.DEMAND_LETTER}</option>
                <option value="SMALL_CLAIMS">{CASE_TYPE_LABEL.SMALL_CLAIMS}</option>
              </select>
            </div>
            <div className="space-y-2 text-right">
              <div className="text-sm font-medium text-muted">סטטוס</div>
              <select className="input h-12" value={status} onChange={(e) => setStatus(e.target.value)}>
                <option value="ALL">{STATUS_LABEL.ALL}</option>
                <option value="OPEN">{STATUS_LABEL.OPEN}</option>
                <option value="CLOSED">{STATUS_LABEL.CLOSED}</option>
              </select>
            </div>
            <div className="space-y-2 text-right">
              <div className="text-sm font-medium text-muted">סניף</div>
              <select className="input h-12" value={branchName} onChange={(e) => setBranchName(e.target.value)}>
                <option value="ALL">הכל</option>
                {branches.map((b) => (
                  <option key={b === null ? '__NULL__' : b!} value={b === null ? '__NULL__' : b!}>
                    {b === null ? 'ללא סניף' : b}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex items-end">
              <button onClick={run} disabled={isLoading} className="btn btn-primary w-full h-12 rounded-2xl">
                הפעל
              </button>
            </div>
          </div>

          {error ? <div className="mt-4 text-sm text-red-300 text-right">{error}</div> : null}
          {isLoading ? <div className="mt-4 text-sm text-muted text-right">טוען...</div> : null}
        </div>

        {data ? (
          <div className="mt-6 space-y-6">
            <div className="text-sm text-muted text-right">
              תיקים בפילטר: {data.filters.denominator_cases} (תאריך פתיחה {data.filters.start_date} – {data.filters.end_date})
            </div>

            <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
              <Kpi title="שכ״ט ממוצע לפי שלבים" value={formatILS(data.kpis.avg_stage_fee_ils)} />
              <Kpi title="שכ״ט ממוצע לפי ריטיינר (תיאורטי)" value={formatILS(data.kpis.avg_retainer_fee_ils)} />
              <Kpi title="הוצאות ממוצעות לתיק" value={formatILS(data.kpis.avg_expenses_ils)} />
              {data.extra_metrics && data.extra_metrics.closing_stage_index_denominator_cases > 0 ? (
                <div className="rounded-2xl border border-border/60 bg-card/40 p-4 text-right">
                  <div className="text-xs text-muted">שלב סיום ממוצע (תיקי ביהמ״ש)</div>
                  <div className="mt-1 text-lg font-bold">{data.extra_metrics.avg_closing_stage_index.toFixed(2)}</div>
                  <div className="text-xs text-muted mt-0.5">
                    מבוסס על {data.extra_metrics.closing_stage_index_denominator_cases} תיקים שנסגרו בשלבים 1–5
                  </div>
                </div>
              ) : null}
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <ChartCard title="התפלגות שלב סיום (תיקים סגורים)">
                <div className="h-[280px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={closingStageChartData} layout="vertical" margin={{ left: 8, right: 24 }}>
                      <CartesianGrid stroke="rgb(var(--border) / 0.30)" />
                      <XAxis type="number" stroke="rgb(var(--muted) / 0.9)" allowDecimals={false} />
                      <YAxis type="category" dataKey="name" stroke="rgb(var(--muted) / 0.9)" width={140} tick={{ fontSize: 12 }} />
                      <Tooltip
                        formatter={(v: number | undefined) => [v ?? 0, 'תיקים']}
                        labelFormatter={(l) => `שלב: ${l}`}
                        content={({ active, payload }) =>
                          active && payload?.[0] ? (
                            <div className="bg-card border border-border rounded-lg p-2 shadow">
                              <div className="text-right">{payload[0].payload?.name}</div>
                              <div className="text-right text-muted">
                                {payload[0].value} תיקים ({Number((payload[0].payload?.pct ?? 0).toFixed(1))}%)
                              </div>
                            </div>
                          ) : null
                        }
                      />
                      <Bar dataKey="count" fill="rgb(var(--primary) / 0.90)" radius={[0, 4, 4, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </ChartCard>

              <div className="card p-6">
                <div className="text-right">
                  <div className="text-lg font-semibold">נפח לפי סניף וסוג תיק</div>
                  <div className="text-sm text-muted mt-1">מספר תיקים בפילטר</div>
                </div>
                <div className="mt-4 overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="text-muted">
                      <tr className="border-b border-border/60">
                        <th className="text-right py-3">סניף</th>
                        <th className="text-right py-3">סוג תיק</th>
                        <th className="text-right py-3">כמות</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.distributions.branch_case_type.map((r, i) => (
                        <tr key={i} className="border-b border-border/30 hover:bg-surface/30">
                          <td className="py-3">{r.branch_name ?? 'ללא סניף'}</td>
                          <td className="py-3">{CASE_TYPE_LABEL[r.case_type] ?? r.case_type}</td>
                          <td className="py-3">{r.count}</td>
                        </tr>
                      ))}
                      {data.distributions.branch_case_type.length === 0 ? (
                        <tr>
                          <td colSpan={3} className="py-8 text-center text-muted">
                            אין נתונים
                          </td>
                        </tr>
                      ) : null}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>

            {(data.branch_fee_averages?.length ?? 0) > 0 ? (
              <div className="card p-6">
                <div className="flex items-center justify-between gap-4 flex-wrap">
                  <div className="text-right">
                    <div className="text-lg font-semibold">שכ״ט ממוצע לפי סניף</div>
                    <div className="text-sm text-muted mt-1">פילוח לפי שלבים וריטיינר (תיאורטי)</div>
                  </div>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={splitByCaseType}
                      onChange={(e) => setSplitByCaseType(e.target.checked)}
                      className="rounded"
                    />
                    <span className="text-sm">לפצל לפי סוג תיק</span>
                  </label>
                </div>
                <div className="mt-4 overflow-x-auto">
                  {splitByCaseType && (data.branch_case_type_fee_averages?.length ?? 0) > 0 ? (
                    <table className="w-full text-sm">
                      <thead className="text-muted">
                        <tr className="border-b border-border/60">
                          <th className="text-right py-3">סניף</th>
                          <th className="text-right py-3">סוג תיק</th>
                          <th className="text-right py-3">מספר תיקים</th>
                          <th className="text-right py-3">שכ״ט ממוצע לפי שלבים</th>
                          <th className="text-right py-3">שכ״ט ממוצע ריטיינר</th>
                          <th className="text-right py-3">הוצאות ממוצעות</th>
                        </tr>
                      </thead>
                      <tbody>
                        {data.branch_case_type_fee_averages!.map((r, i) => (
                          <tr key={i} className="border-b border-border/30 hover:bg-surface/30">
                            <td className="py-3">{r.branch_name}</td>
                            <td className="py-3">{CASE_TYPE_LABEL[r.case_type] ?? r.case_type}</td>
                            <td className="py-3">{r.cases_count}</td>
                            <td className="py-3">{formatILS(r.avg_stage_fee_ils)}</td>
                            <td className="py-3">{formatILS(r.avg_retainer_fee_ils)}</td>
                            <td className="py-3">{formatILS(r.avg_expenses_ils)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  ) : (
                    <table className="w-full text-sm">
                      <thead className="text-muted">
                        <tr className="border-b border-border/60">
                          <th className="text-right py-3">סניף</th>
                          <th className="text-right py-3">מספר תיקים</th>
                          <th className="text-right py-3">שכ״ט ממוצע לפי שלבים</th>
                          <th className="text-right py-3">שכ״ט ממוצע ריטיינר (תיאורטי)</th>
                          <th className="text-right py-3">הוצאות ממוצעות</th>
                        </tr>
                      </thead>
                      <tbody>
                        {data.branch_fee_averages!.map((r, i) => (
                          <tr key={i} className="border-b border-border/30 hover:bg-surface/30">
                            <td className="py-3">{r.branch_name}</td>
                            <td className="py-3">{r.cases_count}</td>
                            <td className="py-3">{formatILS(r.avg_stage_fee_ils)}</td>
                            <td className="py-3">{formatILS(r.avg_retainer_fee_ils)}</td>
                            <td className="py-3">{formatILS(r.avg_expenses_ils)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              </div>
            ) : null}

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="card p-6">
                <div className="text-right">
                  <div className="text-lg font-semibold">סה״כ לפי סניף</div>
                </div>
                <ul className="mt-3 space-y-1 text-sm">
                  {data.totals.by_branch.map((r, i) => (
                    <li key={i} className="flex justify-between">
                      <span>{r.branch_name ?? 'ללא סניף'}</span>
                      <span>{r.count}</span>
                    </li>
                  ))}
                  {data.totals.by_branch.length === 0 ? <li className="text-muted">אין נתונים</li> : null}
                </ul>
              </div>
              <div className="card p-6">
                <div className="text-right">
                  <div className="text-lg font-semibold">סה״כ לפי סוג תיק</div>
                </div>
                <ul className="mt-3 space-y-1 text-sm">
                  {data.totals.by_case_type.map((r, i) => (
                    <li key={i} className="flex justify-between">
                      <span>{CASE_TYPE_LABEL[r.case_type] ?? r.case_type}</span>
                      <span>{r.count}</span>
                    </li>
                  ))}
                  {data.totals.by_case_type.length === 0 ? <li className="text-muted">אין נתונים</li> : null}
                </ul>
              </div>
            </div>
          </div>
        ) : (
          <div className="mt-6 card p-6 text-right text-sm text-muted">
            בחרו טווח תאריכי פתיחה (לפי תיק) והפעילו כדי להציג KPIs והתפלגויות.
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

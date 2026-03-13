import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiDownload, apiFetch } from '../lib/api'
import { formatILS } from '../lib/format'

type ClientReportRow = {
  case_reference: string
  case_name: string
  excess_total_ils: string | number
  excess_remaining_ils: string | number
  expenses_total_ils: string | number
  fees_by_stages_ils: string | number
}

type ClientReportResponse = {
  cases: ClientReportRow[]
}

export function ClientReportPage() {
  const [data, setData] = useState<ClientReportRow[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [excelLoading, setExcelLoading] = useState(false)

  useEffect(() => {
    let cancelled = false
    setError(null)
    apiFetch<ClientReportResponse>('/reports/client-report')
      .then((res) => {
        if (!cancelled) setData(res.cases ?? [])
      })
      .catch((e: any) => {
        if (!cancelled) setError(e?.message || 'שגיאה בטעינה')
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false)
      })
    return () => { cancelled = true }
  }, [])

  async function downloadExcel() {
    setExcelLoading(true)
    setError(null)
    try {
      const { blob, filename } = await apiDownload('/reports/client-report/excel')
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename || 'client-report.xlsx'
      a.click()
      URL.revokeObjectURL(url)
    } catch (e: any) {
      setError(e?.message || 'שגיאה בהורדת האקסל')
    } finally {
      setExcelLoading(false)
    }
  }

  return (
    <div className="min-h-screen w-full px-6 py-10">
      <div className="mx-auto w-full max-w-5xl">
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div className="text-right">
            <h1 className="text-2xl font-bold">דיווח ללקוח</h1>
            <p className="text-sm text-muted mt-1">סקירת תיקים פתוחים — אקסס, הוצאות ושכר טרחה לפי שלבים</p>
          </div>
          <div className="flex gap-2">
            <Link to="/dashboard" className="btn btn-secondary">
              חזרה לדשבורד
            </Link>
            <button
              type="button"
              onClick={downloadExcel}
              disabled={excelLoading || data.length === 0}
              className="btn btn-primary"
            >
              {excelLoading ? 'מוריד…' : 'הורד אקסל'}
            </button>
          </div>
        </div>

        {error ? (
          <div className="mt-4 rounded-xl bg-red-500/20 border border-red-500/50 px-4 py-3 text-red-800 dark:text-red-200 text-right">
            {error}
          </div>
        ) : null}

        <div className="mt-6 card p-4 overflow-x-auto">
          {isLoading ? (
            <div className="text-right text-muted py-8">טוען...</div>
          ) : data.length === 0 ? (
            <div className="text-right text-muted py-8">אין תיקים פתוחים</div>
          ) : (
            <table className="w-full text-sm text-right">
              <thead>
                <tr className="border-b border-border/60 text-muted">
                  <th className="py-3 px-2">שם תיק</th>
                  <th className="py-3 px-2">אקסס מלא (ש״ח)</th>
                  <th className="py-3 px-2">יתרת אקסס (ש״ח)</th>
                  <th className="py-3 px-2">הוצאות (ש״ח)</th>
                  <th className="py-3 px-2">שכר טרחה לפי שלבים (ש״ח)</th>
                </tr>
              </thead>
              <tbody>
                {data.map((row, i) => (
                  <tr key={i} className="border-b border-border/30 last:border-0">
                    <td className="py-3 px-2 font-medium">
                      {(row.case_name || row.case_reference || '—').trim() || row.case_reference || '—'}
                    </td>
                    <td className="py-3 px-2">{formatILS(row.excess_total_ils)}</td>
                    <td className="py-3 px-2">{formatILS(row.excess_remaining_ils)}</td>
                    <td className="py-3 px-2">{formatILS(row.expenses_total_ils)}</td>
                    <td className="py-3 px-2">{formatILS(row.fees_by_stages_ils)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  )
}

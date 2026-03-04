import { useEffect, useState } from 'react'
import { BackButton } from '../components/BackButton'
import { API_BASE_URL, getCsrfHeadersForMutation } from '../lib/api'

type ImportMode = 'create' | 'update'

type PreviewResponse = {
  detected_headers: string[]
  operational_headers: string[]
  raw_headers: string[]
  sample_rows: Array<{
    case_reference: string | null
    operational_values: Record<string, unknown>
    raw_values: Record<string, unknown>
    case_found?: boolean
    will_update_fields?: string[]
  }>
  warnings: string[]
  sample_rows_not_found_count?: number
}

export function ImportPage() {
  const [step, setStep] = useState<1 | 2 | 3>(1)
  const [mode, setMode] = useState<ImportMode>('create')
  const [overwriteBlanks, setOverwriteBlanks] = useState(false)
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<PreviewResponse | null>(null)
  const [result, setResult] = useState<any>(null)
  const [error, setError] = useState<string | null>(null)
  const [isPreviewLoading, setIsPreviewLoading] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [wipeToken, setWipeToken] = useState('')
  const [wipeResult, setWipeResult] = useState<any>(null)
  const [isWiping, setIsWiping] = useState(false)
  const [dbStatus, setDbStatus] = useState<{ cases: number; clean: boolean } | null>(null)
  const [expandedRowIndex, setExpandedRowIndex] = useState<number | null>(null)

  useEffect(() => {
    checkDbStatus()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (step === 2 && file) {
      loadPreview()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step, file?.name, mode, overwriteBlanks])

  async function checkDbStatus() {
    try {
      const r = await fetch(`${API_BASE_URL}/admin/wipe-case-data-status`, { credentials: 'include' })
      if (r.ok) setDbStatus(await r.json())
    } catch {
      /* ignore */
    }
  }

  async function loadPreview() {
    if (!file) return
    setError(null)
    setPreview(null)
    setIsPreviewLoading(true)
    try {
      const form = new FormData()
      form.append('file', file)
      let url = `${API_BASE_URL}/import/excel-update/preview`
      if (mode === 'create') url = `${API_BASE_URL}/import/excel/preview`
      else if (overwriteBlanks) url += '?overwrite_blanks=true'
      const res = await fetch(url, {
        method: 'POST',
        body: form,
        credentials: 'include',
        headers: getCsrfHeadersForMutation(),
      })
      if (!res.ok) {
        const d = await res.json().catch(() => ({}))
        throw new Error(d?.detail || 'שגיאה בתצוגה מקדימה')
      }
      const data = await res.json()
      setPreview(data)
    } catch (e: any) {
      setError(e?.message || 'שגיאה')
    } finally {
      setIsPreviewLoading(false)
    }
  }

  async function runImport() {
    if (!file) return
    setError(null)
    setResult(null)
    setIsSubmitting(true)
    try {
      const form = new FormData()
      form.append('file', file)
      let url = mode === 'update' ? `${API_BASE_URL}/import/excel-update` : `${API_BASE_URL}/import/excel`
      if (mode === 'update' && overwriteBlanks) url += '?overwrite_blanks=true'
      const res = await fetch(url, {
        method: 'POST',
        body: form,
        credentials: 'include',
        headers: getCsrfHeadersForMutation(),
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data?.detail || 'שגיאה')
      }
      setResult(await res.json())
      setStep(3)
    } catch (e: any) {
      setError(e?.message || 'שגיאה')
    } finally {
      setIsSubmitting(false)
    }
  }

  async function wipeData() {
    if (!wipeToken.trim()) {
      setError('נא להזין קוד אימות')
      return
    }
    setError(null)
    setWipeResult(null)
    setIsWiping(true)
    try {
      const r = await fetch(`${API_BASE_URL}/admin/wipe-case-data`, {
        method: 'POST',
        credentials: 'include',
        headers: { ...getCsrfHeadersForMutation(), 'X-Wipe-Token': wipeToken.trim(), 'Content-Type': 'application/json' },
      })
      if (!r.ok) {
        const d = await r.json().catch(() => ({}))
        throw new Error(d?.detail || 'שגיאה')
      }
      setWipeResult(await r.json())
      checkDbStatus()
    } catch (e: any) {
      setError(e?.message || 'שגיאה')
    } finally {
      setIsWiping(false)
    }
  }

  function goToStep1() {
    setStep(1)
    setFile(null)
    setPreview(null)
    setResult(null)
    setError(null)
  }

  return (
    <div className="min-h-screen w-full px-6 py-10">
      <div className="mx-auto w-full max-w-4xl">
        <div className="flex items-center justify-between gap-4">
          <div className="text-right">
            <div className="text-2xl font-bold">ייבוא מאקסל</div>
            <div className="text-sm text-muted mt-1">
              {step === 1 && 'בחירת מצב וקובץ'}
              {step === 2 && 'תצוגה מקדימה'}
              {step === 3 && 'תוצאות ייבוא'}
            </div>
          </div>
          <BackButton />
        </div>

        <div className="mt-6 card p-6 text-right">
          <div className="text-sm font-semibold text-amber-400/90">מחיקת נתונים לפני ייבוא חדש</div>
          <div className="text-xs text-muted mt-1">מוחק תיקים, אירועי שכ״ט, אקרואלים, תשלומים, הוצאות. לא מוחק משתמשים.</div>
          <div className="mt-3 flex gap-3 items-center">
            <input
              type="password"
              placeholder="קוד אימות (WIPE_CASE_DATA_SECRET)"
              value={wipeToken}
              onChange={(e) => setWipeToken(e.target.value)}
              className="input max-w-xs"
            />
            <button onClick={wipeData} disabled={!wipeToken.trim() || isWiping} className="btn btn-secondary">
              {isWiping ? 'מוחק…' : 'מחיקת כל הנתונים'}
            </button>
          </div>
          {wipeResult ? (
            <div className="mt-2 text-sm text-green-400">נמחק: {wipeResult.deleted?.cases ?? 0} תיקים</div>
          ) : null}
          <div className="mt-2">
            <button type="button" onClick={checkDbStatus} className="text-xs text-muted hover:text-primary">
              בדיקת מצב DB
            </button>
            {dbStatus !== null ? (
              <span className="mr-2 text-xs">{dbStatus.clean ? '✓ נקי (0 תיקים)' : `${dbStatus.cases} תיקים`}</span>
            ) : null}
          </div>
        </div>

        {/* Step 1: Choose mode + file */}
        {step === 1 ? (
          <div className="mt-6 card p-6 text-right">
            <div className="flex flex-wrap items-center gap-4 mb-4">
              <span className="text-sm font-semibold text-muted">מצב ייבוא:</span>
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="radio" name="mode" checked={mode === 'create'} onChange={() => setMode('create')} />
                <span>יצירת תיקים חדשים</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="radio" name="mode" checked={mode === 'update'} onChange={() => setMode('update')} />
                <span>עדכון תיקים קיימים (לפי מזהה תיק)</span>
              </label>
            </div>
            {mode === 'update' ? (
              <label className="flex items-center gap-2 cursor-pointer mt-2 text-sm text-muted">
                <input type="checkbox" checked={overwriteBlanks} onChange={(e) => setOverwriteBlanks(e.target.checked)} />
                <span>ריקים ידרסו ערכים קיימים (overwrite_blanks)</span>
              </label>
            ) : null}
            <div className="text-sm text-muted mt-2">בחרו קובץ Excel והעלו אותו.</div>
            <div className="mt-4 flex flex-col md:flex-row gap-3 md:items-center">
              <input
                type="file"
                accept=".xlsx,.xls"
                onChange={(e) => setFile(e.target.files?.[0] || null)}
                className="block w-full text-sm text-muted file:mr-4 file:py-2 file:px-4 file:rounded-xl file:border-0 file:bg-surface file:text-text hover:file:text-primary"
              />
              <button
                onClick={() => setStep(2)}
                disabled={!file}
                className="btn btn-primary h-12 rounded-2xl"
              >
                המשך לתצוגה מקדימה
              </button>
            </div>
          </div>
        ) : null}

        {/* Step 2: Preview */}
        {step === 2 ? (
          <div className="mt-6 card p-6 text-right space-y-6">
            <div className="flex flex-wrap gap-3 items-center justify-end">
              <button type="button" onClick={goToStep1} className="btn btn-secondary">
                חזור
              </button>
              <button onClick={runImport} disabled={isSubmitting || isPreviewLoading} className="btn btn-primary">
                {isSubmitting ? 'מריץ ייבוא…' : 'הרץ ייבוא'}
              </button>
            </div>

            {error ? <div className="text-sm text-red-300">{error}</div> : null}

            {isPreviewLoading ? (
              <div className="text-sm text-muted py-8">טוען תצוגה מקדימה…</div>
            ) : preview ? (
              <>
                <section>
                  <h3 className="text-sm font-semibold text-muted mb-2">עמודות אופרציונליות (ממופות)</h3>
                  <div className="flex flex-wrap gap-2">
                    {preview.operational_headers.map((h) => (
                      <span key={h} className="px-3 py-1 rounded-full bg-primary/20 text-primary text-sm">
                        {h}
                      </span>
                    ))}
                  </div>
                </section>
                <section>
                  <h3 className="text-sm font-semibold text-muted mb-2">עמודות גולמיות (יישלחו ל־raw_import_fields_json)</h3>
                  <div className="flex flex-wrap gap-2">
                    {preview.raw_headers.length === 0 ? (
                      <span className="text-muted text-sm">אין</span>
                    ) : (
                      preview.raw_headers.map((h) => (
                        <span key={h} className="px-3 py-1 rounded-full bg-surface border border-border/60 text-muted text-sm">
                          {h}
                        </span>
                      ))
                    )}
                  </div>
                </section>
                {mode === 'update' && (preview.sample_rows_not_found_count ?? 0) > 0 ? (
                  <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-200 text-sm">
                    שורות עם מזהה תיק שלא נמצא במערכת (בדגימה): <strong>{preview.sample_rows_not_found_count}</strong>. שורות אלה ייכשלו בעת הרצת הייבוא.
                  </div>
                ) : null}
                {preview.warnings.length > 0 ? (
                  <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 text-right">
                    <h3 className="text-sm font-semibold text-amber-200 mb-2">אזהרות</h3>
                    <ul className="list-disc list-inside text-sm text-amber-200/90 space-y-1">
                      {preview.warnings.map((w, i) => (
                        <li key={i}>{w}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
                <section>
                  <h3 className="text-sm font-semibold text-muted mb-3">דוגמת שורות (עד 10)</h3>
                  <div className="overflow-x-auto rounded-xl border border-border/60">
                    <table className="w-full text-sm" dir="rtl">
                      <thead className="text-muted bg-surface/50">
                        <tr className="border-b border-border/60">
                          <th className="text-right py-2 px-3">מזהה תיק</th>
                          {mode === 'update' ? (
                            <>
                              <th className="text-right py-2 px-3">נמצא במערכת</th>
                              <th className="text-right py-2 px-3">שדות שיעודכנו</th>
                            </>
                          ) : null}
                          <th className="text-right py-2 px-3">ערכים אופרציונליים</th>
                          <th className="text-right py-2 px-3">ערכים גולמיים</th>
                        </tr>
                      </thead>
                      <tbody>
                        {preview.sample_rows.map((row, idx) => (
                          <tr key={idx} className="border-b border-border/30 hover:bg-surface/30">
                            <td className="py-2 px-3 font-medium">{row.case_reference ?? '—'}</td>
                            {mode === 'update' ? (
                              <>
                                <td className="py-2 px-3">{row.case_found ? 'כן' : 'לא'}</td>
                                <td className="py-2 px-3 text-muted text-xs">
                                  {row.will_update_fields?.length ? row.will_update_fields.join(', ') : '—'}
                                </td>
                              </>
                            ) : null}
                            <td className="py-2 px-3 text-muted text-xs max-w-[200px] truncate">
                              {Object.keys(row.operational_values || {}).length
                                ? JSON.stringify(row.operational_values)
                                : '—'}
                            </td>
                            <td className="py-2 px-3">
                              <button
                                type="button"
                                onClick={() => setExpandedRowIndex(expandedRowIndex === idx ? null : idx)}
                                className="text-primary hover:underline text-xs"
                              >
                                {expandedRowIndex === idx ? 'הסתר' : 'הצג'}
                              </button>
                              {expandedRowIndex === idx && row.raw_values && Object.keys(row.raw_values).length > 0 ? (
                                <pre className="mt-2 text-xs bg-surface/50 p-2 rounded overflow-auto max-h-40 text-left">
                                  {JSON.stringify(row.raw_values, null, 2)}
                                </pre>
                              ) : null}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </section>
              </>
            ) : null}
          </div>
        ) : null}

        {/* Step 3: Result */}
        {step === 3 ? (
          <div className="mt-6 card p-6 text-right">
            <div className="flex gap-3 mb-4">
              <button type="button" onClick={goToStep1} className="btn btn-primary">
                ייבוא נוסף
              </button>
            </div>
            {result ? (
              <div className="space-y-3">
                {mode === 'update' ? (
                  <div className="text-sm">
                    <span className="text-muted">עודכנו: </span>
                    <strong>{result.updated ?? 0}</strong>
                    {result.error_count > 0 && (
                      <span className="mr-3 text-amber-400"> • שגיאות: {result.error_count}</span>
                    )}
                  </div>
                ) : (
                  <div className="text-sm">
                    <span className="text-muted">נוצרו: </span>
                    <strong>{result.created ?? 0}</strong>
                    {result.error_count > 0 && (
                      <span className="mr-3 text-amber-400"> • שגיאות: {result.error_count}</span>
                    )}
                  </div>
                )}
                <pre className="text-xs bg-surface/50 border border-border/60 rounded-2xl p-4 overflow-auto text-left">
                  {JSON.stringify(result, null, 2)}
                </pre>
              </div>
            ) : null}
          </div>
        ) : null}
      </div>
    </div>
  )
}

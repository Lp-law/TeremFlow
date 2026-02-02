import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { apiDownload, apiFetch } from '../lib/api'

type BackupLastOut = {
  id: number
  created_at: string
  created_by_username: string
  file_name: string
  size_bytes: number
}

type ActivityItem = {
  id: number
  created_at: string
  action: string
  action_label: string
  entity_type: string
  entity_id: number | null
  username: string | null
}

export function DashboardPage() {
  const { user, logout } = useAuth()
  const [lastBackup, setLastBackup] = useState<BackupLastOut | null>(null)
  const [backupError, setBackupError] = useState<string | null>(null)
  const [isBackingUp, setIsBackingUp] = useState(false)
  const [showLogoutModal, setShowLogoutModal] = useState(false)
  const [activityItems, setActivityItems] = useState<ActivityItem[]>([])

  const fmt = useMemo(
    () =>
      new Intl.DateTimeFormat('he-IL', {
        dateStyle: 'short',
        timeStyle: 'medium',
      }),
    []
  )

  async function refreshLastBackup() {
    try {
      setBackupError(null)
      const data = await apiFetch<BackupLastOut>('/backups/last')
      setLastBackup(data)
    } catch (e: any) {
      setBackupError(e?.message || 'שגיאה')
    }
  }

  async function refreshActivity() {
    try {
      const data = await apiFetch<ActivityItem[]>('/activity/latest?limit=10')
      setActivityItems(data)
    } catch {
      setActivityItems([])
    }
  }

  useEffect(() => {
    refreshLastBackup()
    refreshActivity()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const [downloadFallback, setDownloadFallback] = useState<{ url: string; filename: string } | null>(null)

  async function downloadBackup(): Promise<string | undefined> {
    setIsBackingUp(true)
    setBackupError(null)
    setDownloadFallback(null)
    try {
      const { blob, filename, backupId } = await apiDownload('/backups/export', { method: 'POST' })

      if (!blob || blob.size === 0) {
        throw new Error('השרת החזיר קובץ ריק')
      }

      const safeName = filename || 'teremflow-backup.zip'
      const url = URL.createObjectURL(blob)
      setDownloadFallback({ url, filename: safeName })

      const a = document.createElement('a')
      a.href = url
      a.download = safeName
      a.rel = 'noopener noreferrer'
      a.setAttribute('download', safeName)
      document.body.appendChild(a)
      a.click()

      setTimeout(() => {
        try {
          document.body.removeChild(a)
        } catch {
          /* already removed */
        }
        setDownloadFallback(null)
        URL.revokeObjectURL(url)
      }, 30000)

      await refreshLastBackup()
      return backupId
    } catch (e: any) {
      setBackupError(e?.message || 'שגיאה בהורדת גיבוי')
      throw e
    } finally {
      setIsBackingUp(false)
    }
  }

  async function backupAndLogout() {
    const backupId = await downloadBackup()
    if (!backupId) throw new Error('לא התקבל מזהה גיבוי מהשרת')
    await logout({ backupId })
  }

  return (
    <div className="min-h-screen w-full px-6 py-10">
      <div className="mx-auto w-full max-w-6xl">
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div className="flex items-center gap-3 order-first flex-wrap">
            <img src="/logo-trm.png" alt="טר״מ" className="h-[176px] w-auto object-contain" />
            <img src="/logo-law-firm.png" alt="משרד עורכי דין" className="h-[288px] w-auto object-contain opacity-90" />
          </div>
          <div className="text-right order-2 flex-1 min-w-0">
            <div className="text-2xl font-bold">דשבורד</div>
            <div className="text-sm text-muted mt-1">שלום {user?.username}</div>
          </div>
          <button
            onClick={() => {
              setBackupError(null)
              setShowLogoutModal(true)
            }}
            className="btn btn-secondary order-3"
          >
            התנתקות
          </button>
        </div>

        <div className="mt-6 card p-6">
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
            <div className="text-right">
              <div className="text-lg font-semibold">גיבוי</div>
              {backupError ? (
                <div className="text-sm text-red-300 mt-1">{backupError}</div>
              ) : lastBackup && lastBackup.id !== 0 ? (
                <div className="text-sm text-muted mt-1">
                  גיבוי אחרון: {fmt.format(new Date(lastBackup.created_at))} • {lastBackup.created_by_username}
                </div>
              ) : (
                <div className="text-sm text-muted mt-1">עדיין לא בוצע גיבוי</div>
              )}
            </div>
            <button
              disabled={isBackingUp}
              onClick={async () => {
                try {
                  await downloadBackup()
                } catch {
                  /* error shown via backupError */
                }
              }}
              className="btn btn-primary"
            >
              {isBackingUp ? 'מכין גיבוי…' : 'הורדת גיבוי עכשיו'}
            </button>
          </div>
          <div className="text-right text-xs text-muted mt-3">
            הגיבוי יורד כ־ZIP עם קבצי CSV (כל טבלה בנפרד) + manifest.json — אפשר לפתוח את ה־CSV באקסל.
          </div>
          {downloadFallback ? (
            <div className="text-right text-sm mt-3">
              <a
                href={downloadFallback.url}
                download={downloadFallback.filename}
                className="text-primary hover:underline"
              >
                אם ההורדה לא החלה — לחץ כאן להורדה
              </a>
            </div>
          ) : null}
        </div>

        <div className="mt-8 grid grid-cols-1 md:grid-cols-3 gap-4">
          <CardLink to="/cases" title="תיקים" subtitle="ניהול תיקים, הוצאות, יתרת השתתפות עצמית" />
          <CardLink to="/analytics" title="אנליטיקה" subtitle="סיכומים, פילוחים והשוואות זמן" />
          <CardLink to="/import" title="ייבוא" subtitle="ייבוא מאקסל (MVP)" />
        </div>

        <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-4">
          <CardLink to="/notifications" title="התראות" subtitle="התראות מערכת (ריטיינר / השתתפות עצמית / מבטח)" />
        </div>

        <div className="mt-8 card p-6">
          <div className="text-right">
            <div className="text-lg font-semibold">יומן אירועים</div>
            <div className="text-sm text-muted mt-1">פעולות אחרונות במערכת</div>
          </div>
          <div className="mt-4 space-y-2">
            {activityItems.length === 0 ? (
              <div className="text-sm text-muted py-4">אין אירועים עדיין</div>
            ) : (
              activityItems.map((a) => (
                <div
                  key={a.id}
                  className="flex items-center justify-between gap-4 py-2 border-b border-border/30 last:border-0 text-sm text-right"
                >
                  <span className="text-muted shrink-0">
                    {a.created_at ? fmt.format(new Date(a.created_at)) : '—'}
                  </span>
                  <span className="font-medium flex-1">{a.action_label}</span>
                  <span className="text-muted shrink-0">{a.username ?? '—'}</span>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {showLogoutModal ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4">
          <div className="relative z-[51] w-full max-w-lg rounded-3xl border border-border/60 bg-surface p-6 shadow-card">
            <div className="text-right">
              <div className="text-xl font-bold">התנתקות</div>
              <div className="text-sm text-muted mt-2">
                לפני התנתקות חובה לבצע גיבוי ולהוריד אותו למחשב, כדי שניתן יהיה לשחזר מידע בקלות במקרה תקלה.
              </div>
              {backupError ? (
                <div className="mt-3 text-sm text-red-300">{backupError}</div>
              ) : null}
            </div>

            <div className="mt-5 flex flex-col md:flex-row gap-3 md:justify-end">
              <button
                onClick={() => setShowLogoutModal(false)}
                className="btn btn-secondary"
                disabled={isBackingUp}
              >
                ביטול
              </button>
              <button
                onClick={async () => {
                  try {
                    await backupAndLogout()
                    setShowLogoutModal(false)
                  } catch (e: any) {
                    setBackupError(e?.message || 'שגיאה — נא לנסות שוב')
                    /* keep modal open so user can retry */
                  }
                }}
                className="btn btn-primary"
                disabled={isBackingUp}
              >
                {isBackingUp ? 'מכין גיבוי…' : 'בצע גיבוי והתנתק'}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}

function CardLink({ to, title, subtitle }: { to: string; title: string; subtitle: string }) {
  return (
    <Link
      to={to}
      className="card block p-6 hover:border-primary/60 transition-colors"
    >
      <div className="text-right">
        <div className="text-lg font-semibold">{title}</div>
        <div className="text-sm text-muted mt-2">{subtitle}</div>
      </div>
    </Link>
  )
}



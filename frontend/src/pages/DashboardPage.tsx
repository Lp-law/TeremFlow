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

export function DashboardPage() {
  const { user, logout } = useAuth()
  const [lastBackup, setLastBackup] = useState<BackupLastOut | null>(null)
  const [backupError, setBackupError] = useState<string | null>(null)
  const [isBackingUp, setIsBackingUp] = useState(false)
  const [showLogoutModal, setShowLogoutModal] = useState(false)

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

  useEffect(() => {
    refreshLastBackup()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function downloadBackup(): Promise<string | undefined> {
    setIsBackingUp(true)
    setBackupError(null)
    try {
      const { blob, filename, backupId } = await apiDownload('/backups/export', { method: 'POST' })

      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename || 'teremflow-backup.zip'
      document.body.appendChild(a)
      a.click()
      a.remove()
      setTimeout(() => URL.revokeObjectURL(url), 1000)

      await refreshLastBackup()
      return backupId
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
        <div className="flex items-center justify-between gap-4">
          <div className="text-right">
            <div className="text-2xl font-bold">דשבורד</div>
            <div className="text-sm text-muted mt-1">שלום {user?.username}</div>
          </div>
          <button
            onClick={() => setShowLogoutModal(true)}
            className="btn btn-secondary"
          >
            התנתקות
          </button>
        </div>

        <div className="mt-6 card p-6">
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
            <div className="text-right">
              <div className="text-lg font-semibold">גיבוי</div>
              {backupError ? (
                <div className="text-sm text-danger mt-1">{backupError}</div>
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
              onClick={() => downloadBackup()}
              className="btn btn-primary"
            >
              {isBackingUp ? 'מכין גיבוי…' : 'הורדת גיבוי עכשיו'}
            </button>
          </div>
          <div className="text-right text-xs text-muted mt-3">
            הגיבוי יורד כ־ZIP עם קבצי CSV (כל טבלה בנפרד) + manifest.json — אפשר לפתוח את ה־CSV באקסל.
          </div>
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
            <div className="text-lg font-semibold">קיצורי דרך</div>
            <div className="text-sm text-muted mt-1">בשלב זה ה־MVP מציג בסיס UI; מסכים נוספים יתווספו מיד אחרי חיבור כל ה־API.</div>
          </div>
        </div>
      </div>

      {showLogoutModal ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4">
          <div className="w-full max-w-lg rounded-3xl border border-border/60 bg-surface p-6 shadow-card">
            <div className="text-right">
              <div className="text-xl font-bold">התנתקות</div>
              <div className="text-sm text-muted mt-2">
                לפני התנתקות חובה לבצע גיבוי ולהוריד אותו למחשב, כדי שניתן יהיה לשחזר מידע בקלות במקרה תקלה.
              </div>
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
                  } catch (e: any) {
                    setBackupError(e?.message || 'שגיאה')
                  } finally {
                    setShowLogoutModal(false)
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



import { Link } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { apiFetch } from '../lib/api'
import { Badge } from '../components/Badge'
import { formatDateTimeShort } from '../lib/format'
import type { Notification } from '../lib/types'

export function NotificationsPage() {
  const [items, setItems] = useState<Notification[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  async function load() {
    setError(null)
    setIsLoading(true)
    try {
      const data = await apiFetch<Notification[]>('/notifications/')
      setItems(data)
    } catch (e: any) {
      setError(e?.message || 'שגיאה')
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  async function markRead(id: number) {
    await apiFetch(`/notifications/${id}/read`, { method: 'POST' })
    setItems((prev) => prev.map((n) => (n.id === id ? { ...n, is_read: true } : n)))
  }

  return (
    <div className="min-h-screen w-full px-6 py-10">
      <div className="mx-auto w-full max-w-6xl">
        <div className="flex items-center justify-between gap-4">
          <div className="text-right">
            <div className="text-2xl font-bold">התראות</div>
            <div className="text-sm text-muted mt-1">התראות מערכת שנוצרו ע״י משימות יומיות</div>
          </div>
          <div className="flex gap-2">
            <button
              onClick={load}
              className="btn btn-primary"
            >
              רענון
            </button>
            <Link
              to="/dashboard"
              className="btn btn-secondary"
            >
              חזרה לדשבורד
            </Link>
          </div>
        </div>

        {error ? <div className="mt-6 text-sm text-red-300 text-right">{error}</div> : null}
        {isLoading ? <div className="mt-6 text-sm text-muted text-right">טוען...</div> : null}

        {!isLoading ? (
          <div className="mt-6 space-y-3">
            {items.map((n) => (
              <div
                key={n.id}
                className={[
                  'card p-5',
                  n.is_read ? 'opacity-80' : 'border-primary/30',
                ].join(' ')}
              >
                <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
                  <div className="text-right">
                    <div className="flex items-center gap-2 justify-end flex-wrap">
                      <div className="text-lg font-semibold">{n.title}</div>
                      <Badge
                        label={n.severity === 'danger' ? 'דחוף' : n.severity === 'warning' ? 'אזהרה' : 'מידע'}
                        variant={n.severity === 'danger' ? 'danger' : n.severity === 'warning' ? 'warning' : 'info'}
                      />
                      {n.is_read ? <Badge label="נקרא" variant="muted" /> : <Badge label="חדש" variant="success" />}
                    </div>
                    <div className="text-sm text-muted mt-1">{formatDateTimeShort(n.created_at)}</div>
                    <div className="text-sm mt-3">{n.message}</div>

                    {n.case_id ? (
                      <div className="mt-3">
                        <Link to={`/cases/${n.case_id}`} className="text-primary hover:underline">
                          מעבר לתיק #{n.case_id}
                        </Link>
                      </div>
                    ) : null}
                  </div>

                  {!n.is_read ? (
                    <button
                      onClick={() => markRead(n.id)}
                      className="btn btn-secondary"
                    >
                      סמן כנקרא
                    </button>
                  ) : null}
                </div>
              </div>
            ))}

            {items.length === 0 ? (
              <div className="card p-8 text-center text-muted">
                אין התראות
              </div>
            ) : null}
          </div>
        ) : null}
      </div>
    </div>
  )
}



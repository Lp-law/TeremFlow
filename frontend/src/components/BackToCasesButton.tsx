import { Link, useLocation } from 'react-router-dom'

/**
 * Shown when user is logged in and not on /dashboard or /login.
 * Dashboard link on all inner pages; "חזרה לרשימת תיקים" only when not on /cases.
 */
export function BackToCasesButton() {
  const location = useLocation()
  const pathname = location.pathname
  const showBackToCases = pathname !== '/dashboard' && pathname !== '/cases'

  return (
    <div className="px-6 py-2 flex justify-end gap-2">
      <Link to="/dashboard" className="btn btn-secondary btn-sm">
        דשבורד
      </Link>
      {showBackToCases ? (
        <Link to="/cases" className="btn btn-secondary btn-sm">
          חזרה לרשימת תיקים
        </Link>
      ) : null}
    </div>
  )
}

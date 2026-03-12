import { Link } from 'react-router-dom'

/**
 * Shown on inner pages (case details, analytics, import, notifications).
 * Hidden on /dashboard and on /cases (list). RTL-safe, secondary style.
 */
export function BackToCasesButton() {
  return (
    <div className="px-6 py-2 flex justify-end">
      <Link to="/cases" className="btn btn-secondary btn-sm">
        חזרה לרשימת תיקים
      </Link>
    </div>
  )
}

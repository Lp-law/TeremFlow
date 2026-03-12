import { Suspense, lazy } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { AuthProvider, RequireAuth, useAuth } from './auth/AuthContext'
import { BackToCasesButton } from './components/BackToCasesButton'
import { BuildFingerprint } from './components/BuildFingerprint'

const LoginPage = lazy(() => import('./pages/LoginPage').then((m) => ({ default: m.LoginPage })))
const DashboardPage = lazy(() => import('./pages/DashboardPage').then((m) => ({ default: m.DashboardPage })))
const CasesPage = lazy(() => import('./pages/CasesPage').then((m) => ({ default: m.CasesPage })))
const CaseDetailsPage = lazy(() => import('./pages/CaseDetailsPage').then((m) => ({ default: m.CaseDetailsPage })))
const AnalyticsPage = lazy(() => import('./pages/AnalyticsPage').then((m) => ({ default: m.AnalyticsPage })))
const ImportPage = lazy(() => import('./pages/ImportPage').then((m) => ({ default: m.ImportPage })))
const NotificationsPage = lazy(() => import('./pages/NotificationsPage').then((m) => ({ default: m.NotificationsPage })))

function HomeRedirect() {
  const { user, isLoading } = useAuth()
  if (isLoading) return null
  return <Navigate to={user ? '/dashboard' : '/login'} replace />
}

function AppContent() {
  const { user } = useAuth()
  const location = useLocation()
  const pathname = location.pathname
  const showBackToCases = pathname !== '/dashboard' && pathname !== '/cases'
  return (
    <div className="min-h-screen flex flex-col">
      <main className="flex-1">
        {user && showBackToCases ? <BackToCasesButton /> : null}
        <Suspense fallback={<div className="min-h-screen w-full px-6 py-10 text-right text-sm text-muted">טוען...</div>}>
          <Routes>
            <Route path="/" element={<HomeRedirect />} />
            <Route path="/login" element={<LoginPage />} />
            <Route
              path="/dashboard"
              element={
                <RequireAuth>
                  <DashboardPage />
                </RequireAuth>
              }
            />
            <Route
              path="/cases"
            element={
              <RequireAuth>
                <CasesPage />
              </RequireAuth>
            }
            />
            <Route
              path="/cases/:caseId"
              element={
                <RequireAuth>
                  <CaseDetailsPage />
                </RequireAuth>
              }
            />
            <Route
              path="/analytics"
              element={
                <RequireAuth>
                  <AnalyticsPage />
                </RequireAuth>
              }
            />
            <Route
              path="/import"
              element={
                <RequireAuth>
                  <ImportPage />
                </RequireAuth>
              }
            />
            <Route
              path="/notifications"
              element={
                <RequireAuth>
                  <NotificationsPage />
                </RequireAuth>
              }
            />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
      </main>
      {user ? <BuildFingerprint /> : null}
    </div>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  )
}

import React, { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { apiFetch, setCsrfToken } from '../lib/api'

export type User = {
  id: number
  username: string
  role: string
  csrf_token?: string
}

type AuthState = {
  user: User | null
  isLoading: boolean
  login: (username: string, password: string) => Promise<void>
  logout: (opts?: { backupId?: string }) => Promise<void>
  refresh: () => Promise<void>
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  async function refresh() {
    try {
      const me = await apiFetch<User>('/auth/me')
      setUser(me)
      if (me.csrf_token) setCsrfToken(me.csrf_token)
    } catch {
      setUser(null)
      setCsrfToken(null)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    refresh()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const navigate = useNavigate()

  async function login(username: string, password: string) {
    const me = await apiFetch<User>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    })
    setUser(me)
    if (me.csrf_token) setCsrfToken(me.csrf_token)
    navigate('/dashboard', { replace: true })
  }

  async function logout(opts?: { backupId?: string }) {
    await apiFetch('/auth/logout', {
      method: 'POST',
      headers: opts?.backupId ? { 'X-Backup-Id': opts.backupId } : undefined,
    })
    setUser(null)
    setCsrfToken(null)
    navigate('/login', { replace: true })
  }

  const value = useMemo<AuthState>(() => ({ user, isLoading, login, logout, refresh }), [user, isLoading])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}

export function RequireAuth({ children }: { children: React.ReactNode }) {
  const { user, isLoading } = useAuth()
  const location = useLocation()
  if (isLoading) return null
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  return <>{children}</>
}



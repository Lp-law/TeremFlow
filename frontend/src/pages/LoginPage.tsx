import { useState } from 'react'
import { useAuth } from '../auth/AuthContext'

export function LoginPage() {
  const { login } = useAuth()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setIsSubmitting(true)
    try {
      await login(username.trim(), password)
    } catch (err: any) {
      setError(err?.message || 'שגיאה')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen w-full px-6 py-10 flex items-center justify-center">
      <div className="w-full max-w-[560px] card px-8 py-10 bg-card/80">
        <div className="text-center">
          <div className="text-4xl font-extrabold tracking-tight text-text">TeremFlow</div>
          <div className="mt-3 text-muted text-base">“Every expense. Every stage. One clear picture.”</div>
        </div>

        <form onSubmit={onSubmit} className="mt-10 space-y-5">
          <div className="space-y-2 text-right">
            <label className="text-sm font-medium text-muted">שם משתמש</label>
            <input
              className="w-full h-14 rounded-xl bg-surface border border-border/70 px-4 text-text placeholder:text-placeholder outline-none focus:ring-2 focus:ring-primary/60 focus:border-primary/70"
              placeholder="lidor / iris / lior"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              dir="ltr"
            />
          </div>
          <div className="space-y-2 text-right">
            <label className="text-sm font-medium text-muted">סיסמה</label>
            <input
              className="w-full h-14 rounded-xl bg-surface border border-border/70 px-4 text-text placeholder:text-placeholder outline-none focus:ring-2 focus:ring-primary/60 focus:border-primary/70"
              placeholder="ChangeMe123!"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              type="password"
              autoComplete="current-password"
              dir="ltr"
            />
          </div>

          {error ? <div className="text-sm text-red-300 text-right">{error}</div> : null}

          <button
            type="submit"
            disabled={isSubmitting}
            className="btn btn-primary w-full h-14 rounded-2xl"
          >
            התחברות
          </button>
        </form>

        <div className="mt-6 text-xs text-muted text-center">
          כל הסכומים במערכת הם בש״ח וכוללים מע״מ (ברוטו).
        </div>
      </div>
    </div>
  )
}



import { useEffect, useState } from 'react'
import { useAuth } from '../auth/AuthContext'

export function LoginPage() {
  const { login } = useAuth()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [showSlowServerHint, setShowSlowServerHint] = useState(false)

  useEffect(() => {
    if (!isSubmitting) {
      setShowSlowServerHint(false)
      return
    }
    const timer = window.setTimeout(() => setShowSlowServerHint(true), 3500)
    return () => window.clearTimeout(timer)
  }, [isSubmitting])

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
            <div className="relative">
              <input
                className="w-full h-14 rounded-xl bg-surface border border-border/70 pl-12 pr-4 text-text placeholder:text-placeholder outline-none focus:ring-2 focus:ring-primary/60 focus:border-primary/70"
                placeholder="ChangeMe123!"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                type={showPassword ? 'text' : 'password'}
                autoComplete="current-password"
                dir="ltr"
              />
              <button
                type="button"
                onClick={() => setShowPassword((v) => !v)}
                className="absolute left-3 top-1/2 -translate-y-1/2 p-1.5 rounded-lg text-muted hover:text-text hover:bg-black/5 focus:outline-none focus:ring-2 focus:ring-primary/40"
                aria-label={showPassword ? 'הסתר סיסמה' : 'הצג סיסמה'}
                tabIndex={0}
              >
                {showPassword ? (
                  <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                    <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
                    <line x1="1" y1="1" x2="23" y2="23" />
                  </svg>
                ) : (
                  <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                    <circle cx="12" cy="12" r="3" />
                  </svg>
                )}
              </button>
            </div>
          </div>

          {error ? <div className="text-sm text-red-300 text-right">{error}</div> : null}
          {showSlowServerHint ? (
            <div className="text-sm text-muted text-right" role="status" aria-live="polite">
              השרת מתעורר כרגע. ההתחברות עלולה לקחת עד כדקה בפעם הראשונה.
            </div>
          ) : null}

          <button
            type="submit"
            disabled={isSubmitting}
            className="btn btn-primary w-full h-14 rounded-2xl"
          >
            התחברות
          </button>
          <a
            href="https://ringforge.onrender.com/dashboard"
            className="btn btn-secondary w-full h-14 rounded-2xl"
            aria-label="מעבר לדשבורד"
          >
            דשבורד
          </a>
        </form>

        <div className="mt-6 text-xs text-muted text-center">
          כל הסכומים במערכת הם בש״ח וכוללים מע״מ (ברוטו).
        </div>
      </div>
    </div>
  )
}



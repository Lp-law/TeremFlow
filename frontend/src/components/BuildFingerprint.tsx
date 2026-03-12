import { useEffect, useState } from 'react'
import { API_BASE_URL } from '../lib/api'

const FRONTEND_SHA =
  (typeof import.meta !== 'undefined' && (import.meta as { env?: { VITE_GIT_SHA?: string } }).env?.VITE_GIT_SHA) ||
  'unknown'

type VersionResponse = {
  git_sha?: string
  build_time_utc?: string
  environment?: string
  service?: string
}

type BackendState =
  | { kind: 'ok'; sha: string }
  | { kind: 'fail'; reason: string }
  | null

export function BuildFingerprint() {
  const [backendState, setBackendState] = useState<BackendState>(null)

  useEffect(() => {
    const url = `${API_BASE_URL}/version`
    fetch(url, { credentials: 'include', headers: { Accept: 'application/json' } })
      .then((res) => {
        if (!res.ok) {
          setBackendState({ kind: 'fail', reason: `${res.status}` })
          return null
        }
        return res.json() as Promise<VersionResponse>
      })
      .then((data) => {
        if (data === null) return
        if (data?.git_sha != null && data.git_sha !== '') {
          setBackendState({ kind: 'ok', sha: data.git_sha })
        } else {
          setBackendState({ kind: 'fail', reason: 'no sha' })
        }
      })
      .catch((e: unknown) => {
        const msg = e instanceof Error ? e.message : String(e)
        setBackendState({ kind: 'fail', reason: msg.slice(0, 40) })
      })
  }, [])

  const backendDisplay =
    backendState === null
      ? '…'
      : backendState.kind === 'ok'
        ? backendState.sha
        : `unavailable (${backendState.reason})`

  return (
    <footer className="mt-auto py-2 px-4 text-center text-xs text-muted" role="contentinfo">
      <span className="me-2" dir="ltr">
        Frontend: <span className="font-mono">{FRONTEND_SHA}</span>
      </span>
      <span className="me-2">|</span>
      <span className="me-2" dir="ltr">
        Backend: <span className="font-mono">{backendDisplay}</span>
      </span>
    </footer>
  )
}

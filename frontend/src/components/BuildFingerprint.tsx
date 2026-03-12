import { useEffect, useState } from 'react'
import { API_BASE_URL } from '../lib/api'

type VersionResponse = {
  git_sha?: string
  build_time_utc?: string
  environment?: string
  service?: string
}

type FingerprintState =
  | { kind: 'ok'; sha: string }
  | { kind: 'fail'; reason: string }
  | null

export function BuildFingerprint() {
  const [state, setState] = useState<FingerprintState>(null)

  useEffect(() => {
    const url = `${API_BASE_URL}/version`
    fetch(url, { credentials: 'include', headers: { Accept: 'application/json' } })
      .then((res) => {
        if (!res.ok) {
          setState({ kind: 'fail', reason: `${res.status}` })
          return null
        }
        return res.json() as Promise<VersionResponse>
      })
      .then((data) => {
        if (data === null) return
        if (data?.git_sha != null && data.git_sha !== '') {
          setState({ kind: 'ok', sha: data.git_sha })
        } else {
          setState({ kind: 'fail', reason: 'no sha' })
        }
      })
      .catch((e: unknown) => {
        const msg = e instanceof Error ? e.message : String(e)
        setState({ kind: 'fail', reason: msg.slice(0, 40) })
      })
  }, [])

  const displayText =
    state === null
      ? '…'
      : state.kind === 'ok'
        ? state.sha
        : `unavailable (${state.reason})`

  return (
    <footer className="mt-auto py-2 px-4 text-center text-xs text-muted" role="contentinfo">
      <span className="me-1">Build:</span>
      <span dir="ltr" className="font-mono">
        {displayText}
      </span>
    </footer>
  )
}

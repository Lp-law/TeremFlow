import { useEffect, useState } from 'react'
import { apiFetch } from '../lib/api'

type VersionResponse = {
  git_sha: string
  build_time_utc?: string
  environment?: string
  db_revision?: string
  service?: string
}

export function BuildFingerprint() {
  const [sha, setSha] = useState<string | null>(null)

  useEffect(() => {
    apiFetch<VersionResponse>('/version')
      .then((data) => setSha(data.git_sha || 'unknown'))
      .catch(() => setSha(null))
  }, [])

  if (!sha) return null

  return (
    <footer className="mt-auto py-2 px-4 text-center text-xs text-muted" role="contentinfo">
      <span className="me-1">Build:</span>
      <span dir="ltr" className="font-mono">
        {sha}
      </span>
    </footer>
  )
}

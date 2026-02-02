export const API_BASE_URL = (import.meta as any).env?.VITE_API_URL || 'http://localhost:8000'

function getCookie(name: string): string | undefined {
  if (typeof document === 'undefined') return undefined
  const m = document.cookie.match(new RegExp('(?:^|; )' + name.replace(/[-.*+?^${}()|[\\]\\\\]/g, '\\\\$&') + '=([^;]*)'))
  return m ? decodeURIComponent(m[1]) : undefined
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const method = (init?.method || 'GET').toUpperCase()
  const csrf = getCookie('teremflow_csrf')

  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...(csrf && method !== 'GET' && method !== 'HEAD' ? { 'X-CSRF-Token': csrf } : {}),
      ...(init?.headers || {}),
    },
  })

  if (!res.ok) {
    let detail = 'שגיאה'
    try {
      const data = await res.json()
      if (Array.isArray(data?.detail)) {
        detail = data.detail.map((d: any) => d?.msg || JSON.stringify(d)).join('; ')
      } else {
        detail = data?.detail || detail
      }
    } catch {
      // ignore
    }
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
  }

  if (res.status === 204) return undefined as any
  return (await res.json()) as T
}

function parseContentDispositionFilename(v: string | null): string | undefined {
  if (!v) return undefined
  // Basic: attachment; filename="file.zip"
  const m = v.match(/filename\*?=(?:UTF-8''|")?([^";]+)"?/i)
  if (!m) return undefined
  try {
    return decodeURIComponent(m[1])
  } catch {
    return m[1]
  }
}

export async function apiDownload(
  path: string,
  init?: RequestInit
): Promise<{ blob: Blob; filename?: string; backupId?: string }> {
  const method = (init?.method || 'GET').toUpperCase()
  const csrf = getCookie('teremflow_csrf')

  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    credentials: 'include',
    headers: {
      ...(csrf && method !== 'GET' && method !== 'HEAD' ? { 'X-CSRF-Token': csrf } : {}),
      ...(init?.headers || {}),
    },
  })

  if (!res.ok) {
    let detail = 'שגיאה'
    try {
      const data = await res.json()
      detail = data?.detail || detail
    } catch {
      // ignore
    }
    throw new Error(detail)
  }

  const blob = await res.blob()
  const backupId = res.headers.get('X-Backup-Id') || undefined
  const filename = parseContentDispositionFilename(res.headers.get('Content-Disposition'))
  return { blob, filename, backupId }
}



export function toNumber(x: unknown): number {
  if (typeof x === 'number') return x
  if (typeof x === 'string') return Number(x)
  return Number(x as any)
}

export function formatILS(x: unknown): string {
  const n = toNumber(x)
  if (!Number.isFinite(n)) return '0.00 ₪'
  try {
    const nf = new Intl.NumberFormat('he-IL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    return `${nf.format(n)} ₪`
  } catch {
    return `${n.toFixed(2)} ₪`
  }
}

export function formatMoney(x: unknown): string {
  const n = toNumber(x)
  if (!Number.isFinite(n)) return '0.00'
  try {
    const nf = new Intl.NumberFormat('he-IL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    return nf.format(n)
  } catch {
    return n.toFixed(2)
  }
}

export function formatDateYMD(d: string | Date): string {
  if (d instanceof Date) return d.toISOString().slice(0, 10)
  return String(d).slice(0, 10)
}

export function formatDateTimeShort(iso: string): string {
  const s = String(iso)
  // "2026-01-13T12:34:56.789Z" -> "2026-01-13 12:34"
  return s.replace('T', ' ').slice(0, 16)
}

export function isOverdue(dueDateYmd: string, isPaid: boolean): boolean {
  if (isPaid) return false
  const today = new Date()
  const todayYmd = today.toISOString().slice(0, 10)
  return dueDateYmd.slice(0, 10) < todayYmd
}



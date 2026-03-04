/**
 * Display-only mapping and formatting for Case.raw_import_fields_json.
 * Keys are as stored (often snake_case from Excel headers). Unknown keys → group "שדות נוספים".
 */

export const RAW_GROUP_ORDER = [
  'ריטיינר (ייבוא גולמי)',
  'הוצאות (ייבוא גולמי)',
  'השתתפות עצמית / אקסס (ייבוא גולמי)',
  'סטטוס וניהול (ייבוא גולמי)',
  'שדות נוספים (ייבוא גולמי)',
] as const

const RAW_FIELD_META: Record<string, { label: string; group: (typeof RAW_GROUP_ORDER)[number] }> = {
  // ריטיינר (ייבוא גולמי)
  retainer_paid_total_ils: { label: 'סה״כ ריטיינר ששולם (ש״ח)', group: 'ריטיינר (ייבוא גולמי)' },
  retainer_paid_through_amount_ils: { label: 'ריטיינר שולם עד סכום (ש״ח)', group: 'ריטיינר (ייבוא גולמי)' },
  retainer_paid_from_amount_ils: { label: 'ריטיינר שולם מתאריך/סכום (ש״ח)', group: 'ריטיינר (ייבוא גולמי)' },
  retainer_billing_months_through: { label: 'חודשי חיוב ריטיינר עד', group: 'ריטיינר (ייבוא גולמי)' },
  retainer_debt_reference: { label: 'מזהה חוב ריטיינר', group: 'ריטיינר (ייבוא גולמי)' },
  retainer_snapshot_ils: { label: 'סנאפשוט ריטיינר (ש״ח)', group: 'ריטיינר (ייבוא גולמי)' },
  total_retainer_ils: { label: 'סה״כ ריטיינר (ש״ח)', group: 'ריטיינר (ייבוא גולמי)' },

  // הוצאות (ייבוא גולמי)
  case_expenses_total_ils: { label: 'סה״כ הוצאות תיק (ש״ח)', group: 'הוצאות (ייבוא גולמי)' },
  expenses_other_paid_ils: { label: 'הוצאות אחרות ששולמו (ש״ח)', group: 'הוצאות (ייבוא גולמי)' },
  expenses_snapshot_ils: { label: 'סנאפשוט הוצאות (ש״ח)', group: 'הוצאות (ייבוא גולמי)' },

  // השתתפות עצמית / אקסס (ייבוא גולמי)
  deductible_balance_ils: { label: 'יתרת השתתפות עצמית (ש״ח)', group: 'השתתפות עצמית / אקסס (ייבוא גולמי)' },
  deductible_remaining_ils: { label: 'יתרת אקסס (ש״ח)', group: 'השתתפות עצמית / אקסס (ייבוא גולמי)' },
  excess_balance_ils: { label: 'יתרת אקסס (ש״ח)', group: 'השתתפות עצמית / אקסס (ייבוא גולמי)' },

  // סטטוס וניהול (ייבוא גולמי)
  is_billable: { label: 'חייב', group: 'סטטוס וניהול (ייבוא גולמי)' },
  case_status_text: { label: 'סטטוס תיק (טקסט)', group: 'סטטוס וניהול (ייבוא גולמי)' },
  case_status: { label: 'סטטוס תיק', group: 'סטטוס וניהול (ייבוא גולמי)' },
  status: { label: 'סטטוס', group: 'סטטוס וניהול (ייבוא גולמי)' },
}

const GROUP_OTHER: (typeof RAW_GROUP_ORDER)[number] = 'שדות נוספים (ייבוא גולמי)'

function normalizeKey(k: string): string {
  return k.replace(/\s+/g, '_').toLowerCase().trim()
}

export function getRawFieldLabel(key: string): string {
  const meta = RAW_FIELD_META[normalizeKey(key)] ?? RAW_FIELD_META[key]
  return meta?.label ?? key
}

export function getRawFieldGroup(key: string): (typeof RAW_GROUP_ORDER)[number] {
  const meta = RAW_FIELD_META[normalizeKey(key)] ?? RAW_FIELD_META[key]
  return (meta?.group ?? GROUP_OTHER) as (typeof RAW_GROUP_ORDER)[number]
}

function isIsoDate(s: string): boolean {
  return /^\d{4}-\d{2}-\d{2}(T|$)/.test(String(s).trim())
}

export function formatRawValue(key: string, val: unknown): string {
  if (val === null || val === undefined) return '—'
  const k = String(key)
  const kNorm = normalizeKey(k)
  const strVal = typeof val === 'object' ? JSON.stringify(val) : String(val)

  // Boolean
  if (val === true) return 'כן'
  if (val === false) return 'לא'
  if (strVal.toLowerCase() === 'true') return 'כן'
  if (strVal.toLowerCase() === 'false') return 'לא'

  // Date: key ends with _date or contains _through_ (month), or value is ISO date
  if (kNorm.endsWith('_date') || kNorm.includes('_through_') || isIsoDate(strVal)) {
    const slice = String(strVal).slice(0, 10)
    if (/^\d{4}-\d{2}-\d{2}$/.test(slice)) return slice
    return strVal
  }

  // ILS: key ends with _ils or contains _ils_
  if (kNorm.endsWith('_ils') || kNorm.includes('_ils_')) {
    const n = Number(val)
    if (!Number.isFinite(n)) return strVal
    try {
      const nf = new Intl.NumberFormat('he-IL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
      return `${nf.format(n)} ₪`
    } catch {
      return `${n.toFixed(2)} ₪`
    }
  }

  // USD
  if (kNorm.endsWith('_usd')) {
    const n = Number(val)
    if (!Number.isFinite(n)) return strVal
    try {
      const nf = new Intl.NumberFormat('he-IL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
      return `$${nf.format(n)}`
    } catch {
      return `$${n.toFixed(2)}`
    }
  }

  return strVal
}

export function groupRawEntries(
  entries: [string, unknown][],
  filterEmpty: boolean,
  searchQuery: string
): Record<string, { key: string; label: string; value: unknown }[]> {
  const q = searchQuery.trim().toLowerCase()
  const filtered = entries.filter(([key, value]) => {
    if (filterEmpty && (value === null || value === undefined || value === '')) return false
    if (!q) return true
    const label = getRawFieldLabel(key)
    return (
      key.toLowerCase().includes(q) ||
      label.toLowerCase().includes(q) ||
      normalizeKey(key).includes(q)
    )
  })

  const byGroup: Record<string, { key: string; label: string; value: unknown }[]> = {}
  for (const g of RAW_GROUP_ORDER) {
    byGroup[g] = []
  }
  for (const [key, value] of filtered) {
    const group = getRawFieldGroup(key)
    if (!byGroup[group]) byGroup[group] = []
    byGroup[group].push({ key, label: getRawFieldLabel(key), value })
  }
  return byGroup
}

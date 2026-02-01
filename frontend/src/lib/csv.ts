function escapeCsvCell(v: any): string {
  if (v === null || v === undefined) return ''
  const s = String(v)
  // Quote if it contains delimiter/newline/quote
  if (/[",\n\r\t;]/.test(s)) return `"${s.replace(/"/g, '""')}"`
  return s
}

export function toCsv(rows: Record<string, any>[], columns: string[], delimiter: ',' | ';' = ','): string {
  const header = columns.map((c) => escapeCsvCell(c)).join(delimiter)
  const body = rows
    .map((r) => columns.map((c) => escapeCsvCell((r as any)[c])).join(delimiter))
    .join('\n')
  return `${header}\n${body}\n`
}

export function downloadTextFile(filename: string, content: string, mime = 'text/csv;charset=utf-8') {
  // UTF‑8 BOM helps Excel open Hebrew correctly.
  const blob = new Blob(['\ufeff', content], { type: mime })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}



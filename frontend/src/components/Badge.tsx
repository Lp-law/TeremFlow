export function Badge({
  label,
  variant,
}: {
  label: string
  variant: 'info' | 'success' | 'warning' | 'danger' | 'muted'
}) {
  const cls =
    variant === 'success'
      ? 'border-emerald-400/30 bg-emerald-400/10 text-emerald-100'
      : variant === 'warning'
        ? 'border-yellow-400/30 bg-yellow-400/10 text-yellow-100'
        : variant === 'danger'
          ? 'border-red-400/30 bg-red-400/10 text-red-100'
          : variant === 'info'
            ? 'border-sky-400/30 bg-sky-400/10 text-sky-100'
            : 'border-border/60 bg-surface/40 text-muted'

  return <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs ${cls}`}>{label}</span>
}



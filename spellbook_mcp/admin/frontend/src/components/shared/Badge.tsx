const severityColors: Record<string, string> = {
  critical: 'text-accent-red border-accent-red',
  error: 'text-accent-red border-accent-red',
  warning: 'text-accent-amber border-accent-amber',
  info: 'text-accent-cyan border-accent-cyan',
  success: 'text-accent-green border-accent-green',
  active: 'text-accent-green border-accent-green',
  deleted: 'text-text-dim border-text-dim',
  saturated: 'text-accent-green border-accent-green',
  pending: 'text-accent-amber border-accent-amber',
}

interface BadgeProps {
  label: string
  variant?: string
}

export function Badge({ label, variant }: BadgeProps) {
  const colors = severityColors[variant || label.toLowerCase()] || 'text-text-secondary border-text-secondary'
  return (
    <span className={`inline-block px-2 py-0.5 border font-mono text-xs uppercase tracking-widest ${colors}`}>
      {label}
    </span>
  )
}

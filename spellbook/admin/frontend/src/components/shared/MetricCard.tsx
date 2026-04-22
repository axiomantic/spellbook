type MetricCardVariant = 'default' | 'success' | 'warning' | 'error'

interface MetricCardProps {
  label: string
  value: string | number | null
  unit?: string
  variant?: MetricCardVariant
}

const VARIANT_COLORS: Record<MetricCardVariant, string> = {
  default: 'text-text-primary',
  success: 'text-accent-green',
  warning: 'text-accent-amber',
  error: 'text-accent-red',
}

export function MetricCard({ label, value, unit, variant = 'default' }: MetricCardProps) {
  const colorClass = VARIANT_COLORS[variant]
  const isNull = value === null

  return (
    <div className="card">
      <div className="font-mono text-xs text-text-dim uppercase tracking-widest mb-1">
        {label}
      </div>
      <div
        data-testid="metric-card-value"
        className={`font-mono text-2xl ${colorClass}`}
      >
        {isNull ? (
          '\u2014'
        ) : (
          <>
            <span>{value}</span>
            {unit && (
              <span className="text-sm text-text-dim ml-1">{unit}</span>
            )}
          </>
        )}
      </div>
    </div>
  )
}

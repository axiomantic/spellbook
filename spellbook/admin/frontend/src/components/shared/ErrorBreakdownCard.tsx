interface ErrorBreakdownCardProps {
  breakdown: Record<string, number> | null
}

export function ErrorBreakdownCard({ breakdown }: ErrorBreakdownCardProps) {
  const entries = breakdown
    ? Object.entries(breakdown).sort((a, b) => b[1] - a[1])
    : []

  return (
    <div className="card">
      <div className="font-mono text-xs text-text-dim uppercase tracking-widest mb-3">
        Error Breakdown
      </div>
      {entries.length === 0 ? (
        <div className="font-mono text-sm text-text-dim">No errors</div>
      ) : (
        <ul className="space-y-1">
          {entries.map(([label, count]) => (
            <li
              key={label}
              data-testid="error-breakdown-row"
              className="flex items-center justify-between font-mono text-xs"
            >
              <span
                data-testid="error-label"
                className="text-text-secondary truncate pr-2"
              >
                {label}
              </span>
              <span
                data-testid="error-count"
                className="text-accent-red tabular-nums"
              >
                {count}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

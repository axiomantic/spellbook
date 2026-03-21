interface ErrorDisplayProps {
  error: Error | unknown
  title?: string
  onRetry?: () => void
}

export function ErrorDisplay({ error, title = 'Failed to load data', onRetry }: ErrorDisplayProps) {
  const message = error instanceof Error ? error.message : String(error)
  return (
    <div className="bg-bg-surface border border-accent-red p-4">
      <div className="font-mono text-xs uppercase tracking-widest text-accent-red mb-1">
        // {title.toUpperCase()}
      </div>
      <p className="text-text-primary text-sm font-mono">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-3 px-3 py-1 border border-accent-green text-accent-green font-mono text-xs uppercase tracking-widest hover:bg-accent-green hover:text-bg-base transition-colors"
        >
          Retry
        </button>
      )}
    </div>
  )
}

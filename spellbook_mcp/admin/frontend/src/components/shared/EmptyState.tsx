interface EmptyStateProps {
  title: string
  message?: string
}

export function EmptyState({ title, message }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <h3 className="font-mono text-xs uppercase tracking-widest text-text-secondary">{title}</h3>
      {message && <p className="text-text-dim text-sm mt-2">{message}</p>}
    </div>
  )
}

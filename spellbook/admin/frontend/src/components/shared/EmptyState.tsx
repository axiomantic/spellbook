interface EmptyStateProps {
  title: string
  message?: string
}

function SparkleIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className="w-8 h-8 text-text-dim mb-3 opacity-50"
    >
      {/* Four-pointed star */}
      <path
        d="M12 2l1.8 5.2L19 9l-5.2 1.8L12 16l-1.8-5.2L5 9l5.2-1.8z"
        fill="currentColor"
      />
      {/* Small accent star */}
      <path
        d="M19 15l.7 2 2 .7-2 .7-.7 2-.7-2-2-.7 2-.7z"
        fill="currentColor"
        opacity="0.5"
      />
    </svg>
  )
}

export function EmptyState({ title, message }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <SparkleIcon />
      <h3 className="font-mono text-xs uppercase tracking-widest text-text-secondary">{title}</h3>
      {message && <p className="text-text-dim text-sm mt-2">{message}</p>}
    </div>
  )
}

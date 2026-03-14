export function LoadingSpinner({ className = '' }: { className?: string }) {
  return (
    <div className={`flex items-center justify-center ${className}`}>
      <div className="w-4 h-4 border border-accent-green border-t-transparent animate-spin" />
    </div>
  )
}

export function LoadingSpinner({ className = '' }: { className?: string }) {
  return (
    <div className={`flex items-center justify-center ${className}`}>
      <div className="relative w-6 h-6">
        {/* Outer rotating ring */}
        <div className="absolute inset-0 border border-accent-green/30 border-t-accent-green animate-spin" />
        {/* Inner sparkle dot */}
        <svg
          viewBox="0 0 24 24"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          className="absolute inset-0 w-full h-full p-1.5 text-accent-green animate-pulse"
        >
          <path
            d="M12 4l1 3 3 1-3 1-1 3-1-3-3-1 3-1z"
            fill="currentColor"
          />
        </svg>
      </div>
    </div>
  )
}

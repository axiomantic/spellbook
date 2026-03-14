export function Header() {
  return (
    <header className="h-10 border-b border-bg-border bg-bg-surface flex items-center px-4 justify-between">
      <div className="flex items-center gap-2">
        <div className="w-2 h-2 bg-accent-green animate-pulse" />
        <span className="font-mono text-xs text-text-secondary uppercase tracking-widest">
          Connected
        </span>
      </div>
    </header>
  )
}

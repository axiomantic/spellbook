import { useEventStream } from '../../hooks/useEventStream'

export function Header() {
  const { state: wsState } = useEventStream()

  const statusColor = wsState === 'connected' ? 'bg-accent-green' : 'bg-accent-red'
  const statusText =
    wsState === 'connected'
      ? 'Connected'
      : wsState === 'connecting'
        ? 'Connecting...'
        : 'Disconnected'

  return (
    <header className="h-10 border-b border-bg-border bg-bg-surface flex items-center px-4 justify-between">
      <div className="flex items-center gap-2">
        <div className={`w-2 h-2 ${statusColor} ${wsState === 'connected' ? 'animate-pulse' : ''}`} />
        <span className="font-mono text-xs text-text-secondary uppercase tracking-widest">
          {statusText}
        </span>
      </div>
    </header>
  )
}

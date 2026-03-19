import { useWebSocketContext } from '../../contexts/WebSocketContext'
import { useAuth } from '../../contexts/AuthContext'

export function Header() {
  const { connectionState } = useWebSocketContext()
  const { logout } = useAuth()

  const statusColor = connectionState === 'connected' ? 'bg-accent-green' : 'bg-accent-red'
  const statusText =
    connectionState === 'connected'
      ? 'Connected'
      : connectionState === 'connecting'
        ? 'Connecting...'
        : 'Disconnected'

  return (
    <header className="h-10 border-b border-bg-border bg-bg-surface flex items-center px-4 justify-between">
      <div className="flex items-center gap-2">
        <div className={`w-2 h-2 ${statusColor} ${connectionState === 'connected' ? 'animate-pulse' : ''}`} />
        <span className="font-mono text-xs text-text-secondary uppercase tracking-widest">
          {statusText}
        </span>
      </div>
      <button
        onClick={logout}
        className="font-mono text-xs text-text-dim uppercase tracking-widest hover:text-text-secondary"
      >
        // LOGOUT
      </button>
    </header>
  )
}

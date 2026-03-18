import { useDashboard } from '../hooks/useDashboard'
import { useFocusSummary } from '../hooks/useFocus'
import { useWebSocketContext } from '../contexts/WebSocketContext'
import { LoadingSpinner } from '../components/shared/LoadingSpinner'
import { ActivityFeed } from '../components/dashboard/ActivityFeed'

function formatUptime(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)}s`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  return `${h}h ${m}m`
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

interface StatCardProps {
  label: string
  value: string | number
  accent?: boolean
}

function StatCard({ label, value, accent }: StatCardProps) {
  return (
    <div className="bg-bg-surface border border-bg-border p-4">
      <div className="font-mono text-xs uppercase tracking-widest text-text-secondary mb-2">
        // {label}
      </div>
      <div className={`font-mono text-2xl ${accent ? 'text-accent-green' : 'text-text-primary'}`}>
        {value}
      </div>
    </div>
  )
}


export default function Dashboard() {
  const { data, isLoading, error } = useDashboard()
  const { data: focusSummary } = useFocusSummary()
  const { connectionState } = useWebSocketContext()

  if (isLoading) {
    return (
      <div className="p-8">
        <LoadingSpinner className="h-64" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-8">
        <div className="bg-bg-surface border border-accent-red p-4">
          <div className="font-mono text-xs uppercase tracking-widest text-accent-red mb-1">
            // ERROR
          </div>
          <p className="text-text-primary text-sm">
            {error instanceof Error ? error.message : 'Failed to load dashboard'}
          </p>
        </div>
      </div>
    )
  }

  if (!data) return null

  const { health, counts, recent_activity } = data

  return (
    <div className="p-8 space-y-8">
      {/* Header */}
      <div>
        <h1 className="font-mono text-xs uppercase tracking-widest text-text-secondary">
          // DASHBOARD
        </h1>
      </div>

      {/* Health Cards */}
      <div>
        <h2 className="font-mono text-xs uppercase tracking-widest text-text-dim mb-3">
          // HEALTH
        </h2>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <StatCard label="UPTIME" value={formatUptime(health.uptime_seconds)} accent />
          <StatCard label="VERSION" value={health.version} />
          <StatCard label="DB SIZE" value={formatBytes(health.db_size_bytes)} />
          <StatCard
            label="STATUS"
            value={health.status.toUpperCase()}
            accent={health.status === 'ok'}
          />
        </div>
      </div>

      {/* Status Board */}
      <div>
        <h2 className="font-mono text-xs uppercase tracking-widest text-text-dim mb-3">
          // STATUS
        </h2>
        <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
          <StatCard label="SESSIONS" value={counts.active_sessions} accent={counts.active_sessions > 0} />
          <StatCard label="MEMORIES" value={counts.total_memories} />
          <StatCard label="SECURITY 24H" value={counts.security_events_24h} accent={counts.security_events_24h > 0} />
          <StatCard label="SWARMS" value={counts.running_swarms} accent={counts.running_swarms > 0} />
          <StatCard label="EXPERIMENTS" value={counts.open_experiments} accent={counts.open_experiments > 0} />
          <StatCard label="FRACTAL GRAPHS" value={counts.fractal_graphs} />
        </div>
      </div>

      {/* Focus */}
      <div>
        <h2 className="font-mono text-xs uppercase tracking-widest text-text-dim mb-3">
          // FOCUS
        </h2>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <StatCard label="ACTIVE STACKS" value={focusSummary?.active_projects ?? '-'} accent={!!focusSummary && focusSummary.active_projects > 0} />
          <StatCard label="MAX DEPTH" value={focusSummary?.max_depth ?? '-'} />
          <StatCard label="CORRECTIONS 24H" value={focusSummary?.total_corrections_24h ?? '-'} accent={!!focusSummary && focusSummary.total_corrections_24h > 0} />
          <StatCard
            label="LLM / MCP WRONG"
            value={focusSummary ? `${focusSummary.llm_wrong_24h} / ${focusSummary.mcp_wrong_24h}` : '-'}
          />
        </div>
      </div>

      {/* Event Bus */}
      <div>
        <h2 className="font-mono text-xs uppercase tracking-widest text-text-dim mb-3">
          // EVENT BUS
        </h2>
        <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
          <StatCard label="SUBSCRIBERS" value={health.event_bus_subscribers} />
          <StatCard label="DROPPED" value={health.event_bus_dropped_events} accent={health.event_bus_dropped_events > 0} />
          <StatCard
            label="WEBSOCKET"
            value={connectionState.toUpperCase()}
            accent={connectionState === 'connected'}
          />
        </div>
      </div>

      {/* Recent Activity (live + polled) */}
      <div>
        <h2 className="font-mono text-xs uppercase tracking-widest text-text-dim mb-3">
          // RECENT ACTIVITY
        </h2>
        <div className="bg-bg-surface border border-bg-border p-4">
          <ActivityFeed initialItems={recent_activity} />
        </div>
      </div>
    </div>
  )
}

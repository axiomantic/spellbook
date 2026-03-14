import { useDashboard } from '../hooks/useDashboard'
import { LoadingSpinner } from '../components/shared/LoadingSpinner'
import { Badge } from '../components/shared/Badge'
import type { ActivityItem } from '../api/types'

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

function formatTimestamp(ts: string): string {
  try {
    const date = new Date(ts)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffMin = Math.floor(diffMs / 60000)
    if (diffMin < 1) return 'just now'
    if (diffMin < 60) return `${diffMin}m ago`
    const diffHr = Math.floor(diffMin / 60)
    if (diffHr < 24) return `${diffHr}h ago`
    return date.toLocaleDateString()
  } catch {
    return ts
  }
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

function ActivityRow({ item }: { item: ActivityItem }) {
  return (
    <div className="flex items-start gap-3 py-2 border-b border-bg-border last:border-b-0">
      <Badge label={item.type} />
      <span className="text-text-primary text-sm font-mono flex-1 truncate">
        {item.summary}
      </span>
      <span className="text-text-dim text-xs font-mono whitespace-nowrap">
        {formatTimestamp(item.timestamp)}
      </span>
    </div>
  )
}

export default function Dashboard() {
  const { data, isLoading, error } = useDashboard()

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

      {/* Event Bus */}
      <div>
        <h2 className="font-mono text-xs uppercase tracking-widest text-text-dim mb-3">
          // EVENT BUS
        </h2>
        <div className="grid grid-cols-2 gap-3">
          <StatCard label="SUBSCRIBERS" value={health.event_bus_subscribers} />
          <StatCard label="DROPPED" value={health.event_bus_dropped_events} accent={health.event_bus_dropped_events > 0} />
        </div>
      </div>

      {/* Recent Activity */}
      <div>
        <h2 className="font-mono text-xs uppercase tracking-widest text-text-dim mb-3">
          // RECENT ACTIVITY
        </h2>
        <div className="bg-bg-surface border border-bg-border p-4">
          {recent_activity.length === 0 ? (
            <p className="text-text-dim text-sm font-mono">No recent activity.</p>
          ) : (
            <div className="max-h-96 overflow-y-auto">
              {recent_activity.map((item, i) => (
                <ActivityRow key={`${item.timestamp}-${i}`} item={item} />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

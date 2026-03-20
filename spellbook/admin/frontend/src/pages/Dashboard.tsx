import { useDashboard } from '../hooks/useDashboard'
import { useFocusSummary } from '../hooks/useFocus'
import { useWebSocketContext } from '../contexts/WebSocketContext'
import { useToolFrequency, useAnalyticsSummary } from '../hooks/useAnalytics'
import { useHealthMatrix } from '../hooks/useHealth'
import { LoadingSpinner } from '../components/shared/LoadingSpinner'
import { ActivityFeed } from '../components/dashboard/ActivityFeed'
import { PageLayout } from '../components/layout/PageLayout'
import type { SubsystemHealth } from '../api/types'

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

function formatRelativeTime(ts: string | null): string {
  if (!ts) return 'never'
  try {
    const date = new Date(ts)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffMin = Math.floor(diffMs / 60000)
    if (diffMin < 1) return 'just now'
    if (diffMin < 60) return `${diffMin}m ago`
    const diffHr = Math.floor(diffMin / 60)
    if (diffHr < 24) return `${diffHr}h ago`
    const diffDays = Math.floor(diffHr / 24)
    return `${diffDays}d ago`
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

const statusColor: Record<SubsystemHealth['status'], string> = {
  healthy: 'bg-accent-green',
  idle: 'bg-accent-amber',
  error: 'bg-accent-red',
  missing: 'bg-text-dim',
}

const statusLabel: Record<SubsystemHealth['status'], string> = {
  healthy: 'OK',
  idle: 'IDLE',
  error: 'ERR',
  missing: 'N/A',
}

function DbHealthRow({ db }: { db: SubsystemHealth }) {
  const totalRows = db.tables.reduce((sum, t) => sum + t.row_count, 0)
  const lastActivity = db.tables
    .map((t) => t.last_activity)
    .filter(Boolean)
    .sort()
    .reverse()[0] ?? null

  return (
    <div className="flex items-center gap-3 py-1.5">
      <span className={`w-2 h-2 rounded-full flex-shrink-0 ${statusColor[db.status]}`} />
      <span className="font-mono text-xs text-text-primary w-28 truncate">{db.name}</span>
      <span className="font-mono text-xs text-text-dim w-12 text-right">{statusLabel[db.status]}</span>
      <span className="font-mono text-xs text-text-secondary w-20 text-right">
        {totalRows.toLocaleString()} rows
      </span>
      <span className="font-mono text-xs text-text-dim flex-1 text-right">
        {formatRelativeTime(lastActivity)}
      </span>
    </div>
  )
}

function TopToolsList() {
  const { data: toolData } = useToolFrequency()
  const { data: summary } = useAnalyticsSummary()

  const tools = toolData?.tools ?? []
  const top5 = tools.slice(0, 5)
  const maxCount = top5.length > 0 ? top5[0].count : 1

  if (top5.length === 0 && !summary) return null

  return (
    <div>
      <h2 className="font-mono text-xs uppercase tracking-widest text-text-dim mb-3">
        // TOP TOOLS
      </h2>
      <div className="bg-bg-surface border border-bg-border p-4">
        {summary && (
          <div className="flex gap-6 mb-4 pb-3 border-b border-bg-border">
            <div className="font-mono text-xs text-text-secondary">
              <span className="text-text-dim">TOTAL</span>{' '}
              <span className="text-text-primary">{summary.total_events.toLocaleString()}</span>
            </div>
            <div className="font-mono text-xs text-text-secondary">
              <span className="text-text-dim">TODAY</span>{' '}
              <span className="text-accent-green">{summary.events_today.toLocaleString()}</span>
            </div>
            <div className="font-mono text-xs text-text-secondary">
              <span className="text-text-dim">TOOLS</span>{' '}
              <span className="text-text-primary">{summary.unique_tools}</span>
            </div>
            <div className="font-mono text-xs text-text-secondary">
              <span className="text-text-dim">ERR%</span>{' '}
              <span className={summary.error_rate > 5 ? 'text-accent-red' : 'text-text-primary'}>
                {summary.error_rate.toFixed(1)}%
              </span>
            </div>
          </div>
        )}
        {top5.length === 0 ? (
          <p className="text-text-dim text-sm font-mono">No tool usage recorded.</p>
        ) : (
          <div className="space-y-2">
            {top5.map((tool) => (
              <div key={tool.tool_name} className="flex items-center gap-3">
                <span className="font-mono text-xs text-text-primary w-40 truncate" title={tool.tool_name}>
                  {tool.tool_name}
                </span>
                <div className="flex-1 h-1.5 bg-bg-border rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full ${tool.errors > 0 ? 'bg-accent-amber' : 'bg-accent-cyan'}`}
                    style={{ width: `${(tool.count / maxCount) * 100}%` }}
                  />
                </div>
                <span className="font-mono text-xs text-text-dim w-16 text-right">
                  {tool.count.toLocaleString()}
                  {tool.errors > 0 && (
                    <span className="text-accent-red ml-1">({tool.errors})</span>
                  )}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}


export default function Dashboard() {
  const { data, isLoading, error } = useDashboard()
  const { data: focusSummary } = useFocusSummary()
  const { data: healthMatrix } = useHealthMatrix()
  const { connectionState } = useWebSocketContext()

  if (isLoading) {
    return (
      <PageLayout segments={[{ label: 'DASHBOARD' }]}>
        <LoadingSpinner className="h-64" />
      </PageLayout>
    )
  }

  if (error) {
    return (
      <PageLayout segments={[{ label: 'DASHBOARD' }]}>
        <div className="bg-bg-surface border border-accent-red p-4">
          <div className="font-mono text-xs uppercase tracking-widest text-accent-red mb-1">
            // ERROR
          </div>
          <p className="text-text-primary text-sm">
            {error instanceof Error ? error.message : 'Failed to load dashboard'}
          </p>
        </div>
      </PageLayout>
    )
  }

  if (!data) return null

  const { health, counts, recent_activity } = data

  return (
    <PageLayout segments={[{ label: 'DASHBOARD' }]}>
      <div className="space-y-8">
      {/* Health + DB Matrix */}
      <div>
        <h2 className="font-mono text-xs uppercase tracking-widest text-text-dim mb-3">
          // HEALTH
        </h2>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
          <StatCard label="UPTIME" value={formatUptime(health.uptime_seconds)} accent />
          <StatCard label="VERSION" value={health.version} />
          <StatCard label="DB SIZE" value={formatBytes(health.db_size_bytes)} />
          <StatCard
            label="WEBSOCKET"
            value={connectionState.toUpperCase()}
            accent={connectionState === 'connected'}
          />
        </div>
        {healthMatrix && healthMatrix.databases.length > 0 && (
          <div className="bg-bg-surface border border-bg-border p-4">
            <div className="font-mono text-xs uppercase tracking-widest text-text-secondary mb-3">
              // DATABASES
            </div>
            {healthMatrix.databases.map((db) => (
              <DbHealthRow key={db.name} db={db} />
            ))}
          </div>
        )}
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

      {/* Top Tools */}
      <TopToolsList />

      {/* Event Bus (compact) */}
      <div className="bg-bg-surface border border-bg-border px-4 py-2 flex items-center gap-6">
        <span className="font-mono text-xs uppercase tracking-widest text-text-dim">// EVENT BUS</span>
        <span className="font-mono text-xs text-text-secondary">
          <span className="text-text-dim">SUBS</span> {health.event_bus_subscribers}
        </span>
        <span className="font-mono text-xs text-text-secondary">
          <span className="text-text-dim">DROPPED</span>{' '}
          <span className={health.event_bus_dropped_events > 0 ? 'text-accent-red' : 'text-text-primary'}>
            {health.event_bus_dropped_events}
          </span>
        </span>
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
    </PageLayout>
  )
}

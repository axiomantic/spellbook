import { useState } from 'react'
import { useSecurityEvents, useSecuritySummary } from '../hooks/useSecurity'
import { usePagination } from '../hooks/usePagination'
import { Badge } from '../components/shared/Badge'
import { Pagination } from '../components/shared/Pagination'
import { LoadingSpinner } from '../components/shared/LoadingSpinner'
import { EmptyState } from '../components/shared/EmptyState'
import type { SecurityEvent } from '../api/types'

const SEVERITY_LEVELS = ['all', 'critical', 'warning', 'info'] as const

const severityBorder: Record<string, string> = {
  critical: 'border-l-accent-red',
  error: 'border-l-accent-red',
  warning: 'border-l-accent-amber',
  info: 'border-l-accent-cyan',
}

const severityCardColor: Record<string, string> = {
  critical: 'text-accent-red',
  warning: 'text-accent-amber',
  info: 'text-accent-cyan',
}

function SummaryCards({ summary }: { summary: Record<string, number> }) {
  const levels = ['critical', 'warning', 'info']
  const total = Object.values(summary).reduce((a, b) => a + b, 0)

  return (
    <div className="grid grid-cols-4 gap-3 mb-6">
      <div className="card">
        <div className="section-header mb-1">Total</div>
        <div className="font-mono text-2xl text-text-primary">{total}</div>
      </div>
      {levels.map((level) => (
        <div key={level} className="card">
          <div className="section-header mb-1">{level}</div>
          <div className={`font-mono text-2xl ${severityCardColor[level] || 'text-text-dim'}`}>
            {summary[level] || 0}
          </div>
        </div>
      ))}
    </div>
  )
}

function EventRow({
  event,
  isExpanded,
  onToggle,
}: {
  event: SecurityEvent
  isExpanded: boolean
  onToggle: () => void
}) {
  const borderColor = severityBorder[event.severity] || 'border-l-text-dim'

  return (
    <div
      className={`card border-l-4 ${borderColor} mb-2 cursor-pointer hover:bg-bg-elevated transition-colors`}
      onClick={onToggle}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Badge label={event.severity} />
          <span className="font-mono text-xs text-text-secondary">{event.event_type}</span>
          {event.tool_name && (
            <span className="font-mono text-xs text-text-dim">{event.tool_name}</span>
          )}
        </div>
        <span className="font-mono text-xs text-text-dim">
          {new Date(event.created_at).toLocaleString()}
        </span>
      </div>
      {event.detail && (
        <p className="mt-1 font-mono text-xs text-text-secondary truncate">
          {event.detail}
        </p>
      )}
      {isExpanded && (
        <div className="mt-3 pt-3 border-t border-bg-border grid grid-cols-2 gap-2">
          <Detail label="Source" value={event.source} />
          <Detail label="Session" value={event.session_id} />
          <Detail label="Tool" value={event.tool_name} />
          <Detail label="Action" value={event.action_taken} />
          <Detail label="Event ID" value={String(event.id)} />
        </div>
      )}
    </div>
  )
}

function Detail({ label, value }: { label: string; value: string | null }) {
  if (!value) return null
  return (
    <div>
      <span className="font-mono text-xs text-text-dim uppercase">{label}: </span>
      <span className="font-mono text-xs text-text-secondary">{value}</span>
    </div>
  )
}

export function SecurityLog() {
  const [severity, setSeverity] = useState<string>('all')
  const [eventType, setEventType] = useState<string>('')
  const [since, setSince] = useState<string>('')
  const [until, setUntil] = useState<string>('')
  const [expandedId, setExpandedId] = useState<number | null>(null)
  const pagination = usePagination(50)

  const { data: summaryData } = useSecuritySummary()
  const { data, isLoading, isError } = useSecurityEvents({
    severity: severity === 'all' ? undefined : severity,
    event_type: eventType || undefined,
    since: since || undefined,
    until: until || undefined,
    page: pagination.page,
    per_page: pagination.per_page,
  })

  return (
    <div className="p-6">
      <h1 className="font-mono text-sm uppercase tracking-widest text-text-secondary mb-6">
        // Security Log
      </h1>

      {summaryData && <SummaryCards summary={summaryData.by_severity} />}

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3 mb-4">
        {/* Severity filter chips */}
        <div className="flex gap-1">
          {SEVERITY_LEVELS.map((level) => (
            <button
              key={level}
              onClick={() => { setSeverity(level); pagination.resetPage() }}
              className={`px-3 py-1 font-mono text-xs uppercase tracking-widest border transition-colors ${
                severity === level
                  ? 'border-accent-green text-accent-green bg-bg-elevated'
                  : 'border-bg-border text-text-secondary hover:border-accent-cyan'
              }`}
            >
              {level}
            </button>
          ))}
        </div>

        {/* Event type filter */}
        <input
          type="text"
          placeholder="Event type..."
          value={eventType}
          onChange={(e) => { setEventType(e.target.value); pagination.resetPage() }}
          className="bg-bg-surface border border-bg-border px-3 py-1 font-mono text-xs text-text-primary placeholder:text-text-dim focus:border-accent-green outline-none"
        />

        {/* Date range */}
        <input
          type="date"
          value={since}
          onChange={(e) => { setSince(e.target.value); pagination.resetPage() }}
          className="bg-bg-surface border border-bg-border px-3 py-1 font-mono text-xs text-text-primary focus:border-accent-green outline-none"
        />
        <span className="font-mono text-xs text-text-dim">to</span>
        <input
          type="date"
          value={until}
          onChange={(e) => { setUntil(e.target.value); pagination.resetPage() }}
          className="bg-bg-surface border border-bg-border px-3 py-1 font-mono text-xs text-text-primary focus:border-accent-green outline-none"
        />
      </div>

      {/* Event list */}
      {isLoading && <LoadingSpinner className="py-16" />}
      {isError && (
        <EmptyState title="Error loading events" message="Failed to fetch security events." />
      )}
      {data && data.events.length === 0 && (
        <EmptyState title="No events" message="No security events match the current filters." />
      )}
      {data && data.events.map((event) => (
        <EventRow
          key={event.id}
          event={event}
          isExpanded={expandedId === event.id}
          onToggle={() => setExpandedId(expandedId === event.id ? null : event.id)}
        />
      ))}

      {/* Pagination */}
      {data && data.pages > 1 && (
        <Pagination
          page={data.page}
          pages={data.pages}
          total={data.total}
          onPageChange={pagination.setPage}
        />
      )}
    </div>
  )
}

import { useState } from 'react'
import { useSecuritySummary } from '../hooks/useSecurity'
import { useListPage } from '../hooks/useListPage'
import { DataTable } from '../components/shared/DataTable'
import { FilterBar } from '../components/shared/FilterBar'
import { Badge } from '../components/shared/Badge'
import { ErrorDisplay } from '../components/shared/ErrorDisplay'
import { PageLayout } from '../components/layout/PageLayout'
import type { SecurityEvent } from '../api/types'
import type { ColumnDef } from '@tanstack/react-table'

const SEVERITY_OPTIONS = [
  { label: 'all', value: 'all' },
  { label: 'critical', value: 'critical' },
  { label: 'warning', value: 'warning' },
  { label: 'info', value: 'info' },
]

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

function Detail({ label, value }: { label: string; value: string | null }) {
  if (!value) return null
  return (
    <div>
      <span className="font-mono text-xs text-text-dim uppercase">{label}: </span>
      <span className="font-mono text-xs text-text-secondary">{value}</span>
    </div>
  )
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const columns: ColumnDef<SecurityEvent, any>[] = [
  {
    id: 'severity',
    header: 'Severity',
    accessorKey: 'severity',
    cell: ({ getValue }) => <Badge label={getValue() as string} />,
  },
  {
    id: 'event_type',
    header: 'Event Type',
    accessorKey: 'event_type',
  },
  {
    id: 'tool_name',
    header: 'Tool',
    accessorKey: 'tool_name',
    cell: ({ getValue }) => getValue() || '\u2014',
  },
  {
    id: 'detail',
    header: 'Detail',
    accessorKey: 'detail',
    cell: ({ getValue }) => {
      const v = getValue() as string | null
      return v ? (
        <span className="truncate max-w-xs inline-block">{v}</span>
      ) : (
        '\u2014'
      )
    },
  },
  {
    id: 'created_at',
    header: 'Time',
    accessorKey: 'created_at',
    cell: ({ getValue }) => new Date(getValue() as string).toLocaleString(),
  },
]

export function SecurityLog() {
  const [expandedId, setExpandedId] = useState<number | null>(null)

  const listPage = useListPage<SecurityEvent>({
    queryKey: ['security-events'],
    endpoint: '/api/security/events',
    defaultPerPage: 50,
  })

  const { data: summaryData } = useSecuritySummary()

  const activeSeverity = listPage.filters.severity || 'all'

  const handleSeverityChange = (value: string) => {
    if (value === 'all') {
      const { severity: _, ...rest } = listPage.filters
      listPage.setFilters(rest)
    } else {
      listPage.setFilters({ ...listPage.filters, severity: value })
    }
  }

  const handleRowClick = (event: SecurityEvent) => {
    setExpandedId(expandedId === event.id ? null : event.id)
  }

  const expandedEvent = listPage.data.find((e) => e.id === expandedId)

  return (
    <PageLayout segments={[{ label: 'SECURITY LOG' }]}>
      {summaryData && <SummaryCards summary={summaryData.by_severity} />}

      {/* Severity filter */}
      <div className="flex flex-wrap items-center gap-3 mb-4">
        <FilterBar
          type="chips"
          options={SEVERITY_OPTIONS}
          value={activeSeverity}
          onChange={handleSeverityChange}
        />
      </div>

      {/* Error state */}
      {listPage.isError && (
        <ErrorDisplay error={listPage.error} title="Failed to load security events" />
      )}

      {/* Event table */}
      <DataTable<SecurityEvent>
        columns={columns}
        emptyTitle="No events"
        emptyMessage="No security events match the current filters."
        onRowClick={handleRowClick}
        {...listPage.tableProps}
      />

      {/* Expanded detail */}
      {expandedEvent && (
        <div className="mt-2 p-3 card border-l-4 border-l-accent-cyan">
          <div className="grid grid-cols-2 gap-2">
            <Detail label="Source" value={expandedEvent.source} />
            <Detail label="Session" value={expandedEvent.session_id} />
            <Detail label="Tool" value={expandedEvent.tool_name} />
            <Detail label="Action" value={expandedEvent.action_taken} />
            <Detail label="Event ID" value={String(expandedEvent.id)} />
          </div>
        </div>
      )}
    </PageLayout>
  )
}

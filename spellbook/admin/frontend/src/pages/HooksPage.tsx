import { useCallback, useMemo, useState } from 'react'
import { createColumnHelper } from '@tanstack/react-table'
import {
  useHookEvents,
  useHookMetrics,
  type HookEvent,
} from '../hooks/useHooks'
import { DataTable } from '../components/shared/DataTable'
import { FilterBar } from '../components/shared/FilterBar'
import { MetricCard } from '../components/shared/MetricCard'
import { ErrorDisplay } from '../components/shared/ErrorDisplay'
import { PageLayout } from '../components/layout/PageLayout'

// Match the WorkerLLMPage convention (time windows, not row counts) so the
// "1h / 6h / 24h" chip row behaves identically across both observability
// pages.
type WindowHours = 1 | 6 | 24

const WINDOW_OPTIONS = [
  { value: '1', label: '1h' },
  { value: '6', label: '6h' },
  { value: '24', label: '24h' },
]

const EVENT_OPTIONS = [
  { value: '', label: 'All' },
  { value: 'PreToolUse', label: 'PreToolUse' },
  { value: 'PostToolUse', label: 'PostToolUse' },
  { value: 'UserPromptSubmit', label: 'UserPromptSubmit' },
  { value: 'Stop', label: 'Stop' },
  { value: 'PreCompact', label: 'PreCompact' },
  { value: 'SessionStart', label: 'SessionStart' },
]

function formatTime(ts: string): string {
  try {
    return new Date(ts).toLocaleString()
  } catch {
    return ts
  }
}

function formatNumber(value: number | null | undefined): number | null {
  if (value === null || value === undefined) return null
  return Math.round(value)
}

function formatPercent(value: number | null | undefined): string | null {
  if (value === null || value === undefined) return null
  return (value * 100).toFixed(1)
}

const columnHelper = createColumnHelper<HookEvent>()

export function HooksPage() {
  const [windowHours, setWindowHours] = useState<WindowHours>(24)
  const [eventName, setEventName] = useState<string>('')
  const [hookName, setHookName] = useState<string>('')

  const filters = useMemo(() => {
    const f: Record<string, string> = {}
    if (eventName) f.event_name = eventName
    if (hookName) f.hook_name = hookName
    return f
  }, [eventName, hookName])

  const listPage = useHookEvents(filters)
  const metricsQuery = useHookMetrics(windowHours)
  const metrics = metricsQuery.data

  const handleWindowChange = useCallback((value: string) => {
    const parsed = Number(value) as WindowHours
    if (parsed === 1 || parsed === 6 || parsed === 24) {
      setWindowHours(parsed)
    }
  }, [])

  // Drive the Error Rate variant off the rate itself so a nonzero rate
  // renders red instead of always green.
  const errorRate = metrics?.summary?.error_rate ?? null
  const errorVariant =
    errorRate !== null && errorRate > 0 ? 'error' : 'success'

  const columns = useMemo(
    () => [
      columnHelper.accessor('timestamp', {
        header: 'Timestamp',
        cell: (info) => (
          <span className="text-text-dim">{formatTime(info.getValue())}</span>
        ),
      }),
      columnHelper.accessor('hook_name', {
        header: 'Hook',
        cell: (info) => (
          <span className="text-text-secondary">{info.getValue()}</span>
        ),
      }),
      columnHelper.accessor('event_name', {
        header: 'Event',
        cell: (info) => (
          <span className="text-text-primary">{info.getValue()}</span>
        ),
      }),
      columnHelper.accessor('tool_name', {
        header: 'Tool',
        cell: (info) => (
          <span className="text-text-dim">{info.getValue() ?? '--'}</span>
        ),
      }),
      columnHelper.accessor('duration_ms', {
        header: 'Duration (ms)',
        cell: (info) => (
          <span className="text-text-secondary tabular-nums">
            {info.getValue()}
          </span>
        ),
      }),
      columnHelper.accessor('exit_code', {
        header: 'Exit',
        cell: (info) => {
          const value = info.getValue()
          const color =
            value === 0 ? 'text-accent-green' : 'text-accent-red'
          return (
            <span className={`font-mono text-xs tabular-nums ${color}`}>
              {value}
            </span>
          )
        },
      }),
      columnHelper.accessor('error', {
        header: 'Error',
        cell: (info) => (
          <span className="text-text-dim truncate">
            {info.getValue() ?? '--'}
          </span>
        ),
      }),
    ],
    [],
  )

  return (
    <PageLayout segments={[{ label: 'HOOK EVENTS' }]}>
      <div className="flex gap-3 mb-4 items-center">
        <FilterBar
          type="chips"
          options={WINDOW_OPTIONS}
          value={String(windowHours)}
          onChange={handleWindowChange}
        />
        <FilterBar
          type="chips"
          options={EVENT_OPTIONS}
          value={eventName}
          onChange={setEventName}
        />
        <input
          type="text"
          placeholder="Filter by hook_name..."
          value={hookName}
          onChange={(e) => setHookName(e.target.value)}
          className="bg-bg-surface border border-bg-border px-3 py-1 font-mono text-xs text-text-primary focus:border-accent-green outline-none"
        />
      </div>
      <div className="grid grid-cols-4 gap-3 mb-4">
        <MetricCard
          label="Total"
          value={metrics?.total ?? null}
        />
        <MetricCard
          label="Avg Duration"
          value={formatNumber(metrics?.summary?.avg_duration_ms ?? null)}
          unit="ms"
        />
        <MetricCard
          label="P95 Duration"
          value={formatNumber(metrics?.summary?.p95_duration_ms ?? null)}
          unit="ms"
        />
        <MetricCard
          label="Error Rate"
          value={formatPercent(errorRate)}
          unit="%"
          variant={errorVariant}
        />
      </div>
      {listPage.isError && (
        <ErrorDisplay
          error={listPage.error}
          title="Failed to load hook events"
        />
      )}
      <DataTable
        columns={columns}
        {...listPage.tableProps}
        emptyTitle="No Events"
        emptyMessage="No hook events recorded yet."
      />
    </PageLayout>
  )
}

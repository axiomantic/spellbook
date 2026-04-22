import { useCallback, useMemo, useState } from 'react'
import { createColumnHelper } from '@tanstack/react-table'
import {
  useWorkerLLMCalls,
  useWorkerLLMMetrics,
  type WorkerLLMCall,
} from '../hooks/useWorkerLLM'
import { DataTable } from '../components/shared/DataTable'
import { FilterBar } from '../components/shared/FilterBar'
import { MetricCard } from '../components/shared/MetricCard'
import { ErrorBreakdownCard } from '../components/shared/ErrorBreakdownCard'
import { ErrorDisplay } from '../components/shared/ErrorDisplay'
import { PageLayout } from '../components/layout/PageLayout'

type WindowHours = 1 | 6 | 24

const WINDOW_OPTIONS = [
  { value: '1', label: '1h' },
  { value: '6', label: '6h' },
  { value: '24', label: '24h' },
]

const STATUS_OPTIONS = [
  { value: '', label: 'All' },
  { value: 'success', label: 'Success' },
  { value: 'error', label: 'Error' },
  { value: 'timeout', label: 'Timeout' },
  { value: 'fail_open', label: 'Fail Open' },
]

function formatTime(ts: string): string {
  try {
    return new Date(ts).toLocaleString()
  } catch {
    return ts
  }
}

function formatPercent(value: number | null | undefined): string | null {
  if (value === null || value === undefined) return null
  return (value * 100).toFixed(1)
}

function formatNumber(value: number | null | undefined): number | null {
  if (value === null || value === undefined) return null
  return Math.round(value)
}

const columnHelper = createColumnHelper<WorkerLLMCall>()

export function WorkerLLMPage() {
  const [windowHours, setWindowHours] = useState<WindowHours>(24)
  const [task, setTask] = useState<string>('')
  const [status, setStatus] = useState<string>('')

  const since = useMemo(() => {
    const now = Date.now()
    return new Date(now - windowHours * 3600 * 1000).toISOString()
  }, [windowHours])

  const filters = useMemo(() => {
    const f: Record<string, string> = { since }
    if (task) f.task = task
    if (status) f.status = status
    return f
  }, [since, task, status])

  const listPage = useWorkerLLMCalls(filters)
  const metricsQuery = useWorkerLLMMetrics(windowHours)
  const metrics = metricsQuery.data

  const handleWindowChange = useCallback((value: string) => {
    const parsed = Number(value) as WindowHours
    if (parsed === 1 || parsed === 6 || parsed === 24) {
      setWindowHours(parsed)
    }
  }, [])

  const columns = useMemo(
    () => [
      columnHelper.accessor('timestamp', {
        header: 'Timestamp',
        cell: (info) => (
          <span className="text-text-dim">{formatTime(info.getValue())}</span>
        ),
      }),
      columnHelper.accessor('task', {
        header: 'Task',
        cell: (info) => (
          <span className="text-text-primary">{info.getValue()}</span>
        ),
      }),
      columnHelper.accessor('model', {
        header: 'Model',
        cell: (info) => (
          <span className="text-text-secondary">{info.getValue()}</span>
        ),
      }),
      columnHelper.accessor('status', {
        header: 'Status',
        cell: (info) => {
          const value = info.getValue()
          const color =
            value === 'success'
              ? 'text-accent-green'
              : value === 'error' || value === 'timeout'
                ? 'text-accent-red'
                : 'text-accent-amber'
          return (
            <span className={`font-mono text-xs uppercase ${color}`}>{value}</span>
          )
        },
      }),
      columnHelper.accessor('latency_ms', {
        header: 'Latency (ms)',
        cell: (info) => (
          <span className="text-text-secondary tabular-nums">
            {info.getValue()}
          </span>
        ),
      }),
      columnHelper.accessor('error', {
        header: 'Error',
        cell: (info) => (
          <span className="text-text-dim truncate">{info.getValue() ?? '--'}</span>
        ),
      }),
    ],
    [],
  )

  return (
    <PageLayout segments={[{ label: 'WORKER LLM CALLS' }]}>
      <div className="flex gap-3 mb-4 items-center">
        <FilterBar
          type="chips"
          options={WINDOW_OPTIONS}
          value={String(windowHours)}
          onChange={handleWindowChange}
        />
        <FilterBar
          type="chips"
          options={STATUS_OPTIONS}
          value={status}
          onChange={setStatus}
        />
        <input
          type="text"
          placeholder="Filter by task..."
          value={task}
          onChange={(e) => setTask(e.target.value)}
          className="bg-bg-surface border border-bg-border px-3 py-1 font-mono text-xs text-text-primary focus:border-accent-green outline-none"
        />
      </div>
      <div className="grid grid-cols-3 gap-3 mb-4">
        <MetricCard
          label="Success Rate"
          value={formatPercent(metrics?.success_rate ?? null)}
          unit="%"
          variant="success"
        />
        <MetricCard
          label="P95 Latency"
          value={formatNumber(metrics?.p95_latency_ms ?? null)}
          unit="ms"
        />
        <MetricCard
          label="P99 Latency"
          value={formatNumber(metrics?.p99_latency_ms ?? null)}
          unit="ms"
        />
      </div>
      <div className="mb-4">
        <ErrorBreakdownCard breakdown={metrics?.error_breakdown ?? null} />
      </div>
      {listPage.isError && (
        <ErrorDisplay error={listPage.error} title="Failed to load worker LLM calls" />
      )}
      <DataTable
        columns={columns}
        {...listPage.tableProps}
        emptyTitle="No Calls"
        emptyMessage="No worker LLM calls recorded in the selected window."
      />
    </PageLayout>
  )
}

import { useState, useCallback, useMemo } from 'react'
import { createColumnHelper } from '@tanstack/react-table'
import { useListPage } from '../hooks/useListPage'
import { DataTable } from '../components/shared/DataTable'
import { FilterBar } from '../components/shared/FilterBar'
import { ErrorDisplay } from '../components/shared/ErrorDisplay'
import { PageLayout } from '../components/layout/PageLayout'
import type { CorrectionEvent } from '../api/types'

const CORRECTION_TYPE_OPTIONS = [
  { value: '', label: 'All' },
  { value: 'llm_wrong', label: 'LLM Wrong' },
  { value: 'mcp_wrong', label: 'MCP Wrong' },
]

const PERIOD_OPTIONS = [
  { value: '7d', label: '7 days' },
  { value: '30d', label: '30 days' },
  { value: 'all', label: 'All time' },
]

function shortenPath(path: string): string {
  const segments = path.split('/')
  return segments.length > 2 ? segments.slice(-2).join('/') : path
}

function formatTime(ts: string): string {
  try {
    return new Date(ts).toLocaleString()
  } catch {
    return ts
  }
}

function CorrectionTypeBadge({ type }: { type: 'llm_wrong' | 'mcp_wrong' }) {
  const colors =
    type === 'llm_wrong'
      ? 'text-accent-red border-accent-red'
      : 'text-accent-green border-accent-green'
  return (
    <span
      className={`inline-block px-2 py-0.5 border font-mono text-xs uppercase tracking-widest ${colors}`}
    >
      {type === 'llm_wrong' ? 'LLM' : 'MCP'}
    </span>
  )
}

interface ExpandedRowDetailProps {
  event: CorrectionEvent
  onCollapse: () => void
}

function ExpandedRowDetail({ event, onCollapse }: ExpandedRowDetailProps) {
  return (
    <div className="card mt-2 mb-4">
      <div className="flex items-center justify-between mb-3">
        <span className="font-mono text-xs uppercase tracking-widest text-text-dim">
          // Stack Diff
        </span>
        <button
          onClick={onCollapse}
          aria-label="collapse"
          className="font-mono text-xs text-text-dim hover:text-accent-cyan transition-colors"
        >
          [-]
        </button>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <div className="font-mono text-xs uppercase tracking-widest text-text-dim mb-2">
            Old Stack
          </div>
          <pre className="font-mono text-xs text-text-secondary bg-bg-surface border border-bg-border p-2 overflow-auto max-h-48">
            {JSON.stringify(event.old_stack, null, 2)}
          </pre>
        </div>
        <div>
          <div className="font-mono text-xs uppercase tracking-widest text-text-dim mb-2">
            New Stack
          </div>
          <pre className="font-mono text-xs text-text-secondary bg-bg-surface border border-bg-border p-2 overflow-auto max-h-48">
            {JSON.stringify(event.new_stack, null, 2)}
          </pre>
        </div>
      </div>
    </div>
  )
}

const columnHelper = createColumnHelper<CorrectionEvent>()

export function CorrectionsPage() {
  const [expandedId, setExpandedId] = useState<number | null>(null)

  const listPage = useListPage<CorrectionEvent>({
    queryKey: ['corrections'],
    endpoint: '/api/focus/corrections',
    defaultSort: { column: 'created_at', order: 'desc' },
  })

  const correctionTypeValue = listPage.filters.correction_type || ''
  const periodValue = listPage.filters.period || '7d'

  const handleCorrectionTypeChange = useCallback(
    (value: string) => {
      listPage.setFilters({
        ...listPage.filters,
        correction_type: value,
        period: listPage.filters.period || '7d',
      })
    },
    [listPage]
  )

  const handlePeriodChange = useCallback(
    (value: string) => {
      listPage.setFilters({
        ...listPage.filters,
        period: value,
        correction_type: listPage.filters.correction_type || '',
      })
    },
    [listPage]
  )

  const columns = useMemo(
    () => [
      columnHelper.accessor('created_at', {
        header: 'Timestamp',
        cell: (info) => (
          <span className="text-text-dim">{formatTime(info.getValue())}</span>
        ),
      }),
      columnHelper.accessor('project_path', {
        header: 'Project',
        cell: (info) => shortenPath(info.getValue()),
      }),
      columnHelper.accessor('correction_type', {
        header: 'Type',
        cell: (info) => <CorrectionTypeBadge type={info.getValue()} />,
      }),
      columnHelper.accessor('diff_summary', {
        header: 'Diff Summary',
        cell: (info) => (
          <span className="text-text-secondary">{info.getValue() || '--'}</span>
        ),
      }),
      columnHelper.display({
        id: 'expand',
        header: '',
        cell: (info) => {
          const isExpanded = expandedId === info.row.original.id
          return (
            <button
              aria-label={isExpanded ? 'collapse' : 'expand'}
              onClick={(e) => {
                e.stopPropagation()
                setExpandedId(isExpanded ? null : info.row.original.id)
              }}
              className="font-mono text-xs text-text-dim hover:text-accent-cyan transition-colors"
            >
              {isExpanded ? '[-]' : '[+]'}
            </button>
          )
        },
      }),
    ],
    [expandedId]
  )

  const expandedEvent = expandedId !== null
    ? listPage.data.find((e) => e.id === expandedId)
    : null

  return (
    <PageLayout
      segments={[{ label: 'CORRECTION LOG' }]}
    >
      <div className="flex gap-3 mb-4">
        <FilterBar
          type="chips"
          options={CORRECTION_TYPE_OPTIONS}
          value={correctionTypeValue}
          onChange={handleCorrectionTypeChange}
        />
        <FilterBar
          type="chips"
          options={PERIOD_OPTIONS}
          value={periodValue}
          onChange={handlePeriodChange}
        />
      </div>
      {listPage.isError && (
        <ErrorDisplay error={listPage.error} title="Failed to load corrections" />
      )}
      <DataTable
        columns={columns}
        {...listPage.tableProps}
        emptyTitle="No Corrections"
        emptyMessage="No correction events recorded for the selected filters."
      />
      {expandedEvent && (
        <ExpandedRowDetail
          event={expandedEvent}
          onCollapse={() => setExpandedId(null)}
        />
      )}
    </PageLayout>
  )
}

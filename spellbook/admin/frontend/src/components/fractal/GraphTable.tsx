import { useCallback, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { createColumnHelper } from '@tanstack/react-table'
import { Badge } from '../shared/Badge'
import { DataTable } from '../shared/DataTable'
import { SearchBar } from '../shared/SearchBar'
import { FilterBar } from '../shared/FilterBar'
import { useListPage } from '../../hooks/useListPage'
import type { FractalGraphSummary } from '../../api/types'

type GraphRow = FractalGraphSummary & { total_nodes: number }

function formatTimestamp(ts: string): string {
  if (!ts) return '--'
  try {
    return new Date(ts).toLocaleString()
  } catch {
    return ts
  }
}

function truncateSeed(seed: string, max = 60): string {
  if (seed.length <= max) return seed
  return seed.slice(0, max) + '...'
}

const columnHelper = createColumnHelper<GraphRow>()

const statusFilterOptions = [
  { label: 'All statuses', value: '' },
  { label: 'active', value: 'active' },
  { label: 'paused', value: 'paused' },
  { label: 'completed', value: 'completed' },
  { label: 'error', value: 'error' },
  { label: 'budget_exhausted', value: 'budget_exhausted' },
]

export function GraphTable() {
  const navigate = useNavigate()

  const listPage = useListPage<GraphRow>({
    queryKey: ['fractal', 'graphs'],
    endpoint: '/api/fractal/graphs',
    defaultSort: { column: 'created_at', order: 'desc' },
  })

  const columns = useMemo(
    () => [
      columnHelper.accessor('seed', {
        header: 'Seed',
        enableSorting: true,
        cell: (info) => truncateSeed(info.getValue()),
      }),
      columnHelper.accessor('status', {
        header: 'Status',
        enableSorting: true,
        cell: (info) => <Badge label={info.getValue()} />,
      }),
      columnHelper.accessor('intensity', {
        header: 'Intensity',
        enableSorting: false,
        cell: (info) => <Badge label={info.getValue()} variant="info" />,
      }),
      columnHelper.accessor('total_nodes', {
        header: 'Nodes',
        enableSorting: false,
      }),
      columnHelper.accessor('project_dir', {
        header: 'Project',
        enableSorting: false,
        cell: (info) => info.getValue() || '--',
      }),
      columnHelper.accessor('created_at', {
        header: 'Created',
        enableSorting: true,
        cell: (info) => formatTimestamp(info.getValue()),
      }),
      columnHelper.accessor('updated_at', {
        header: 'Updated',
        enableSorting: true,
        cell: (info) => formatTimestamp(info.getValue()),
      }),
    ],
    []
  )

  const handleRowClick = useCallback(
    (row: GraphRow) => {
      navigate(`/fractal/${row.id}`)
    },
    [navigate]
  )

  const hasFilters = listPage.search || Object.values(listPage.filters).some((v) => v)

  const emptyMessage = hasFilters
    ? 'No graphs match the current filters.'
    : 'No fractal graphs have been created yet.'

  return (
    <div className="flex flex-col h-full p-4 space-y-4">
      {/* Filters row */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="flex-1 min-w-[200px]">
          <SearchBar
            value={listPage.search}
            onChange={listPage.setSearch}
            placeholder="Search by seed text..."
          />
        </div>

        <FilterBar
          type="select"
          options={statusFilterOptions}
          value={listPage.filters.status || ''}
          onChange={(value) =>
            listPage.setFilters({ ...listPage.filters, status: value })
          }
        />

        <div className="min-w-[180px]">
          <SearchBar
            value={listPage.filters.project_dir || ''}
            onChange={(value) =>
              listPage.setFilters({ ...listPage.filters, project_dir: value })
            }
            placeholder="Filter by project dir..."
          />
        </div>
      </div>

      {/* Table */}
      <DataTable<GraphRow>
        {...listPage.tableProps}
        columns={columns}
        onRowClick={handleRowClick}
        emptyTitle="No Graphs"
        emptyMessage={emptyMessage}
      />
    </div>
  )
}

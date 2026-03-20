import { useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { Badge } from '../shared/Badge'
import { Pagination } from '../shared/Pagination'
import { LoadingSpinner } from '../shared/LoadingSpinner'
import { EmptyState } from '../shared/EmptyState'
import { useFractalGraphList, type FractalGraphListParams } from '../../hooks/useFractalGraph'

type SortField = 'created_at' | 'updated_at' | 'seed' | 'status'
type SortOrder = 'asc' | 'desc'

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

interface SortHeaderProps {
  label: string
  field: SortField
  currentSort: SortField | undefined
  currentOrder: SortOrder
  onSort: (field: SortField) => void
}

function SortHeader({ label, field, currentSort, currentOrder, onSort }: SortHeaderProps) {
  const isActive = currentSort === field
  const arrow = isActive ? (currentOrder === 'asc' ? ' ^' : ' v') : ''

  return (
    <th
      className="px-3 py-2 text-left cursor-pointer select-none hover:text-accent-cyan transition-colors"
      onClick={() => onSort(field)}
    >
      <span className="font-mono text-xs uppercase tracking-widest text-text-dim">
        {label}{arrow}
      </span>
    </th>
  )
}

export function GraphTable() {
  const navigate = useNavigate()
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [projectDirFilter, setProjectDirFilter] = useState('')
  const [sortBy, setSortBy] = useState<SortField | undefined>(undefined)
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc')

  const params: FractalGraphListParams = {
    page,
    search: search || undefined,
    status: statusFilter || undefined,
    project_dir: projectDirFilter || undefined,
    sort_by: sortBy,
    sort_order: sortOrder,
  }

  const { data, isLoading } = useFractalGraphList(params)

  const handleSort = useCallback((field: SortField) => {
    setSortBy((prev) => {
      if (prev === field) {
        setSortOrder((o) => (o === 'asc' ? 'desc' : 'asc'))
        return field
      }
      setSortOrder('desc')
      return field
    })
    setPage(1)
  }, [])

  const handleRowClick = useCallback((graphId: string) => {
    navigate(`/fractal/${graphId}`)
  }, [navigate])

  const statusOptions = ['active', 'paused', 'completed', 'error', 'budget_exhausted']

  return (
    <div className="flex flex-col h-full p-4 space-y-4">
      {/* Filters row */}
      <div className="flex items-center gap-3 flex-wrap">
        {/* Search */}
        <div className="flex-1 min-w-[200px]">
          <input
            type="text"
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1) }}
            placeholder="Search by seed text..."
            className="w-full px-3 py-2 bg-bg-surface border border-bg-border font-mono text-xs text-text-primary
                       placeholder:text-text-dim focus:border-accent-cyan focus:outline-none transition-colors"
          />
        </div>

        {/* Status filter */}
        <select
          value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value); setPage(1) }}
          className="px-3 py-2 bg-bg-surface border border-bg-border font-mono text-xs text-text-primary
                     focus:border-accent-cyan focus:outline-none transition-colors appearance-none cursor-pointer"
        >
          <option value="">All statuses</option>
          {statusOptions.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>

        {/* Project dir filter */}
        <input
          type="text"
          value={projectDirFilter}
          onChange={(e) => { setProjectDirFilter(e.target.value); setPage(1) }}
          placeholder="Filter by project dir..."
          className="px-3 py-2 bg-bg-surface border border-bg-border font-mono text-xs text-text-primary
                     placeholder:text-text-dim focus:border-accent-cyan focus:outline-none transition-colors min-w-[180px]"
        />
      </div>

      {/* Table */}
      {isLoading ? (
        <LoadingSpinner className="h-64" />
      ) : !data?.graphs.length ? (
        <EmptyState
          title="No Graphs"
          message={search || statusFilter || projectDirFilter
            ? 'No graphs match the current filters.'
            : 'No fractal graphs have been created yet.'}
        />
      ) : (
        <div className="flex-1 overflow-auto">
          <table className="w-full border-collapse">
            <thead>
              <tr className="border-b border-bg-border">
                <SortHeader label="Seed" field="seed" currentSort={sortBy} currentOrder={sortOrder} onSort={handleSort} />
                <SortHeader label="Status" field="status" currentSort={sortBy} currentOrder={sortOrder} onSort={handleSort} />
                <th className="px-3 py-2 text-left">
                  <span className="font-mono text-xs uppercase tracking-widest text-text-dim">Intensity</span>
                </th>
                <th className="px-3 py-2 text-left">
                  <span className="font-mono text-xs uppercase tracking-widest text-text-dim">Nodes</span>
                </th>
                <th className="px-3 py-2 text-left">
                  <span className="font-mono text-xs uppercase tracking-widest text-text-dim">Project</span>
                </th>
                <SortHeader label="Created" field="created_at" currentSort={sortBy} currentOrder={sortOrder} onSort={handleSort} />
                <SortHeader label="Updated" field="updated_at" currentSort={sortBy} currentOrder={sortOrder} onSort={handleSort} />
              </tr>
            </thead>
            <tbody>
              {data.graphs.map((g) => (
                <tr
                  key={g.id}
                  onClick={() => handleRowClick(g.id)}
                  className="border-b border-bg-border cursor-pointer hover:bg-bg-elevated transition-colors"
                >
                  <td className="px-3 py-2">
                    <span className="font-mono text-xs text-text-primary">
                      {truncateSeed(g.seed)}
                    </span>
                  </td>
                  <td className="px-3 py-2">
                    <Badge label={g.status} />
                  </td>
                  <td className="px-3 py-2">
                    <Badge label={g.intensity} variant="info" />
                  </td>
                  <td className="px-3 py-2">
                    <span className="font-mono text-xs text-text-secondary">
                      {g.total_nodes}
                    </span>
                  </td>
                  <td className="px-3 py-2">
                    <span className="font-mono text-xs text-text-dim truncate block max-w-[200px]">
                      {g.project_dir || '--'}
                    </span>
                  </td>
                  <td className="px-3 py-2">
                    <span className="font-mono text-xs text-text-dim">
                      {formatTimestamp(g.created_at)}
                    </span>
                  </td>
                  <td className="px-3 py-2">
                    <span className="font-mono text-xs text-text-dim">
                      {formatTimestamp(g.updated_at)}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination */}
      {data && data.pages > 1 && (
        <Pagination
          page={data.page}
          pages={data.pages}
          total={data.total}
          onPageChange={setPage}
        />
      )}
    </div>
  )
}

import { useState, useCallback, useEffect, useRef } from 'react'
import {
  useMemories,
  useMemory,
  useUpdateMemory,
  useDeleteMemory,
  useConsolidate,
  useMemoryNamespaces,
  type MemoryListParams,
  type MemoryDetail,
} from '../hooks/useMemories'
import { usePagination } from '../hooks/usePagination'
import { LoadingSpinner } from '../components/shared/LoadingSpinner'
import { EmptyState } from '../components/shared/EmptyState'
import { Badge } from '../components/shared/Badge'
import { Pagination } from '../components/shared/Pagination'
import { PageLayout } from '../components/layout/PageLayout'
import type { MemoryItem } from '../api/types'

// -- Search bar with debounce --

function MemorySearch({
  value,
  onChange,
}: {
  value: string
  onChange: (q: string) => void
}) {
  const [local, setLocal] = useState(value)
  const timerRef = useRef<ReturnType<typeof setTimeout>>()

  useEffect(() => {
    setLocal(value)
  }, [value])

  const handleChange = useCallback(
    (v: string) => {
      setLocal(v)
      clearTimeout(timerRef.current)
      timerRef.current = setTimeout(() => onChange(v), 300)
    },
    [onChange],
  )

  useEffect(() => () => clearTimeout(timerRef.current), [])

  return (
    <input
      type="text"
      placeholder="Search memories (FTS)..."
      value={local}
      onChange={(e) => handleChange(e.target.value)}
      className="flex-1 bg-bg-elevated border border-bg-border px-3 py-2 text-sm text-text-primary font-mono focus:outline-none focus:border-accent-green"
    />
  )
}

// -- Namespace filter dropdown --

function NamespaceFilter({
  value,
  onChange,
}: {
  value: string
  onChange: (ns: string) => void
}) {
  const { data } = useMemoryNamespaces()
  const namespaces = data?.namespaces ?? []

  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="bg-bg-elevated border border-bg-border px-3 py-2 text-sm text-text-primary font-mono focus:outline-none focus:border-accent-green"
    >
      <option value="">All namespaces</option>
      {namespaces.map((ns) => (
        <option key={ns} value={ns}>
          {ns}
        </option>
      ))}
    </select>
  )
}

// -- Sortable table header --

function SortHeader({
  label,
  field,
  currentSort,
  currentOrder,
  onSort,
}: {
  label: string
  field: string
  currentSort: string
  currentOrder: string
  onSort: (field: string) => void
}) {
  const isActive = currentSort === field
  const arrow = isActive ? (currentOrder === 'asc' ? ' ^' : ' v') : ''

  return (
    <th
      className="px-3 py-2 text-left cursor-pointer select-none hover:text-accent-cyan transition-colors"
      onClick={() => onSort(field)}
    >
      {label}
      <span className="text-accent-green">{arrow}</span>
    </th>
  )
}

// -- Citation list in detail panel --

function CitationList({ citations }: { citations: MemoryDetail['citations'] }) {
  if (!citations || citations.length === 0) {
    return <p className="text-text-dim text-xs">No citations.</p>
  }
  return (
    <div className="space-y-1">
      {citations.map((c) => (
        <div key={c.id} className="text-xs font-mono text-text-secondary border border-bg-border px-2 py-1">
          <span className="text-accent-cyan">{c.file_path}</span>
          {c.line_range && (
            <span className="text-text-dim ml-2">L{c.line_range}</span>
          )}
          {c.content_snippet && (
            <div className="text-text-dim mt-0.5 truncate">{c.content_snippet}</div>
          )}
        </div>
      ))}
    </div>
  )
}

// -- Detail / edit panel --

function MemoryDetailPanel({
  memoryId,
  onClose,
  onDeleted,
}: {
  memoryId: string
  onClose: () => void
  onDeleted: () => void
}) {
  const { data: memory, isLoading, error } = useMemory(memoryId)
  const updateMutation = useUpdateMemory()
  const deleteMutation = useDeleteMemory()

  const [editing, setEditing] = useState(false)
  const [editContent, setEditContent] = useState('')
  const [editImportance, setEditImportance] = useState(1.0)

  const startEditing = useCallback(() => {
    if (memory) {
      setEditContent(memory.content)
      setEditImportance(memory.importance)
    }
    setEditing(true)
  }, [memory])

  const handleSave = useCallback(() => {
    if (!memory) return
    const data: Record<string, unknown> = {}
    if (editContent !== memory.content) data.content = editContent
    if (editImportance !== memory.importance) data.importance = editImportance
    if (Object.keys(data).length === 0) {
      setEditing(false)
      return
    }
    updateMutation.mutate(
      { id: memoryId, data },
      {
        onSuccess: () => setEditing(false),
      },
    )
  }, [memory, editContent, editImportance, memoryId, updateMutation])

  const handleDelete = useCallback(() => {
    if (!window.confirm('Delete this memory? This is a soft delete.')) return
    deleteMutation.mutate(memoryId, {
      onSuccess: () => onDeleted(),
    })
  }, [memoryId, deleteMutation, onDeleted])

  if (isLoading) {
    return (
      <div className="border-l border-bg-border w-[480px] p-4">
        <LoadingSpinner className="py-16" />
      </div>
    )
  }

  if (error || !memory) {
    return (
      <div className="border-l border-bg-border w-[480px] p-4">
        <div className="text-accent-red text-sm font-mono">
          {error ? (error as Error).message : 'Memory not found'}
        </div>
        <button onClick={onClose} className="btn mt-4">
          Close
        </button>
      </div>
    )
  }

  return (
    <div className="border-l border-bg-border w-[480px] flex flex-col overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-bg-border">
        <div className="font-mono text-xs text-text-dim truncate mr-2">
          {memory.id}
        </div>
        <div className="flex gap-2 shrink-0">
          {!editing && (
            <button onClick={startEditing} className="btn text-xs">
              Edit
            </button>
          )}
          <button onClick={onClose} className="btn text-xs">
            Close
          </button>
        </div>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-auto p-4 space-y-4">
        {/* Metadata badges */}
        <div className="flex flex-wrap gap-2">
          <Badge label={memory.status} />
          {memory.memory_type && <Badge label={memory.memory_type} variant="info" />}
          <Badge label={memory.namespace} variant="info" />
        </div>

        {/* Content */}
        <div>
          <h3 className="section-header mb-1">Content</h3>
          {editing ? (
            <textarea
              value={editContent}
              onChange={(e) => setEditContent(e.target.value)}
              className="w-full bg-bg-elevated border border-bg-border p-2 text-sm text-text-primary font-mono focus:outline-none focus:border-accent-green min-h-[120px] resize-y"
            />
          ) : (
            <div className="text-sm text-text-primary whitespace-pre-wrap bg-bg-elevated border border-bg-border p-2">
              {memory.content}
            </div>
          )}
        </div>

        {/* Importance */}
        <div>
          <h3 className="section-header mb-1">Importance</h3>
          {editing ? (
            <input
              type="number"
              step="0.1"
              min="0"
              max="10"
              value={editImportance}
              onChange={(e) => setEditImportance(parseFloat(e.target.value))}
              className="bg-bg-elevated border border-bg-border px-2 py-1 text-sm text-text-primary font-mono w-24 focus:outline-none focus:border-accent-green"
            />
          ) : (
            <span className="text-sm text-text-primary font-mono">{memory.importance}</span>
          )}
        </div>

        {/* Edit actions */}
        {editing && (
          <div className="flex gap-2">
            <button
              onClick={handleSave}
              disabled={updateMutation.isPending}
              className="btn-primary text-xs"
            >
              {updateMutation.isPending ? 'Saving...' : 'Save'}
            </button>
            <button
              onClick={() => {
                setEditing(false)
                setEditContent(memory.content)
                setEditImportance(memory.importance)
              }}
              className="btn text-xs"
            >
              Cancel
            </button>
          </div>
        )}

        {/* Dates */}
        <div className="grid grid-cols-2 gap-2 text-xs">
          <div>
            <span className="text-text-dim">Created: </span>
            <span className="text-text-secondary font-mono">
              {new Date(memory.created_at).toLocaleString()}
            </span>
          </div>
          {memory.accessed_at && (
            <div>
              <span className="text-text-dim">Accessed: </span>
              <span className="text-text-secondary font-mono">
                {new Date(memory.accessed_at).toLocaleString()}
              </span>
            </div>
          )}
        </div>

        {/* Meta */}
        {memory.meta && Object.keys(memory.meta).length > 0 && (
          <div>
            <h3 className="section-header mb-1">Metadata</h3>
            <pre className="text-xs text-text-secondary bg-bg-elevated border border-bg-border p-2 overflow-auto">
              {JSON.stringify(memory.meta, null, 2)}
            </pre>
          </div>
        )}

        {/* Citations */}
        <div>
          <h3 className="section-header mb-1">
            Citations ({memory.citation_count})
          </h3>
          <CitationList citations={memory.citations} />
        </div>

        {/* Delete */}
        <div className="pt-4 border-t border-bg-border">
          <button
            onClick={handleDelete}
            disabled={deleteMutation.isPending}
            className="btn text-accent-red border-accent-red hover:border-accent-red text-xs"
          >
            {deleteMutation.isPending ? 'Deleting...' : 'Delete Memory'}
          </button>
        </div>
      </div>
    </div>
  )
}

// -- Consolidation panel --

function ConsolidatePanel() {
  const { data: nsData } = useMemoryNamespaces()
  const consolidate = useConsolidate()
  const [namespace, setNamespace] = useState('')
  const [maxEvents, setMaxEvents] = useState(50)

  const handleTrigger = useCallback(() => {
    if (!namespace) return
    consolidate.mutate({ namespace, max_events: maxEvents })
  }, [namespace, maxEvents, consolidate])

  const isConflict = consolidate.error && (consolidate.error as Error & { code?: string }).code === 'CONSOLIDATION_IN_PROGRESS'

  return (
    <div className="card">
      <h3 className="section-header mb-3">Consolidation</h3>
      <div className="flex gap-2 items-end flex-wrap">
        <div>
          <label className="text-xs text-text-dim block mb-1">Namespace</label>
          <select
            value={namespace}
            onChange={(e) => setNamespace(e.target.value)}
            className="bg-bg-elevated border border-bg-border px-2 py-1 text-sm text-text-primary font-mono focus:outline-none focus:border-accent-green"
          >
            <option value="">Select namespace...</option>
            {(nsData?.namespaces ?? []).map((ns) => (
              <option key={ns} value={ns}>
                {ns}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="text-xs text-text-dim block mb-1">
            Max events: {maxEvents}
          </label>
          <input
            type="range"
            min="1"
            max="500"
            value={maxEvents}
            onChange={(e) => setMaxEvents(parseInt(e.target.value))}
            className="w-32"
          />
        </div>
        <button
          onClick={handleTrigger}
          disabled={!namespace || consolidate.isPending}
          className="btn-primary text-xs"
        >
          {consolidate.isPending ? 'Running...' : 'Consolidate'}
        </button>
      </div>
      {consolidate.isSuccess && consolidate.data && (
        <div className="text-xs text-accent-green mt-2 font-mono">
          Created {consolidate.data.memories_created} memories from{' '}
          {consolidate.data.events_consolidated} events.
        </div>
      )}
      {consolidate.isError && (
        <div className="text-xs text-accent-red mt-2 font-mono">
          {isConflict
            ? 'Consolidation already in progress.'
            : (consolidate.error as Error).message}
        </div>
      )}
    </div>
  )
}

// -- Main page --

export function MemoryBrowser() {
  const [searchQuery, setSearchQuery] = useState('')
  const [namespace, setNamespace] = useState('')
  const [sort, setSort] = useState('created_at')
  const [order, setOrder] = useState('desc')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const pagination = usePagination(50)

  const params: MemoryListParams = {
    q: searchQuery || undefined,
    namespace: namespace || undefined,
    sort,
    order,
    page: pagination.page,
    per_page: pagination.per_page,
  }

  const { data, isLoading, error } = useMemories(params)

  const handleSort = useCallback(
    (field: string) => {
      if (sort === field) {
        setOrder((o) => (o === 'asc' ? 'desc' : 'asc'))
      } else {
        setSort(field)
        setOrder('desc')
      }
      pagination.resetPage()
    },
    [sort, pagination],
  )

  const handleSearchChange = useCallback(
    (q: string) => {
      setSearchQuery(q)
      pagination.resetPage()
    },
    [pagination],
  )

  const handleNamespaceChange = useCallback(
    (ns: string) => {
      setNamespace(ns)
      pagination.resetPage()
    },
    [pagination],
  )

  return (
    <PageLayout segments={[{ label: 'MEMORY' }]} fullHeight>
      {/* Subheader */}
      <div className="p-6 pb-0">
        <p className="text-sm text-text-secondary mb-4">
          Browse, search, and manage memories across namespaces.
        </p>

        {/* Consolidation panel */}
        <ConsolidatePanel />
      </div>

      {/* Content area */}
      <div className="flex flex-1 overflow-hidden">
        {/* Table section */}
        <div className="flex-1 flex flex-col overflow-hidden p-6 pt-4">
          {/* Search and filters */}
          <div className="flex gap-2 mb-4">
            <MemorySearch value={searchQuery} onChange={handleSearchChange} />
            <NamespaceFilter value={namespace} onChange={handleNamespaceChange} />
          </div>

          {/* Error state */}
          {error && (
            <div className="text-accent-red text-sm font-mono mb-4">
              {(error as Error).message}
            </div>
          )}

          {/* Loading */}
          {isLoading && !data && <LoadingSpinner className="py-16" />}

          {/* Empty */}
          {data && data.memories.length === 0 && (
            <EmptyState
              title="No memories found"
              message={searchQuery ? 'Try adjusting your search query.' : undefined}
            />
          )}

          {/* Table */}
          {data && data.memories.length > 0 && (
            <div className="flex-1 overflow-auto">
              <table className="w-full text-sm">
                <thead className="font-mono text-xs uppercase tracking-widest text-text-dim border-b border-bg-border sticky top-0 bg-bg-primary">
                  <tr>
                    <SortHeader label="Content" field="content" currentSort={sort} currentOrder={order} onSort={handleSort} />
                    <th className="px-3 py-2 text-left">Type</th>
                    <SortHeader label="Namespace" field="namespace" currentSort={sort} currentOrder={order} onSort={handleSort} />
                    <SortHeader label="Importance" field="importance" currentSort={sort} currentOrder={order} onSort={handleSort} />
                    <SortHeader label="Created" field="created_at" currentSort={sort} currentOrder={order} onSort={handleSort} />
                    <th className="px-3 py-2 text-left">Citations</th>
                  </tr>
                </thead>
                <tbody>
                  {data.memories.map((mem: MemoryItem) => (
                    <tr
                      key={mem.id}
                      onClick={() => setSelectedId(mem.id)}
                      className={`border-b border-bg-border cursor-pointer transition-colors hover:bg-bg-elevated ${
                        selectedId === mem.id ? 'bg-bg-elevated' : ''
                      }`}
                    >
                      <td className="px-3 py-2 max-w-xs truncate text-text-primary">
                        {mem.content.length > 80
                          ? mem.content.slice(0, 80) + '...'
                          : mem.content}
                      </td>
                      <td className="px-3 py-2">
                        {mem.memory_type && (
                          <Badge label={mem.memory_type} variant="info" />
                        )}
                      </td>
                      <td className="px-3 py-2 font-mono text-text-secondary text-xs">
                        {mem.namespace}
                      </td>
                      <td className="px-3 py-2 font-mono text-text-secondary">
                        {mem.importance}
                      </td>
                      <td className="px-3 py-2 font-mono text-text-secondary text-xs">
                        {new Date(mem.created_at).toLocaleDateString()}
                      </td>
                      <td className="px-3 py-2 font-mono text-text-secondary text-center">
                        {mem.citation_count}
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
              onPageChange={pagination.setPage}
            />
          )}
        </div>

        {/* Detail panel */}
        {selectedId && (
          <MemoryDetailPanel
            memoryId={selectedId}
            onClose={() => setSelectedId(null)}
            onDeleted={() => setSelectedId(null)}
          />
        )}
      </div>
    </PageLayout>
  )
}

import { useState, useCallback } from 'react'
import { type ColumnDef } from '@tanstack/react-table'
import { useListPage } from '../hooks/useListPage'
import {
  useMemory,
  useUpdateMemory,
  useDeleteMemory,
  useConsolidate,
  useMemoryNamespaces,
  type MemoryDetail,
} from '../hooks/useMemories'
import { DataTable } from '../components/shared/DataTable'
import { SearchBar } from '../components/shared/SearchBar'
import { LoadingSpinner } from '../components/shared/LoadingSpinner'
import { Badge } from '../components/shared/Badge'
import { PageLayout } from '../components/layout/PageLayout'
import type { MemoryItem } from '../api/types'

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

// -- Column definitions --

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const columns: ColumnDef<MemoryItem, any>[] = [
  {
    id: 'content',
    header: 'Content',
    accessorKey: 'content',
    enableSorting: true,
    cell: ({ getValue }) => {
      const content = getValue() as string
      return (
        <span className="max-w-xs truncate block text-text-primary">
          {content.length > 80 ? content.slice(0, 80) + '...' : content}
        </span>
      )
    },
  },
  {
    id: 'memory_type',
    header: 'Type',
    accessorKey: 'memory_type',
    enableSorting: false,
    cell: ({ getValue }) => {
      const memType = getValue() as string | null
      return memType ? <Badge label={memType} variant="info" /> : null
    },
  },
  {
    id: 'namespace',
    header: 'Namespace',
    accessorKey: 'namespace',
    enableSorting: true,
    cell: ({ getValue }) => (
      <span className="text-text-secondary">{getValue() as string}</span>
    ),
  },
  {
    id: 'importance',
    header: 'Importance',
    accessorKey: 'importance',
    enableSorting: true,
    cell: ({ getValue }) => (
      <span className="text-text-secondary">{getValue() as number}</span>
    ),
  },
  {
    id: 'created_at',
    header: 'Created',
    accessorKey: 'created_at',
    enableSorting: true,
    cell: ({ getValue }) => (
      <span className="text-text-secondary">
        {new Date(getValue() as string).toLocaleDateString()}
      </span>
    ),
  },
  {
    id: 'citation_count',
    header: 'Citations',
    accessorKey: 'citation_count',
    enableSorting: false,
    cell: ({ getValue }) => (
      <span className="text-text-secondary text-center block">{getValue() as number}</span>
    ),
  },
]

// -- Main page --

export function MemoryBrowser() {
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const listPage = useListPage<MemoryItem>({
    queryKey: ['memories'],
    endpoint: '/api/memories',
    defaultPerPage: 50,
    defaultSort: { column: 'created_at', order: 'desc' },
  })

  const { data: nsData } = useMemoryNamespaces()
  const namespaces = nsData?.namespaces ?? []

  const handleRowClick = useCallback((row: MemoryItem) => {
    setSelectedId(row.id)
  }, [])

  const handleNamespaceChange = useCallback(
    (e: React.ChangeEvent<HTMLSelectElement>) => {
      const ns = e.target.value
      if (ns) {
        listPage.setFilters({ ...listPage.filters, namespace: ns })
      } else {
        // Remove namespace from filters
        const { namespace: _, ...rest } = listPage.filters
        listPage.setFilters(rest)
      }
    },
    [listPage],
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
            <div className="flex-1">
              <SearchBar
                value={listPage.search}
                onChange={listPage.setSearch}
                placeholder="Search memories (FTS)..."
              />
            </div>
            <select
              value={listPage.filters.namespace ?? ''}
              onChange={handleNamespaceChange}
              className="bg-bg-surface border border-bg-border px-3 py-1 font-mono text-xs text-text-primary focus:border-accent-green outline-none"
            >
              <option value="">All namespaces</option>
              {namespaces.map((ns) => (
                <option key={ns} value={ns}>
                  {ns}
                </option>
              ))}
            </select>
          </div>

          {/* Error state */}
          {listPage.isError && (
            <div className="text-accent-red text-sm font-mono mb-4">
              {(listPage.error as Error).message}
            </div>
          )}

          {/* DataTable */}
          <div className="flex-1 overflow-auto">
            <DataTable
              columns={columns}
              {...listPage.tableProps}
              emptyTitle="No memories found"
              emptyMessage={listPage.search ? 'Try adjusting your search query.' : undefined}
              onRowClick={handleRowClick}
            />
          </div>
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

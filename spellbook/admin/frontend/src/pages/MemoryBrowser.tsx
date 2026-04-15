import { useCallback, useMemo, useState } from 'react'
import {
  useMemory,
  useMemoryList,
  useMemorySearch,
} from '../hooks/useMemories'
import { LoadingSpinner } from '../components/shared/LoadingSpinner'
import { Badge } from '../components/shared/Badge'
import { PageLayout } from '../components/layout/PageLayout'
import { SearchBar } from '../components/shared/SearchBar'
import type {
  Citation,
  MemoryItem,
  MemorySearchResult,
} from '../api/types'

// ---------------------------------------------------------------------------
// Citations list
// ---------------------------------------------------------------------------

function CitationList({ citations }: { citations: Citation[] }) {
  if (!citations || citations.length === 0) {
    return <p className="text-text-dim text-xs">No citations.</p>
  }
  return (
    <div className="space-y-1">
      {citations.map((c, i) => (
        <div
          key={`${c.file}-${c.symbol ?? ''}-${i}`}
          className="text-xs font-mono text-text-secondary border border-bg-border px-2 py-1"
        >
          <span className="text-accent-cyan">{c.file}</span>
          {c.symbol && (
            <span className="text-text-dim ml-2">
              {c.symbol_type ?? 'symbol'}: {c.symbol}
            </span>
          )}
        </div>
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Detail panel
// ---------------------------------------------------------------------------

function MemoryDetailPanel({
  memoryId,
  onClose,
}: {
  memoryId: string
  onClose: () => void
}) {
  const { data: memory, isLoading, error } = useMemory(memoryId)

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
        <button onClick={onClose} className="btn text-xs shrink-0">
          Close
        </button>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-auto p-4 space-y-4">
        {/* Metadata badges */}
        <div className="flex flex-wrap gap-2">
          <Badge label={memory.type} variant="info" />
          {memory.kind && <Badge label={memory.kind} />}
          {memory.confidence && (
            <Badge label={`conf:${memory.confidence}`} />
          )}
        </div>

        {/* Tags */}
        {memory.tags.length > 0 && (
          <div>
            <h3 className="section-header mb-1">Tags</h3>
            <div className="flex flex-wrap gap-1">
              {memory.tags.map((t) => (
                <Badge key={t} label={t} />
              ))}
            </div>
          </div>
        )}

        {/* Body text */}
        <div>
          <h3 className="section-header mb-1">Body</h3>
          <div className="text-sm text-text-primary whitespace-pre-wrap bg-bg-elevated border border-bg-border p-2 font-mono">
            {memory.body}
          </div>
        </div>

        {/* Dates */}
        <div className="grid grid-cols-2 gap-2 text-xs">
          <div>
            <span className="text-text-dim">Created: </span>
            <span className="text-text-secondary font-mono">
              {memory.created}
            </span>
          </div>
          {memory.last_verified && (
            <div>
              <span className="text-text-dim">Verified: </span>
              <span className="text-text-secondary font-mono">
                {memory.last_verified}
              </span>
            </div>
          )}
        </div>

        {/* Citations */}
        <div>
          <h3 className="section-header mb-1">
            Citations ({memory.citations.length})
          </h3>
          <CitationList citations={memory.citations} />
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Row (used by both list and search panels)
// ---------------------------------------------------------------------------

function MemoryRow({
  memory,
  selected,
  onClick,
  score,
}: {
  memory: MemoryItem
  selected: boolean
  onClick: () => void
  score?: number
}) {
  const preview =
    memory.body.length > 120 ? memory.body.slice(0, 120) + '...' : memory.body
  return (
    <button
      type="button"
      onClick={onClick}
      className={`w-full text-left border-b border-bg-border px-3 py-2 hover:bg-bg-elevated ${
        selected ? 'bg-bg-elevated' : ''
      }`}
    >
      <div className="flex items-center gap-2 mb-1">
        <Badge label={memory.type} variant="info" />
        {memory.kind && <Badge label={memory.kind} />}
        <span className="text-text-dim font-mono text-xs">{memory.created}</span>
        {score !== undefined && (
          <span className="text-accent-green font-mono text-xs ml-auto">
            {score.toFixed(2)}
          </span>
        )}
      </div>
      <div className="text-sm text-text-primary whitespace-pre-wrap font-mono">
        {preview}
      </div>
      <div className="font-mono text-xs text-text-dim mt-1 truncate">
        {memory.id}
      </div>
    </button>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

const PAGE_SIZE = 50

export function MemoryBrowser() {
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [offset, setOffset] = useState(0)
  const [search, setSearch] = useState('')

  const trimmedSearch = search.trim()
  const isSearching = trimmedSearch.length > 0

  const listQuery = useMemoryList(offset, PAGE_SIZE)
  const searchQuery = useMemorySearch(trimmedSearch, 25)

  const activeQuery = isSearching ? searchQuery : listQuery
  const items: (MemoryItem | MemorySearchResult)[] = useMemo(() => {
    if (isSearching) {
      return searchQuery.data?.items ?? []
    }
    return listQuery.data?.items ?? []
  }, [isSearching, listQuery.data, searchQuery.data])

  const total = isSearching
    ? searchQuery.data?.total ?? 0
    : listQuery.data?.total ?? 0

  const handleSearchChange = useCallback((value: string) => {
    setSearch(value)
    setOffset(0)
    setSelectedId(null)
  }, [])

  const handleNext = useCallback(() => {
    setOffset((o) => o + PAGE_SIZE)
  }, [])
  const handlePrev = useCallback(() => {
    setOffset((o) => Math.max(0, o - PAGE_SIZE))
  }, [])

  return (
    <PageLayout segments={[{ label: 'MEMORY' }]} fullHeight>
      <div className="p-6 pb-0">
        <p className="text-sm text-text-secondary mb-4">
          Browse and search markdown memory files.
        </p>
        <SearchBar
          value={search}
          onChange={handleSearchChange}
          placeholder="Search memories..."
        />
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* List / results */}
        <div className="flex-1 flex flex-col overflow-hidden p-6 pt-4">
          {activeQuery.isError && (
            <div className="text-accent-red text-sm font-mono mb-4">
              {(activeQuery.error as Error).message}
            </div>
          )}

          {activeQuery.isLoading ? (
            <LoadingSpinner className="py-16" />
          ) : items.length === 0 ? (
            <div className="text-text-dim text-sm font-mono py-16 text-center">
              {isSearching ? 'No results.' : 'No memories found.'}
            </div>
          ) : (
            <div className="flex-1 overflow-auto border border-bg-border">
              {items.map((mem) => (
                <MemoryRow
                  key={mem.id}
                  memory={mem}
                  selected={mem.id === selectedId}
                  onClick={() => setSelectedId(mem.id)}
                  score={
                    'score' in mem ? (mem as MemorySearchResult).score : undefined
                  }
                />
              ))}
            </div>
          )}

          {/* Pagination footer (list mode only) */}
          {!isSearching && total > 0 && (
            <div className="flex items-center justify-between mt-3 text-xs font-mono text-text-dim">
              <span>
                {offset + 1}-{Math.min(offset + PAGE_SIZE, total)} of {total}
              </span>
              <div className="flex gap-2">
                <button
                  onClick={handlePrev}
                  disabled={offset === 0}
                  className="btn text-xs"
                >
                  Prev
                </button>
                <button
                  onClick={handleNext}
                  disabled={offset + PAGE_SIZE >= total}
                  className="btn text-xs"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </div>

        {selectedId && (
          <MemoryDetailPanel
            memoryId={selectedId}
            onClose={() => setSelectedId(null)}
          />
        )}
      </div>
    </PageLayout>
  )
}

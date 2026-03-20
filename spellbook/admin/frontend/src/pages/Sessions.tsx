import { useState, useEffect, useRef, useMemo, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { useSessions } from '../hooks/useSessions'
import { usePagination } from '../hooks/usePagination'
import { Pagination } from '../components/shared/Pagination'
import { LoadingSpinner } from '../components/shared/LoadingSpinner'
import { EmptyState } from '../components/shared/EmptyState'
import { PageLayout } from '../components/layout/PageLayout'
import type { SessionItem } from '../api/types'

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function formatTime(ts: string | null): string {
  if (!ts) return ''
  try {
    return new Date(ts).toLocaleString()
  } catch {
    return ts
  }
}

function decodeProjectPath(encoded: string): string {
  // Project dir names are path-encoded: -Users-alice-proj -> /Users/alice/proj
  return '/' + encoded.replace(/-/g, '/')
}

function SessionRow({ session }: { session: SessionItem }) {
  const [expanded, setExpanded] = useState(false)
  const displayName = session.custom_title || session.slug || session.id.slice(0, 12)

  return (
    <div
      className="card mb-2 cursor-pointer hover:bg-bg-elevated transition-colors"
      onClick={() => setExpanded(!expanded)}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3 flex-1 min-w-0">
          <Link
            to={`/sessions/${session.project}/${session.id}`}
            onClick={(e) => e.stopPropagation()}
            className="font-mono text-sm text-text-primary truncate hover:text-accent-green transition-colors"
          >
            {displayName}
          </Link>
          <span className="font-mono text-xs text-text-dim shrink-0">
            {session.message_count} msgs
          </span>
          <span className="font-mono text-xs text-text-dim shrink-0">
            {formatSize(session.size_bytes)}
          </span>
          <Link
            to={`/sessions/${session.project}/${session.id}/chat`}
            onClick={(e) => e.stopPropagation()}
            className="font-mono text-xs text-text-dim hover:text-accent-green transition-colors shrink-0"
            title="View chat history"
          >
            chat
          </Link>
        </div>
        <span className="font-mono text-xs text-text-dim shrink-0 ml-3">
          {formatTime(session.last_activity)}
        </span>
      </div>

      {session.first_user_message && !expanded && (
        <p className="mt-1 font-mono text-xs text-text-secondary truncate">
          {session.first_user_message}
        </p>
      )}

      {expanded && (
        <div className="mt-3 pt-3 border-t border-bg-border space-y-2">
          <DetailField label="Session ID" value={session.id} />
          <DetailField label="Project" value={decodeProjectPath(session.project)} />
          {session.slug && <DetailField label="Slug" value={session.slug} />}
          <DetailField label="Created" value={formatTime(session.created_at)} />
          <DetailField label="Last Activity" value={formatTime(session.last_activity)} />
          <DetailField label="Messages" value={String(session.message_count)} />
          <DetailField label="Size" value={formatSize(session.size_bytes)} />
          {session.first_user_message && (
            <div>
              <span className="font-mono text-xs text-text-dim uppercase">First Message: </span>
              <p className="font-mono text-xs text-text-secondary mt-0.5 whitespace-pre-wrap">
                {session.first_user_message}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function DetailField({ label, value }: { label: string; value: string | null }) {
  if (!value) return null
  return (
    <div>
      <span className="font-mono text-xs text-text-dim uppercase">{label}: </span>
      <span className="font-mono text-xs text-text-secondary">{value}</span>
    </div>
  )
}

function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState(value)
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedValue(value), delay)
    return () => clearTimeout(timer)
  }, [value, delay])
  return debouncedValue
}

function ProjectMultiSelect({
  options,
  selected,
  onChange,
}: {
  options: string[]
  selected: string[]
  onChange: (selected: string[]) => void
}) {
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const toggle = useCallback((project: string) => {
    onChange(
      selected.includes(project)
        ? selected.filter((p) => p !== project)
        : [...selected, project]
    )
  }, [selected, onChange])

  const label = selected.length === 0
    ? 'All projects'
    : `${selected.length} project${selected.length === 1 ? '' : 's'} selected`

  return (
    <div ref={containerRef} className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="bg-bg-surface border border-bg-border px-3 py-2 font-mono text-xs text-text-primary focus:border-accent-green outline-none w-72 text-left flex items-center justify-between"
      >
        <span className="truncate">{label}</span>
        <span className="text-text-dim ml-2">{open ? '\u25B2' : '\u25BC'}</span>
      </button>
      {open && (
        <div className="absolute z-50 mt-1 w-72 bg-bg-surface border border-bg-border max-h-64 overflow-y-auto shadow-lg">
          {selected.length > 0 && (
            <button
              onClick={() => onChange([])}
              className="w-full px-3 py-1.5 font-mono text-xs text-accent-green hover:bg-bg-elevated text-left border-b border-bg-border"
            >
              Clear selection
            </button>
          )}
          {options.map((project) => (
            <label
              key={project}
              className="flex items-center gap-2 px-3 py-1.5 font-mono text-xs text-text-primary hover:bg-bg-elevated cursor-pointer"
            >
              <input
                type="checkbox"
                checked={selected.includes(project)}
                onChange={() => toggle(project)}
                className="accent-accent-green"
              />
              <span className="truncate" title={decodeProjectPath(project)}>
                {decodeProjectPath(project)}
              </span>
            </label>
          ))}
          {options.length === 0 && (
            <div className="px-3 py-2 font-mono text-xs text-text-dim">No projects found</div>
          )}
        </div>
      )}
    </div>
  )
}

export function Sessions() {
  const [selectedProjects, setSelectedProjects] = useState<string[]>([])
  const [searchInput, setSearchInput] = useState('')
  const debouncedSearch = useDebounce(searchInput, 300)
  const pagination = usePagination(50)

  // Fetch all sessions (unfiltered) to extract unique project names
  const allSessionsQuery = useSessions({
    page: 1,
    per_page: 200,
  })

  const projectOptions = useMemo(() => {
    if (!allSessionsQuery.data) return []
    const projects = new Set(allSessionsQuery.data.sessions.map((s) => s.project))
    return Array.from(projects).sort()
  }, [allSessionsQuery.data])

  const projectParam = selectedProjects.length > 0 ? selectedProjects.join(',') : undefined

  const { data, isLoading, isError } = useSessions({
    project: projectParam,
    search: debouncedSearch || undefined,
    page: pagination.page,
    per_page: pagination.per_page,
  })

  const handleProjectChange = useCallback((projects: string[]) => {
    setSelectedProjects(projects)
    pagination.resetPage()
  }, [pagination])

  return (
    <PageLayout segments={[{ label: 'SESSIONS' }]}>
      {/* Filter bar */}
      <div className="flex items-center gap-3 mb-4">
        <input
          type="text"
          placeholder="Search sessions..."
          value={searchInput}
          onChange={(e) => { setSearchInput(e.target.value); pagination.resetPage() }}
          className="bg-bg-surface border border-bg-border px-3 py-2 font-mono text-xs text-text-primary placeholder:text-text-dim focus:border-accent-green outline-none w-72"
        />
        <ProjectMultiSelect
          options={projectOptions}
          selected={selectedProjects}
          onChange={handleProjectChange}
        />
        {(selectedProjects.length > 0 || searchInput) && (
          <button
            onClick={() => {
              setSelectedProjects([])
              setSearchInput('')
              pagination.resetPage()
            }}
            className="btn"
          >
            Clear all
          </button>
        )}
      </div>

      {/* Session list */}
      {isLoading && <LoadingSpinner className="py-16" />}
      {isError && (
        <EmptyState title="Error loading sessions" message="Failed to fetch sessions." />
      )}
      {data && data.sessions.length === 0 && (
        <EmptyState title="No sessions" message="No sessions match the current filters." />
      )}
      {data && data.sessions.map((session) => (
        <SessionRow key={session.id} session={session} />
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
    </PageLayout>
  )
}

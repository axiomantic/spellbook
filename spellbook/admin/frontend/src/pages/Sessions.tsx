import { useState, useEffect, useRef, useMemo, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { createColumnHelper } from '@tanstack/react-table'
import { useListPage } from '../hooks/useListPage'
import { DataTable } from '../components/shared/DataTable'
import { SearchBar } from '../components/shared/SearchBar'
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

function getDisplayName(session: SessionItem): string {
  return session.custom_title || session.slug || session.id.slice(0, 12)
}

function decodeProjectPath(encoded: string): string {
  return '/' + encoded.replace(/-/g, '/')
}

const columnHelper = createColumnHelper<SessionItem>()

const columns = [
  columnHelper.accessor('id', {
    id: 'name',
    header: 'Name',
    enableSorting: false,
    cell: ({ row }) => {
      const session = row.original
      const displayName = getDisplayName(session)
      return (
        <Link
          to={`/sessions/${session.project}/${session.id}`}
          className="text-text-primary truncate hover:text-accent-green transition-colors"
        >
          {displayName}
        </Link>
      )
    },
  }),
  columnHelper.accessor('message_count', {
    header: 'Messages',
    enableSorting: true,
  }),
  columnHelper.accessor('size_bytes', {
    header: 'Size',
    enableSorting: true,
    cell: ({ getValue }) => formatSize(getValue()),
  }),
  columnHelper.display({
    id: 'chat',
    header: 'Chat',
    enableSorting: false,
    cell: ({ row }) => {
      const session = row.original
      return (
        <Link
          to={`/sessions/${session.project}/${session.id}/chat`}
          className="text-text-dim hover:text-accent-green transition-colors"
          title="View chat history"
        >
          chat
        </Link>
      )
    },
  }),
  columnHelper.accessor('last_activity', {
    header: 'Last Activity',
    enableSorting: true,
    cell: ({ getValue }) => formatTime(getValue()),
  }),
  columnHelper.accessor('created_at', {
    header: 'Created',
    enableSorting: true,
    cell: ({ getValue }) => formatTime(getValue()),
  }),
]

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

  const listPage = useListPage<SessionItem>({
    queryKey: ['sessions'],
    endpoint: '/api/sessions',
    defaultSort: { column: 'last_activity', order: 'desc' },
  })

  // Extract unique project names from current data for the filter dropdown
  const projectOptions = useMemo(() => {
    const projects = new Set(listPage.data.map((s) => s.project))
    return Array.from(projects).sort()
  }, [listPage.data])

  const handleProjectChange = useCallback((projects: string[]) => {
    setSelectedProjects(projects)
    const projectParam = projects.length > 0 ? projects.join(',') : ''
    if (projectParam) {
      listPage.setFilters({ project: projectParam })
    } else {
      listPage.clearFilters()
    }
  }, [listPage])

  const handleClearAll = useCallback(() => {
    setSelectedProjects([])
    listPage.setSearch('')
    listPage.clearFilters()
  }, [listPage])

  const showClearAll = selectedProjects.length > 0 || listPage.search

  return (
    <PageLayout segments={[{ label: 'SESSIONS' }]}>
      {/* Filter bar */}
      <div className="flex items-center gap-3 mb-4">
        <SearchBar
          value={listPage.search}
          onChange={listPage.setSearch}
          placeholder="Search sessions..."
        />
        <ProjectMultiSelect
          options={projectOptions}
          selected={selectedProjects}
          onChange={handleProjectChange}
        />
        {showClearAll && (
          <button onClick={handleClearAll} className="btn">
            Clear all
          </button>
        )}
      </div>

      {/* Session table */}
      <DataTable
        {...listPage.tableProps}
        columns={columns}
        emptyTitle="No sessions"
        emptyMessage="No sessions match the current filters."
      />
    </PageLayout>
  )
}

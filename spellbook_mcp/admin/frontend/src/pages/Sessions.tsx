import { useState } from 'react'
import { useSessions } from '../hooks/useSessions'
import { usePagination } from '../hooks/usePagination'
import { Pagination } from '../components/shared/Pagination'
import { LoadingSpinner } from '../components/shared/LoadingSpinner'
import { EmptyState } from '../components/shared/EmptyState'
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
          <span className="font-mono text-sm text-text-primary truncate">
            {displayName}
          </span>
          <span className="font-mono text-xs text-text-dim shrink-0">
            {session.message_count} msgs
          </span>
          <span className="font-mono text-xs text-text-dim shrink-0">
            {formatSize(session.size_bytes)}
          </span>
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

export function Sessions() {
  const [project, setProject] = useState<string>('')
  const pagination = usePagination(50)

  const { data, isLoading, isError } = useSessions({
    project: project || undefined,
    page: pagination.page,
    per_page: pagination.per_page,
  })

  return (
    <div className="p-6">
      <h1 className="font-mono text-sm uppercase tracking-widest text-text-secondary mb-6">
        // Sessions
      </h1>

      {/* Project filter */}
      <div className="flex items-center gap-3 mb-4">
        <input
          type="text"
          placeholder="Filter by project..."
          value={project}
          onChange={(e) => { setProject(e.target.value); pagination.resetPage() }}
          className="bg-bg-surface border border-bg-border px-3 py-2 font-mono text-xs text-text-primary placeholder:text-text-dim focus:border-accent-green outline-none w-96"
        />
        {project && (
          <button
            onClick={() => { setProject(''); pagination.resetPage() }}
            className="btn"
          >
            Clear
          </button>
        )}
      </div>

      {/* Session list */}
      {isLoading && <LoadingSpinner className="py-16" />}
      {isError && (
        <EmptyState title="Error loading sessions" message="Failed to fetch sessions." />
      )}
      {data && data.sessions.length === 0 && (
        <EmptyState title="No sessions" message="No sessions match the current filter." />
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
    </div>
  )
}

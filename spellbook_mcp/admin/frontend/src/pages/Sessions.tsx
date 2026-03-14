import { useState } from 'react'
import { useSessions, useSessionDetail } from '../hooks/useSessions'
import { usePagination } from '../hooks/usePagination'
import { Badge } from '../components/shared/Badge'
import { Pagination } from '../components/shared/Pagination'
import { LoadingSpinner } from '../components/shared/LoadingSpinner'
import { EmptyState } from '../components/shared/EmptyState'
import type { SessionItem } from '../api/types'

function SessionRow({
  session,
  isExpanded,
  onToggle,
}: {
  session: SessionItem
  isExpanded: boolean
  onToggle: () => void
}) {
  return (
    <div
      className="card mb-2 cursor-pointer hover:bg-bg-elevated transition-colors"
      onClick={onToggle}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="font-mono text-xs text-text-primary">
            {session.project_path.split('/').slice(-2).join('/')}
          </span>
          {session.active_skill && <Badge label={session.active_skill} variant="active" />}
          {session.skill_phase && (
            <span className="font-mono text-xs text-text-dim">{session.skill_phase}</span>
          )}
        </div>
        <div className="flex items-center gap-3">
          {session.workflow_pattern && (
            <Badge label={session.workflow_pattern} variant="info" />
          )}
          <span className="font-mono text-xs text-text-dim">
            {session.bound_at ? new Date(session.bound_at).toLocaleString() : 'unbound'}
          </span>
        </div>
      </div>
      {session.persona && (
        <p className="mt-1 font-mono text-xs text-text-secondary truncate">
          {session.persona}
        </p>
      )}
      {isExpanded && <SessionDetail sessionId={session.id} />}
    </div>
  )
}

function SessionDetail({ sessionId }: { sessionId: string }) {
  const { data, isLoading } = useSessionDetail(sessionId)

  if (isLoading) return <LoadingSpinner className="py-4" />
  if (!data) return null

  return (
    <div className="mt-3 pt-3 border-t border-bg-border space-y-3">
      {/* Metadata grid */}
      <div className="grid grid-cols-2 gap-2">
        <DetailField label="Soul ID" value={data.id} />
        <DetailField label="Session ID" value={data.session_id} />
        <DetailField label="Project" value={data.project_path} />
        <DetailField label="Active Skill" value={data.active_skill} />
        <DetailField label="Phase" value={data.skill_phase} />
        <DetailField label="Workflow" value={data.workflow_pattern} />
        <DetailField label="Persona" value={data.persona} />
        <DetailField label="Summoned" value={data.summoned_at} />
        <DetailField label="Bound" value={data.bound_at} />
        {data.exact_position && (
          <DetailField label="Position" value={data.exact_position} />
        )}
      </div>

      {/* Todos */}
      {data.todos && Array.isArray(data.todos) && data.todos.length > 0 && (
        <div>
          <span className="section-header">Todos</span>
          <div className="mt-1 space-y-1">
            {(data.todos as Array<Record<string, unknown>>).map((todo, i) => (
              <div key={i} className="font-mono text-xs text-text-secondary flex items-center gap-2">
                <span className={todo.done ? 'text-accent-green' : 'text-text-dim'}>
                  {todo.done ? '[x]' : '[ ]'}
                </span>
                <span>{String(todo.text || todo)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recent files */}
      {data.recent_files && Array.isArray(data.recent_files) && data.recent_files.length > 0 && (
        <div>
          <span className="section-header">Recent Files</span>
          <div className="mt-1 space-y-0.5">
            {data.recent_files.map((file: string, i: number) => (
              <div key={i} className="font-mono text-xs text-text-secondary">{file}</div>
            ))}
          </div>
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
  const [expandedId, setExpandedId] = useState<string | null>(null)
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
          placeholder="Filter by project path..."
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
        <SessionRow
          key={session.id}
          session={session}
          isExpanded={expandedId === session.id}
          onToggle={() => setExpandedId(expandedId === session.id ? null : session.id)}
        />
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

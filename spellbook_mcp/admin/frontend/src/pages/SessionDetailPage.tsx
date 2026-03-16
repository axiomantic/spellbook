import { Link, useParams } from 'react-router-dom'
import { useSessionDetail } from '../hooks/useSessions'
import { LoadingSpinner } from '../components/shared/LoadingSpinner'
import { EmptyState } from '../components/shared/EmptyState'

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function formatTime(ts: string | null): string {
  if (!ts) return '-'
  try {
    return new Date(ts).toLocaleString()
  } catch {
    return ts
  }
}

function DetailRow({ label, value }: { label: string; value: string | null }) {
  return (
    <div className="flex py-2 border-b border-bg-border">
      <span className="font-mono text-xs text-text-dim uppercase w-36 shrink-0">{label}</span>
      <span className="font-mono text-xs text-text-secondary break-all">{value || '-'}</span>
    </div>
  )
}

export function SessionDetailPage() {
  const { project, id } = useParams<{ project: string; id: string }>()
  const { data, isLoading, isError, error } = useSessionDetail(project || '', id || '')

  if (isLoading) return <LoadingSpinner className="py-16" />

  if (isError) {
    const errCode = (error as Error & { code?: string })?.code
    if (errCode === 'NOT_FOUND') {
      return (
        <div className="p-6">
          <Link to="/sessions" className="font-mono text-xs text-accent-green hover:underline">
            &larr; Back to Sessions
          </Link>
          <EmptyState title="Session not found" message="This session may have been deleted." />
        </div>
      )
    }
    return (
      <div className="p-6">
        <Link to="/sessions" className="font-mono text-xs text-accent-green hover:underline">
          &larr; Back to Sessions
        </Link>
        <EmptyState title="Error loading session" message={(error as Error)?.message || 'Unknown error'} />
      </div>
    )
  }

  if (!data) return null

  return (
    <div className="p-6">
      <Link to="/sessions" className="font-mono text-xs text-accent-green hover:underline">
        &larr; Back to Sessions
      </Link>

      <h1 className="font-mono text-sm uppercase tracking-widest text-text-secondary mt-4 mb-6">
        // Session Detail
      </h1>

      <div className="card">
        <DetailRow label="Session ID" value={data.id} />
        <DetailRow label="Project" value={data.project_decoded} />
        <DetailRow label="Slug" value={data.slug} />
        <DetailRow label="Title" value={data.custom_title} />
        <DetailRow label="Created" value={formatTime(data.created_at)} />
        <DetailRow label="Last Active" value={formatTime(data.last_activity)} />
        <DetailRow label="Messages" value={String(data.message_count)} />
        <DetailRow label="Size" value={formatSize(data.size_bytes)} />
      </div>

      {data.first_user_message && (
        <div className="mt-6">
          <h2 className="font-mono text-xs text-text-dim uppercase mb-2">First User Message</h2>
          <div className="card font-mono text-xs text-text-secondary whitespace-pre-wrap">
            {data.first_user_message}
          </div>
        </div>
      )}

      <div className="mt-6">
        <Link
          to={`/sessions/${project}/${id}/chat`}
          className="btn inline-flex items-center gap-2"
        >
          View Chat History &rarr;
        </Link>
      </div>
    </div>
  )
}

import { Link, useParams } from 'react-router-dom'
import { useSessionDetail, useSessionMessages } from '../hooks/useSessions'
import { usePagination } from '../hooks/usePagination'
import { MessageBubble } from '../components/sessions/MessageBubble'
import { Pagination } from '../components/shared/Pagination'
import { LoadingSpinner } from '../components/shared/LoadingSpinner'
import { EmptyState } from '../components/shared/EmptyState'

export function ChatHistoryPage() {
  const { project, id } = useParams<{ project: string; id: string }>()
  const pagination = usePagination(100)

  const detailQuery = useSessionDetail(project || '', id || '')
  const messagesQuery = useSessionMessages(project || '', id || '', pagination.page)

  const displayName = detailQuery.data?.custom_title
    || detailQuery.data?.slug
    || detailQuery.data?.id?.slice(0, 12)
    || id?.slice(0, 12)
    || 'Session'

  if (messagesQuery.isLoading && !messagesQuery.data) {
    return <LoadingSpinner className="py-16" />
  }

  if (messagesQuery.isError) {
    const errCode = (messagesQuery.error as Error & { code?: string })?.code
    if (errCode === 'NOT_FOUND') {
      return (
        <div className="p-6">
          <Link
            to={`/sessions/${project}/${id}`}
            className="font-mono text-xs text-accent-green hover:underline"
          >
            &larr; Back to Session Detail
          </Link>
          <EmptyState title="Session not found" message="This session may have been deleted." />
        </div>
      )
    }
    return (
      <div className="p-6">
        <Link
          to={`/sessions/${project}/${id}`}
          className="font-mono text-xs text-accent-green hover:underline"
        >
          &larr; Back to Session Detail
        </Link>
        <EmptyState
          title="Error loading messages"
          message={(messagesQuery.error as Error)?.message || 'Unknown error'}
        />
      </div>
    )
  }

  const data = messagesQuery.data

  return (
    <div className="p-6">
      <Link
        to={`/sessions/${project}/${id}`}
        className="font-mono text-xs text-accent-green hover:underline"
      >
        &larr; Back to Session Detail
      </Link>

      <div className="mt-4 mb-6 flex items-baseline gap-4">
        <h1 className="font-mono text-sm uppercase tracking-widest text-text-secondary">
          // Chat History
        </h1>
        <span className="font-mono text-xs text-text-dim">
          {displayName} | {data?.total_lines ?? 0} messages
        </span>
      </div>

      {data && data.messages.length === 0 && (
        <EmptyState title="No messages" message="This session has no messages." />
      )}

      {data && data.messages.length > 0 && (
        <div className="space-y-1">
          {data.messages.map((msg) => (
            <MessageBubble key={msg.line_number} message={msg} />
          ))}
        </div>
      )}

      {data && data.pages > 1 && (
        <Pagination
          page={data.page}
          pages={data.pages}
          total={data.total_lines}
          onPageChange={pagination.setPage}
        />
      )}
    </div>
  )
}

import { useParams } from 'react-router-dom'
import { useSessionDetail, useSessionMessages } from '../hooks/useSessions'
import { usePagination } from '../hooks/usePagination'
import { MessageBubble } from '../components/sessions/MessageBubble'
import { Pagination } from '../components/shared/Pagination'
import { LoadingSpinner } from '../components/shared/LoadingSpinner'
import { EmptyState } from '../components/shared/EmptyState'
import { PageLayout } from '../components/layout/PageLayout'

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

  const segments = [
    { label: 'SESSIONS', path: '/sessions' },
    { label: 'SESSION', path: `/sessions/${project}/${id}` },
    { label: 'CHAT HISTORY' },
  ]

  if (messagesQuery.isLoading && !messagesQuery.data) {
    return <LoadingSpinner className="py-16" />
  }

  if (messagesQuery.isError) {
    const errCode = (messagesQuery.error as Error & { code?: string })?.code
    if (errCode === 'NOT_FOUND') {
      return (
        <PageLayout segments={segments}>
          <EmptyState title="Session not found" message="This session may have been deleted." />
        </PageLayout>
      )
    }
    return (
      <PageLayout segments={segments}>
        <EmptyState
          title="Error loading messages"
          message={(messagesQuery.error as Error)?.message || 'Unknown error'}
        />
      </PageLayout>
    )
  }

  const data = messagesQuery.data

  return (
    <PageLayout
      segments={segments}
      headerRight={
        <span className="font-mono text-xs text-text-dim">
          {displayName} | {data?.total_lines ?? 0} messages
        </span>
      }
    >

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
    </PageLayout>
  )
}

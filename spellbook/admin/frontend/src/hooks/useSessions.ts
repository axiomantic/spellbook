import { useQuery, keepPreviousData } from '@tanstack/react-query'
import { fetchApi } from '../api/client'
import type { SessionDetail, SessionMessagesResponse } from '../api/types'

export function useSessionDetail(project: string, sessionId: string) {
  return useQuery({
    queryKey: ['session-detail', project, sessionId],
    queryFn: () => fetchApi<SessionDetail>(
      `/api/sessions/${encodeURIComponent(project)}/${encodeURIComponent(sessionId)}`
    ),
    enabled: !!project && !!sessionId,
  })
}

export function useSessionMessages(project: string, sessionId: string, page: number) {
  return useQuery({
    queryKey: ['session-messages', project, sessionId, page],
    queryFn: () => fetchApi<SessionMessagesResponse>(
      `/api/sessions/${encodeURIComponent(project)}/${encodeURIComponent(sessionId)}/messages`,
      { params: { page, per_page: 100 } }
    ),
    placeholderData: keepPreviousData,
    enabled: !!project && !!sessionId,
  })
}

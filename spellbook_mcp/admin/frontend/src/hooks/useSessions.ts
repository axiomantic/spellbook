import { useQuery, keepPreviousData } from '@tanstack/react-query'
import { fetchApi } from '../api/client'
import type { SessionListResponse, SessionItem } from '../api/types'

interface SessionsParams {
  project?: string
  page?: number
  per_page?: number
}

export function useSessions(params: SessionsParams) {
  return useQuery({
    queryKey: ['sessions', params],
    queryFn: () => fetchApi<SessionListResponse>('/api/sessions', { params: params as Record<string, string | number | undefined> }),
    placeholderData: keepPreviousData,
  })
}

interface SessionDetailResponse extends SessionItem {
  todos: unknown[] | null
  recent_files: string[] | null
  exact_position: string | null
}

export function useSessionDetail(sessionId: string | null) {
  return useQuery({
    queryKey: ['session-detail', sessionId],
    queryFn: () => fetchApi<SessionDetailResponse>(`/api/sessions/${sessionId}`),
    enabled: !!sessionId,
  })
}

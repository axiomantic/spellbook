import { useQuery, keepPreviousData } from '@tanstack/react-query'
import { fetchApi } from '../api/client'
import type { SessionListResponse } from '../api/types'

interface SessionsParams {
  project?: string
  search?: string
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

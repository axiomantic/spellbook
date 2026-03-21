import { useQuery, keepPreviousData } from '@tanstack/react-query'
import { fetchApi } from '../api/client'
import type { ListResponse, SecurityDashboardResponse, SecurityEvent } from '../api/types'

interface SecurityEventsParams {
  severity?: string
  event_type?: string
  since?: string
  until?: string
  page?: number
  per_page?: number
}

export function useSecurityEvents(params: SecurityEventsParams) {
  return useQuery({
    queryKey: ['security-events', params],
    queryFn: () => fetchApi<ListResponse<SecurityEvent>>('/api/security/events', { params: params as Record<string, string | number | undefined> }),
    placeholderData: keepPreviousData,
  })
}

interface SecuritySummaryResponse {
  by_severity: Record<string, number>
}

export function useSecuritySummary() {
  return useQuery({
    queryKey: ['security-summary'],
    queryFn: () => fetchApi<SecuritySummaryResponse>('/api/security/summary'),
    refetchInterval: 30_000,
  })
}

export function useSecurityDashboard() {
  return useQuery({
    queryKey: ['security-dashboard'],
    queryFn: () => fetchApi<SecurityDashboardResponse>('/api/security/dashboard'),
    refetchInterval: 30_000,
  })
}

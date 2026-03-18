import { useQuery } from '@tanstack/react-query'
import { fetchApi } from '../api/client'
import type { DashboardResponse } from '../api/types'

export function useDashboard() {
  return useQuery({
    queryKey: ['dashboard'],
    queryFn: () => fetchApi<DashboardResponse>('/api/dashboard'),
    refetchInterval: 30_000,
  })
}

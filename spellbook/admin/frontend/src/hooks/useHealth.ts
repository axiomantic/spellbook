import { useQuery } from '@tanstack/react-query'
import { fetchApi } from '../api/client'
import type { HealthMatrixResponse } from '../api/types'

export function useHealthMatrix() {
  return useQuery({
    queryKey: ['health', 'matrix'],
    queryFn: () => fetchApi<HealthMatrixResponse>('/api/health/matrix'),
    refetchInterval: 30_000,
  })
}

import { useQuery, keepPreviousData } from '@tanstack/react-query'
import { fetchApi } from '../api/client'
import type { FractalGraphListResponse, CytoscapeResponse, FractalGraphSummary } from '../api/types'

export function useFractalGraphList(page: number = 1, status?: string) {
  return useQuery({
    queryKey: ['fractal', 'graphs', page, status],
    queryFn: () =>
      fetchApi<FractalGraphListResponse>('/api/fractal/graphs', {
        params: { page, status },
      }),
    placeholderData: keepPreviousData,
  })
}

export function useFractalGraphDetail(graphId: string | null) {
  return useQuery({
    queryKey: ['fractal', 'graph', graphId],
    queryFn: () => fetchApi<FractalGraphSummary & Record<string, unknown>>(`/api/fractal/graphs/${graphId}`),
    enabled: !!graphId,
  })
}

export function useFractalCytoscape(graphId: string | null, maxDepth?: number) {
  return useQuery({
    queryKey: ['fractal', 'cytoscape', graphId, maxDepth],
    queryFn: () =>
      fetchApi<CytoscapeResponse>(`/api/fractal/graphs/${graphId}/cytoscape`, {
        params: { max_depth: maxDepth },
      }),
    enabled: !!graphId,
    staleTime: 10_000,
  })
}

import { useQuery, useMutation, useQueryClient, keepPreviousData } from '@tanstack/react-query'
import { fetchApi } from '../api/client'
import type {
  FractalGraphListResponse,
  CytoscapeResponse,
  FractalGraphSummary,
  ChatLogResponse,
  GraphDeleteResponse,
  GraphStatusUpdateRequest,
  GraphStatusUpdateResponse,
} from '../api/types'

export interface FractalGraphListParams {
  page?: number
  status?: string
  project_dir?: string
  search?: string
  sort_by?: 'created_at' | 'updated_at' | 'seed' | 'status'
  sort_order?: 'asc' | 'desc'
}

export function useFractalGraphList(params: FractalGraphListParams = {}) {
  const { page = 1, status, project_dir, search, sort_by, sort_order } = params
  return useQuery({
    queryKey: ['fractal', 'graphs', page, status, project_dir, search, sort_by, sort_order],
    queryFn: () =>
      fetchApi<FractalGraphListResponse>('/api/fractal/graphs', {
        params: { page, status, project_dir, search, sort_by, sort_order },
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

export function useChatLog(graphId: string | null, nodeId: string | null) {
  return useQuery({
    queryKey: ['fractal', 'chatlog', graphId, nodeId],
    queryFn: () =>
      fetchApi<ChatLogResponse>(`/api/fractal/graphs/${graphId}/nodes/${nodeId}/chat-log`),
    enabled: !!graphId && !!nodeId,
    staleTime: 30_000,
  })
}

export function useDeleteGraph() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (graphId: string) =>
      fetchApi<GraphDeleteResponse>(`/api/fractal/graphs/${graphId}`, {
        method: 'DELETE',
      }),
    onSuccess: (_data, graphId) => {
      queryClient.invalidateQueries({ queryKey: ['fractal', 'graphs'] })
      queryClient.invalidateQueries({ queryKey: ['fractal', 'graph', graphId] })
      queryClient.invalidateQueries({ queryKey: ['fractal', 'cytoscape', graphId] })
    },
  })
}

export function useUpdateGraphStatus() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      graphId,
      ...body
    }: GraphStatusUpdateRequest & { graphId: string }) =>
      fetchApi<GraphStatusUpdateResponse>(
        `/api/fractal/graphs/${graphId}/status`,
        {
          method: 'PATCH',
          body,
        }
      ),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['fractal', 'graphs'] })
      queryClient.invalidateQueries({
        queryKey: ['fractal', 'graph', variables.graphId],
      })
      queryClient.invalidateQueries({
        queryKey: ['fractal', 'cytoscape', variables.graphId],
      })
    },
  })
}

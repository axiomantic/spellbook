import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchApi } from '../api/client'
import type {
  CytoscapeResponse,
  FractalGraphSummary,
  ChatLogResponse,
  GraphDeleteResponse,
  GraphStatusUpdateRequest,
  GraphStatusUpdateResponse,
} from '../api/types'

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

import { useQuery, useMutation, useQueryClient, keepPreviousData } from '@tanstack/react-query'
import { fetchApi } from '../api/client'
import type { MemoryItem, MemoryListResponse, MemoryUpdateRequest } from '../api/types'

export interface MemoryListParams {
  q?: string
  namespace?: string
  memory_type?: string
  status?: string
  sort?: string
  order?: string
  page?: number
  per_page?: number
}

export interface MemoryDetail extends MemoryItem {
  citations: Citation[]
}

export interface Citation {
  id: number
  memory_id: string
  file_path: string
  line_range: string | null
  content_snippet: string | null
}

export interface ConsolidateRequest {
  namespace: string
  max_events?: number
}

export interface ConsolidateResponse {
  memories_created: number
  events_consolidated: number
}

export interface MemoryStatsResponse {
  total: number
  by_type: Record<string, number>
  by_status: Record<string, number>
  by_namespace: Record<string, number>
}

export interface NamespaceListResponse {
  namespaces: string[]
}

export function useMemories(params: MemoryListParams = {}) {
  return useQuery({
    queryKey: ['memories', params],
    queryFn: () =>
      fetchApi<MemoryListResponse>('/api/memories', {
        params: {
          q: params.q || undefined,
          namespace: params.namespace || undefined,
          memory_type: params.memory_type || undefined,
          status: params.status || undefined,
          sort: params.sort || undefined,
          order: params.order || undefined,
          page: params.page || undefined,
          per_page: params.per_page || undefined,
        },
      }),
    placeholderData: keepPreviousData,
  })
}

export function useMemory(id: string | null) {
  return useQuery({
    queryKey: ['memory', id],
    queryFn: () => fetchApi<MemoryDetail>(`/api/memories/${id}`),
    enabled: !!id,
  })
}

export function useUpdateMemory() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: MemoryUpdateRequest }) =>
      fetchApi<{ status: string; memory_id: string }>(`/api/memories/${id}`, {
        method: 'PUT',
        body: data,
      }),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['memories'] })
      queryClient.invalidateQueries({ queryKey: ['memory', variables.id] })
    },
  })
}

export function useDeleteMemory() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) =>
      fetchApi<{ status: string; memory_id: string }>(`/api/memories/${id}`, {
        method: 'DELETE',
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['memories'] })
    },
  })
}

export function useConsolidate() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: ConsolidateRequest) =>
      fetchApi<ConsolidateResponse>('/api/memories/consolidate', {
        method: 'POST',
        body: data,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['memories'] })
      queryClient.invalidateQueries({ queryKey: ['memory-stats'] })
    },
  })
}

export function useMemoryNamespaces() {
  return useQuery({
    queryKey: ['memory-namespaces'],
    queryFn: () => fetchApi<NamespaceListResponse>('/api/memories/namespaces'),
  })
}

export function useMemoryStats() {
  return useQuery({
    queryKey: ['memory-stats'],
    queryFn: () => fetchApi<MemoryStatsResponse>('/api/memories/stats'),
  })
}

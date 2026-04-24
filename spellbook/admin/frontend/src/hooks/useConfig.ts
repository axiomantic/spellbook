import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchApi } from '../api/client'
import type { ConfigResponse } from '../api/types'

interface ConfigSchemaKey {
  key: string
  type: 'boolean' | 'string' | 'number'
  description: string
  // Backend adds ``secret: true`` for sensitive keys (API tokens, etc).
  // Absent means non-secret. Secret values are masked in GET responses and
  // rendered with ``input type="password"`` in the editor.
  secret?: boolean
}

interface ConfigSchemaResponse {
  keys: ConfigSchemaKey[]
}

export function useConfig() {
  return useQuery({
    queryKey: ['config'],
    queryFn: () => fetchApi<ConfigResponse>('/api/config'),
  })
}

export function useConfigSchema() {
  return useQuery({
    queryKey: ['config', 'schema'],
    queryFn: () => fetchApi<ConfigSchemaResponse>('/api/config/schema'),
    staleTime: 60_000, // schema rarely changes
  })
}

export function useUpdateConfig() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: { key: string; value: unknown }) =>
      fetchApi(`/api/config/${data.key}`, {
        method: 'PUT',
        body: { value: data.value },
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['config'] })
    },
  })
}

export function useBatchUpdateConfig() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (updates: Record<string, unknown>) =>
      fetchApi('/api/config', {
        method: 'PUT',
        body: { updates },
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['config'] })
    },
  })
}

export type { ConfigSchemaKey }

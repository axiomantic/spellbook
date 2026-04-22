import { useQuery } from '@tanstack/react-query'
import { fetchApi } from '../api/client'
import { useListPage, type UseListPageReturn } from './useListPage'

export interface HookEvent {
  id: number
  timestamp: string
  hook_name: string
  event_name: string
  tool_name: string | null
  duration_ms: number
  exit_code: number
  error: string | null
  notes: string | null
}

export interface HookMetricsGroup {
  hook_name: string
  event_name: string
  count: number
  avg_duration_ms: number | null
  p50_duration_ms: number | null
  p95_duration_ms: number | null
  error_rate: number
}

export interface HookMetrics {
  total: number
  window: number
  groups: HookMetricsGroup[]
  summary: {
    avg_duration_ms: number | null
    p95_duration_ms: number | null
    error_rate: number
  }
}

export function useHookEvents(
  filters: Record<string, string>,
): UseListPageReturn<HookEvent> {
  return useListPage<HookEvent>({
    queryKey: ['hook-events'],
    endpoint: '/api/hooks/events',
    defaultSort: { column: 'timestamp', order: 'desc' },
    defaultFilters: filters,
    refetchInterval: 5000,
  })
}

export function useHookMetrics(window: number) {
  return useQuery<HookMetrics>({
    queryKey: ['hook-metrics', window],
    queryFn: () =>
      fetchApi<HookMetrics>('/api/hooks/metrics', {
        params: { window },
      }),
    refetchInterval: 10000,
  })
}

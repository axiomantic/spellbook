import { useQuery } from '@tanstack/react-query'
import { fetchApi } from '../api/client'
import { useListPage, type UseListPageReturn } from './useListPage'

export interface WorkerLLMCall {
  id: number
  timestamp: string
  task: string
  model: string
  status: 'success' | 'error' | 'timeout' | 'fail_open'
  latency_ms: number
  prompt_len: number
  response_len: number
  error: string | null
  override_loaded: boolean
}

export interface WorkerLLMMetrics {
  success_rate: number | null
  p95_latency_ms: number | null
  p99_latency_ms: number | null
  error_breakdown: Record<string, number>
  total_calls: number
  window_hours: number
}

export function useWorkerLLMCalls(
  filters: Record<string, string>,
): UseListPageReturn<WorkerLLMCall> {
  return useListPage<WorkerLLMCall>({
    queryKey: ['worker-llm-calls'],
    endpoint: '/api/worker-llm/calls',
    defaultSort: { column: 'timestamp', order: 'desc' },
    defaultFilters: filters,
    refetchInterval: 5000,
  })
}

export function useWorkerLLMMetrics(windowHours: number) {
  return useQuery<WorkerLLMMetrics>({
    queryKey: ['worker-llm-metrics', windowHours],
    queryFn: () =>
      fetchApi<WorkerLLMMetrics>('/api/worker-llm/metrics', {
        params: { window_hours: windowHours },
      }),
    refetchInterval: 10000,
  })
}

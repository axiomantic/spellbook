import { useQuery, keepPreviousData } from '@tanstack/react-query'
import { fetchApi } from '../api/client'
import type { StintStack, CorrectionEvent, FocusSummary } from '../api/types'

export function useStintStacks() {
  return useQuery({
    queryKey: ['focus', 'stacks'],
    queryFn: () =>
      fetchApi<{ stacks: StintStack[] }>('/api/focus/stacks').then((r) => r.stacks),
    refetchInterval: 30_000,
  })
}

interface CorrectionParams {
  period?: string
  project?: string
  correction_type?: string
}

export function useCorrectionEvents(params: CorrectionParams = {}) {
  return useQuery({
    queryKey: ['focus', 'corrections', params.period, params.project, params.correction_type],
    queryFn: () =>
      fetchApi<{ corrections: CorrectionEvent[] }>('/api/focus/corrections', {
        params: params as Record<string, string | number | undefined>,
      }).then((r) => r.corrections),
    placeholderData: keepPreviousData,
  })
}

export function useFocusSummary() {
  return useQuery({
    queryKey: ['focus', 'summary'],
    queryFn: () => fetchApi<FocusSummary>('/api/focus/summary'),
    refetchInterval: 30_000,
  })
}

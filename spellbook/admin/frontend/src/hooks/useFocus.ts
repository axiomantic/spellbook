import { useQuery, keepPreviousData } from '@tanstack/react-query'
import { fetchApi } from '../api/client'
import type { StintStack, CorrectionEvent, FocusSummary } from '../api/types'

export function useStintStacks() {
  return useQuery({
    queryKey: ['focus', 'stacks'],
    queryFn: () => fetchApi<StintStack[]>('/api/focus/stacks'),
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
      fetchApi<CorrectionEvent[]>('/api/focus/corrections', {
        params: params as Record<string, string | number | undefined>,
      }),
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

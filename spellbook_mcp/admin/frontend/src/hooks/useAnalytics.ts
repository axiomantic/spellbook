import { useQuery, keepPreviousData } from '@tanstack/react-query'
import { fetchApi } from '../api/client'
import type {
  ToolFrequencyResponse,
  ErrorRateResponse,
  TimelineResponse,
  AnalyticsSummary,
} from '../api/types'

interface AnalyticsParams {
  period?: string
  event_type?: string
}

export function useToolFrequency(params: AnalyticsParams = {}) {
  return useQuery({
    queryKey: ['analytics', 'tool-frequency', params],
    queryFn: () =>
      fetchApi<ToolFrequencyResponse>('/api/analytics/tool-frequency', {
        params: params as Record<string, string | number | undefined>,
      }),
    placeholderData: keepPreviousData,
  })
}

export function useErrorRates(params: Pick<AnalyticsParams, 'period'> = {}) {
  return useQuery({
    queryKey: ['analytics', 'error-rates', params],
    queryFn: () =>
      fetchApi<ErrorRateResponse>('/api/analytics/error-rates', {
        params: params as Record<string, string | number | undefined>,
      }),
    placeholderData: keepPreviousData,
  })
}

export function useTimeline(params: Pick<AnalyticsParams, 'period'> = {}) {
  return useQuery({
    queryKey: ['analytics', 'timeline', params],
    queryFn: () =>
      fetchApi<TimelineResponse>('/api/analytics/timeline', {
        params: params as Record<string, string | number | undefined>,
      }),
    placeholderData: keepPreviousData,
  })
}

export function useAnalyticsSummary(params: Pick<AnalyticsParams, 'period'> = {}) {
  return useQuery({
    queryKey: ['analytics', 'summary', params],
    queryFn: () =>
      fetchApi<AnalyticsSummary>('/api/analytics/summary', {
        params: params as Record<string, string | number | undefined>,
      }),
    placeholderData: keepPreviousData,
  })
}

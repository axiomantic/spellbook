import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createElement, type ReactNode } from 'react'
import type { ListResponse } from '../api/types'
import {
  useWorkerLLMCalls,
  useWorkerLLMMetrics,
  type WorkerLLMCall,
  type WorkerLLMMetrics,
} from './useWorkerLLM'

// Mock the fetchApi module
vi.mock('../api/client', () => ({
  fetchApi: vi.fn(),
}))

import { fetchApi } from '../api/client'

const mockFetchApi = fetchApi as Mock

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
      },
    },
  })
  return function Wrapper({ children }: { children: ReactNode }) {
    return createElement(QueryClientProvider, { client: queryClient }, children)
  }
}

const sampleCall: WorkerLLMCall = {
  id: 1,
  timestamp: '2026-04-20T10:00:00+00:00',
  task: 'tool_safety',
  model: 'claude-haiku-4',
  status: 'success',
  latency_ms: 250,
  prompt_len: 120,
  response_len: 48,
  error: null,
  override_loaded: false,
}

function makeListResponse(
  items: WorkerLLMCall[],
  overrides: Partial<ListResponse<WorkerLLMCall>> = {},
): ListResponse<WorkerLLMCall> {
  return {
    items,
    total: items.length,
    page: 1,
    per_page: 50,
    pages: 1,
    ...overrides,
  }
}

describe('useWorkerLLMCalls', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('fetches /api/worker-llm/calls with timestamp-desc default sort and passed filters', async () => {
    const response = makeListResponse([sampleCall])
    mockFetchApi.mockResolvedValueOnce(response)

    const { result } = renderHook(
      () =>
        useWorkerLLMCalls({
          task: 'tool_safety',
          status: 'success',
          since: '2026-04-19T10:00:00+00:00',
        }),
      { wrapper: createWrapper() },
    )

    await waitFor(() => expect(result.current.isLoading).toBe(false))

    // useListPage composes params: page, per_page, sort, order, then filters.
    expect(mockFetchApi).toHaveBeenCalledTimes(1)
    expect(mockFetchApi).toHaveBeenCalledWith('/api/worker-llm/calls', {
      params: {
        page: 1,
        per_page: 50,
        sort: 'timestamp',
        order: 'desc',
        task: 'tool_safety',
        status: 'success',
        since: '2026-04-19T10:00:00+00:00',
      },
    })

    // The envelope exposes tableProps (proves the hook returns UseListPageReturn).
    expect(result.current.data).toEqual([sampleCall])
    expect(result.current.total).toBe(1)
    expect(result.current.page).toBe(1)
    expect(result.current.pages).toBe(1)
    expect(result.current.perPage).toBe(50)
    expect(result.current.sorting).toEqual({ column: 'timestamp', order: 'desc' })
    expect(result.current.tableProps.data).toEqual([sampleCall])
    expect(result.current.tableProps.loading).toBe(false)
    expect(result.current.tableProps.pagination).toEqual({
      page: 1,
      pages: 1,
      total: 1,
      perPage: 50,
      onPageChange: result.current.setPage,
      onPerPageChange: result.current.setPerPage,
    })
    expect(result.current.tableProps.sorting?.sortColumn).toBe('timestamp')
    expect(result.current.tableProps.sorting?.sortOrder).toBe('desc')
  })

  /*
  ESCAPE: fetches /api/worker-llm/calls with timestamp-desc default sort and passed filters
    CLAIM: Verifies useWorkerLLMCalls wires useListPage with the right endpoint, default sort, and filters.
    PATH:  useWorkerLLMCalls -> useListPage -> fetchApi
    CHECK: Exact endpoint, exact params object (page, per_page, sort=timestamp, order=desc, task, status, since);
           full envelope shape (data, total, page, pages, perPage, sorting, tableProps) all asserted.
    MUTATION: Wrong endpoint ('/api/worker_llm/calls') fails; default sort swapped to 'id' fails;
              defaultSort order 'asc' fails; refetchInterval misplaced so tableProps.loading stays stuck
              would not fail immediately, but wrong queryKey would break subsequent re-render dedup.
    ESCAPE: A broken hook that silently swapped filters.status for a literal ('error') would still show
            as a call mismatch because we assert the exact params object.
    IMPACT: Wrong endpoint -> no data; wrong sort -> oldest-first, operator sees stale head-of-list.
  */

  it('uses a stable queryKey so two calls with same args dedupe', async () => {
    const response = makeListResponse([sampleCall])
    mockFetchApi.mockResolvedValueOnce(response)

    const wrapper = createWrapper()
    const { result, rerender } = renderHook(
      () => useWorkerLLMCalls({ task: 'tool_safety' }),
      { wrapper },
    )

    await waitFor(() => expect(result.current.isLoading).toBe(false))

    rerender()
    await waitFor(() => expect(result.current.isLoading).toBe(false))

    expect(mockFetchApi).toHaveBeenCalledTimes(1)
    expect(result.current.data).toEqual([sampleCall])
  })

  /*
  ESCAPE: uses a stable queryKey so two calls with same args dedupe
    CLAIM: Re-rendering with the same filter args does not trigger a second fetch.
    PATH:  renderHook -> useWorkerLLMCalls -> useListPage -> useQuery queryKey
    CHECK: mock.call_count == 1 after two renders; data still populated.
    MUTATION: If queryKey included a new object every render (e.g. fresh literal),
              the second render would refetch and count would be 2.
    ESCAPE: Could pass if react-query dedupes even with different keys, but with gcTime: 0
            that does not happen.
    IMPACT: Duplicate queries -> server load, flashes while refetching.
  */
})

describe('useWorkerLLMMetrics', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('fetches /api/worker-llm/metrics with window_hours param and returns the six-key envelope', async () => {
    const response: WorkerLLMMetrics = {
      success_rate: 0.97,
      p95_latency_ms: 420,
      p99_latency_ms: 1200,
      error_breakdown: { timeout: 3, rate_limit: 1 },
      total_calls: 142,
      window_hours: 24,
    }
    mockFetchApi.mockResolvedValueOnce(response)

    const { result } = renderHook(() => useWorkerLLMMetrics(24), {
      wrapper: createWrapper(),
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(mockFetchApi).toHaveBeenCalledTimes(1)
    expect(mockFetchApi).toHaveBeenCalledWith('/api/worker-llm/metrics', {
      params: { window_hours: 24 },
    })

    expect(result.current.data).toEqual({
      success_rate: 0.97,
      p95_latency_ms: 420,
      p99_latency_ms: 1200,
      error_breakdown: { timeout: 3, rate_limit: 1 },
      total_calls: 142,
      window_hours: 24,
    })
  })

  /*
  ESCAPE: fetches /api/worker-llm/metrics with window_hours param and returns the six-key envelope
    CLAIM: Verifies URL, query param, and that the returned shape matches the Python route envelope.
    PATH:  useWorkerLLMMetrics -> useQuery -> fetchApi
    CHECK: Exact URL and params; data equals the full six-key response.
    MUTATION: Param key 'windowHours' instead of 'window_hours' would fail; dropping any of the six keys
              from the type and passing through would not change runtime, but a hook that silently picked
              only some fields (e.g. via Object.assign filtering) would fail the deep equality.
    ESCAPE: A broken hook that returned a default instead of the fetched body would fail the deep-equal.
    IMPACT: Wrong param key -> backend defaults to 24h, silently wrong cards for other windows.
  */

  it('surfaces null values (empty window) without coercion', async () => {
    const emptyWindow: WorkerLLMMetrics = {
      success_rate: null,
      p95_latency_ms: null,
      p99_latency_ms: null,
      error_breakdown: {},
      total_calls: 0,
      window_hours: 1,
    }
    mockFetchApi.mockResolvedValueOnce(emptyWindow)

    const { result } = renderHook(() => useWorkerLLMMetrics(1), {
      wrapper: createWrapper(),
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(mockFetchApi).toHaveBeenCalledTimes(1)
    expect(mockFetchApi).toHaveBeenCalledWith('/api/worker-llm/metrics', {
      params: { window_hours: 1 },
    })

    expect(result.current.data).toEqual({
      success_rate: null,
      p95_latency_ms: null,
      p99_latency_ms: null,
      error_breakdown: {},
      total_calls: 0,
      window_hours: 1,
    })
  })

  /*
  ESCAPE: surfaces null values (empty window) without coercion
    CLAIM: Null metric values pass through untouched (em-dash rendering contract per design §8).
    PATH:  useWorkerLLMMetrics -> useQuery -> fetchApi
    CHECK: data.success_rate === null, p95 === null, p99 === null, empty breakdown, total_calls === 0.
    MUTATION: A broken hook that defaulted nulls to 0 would fail (success_rate would be 0 not null);
              em-dash rendering would then silently become "0%".
    ESCAPE: None -- exact deep-equal on the whole object catches any field-level mutation.
    IMPACT: Operator sees "0%" success when the window is actually empty -> false alarm.
  */

  it('re-queries with a distinct key when windowHours changes', async () => {
    const firstResponse: WorkerLLMMetrics = {
      success_rate: 0.99,
      p95_latency_ms: 100,
      p99_latency_ms: 200,
      error_breakdown: {},
      total_calls: 50,
      window_hours: 1,
    }
    const secondResponse: WorkerLLMMetrics = {
      success_rate: 0.95,
      p95_latency_ms: 300,
      p99_latency_ms: 800,
      error_breakdown: { timeout: 2 },
      total_calls: 400,
      window_hours: 24,
    }
    mockFetchApi
      .mockResolvedValueOnce(firstResponse)
      .mockResolvedValueOnce(secondResponse)

    const wrapper = createWrapper()
    const { result, rerender } = renderHook(
      ({ hours }: { hours: number }) => useWorkerLLMMetrics(hours),
      { wrapper, initialProps: { hours: 1 } },
    )

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual(firstResponse)

    rerender({ hours: 24 })

    await waitFor(() => expect(result.current.data).toEqual(secondResponse))

    expect(mockFetchApi).toHaveBeenCalledTimes(2)
    expect(mockFetchApi).toHaveBeenNthCalledWith(1, '/api/worker-llm/metrics', {
      params: { window_hours: 1 },
    })
    expect(mockFetchApi).toHaveBeenNthCalledWith(2, '/api/worker-llm/metrics', {
      params: { window_hours: 24 },
    })
  })

  /*
  ESCAPE: re-queries with a distinct key when windowHours changes
    CLAIM: Changing the windowHours arg triggers a new fetch (distinct queryKey).
    PATH:  useWorkerLLMMetrics -> useQuery queryKey -> fetchApi
    CHECK: Two calls total, each with the correct window_hours; second data equals second response.
    MUTATION: If queryKey omitted windowHours, the second render would return cached first data and
              count would stay at 1.
    ESCAPE: None for this specific invariant -- exact call count plus nth-call args nail it down.
    IMPACT: Operator changes window selector but cards never update -> broken window filter.
  */
})

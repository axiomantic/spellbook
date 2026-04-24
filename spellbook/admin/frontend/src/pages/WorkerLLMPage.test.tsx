import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createElement } from 'react'
import { WorkerLLMPage } from './WorkerLLMPage'

vi.mock('../hooks/useWorkerLLM', () => ({
  useWorkerLLMCalls: vi.fn(),
  useWorkerLLMMetrics: vi.fn(),
}))

import { useWorkerLLMCalls, useWorkerLLMMetrics } from '../hooks/useWorkerLLM'

const mockCalls = useWorkerLLMCalls as Mock
const mockMetrics = useWorkerLLMMetrics as Mock

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } })
  return render(
    createElement(
      QueryClientProvider,
      { client: qc },
      createElement(MemoryRouter, { initialEntries: ['/worker-llm'] }, createElement(WorkerLLMPage)),
    ),
  )
}

describe('WorkerLLMPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockCalls.mockReturnValue({
      data: [],
      total: 0,
      isLoading: false,
      isError: false,
      error: null,
      page: 1,
      pages: 0,
      perPage: 50,
      setPage: vi.fn(),
      setPerPage: vi.fn(),
      sorting: { column: 'timestamp', order: 'desc' as const },
      setSorting: vi.fn(),
      search: '',
      setSearch: vi.fn(),
      filters: {},
      setFilters: vi.fn(),
      clearFilters: vi.fn(),
      tableProps: {
        data: [],
        loading: false,
        pagination: {
          page: 1,
          pages: 0,
          total: 0,
          perPage: 50,
          onPageChange: vi.fn(),
          onPerPageChange: vi.fn(),
        },
        sorting: {
          sortColumn: 'timestamp',
          sortOrder: 'desc' as const,
          onSortChange: vi.fn(),
        },
      },
    })
    mockMetrics.mockReturnValue({
      data: {
        success_rate: null,
        p95_latency_ms: null,
        p99_latency_ms: null,
        error_breakdown: {},
        total_calls: 0,
        window_hours: 24,
      },
      isLoading: false,
      isError: false,
    })
  })

  it('renders title, metric cards, and empty error-breakdown state', () => {
    renderPage()

    expect(screen.getByText('WORKER LLM CALLS')).toBeInTheDocument()
    expect(screen.getByText('Success Rate')).toBeInTheDocument()
    expect(screen.getByText('P95 Latency')).toBeInTheDocument()
    expect(screen.getByText('P99 Latency')).toBeInTheDocument()
    expect(screen.getByText('No errors')).toBeInTheDocument()
    expect(mockMetrics).toHaveBeenCalledWith(24)
  })
})

import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createElement } from 'react'
import { GraphTable } from './GraphTable'

// Mock useListPage - the shared hook that manages all list state
vi.mock('../../hooks/useListPage', () => ({
  useListPage: vi.fn(),
}))

import { useListPage } from '../../hooks/useListPage'

const mockUseListPage = useListPage as Mock

// Mock navigate
const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

// --- Test data ---

const mockGraph = {
  id: 'graph-001',
  seed: 'How do neural networks learn?',
  status: 'active',
  intensity: 'deep',
  total_nodes: 12,
  project_dir: '/Users/alice/project',
  created_at: '2026-03-15T10:00:00Z',
  updated_at: '2026-03-15T11:30:00Z',
}

const mockGraph2 = {
  id: 'graph-002',
  seed: 'What is consciousness?',
  status: 'completed',
  intensity: 'quick',
  total_nodes: 5,
  project_dir: null,
  created_at: '2026-03-14T08:00:00Z',
  updated_at: '2026-03-14T09:00:00Z',
}

function buildMockListPageReturn(overrides: Record<string, unknown> = {}) {
  const setSearch = vi.fn()
  const setFilters = vi.fn()
  const clearFilters = vi.fn()
  const setPage = vi.fn()

  return {
    data: [mockGraph, mockGraph2],
    total: 2,
    isLoading: false,
    isError: false,
    error: null,
    page: 1,
    pages: 1,
    perPage: 50,
    setPage,
    setPerPage: vi.fn(),
    sorting: { column: undefined, order: 'asc' as const },
    setSorting: vi.fn(),
    search: '',
    setSearch,
    filters: {},
    setFilters,
    clearFilters,
    tableProps: {
      data: [mockGraph, mockGraph2],
      loading: false,
      pagination: {
        page: 1,
        pages: 1,
        total: 2,
        perPage: 50,
        onPageChange: setPage,
        onPerPageChange: vi.fn(),
      },
      sorting: {
        sortColumn: undefined,
        sortOrder: 'asc' as const,
        onSortChange: vi.fn(),
      },
    },
    ...overrides,
  }
}

function renderGraphTable() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })

  return render(
    createElement(
      QueryClientProvider,
      { client: queryClient },
      createElement(
        MemoryRouter,
        { initialEntries: ['/fractal'] },
        createElement(GraphTable)
      )
    )
  )
}

// --- Tests ---

describe('GraphTable', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockUseListPage.mockReturnValue(buildMockListPageReturn())
  })

  describe('useListPage integration', () => {
    it('calls useListPage with fractal graphs endpoint and query key', () => {
      renderGraphTable()

      expect(mockUseListPage).toHaveBeenCalledTimes(1)
      const callArgs = mockUseListPage.mock.calls[0][0]
      expect(callArgs.queryKey).toEqual(['fractal', 'graphs'])
      expect(callArgs.endpoint).toBe('/api/fractal/graphs')
    })

    it('passes default sort descending by created_at', () => {
      renderGraphTable()

      const callArgs = mockUseListPage.mock.calls[0][0]
      expect(callArgs.defaultSort).toEqual({ column: 'created_at', order: 'desc' })
    })
  })

  describe('column headers', () => {
    it('renders all seven column headers', () => {
      const { container } = renderGraphTable()

      const thead = container.querySelector('thead')!
      expect(thead).toBeInTheDocument()

      const headerCells = thead.querySelectorAll('th')
      const headerTexts = Array.from(headerCells).map((th) => th.textContent!.trim())
      expect(headerTexts).toEqual(['Seed', 'Status', 'Intensity', 'Nodes', 'Project', 'Created', 'Updated'])
    })
  })

  describe('data row rendering', () => {
    it('renders graph data in table cells', () => {
      const { container } = renderGraphTable()

      const tbody = container.querySelector('tbody')!
      const rows = tbody.querySelectorAll('tr')
      expect(rows.length).toBe(2)

      // First row - check key cell content
      const row1Cells = rows[0].querySelectorAll('td')
      expect(row1Cells[0].textContent).toBe('How do neural networks learn?')
      expect(row1Cells[1].textContent).toBe('active')
      expect(row1Cells[2].textContent).toBe('deep')
      expect(row1Cells[3].textContent).toBe('12')
      expect(row1Cells[4].textContent).toBe('/Users/alice/project')

      // Second row
      const row2Cells = rows[1].querySelectorAll('td')
      expect(row2Cells[0].textContent).toBe('What is consciousness?')
      expect(row2Cells[1].textContent).toBe('completed')
      expect(row2Cells[2].textContent).toBe('quick')
      expect(row2Cells[3].textContent).toBe('5')
      expect(row2Cells[4].textContent).toBe('--')
    })

    it('truncates long seed text at 60 characters', () => {
      const longSeed = 'A'.repeat(80)
      mockUseListPage.mockReturnValue(
        buildMockListPageReturn({
          data: [{ ...mockGraph, seed: longSeed }],
          tableProps: {
            data: [{ ...mockGraph, seed: longSeed }],
            loading: false,
            pagination: {
              page: 1, pages: 1, total: 1, perPage: 50,
              onPageChange: vi.fn(), onPerPageChange: vi.fn(),
            },
            sorting: {
              sortColumn: undefined, sortOrder: 'asc',
              onSortChange: vi.fn(),
            },
          },
        })
      )

      const { container } = renderGraphTable()

      const tbody = container.querySelector('tbody')!
      const firstCell = tbody.querySelector('td')!
      expect(firstCell.textContent).toBe('A'.repeat(60) + '...')
    })
  })

  describe('row click navigation', () => {
    it('navigates to /fractal/{graphId} when row is clicked', async () => {
      const user = userEvent.setup()
      const { container } = renderGraphTable()

      const tbody = container.querySelector('tbody')!
      const rows = tbody.querySelectorAll('tr')
      await user.click(rows[0])

      expect(mockNavigate).toHaveBeenCalledTimes(1)
      expect(mockNavigate).toHaveBeenCalledWith('/fractal/graph-001')
    })
  })

  describe('SearchBar integration', () => {
    it('renders a SearchBar with seed text placeholder', () => {
      renderGraphTable()

      const searchInput = screen.getByPlaceholderText('Search by seed text...')
      expect(searchInput).toBeInTheDocument()
    })
  })

  describe('FilterBar integration', () => {
    it('renders a status filter with All statuses option and status values', () => {
      renderGraphTable()

      // The FilterBar renders a select element with status options
      const allOption = screen.getByText('All statuses')
      expect(allOption).toBeInTheDocument()
    })
  })

  describe('empty state', () => {
    it('renders "No Graphs" when data is empty and no filters applied', () => {
      mockUseListPage.mockReturnValue(
        buildMockListPageReturn({
          data: [],
          tableProps: {
            data: [],
            loading: false,
            pagination: {
              page: 1, pages: 0, total: 0, perPage: 50,
              onPageChange: vi.fn(), onPerPageChange: vi.fn(),
            },
            sorting: {
              sortColumn: undefined, sortOrder: 'asc',
              onSortChange: vi.fn(),
            },
          },
        })
      )

      renderGraphTable()

      expect(screen.getByText('No Graphs')).toBeInTheDocument()
    })

    it('renders filter-specific empty message when filters are active', () => {
      mockUseListPage.mockReturnValue(
        buildMockListPageReturn({
          data: [],
          search: 'something',
          tableProps: {
            data: [],
            loading: false,
            pagination: {
              page: 1, pages: 0, total: 0, perPage: 50,
              onPageChange: vi.fn(), onPerPageChange: vi.fn(),
            },
            sorting: {
              sortColumn: undefined, sortOrder: 'asc',
              onSortChange: vi.fn(),
            },
          },
        })
      )

      renderGraphTable()

      expect(screen.getByText('No graphs match the current filters.')).toBeInTheDocument()
    })
  })

  describe('loading state', () => {
    it('shows loading spinner via DataTable when loading', () => {
      mockUseListPage.mockReturnValue(
        buildMockListPageReturn({
          isLoading: true,
          tableProps: {
            data: [],
            loading: true,
            pagination: {
              page: 1, pages: 0, total: 0, perPage: 50,
              onPageChange: vi.fn(), onPerPageChange: vi.fn(),
            },
            sorting: {
              sortColumn: undefined, sortOrder: 'asc',
              onSortChange: vi.fn(),
            },
          },
        })
      )

      const { container } = renderGraphTable()

      const spinner = container.querySelector('.animate-spin')
      expect(spinner).toBeInTheDocument()
    })
  })
})

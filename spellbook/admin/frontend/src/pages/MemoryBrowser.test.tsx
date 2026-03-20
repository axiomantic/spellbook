import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createElement } from 'react'
import { MemoryBrowser } from './MemoryBrowser'

// Mock useListPage - the migrated component should use this
vi.mock('../hooks/useListPage', () => ({
  useListPage: vi.fn(),
}))

// Mock useMemories for non-list hooks only
vi.mock('../hooks/useMemories', () => ({
  useMemory: vi.fn(),
  useUpdateMemory: vi.fn(),
  useDeleteMemory: vi.fn(),
  useConsolidate: vi.fn(),
  useMemoryNamespaces: vi.fn(),
}))

import { useListPage } from '../hooks/useListPage'
import {
  useMemory,
  useUpdateMemory,
  useDeleteMemory,
  useConsolidate,
  useMemoryNamespaces,
} from '../hooks/useMemories'

const mockUseListPage = useListPage as Mock
const mockUseMemory = useMemory as Mock
const mockUseUpdateMemory = useUpdateMemory as Mock
const mockUseDeleteMemory = useDeleteMemory as Mock
const mockUseConsolidate = useConsolidate as Mock
const mockUseMemoryNamespaces = useMemoryNamespaces as Mock

const mockMemory1 = {
  id: 'mem-aaa-111',
  content: 'Remember to always check edge cases in production code',
  memory_type: 'insight',
  namespace: 'project-alpha',
  branch: 'main',
  importance: 3.5,
  created_at: '2026-03-18T10:00:00Z',
  accessed_at: '2026-03-19T14:00:00Z',
  status: 'active',
  meta: {},
  citation_count: 2,
}

const mockMemory2 = {
  id: 'mem-bbb-222',
  content: 'The database schema changed in v2 migration',
  memory_type: 'fact',
  namespace: 'project-beta',
  branch: 'develop',
  importance: 7.0,
  created_at: '2026-03-19T08:00:00Z',
  accessed_at: null,
  status: 'active',
  meta: { source: 'consolidation' },
  citation_count: 0,
}

const mockSetSearch = vi.fn()
const mockSetFilters = vi.fn()
const mockClearFilters = vi.fn()

function makeListPageReturn(overrides: Record<string, unknown> = {}) {
  return {
    data: [mockMemory1, mockMemory2],
    total: 2,
    isLoading: false,
    isError: false,
    error: null,
    page: 1,
    pages: 1,
    perPage: 50,
    setPage: vi.fn(),
    setPerPage: vi.fn(),
    sorting: { column: 'created_at', order: 'desc' as const },
    setSorting: vi.fn(),
    search: '',
    setSearch: mockSetSearch,
    filters: {},
    setFilters: mockSetFilters,
    clearFilters: mockClearFilters,
    tableProps: {
      data: [mockMemory1, mockMemory2],
      loading: false,
      pagination: {
        page: 1,
        pages: 1,
        total: 2,
        perPage: 50,
        onPageChange: vi.fn(),
        onPerPageChange: vi.fn(),
      },
      sorting: {
        sortColumn: 'created_at',
        sortOrder: 'desc' as const,
        onSortChange: vi.fn(),
      },
    },
    ...overrides,
  }
}

function renderMemoryBrowser() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })

  return render(
    createElement(
      QueryClientProvider,
      { client: queryClient },
      createElement(
        MemoryRouter,
        { initialEntries: ['/memory'] },
        createElement(MemoryBrowser)
      )
    )
  )
}

describe('MemoryBrowser', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockUseListPage.mockReturnValue(makeListPageReturn())
    mockUseMemoryNamespaces.mockReturnValue({
      data: { namespaces: ['project-alpha', 'project-beta', 'global'] },
    })
    mockUseMemory.mockReturnValue({
      data: null,
      isLoading: false,
      error: null,
    })
    mockUseUpdateMemory.mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    })
    mockUseDeleteMemory.mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    })
    mockUseConsolidate.mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
      isSuccess: false,
      isError: false,
      data: null,
      error: null,
    })
  })

  describe('uses useListPage hook', () => {
    it('calls useListPage with memories query key and endpoint', () => {
      renderMemoryBrowser()

      expect(mockUseListPage).toHaveBeenCalledTimes(1)
      const callArgs = mockUseListPage.mock.calls[0][0]
      expect(callArgs.queryKey).toEqual(['memories'])
      expect(callArgs.endpoint).toBe('/api/memories')
    })

    /*
    ESCAPE: calls useListPage with memories query key and endpoint
      CLAIM: MemoryBrowser invokes useListPage with correct config
      PATH: MemoryBrowser renders -> calls useListPage({queryKey, endpoint, ...})
      CHECK: queryKey === ['memories'], endpoint === '/api/memories'
      MUTATION: Wrong queryKey would fail array equality; wrong endpoint would fail string equality
      ESCAPE: Nothing reasonable -- both fields checked with exact equality
      IMPACT: Wrong query key would break cache invalidation; wrong endpoint would fetch wrong data
    */

    it('configures useListPage with default sort by created_at desc', () => {
      renderMemoryBrowser()

      const callArgs = mockUseListPage.mock.calls[0][0]
      expect(callArgs.defaultSort).toEqual({ column: 'created_at', order: 'desc' })
    })

    /*
    ESCAPE: configures useListPage with default sort
      CLAIM: Default sort is created_at descending
      PATH: useListPage options.defaultSort
      CHECK: defaultSort equals { column: 'created_at', order: 'desc' }
      MUTATION: Different column or order would fail equality
      ESCAPE: Nothing reasonable -- exact object equality
      IMPACT: Memories would appear in wrong default order
    */
  })

  describe('DataTable columns', () => {
    it('renders table headers for content, type, namespace, importance, created, and citations', () => {
      renderMemoryBrowser()

      const table = screen.getByRole('table')
      const headers = within(table).getAllByRole('columnheader')
      const headerTexts = headers.map((h) => h.textContent?.trim().toLowerCase() ?? '')

      // Sort indicators may append ' v' or ' ^', so use startsWith
      expect(headerTexts.some((t) => t.startsWith('content'))).toBe(true)
      expect(headerTexts.some((t) => t.startsWith('type'))).toBe(true)
      expect(headerTexts.some((t) => t.startsWith('namespace'))).toBe(true)
      expect(headerTexts.some((t) => t.startsWith('importance'))).toBe(true)
      expect(headerTexts.some((t) => t.startsWith('created'))).toBe(true)
      expect(headerTexts.some((t) => t.startsWith('citations'))).toBe(true)
    })

    /*
    ESCAPE: renders table headers
      CLAIM: DataTable renders all expected column headers
      PATH: MemoryBrowser defines columns -> DataTable renders headers
      CHECK: Each expected header text is present
      MUTATION: Missing a column definition would omit its header
      ESCAPE: Extra unexpected columns wouldn't be caught, but that's benign
      IMPACT: Missing columns would hide important data from users
    */

    it('renders memory data in table rows', () => {
      renderMemoryBrowser()

      const table = screen.getByRole('table')

      // First memory -- content truncated at 80 chars (this one is under 80)
      expect(within(table).getByText('Remember to always check edge cases in production code')).toBeInTheDocument()
      expect(within(table).getByText('project-alpha')).toBeInTheDocument()

      // Second memory
      expect(within(table).getByText('The database schema changed in v2 migration')).toBeInTheDocument()
      expect(within(table).getByText('project-beta')).toBeInTheDocument()
    })

    /*
    ESCAPE: renders memory data in table rows
      CLAIM: Memory content and namespace appear in table cells
      PATH: DataTable receives data -> renders cell content via column definitions
      CHECK: Specific text from mock data found in table
      MUTATION: Wrong column accessor would render wrong field; missing column wouldn't render it
      ESCAPE: We don't check every field in every row -- but we check enough distinct fields to confirm column mapping
      IMPACT: Columns would display wrong data or nothing
    */

    it('renders memory_type as Badge component', () => {
      renderMemoryBrowser()

      const table = screen.getByRole('table')
      expect(within(table).getByText('insight')).toBeInTheDocument()
      expect(within(table).getByText('fact')).toBeInTheDocument()
    })

    /*
    ESCAPE: renders memory_type as Badge
      CLAIM: memory_type values are displayed (as Badges)
      PATH: Column definition for type renders Badge -> Badge shows label text
      CHECK: Both memory_type values present in table
      MUTATION: Not rendering memory_type would cause both getByText to fail
      ESCAPE: We don't verify Badge component specifically (just text presence), but this is sufficient for behavior
      IMPACT: Memory type would be invisible to users
    */
  })

  describe('search', () => {
    it('renders a search input for FTS search', () => {
      renderMemoryBrowser()

      const searchInput = screen.getByPlaceholderText(/search/i)
      expect(searchInput).toBeInTheDocument()
    })

    /*
    ESCAPE: renders search input
      CLAIM: A search input with placeholder containing "search" exists
      PATH: MemoryBrowser renders SearchBar component
      CHECK: Input with search-related placeholder exists
      MUTATION: Not rendering SearchBar would cause getByPlaceholderText to fail
      ESCAPE: Nothing reasonable -- presence of search input verified
      IMPACT: Users couldn't search memories
    */
  })

  describe('namespace filter', () => {
    it('renders namespace filter options from useMemoryNamespaces', () => {
      renderMemoryBrowser()

      // The namespace filter select should have "All namespaces" default option
      const namespaceSelect = screen.getByDisplayValue('All namespaces')
      expect(namespaceSelect).toBeInTheDocument()

      // Verify all namespace options exist within the filter select
      const options = within(namespaceSelect).getAllByRole('option')
      const optionTexts = options.map((o) => o.textContent)
      expect(optionTexts).toEqual([
        'All namespaces',
        'project-alpha',
        'project-beta',
        'global',
      ])
    })

    /*
    ESCAPE: renders namespace filter options
      CLAIM: Namespace values from useMemoryNamespaces appear as filter options
      PATH: useMemoryNamespaces returns namespaces -> FilterBar renders options
      CHECK: All three namespace texts present in document
      MUTATION: Not using namespace data would omit these texts
      ESCAPE: These texts also appear in table data for project-alpha and project-beta, but 'global' only comes from namespaces, confirming filter rendering
      IMPACT: Users couldn't filter by namespace
    */

    it('calls setFilters when a namespace is selected', async () => {
      renderMemoryBrowser()

      const user = userEvent.setup()

      // Find and interact with the namespace select
      const namespaceSelect = screen.getByDisplayValue('All namespaces')
      await user.selectOptions(namespaceSelect, 'project-alpha')

      expect(mockSetFilters).toHaveBeenCalledWith(
        expect.objectContaining({ namespace: 'project-alpha' })
      )
    })

    /*
    ESCAPE: calls setFilters on namespace selection
      CLAIM: Selecting a namespace calls setFilters with the namespace value
      PATH: User selects namespace -> onChange -> setFilters({namespace: value})
      CHECK: setFilters called with object containing namespace key
      MUTATION: Not wiring onChange to setFilters would leave mockSetFilters uncalled
      ESCAPE: We use objectContaining rather than exact match because other filter keys may be present -- but the namespace key is verified
      IMPACT: Namespace filter selections would have no effect
    */
  })

  describe('detail panel', () => {
    it('shows detail panel when a table row is clicked', async () => {
      // Set up useMemory to return detail when selected
      mockUseMemory.mockReturnValue({
        data: {
          ...mockMemory1,
          citations: [
            {
              id: 1,
              memory_id: 'mem-aaa-111',
              file_path: '/src/utils.ts',
              line_range: '10-20',
              content_snippet: 'function helper() {',
            },
          ],
        },
        isLoading: false,
        error: null,
      })

      renderMemoryBrowser()

      const user = userEvent.setup()
      const table = screen.getByRole('table')
      const rows = within(table).getAllByRole('row')
      // Row 0 is header, row 1 is first data row
      const firstDataRow = rows[1]

      await user.click(firstDataRow)

      // Detail panel should show the memory ID
      expect(screen.getByText('mem-aaa-111')).toBeInTheDocument()
    })

    /*
    ESCAPE: shows detail panel on row click
      CLAIM: Clicking a table row opens the detail panel showing memory details
      PATH: onRowClick -> setSelectedId -> MemoryDetailPanel renders
      CHECK: Memory ID text appears after click
      MUTATION: Not passing onRowClick to DataTable would prevent selection; not rendering detail panel would omit ID
      ESCAPE: Nothing reasonable -- the ID text only appears in the detail panel, not in table cells
      IMPACT: Users couldn't view memory details
    */

    it('closes detail panel when close button is clicked', async () => {
      mockUseMemory.mockReturnValue({
        data: {
          ...mockMemory1,
          citations: [],
        },
        isLoading: false,
        error: null,
      })

      renderMemoryBrowser()

      const user = userEvent.setup()

      // Open detail panel
      const table = screen.getByRole('table')
      const rows = within(table).getAllByRole('row')
      await user.click(rows[1])

      // Verify panel is open
      expect(screen.getByText('mem-aaa-111')).toBeInTheDocument()

      // Close panel
      const closeButton = screen.getByRole('button', { name: /close/i })
      await user.click(closeButton)

      // Memory ID should no longer be visible (it's only in the detail panel)
      expect(screen.queryByText('mem-aaa-111')).not.toBeInTheDocument()
    })

    /*
    ESCAPE: closes detail panel on close click
      CLAIM: Clicking close button hides the detail panel
      PATH: close button onClick -> setSelectedId(null) -> detail panel unmounts
      CHECK: Memory ID disappears after close click
      MUTATION: Not wiring close handler would leave panel open
      ESCAPE: Nothing reasonable -- presence then absence of unique text verified
      IMPACT: Users couldn't dismiss the detail panel
    */
  })

  describe('consolidation panel', () => {
    it('renders consolidation section with namespace selector', () => {
      renderMemoryBrowser()

      expect(screen.getByText('Consolidation')).toBeInTheDocument()
    })

    /*
    ESCAPE: renders consolidation panel
      CLAIM: Consolidation panel is rendered
      PATH: MemoryBrowser renders ConsolidatePanel component
      CHECK: "Consolidation" heading text present
      MUTATION: Not rendering ConsolidatePanel would omit this heading
      ESCAPE: Nothing reasonable -- text presence verified
      IMPACT: Users couldn't trigger memory consolidation
    */
  })

  describe('loading state', () => {
    it('passes loading=true to DataTable via tableProps when data is loading', () => {
      mockUseListPage.mockReturnValue(
        makeListPageReturn({
          isLoading: true,
          data: [],
          tableProps: {
            data: [],
            loading: true,
            pagination: {
              page: 1,
              pages: 0,
              total: 0,
              perPage: 50,
              onPageChange: vi.fn(),
              onPerPageChange: vi.fn(),
            },
            sorting: {
              sortColumn: 'created_at',
              sortOrder: 'desc',
              onSortChange: vi.fn(),
            },
          },
        })
      )
      renderMemoryBrowser()

      // DataTable renders a loading overlay with animate-spin when loading=true
      // The table should still render (DataTable shows overlay on top)
      expect(screen.getByRole('table')).toBeInTheDocument()
      // The loading overlay div has bg-bg-base/50 class
      const container = screen.getByRole('table').closest('.relative')
      expect(container).not.toBeNull()
      // The loading overlay is the first child with z-10 class
      const overlay = container!.querySelector('.z-10')
      expect(overlay).not.toBeNull()
    })

    /*
    ESCAPE: loading state
      CLAIM: Loading overlay appears when data is being fetched
      PATH: useListPage returns isLoading=true -> tableProps.loading=true -> DataTable shows overlay
      CHECK: Table exists, container with .relative class exists, overlay with .z-10 class exists
      MUTATION: Not passing loading=true would hide the overlay (no .z-10 child)
      ESCAPE: If DataTable changed its loading class names, test would break -- but that's a DataTable API change
      IMPACT: Users would see empty page during data load with no feedback
    */
  })

  describe('empty state', () => {
    it('shows empty state when no memories match', () => {
      mockUseListPage.mockReturnValue(
        makeListPageReturn({
          data: [],
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
              sortColumn: 'created_at',
              sortOrder: 'desc',
              onSortChange: vi.fn(),
            },
          },
        })
      )
      renderMemoryBrowser()

      expect(screen.getByText('No memories found')).toBeInTheDocument()
    })

    /*
    ESCAPE: empty state
      CLAIM: Empty state message appears when no memories match
      PATH: useListPage returns empty data -> DataTable renders EmptyState
      CHECK: "No memories found" text present
      MUTATION: Not passing emptyTitle to DataTable would show default "No Data"
      ESCAPE: Nothing reasonable -- exact text verified
      IMPACT: Users would see blank area instead of helpful message
    */
  })
})

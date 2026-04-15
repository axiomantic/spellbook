import { render, screen, within, waitFor, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createElement } from 'react'
import { MemoryBrowser } from './MemoryBrowser'

// Mock the three hooks the page consumes. The page is pure UI over these hooks.
vi.mock('../hooks/useMemories', () => ({
  useMemoryList: vi.fn(),
  useMemory: vi.fn(),
  useMemorySearch: vi.fn(),
}))

import {
  useMemoryList,
  useMemory,
  useMemorySearch,
} from '../hooks/useMemories'

const mockUseMemoryList = useMemoryList as Mock
const mockUseMemory = useMemory as Mock
const mockUseMemorySearch = useMemorySearch as Mock

const PAGE_SIZE = 50

const memoryA = {
  id: 'project/foo.md',
  type: 'convention',
  kind: 'rule',
  tags: ['python', 'testing'],
  citations: [
    { file: 'spellbook/memory/store.py', symbol: 'MemoryStore', symbol_type: 'class' },
  ],
  confidence: 'high' as const,
  created: '2026-03-01T10:00:00Z',
  last_verified: '2026-03-05T10:00:00Z',
  body: 'Prefer top-level imports. Only use function-level imports for known circular imports.',
}

const memoryB = {
  id: 'project/bar.md',
  type: 'decision',
  kind: null,
  tags: [],
  citations: [],
  confidence: null,
  created: '2026-03-02T11:00:00Z',
  last_verified: null,
  body: 'Short body for memory B.',
}

const memoryC = {
  id: 'project/baz.md',
  type: 'fact',
  kind: 'observation',
  tags: ['perf'],
  citations: [],
  confidence: 'medium' as const,
  created: '2026-03-03T12:00:00Z',
  last_verified: null,
  body: 'Body text for memory C that has enough characters to exercise preview behavior cleanly.',
}

function listResponse(items: typeof memoryA[], total?: number, offset = 0) {
  return {
    items,
    total: total ?? items.length,
    offset,
    limit: PAGE_SIZE,
  }
}

function listHookReturn(overrides: Record<string, unknown> = {}) {
  return {
    data: listResponse([memoryA, memoryB, memoryC]),
    isLoading: false,
    isError: false,
    error: null,
    ...overrides,
  }
}

function searchHookReturn(overrides: Record<string, unknown> = {}) {
  return {
    data: undefined,
    isLoading: false,
    isError: false,
    error: null,
    ...overrides,
  }
}

function memoryHookReturn(overrides: Record<string, unknown> = {}) {
  return {
    data: undefined,
    isLoading: false,
    isError: false,
    error: null,
    ...overrides,
  }
}

function renderBrowser() {
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
        createElement(MemoryBrowser),
      ),
    ),
  )
}

describe('MemoryBrowser', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockUseMemoryList.mockReturnValue(listHookReturn())
    mockUseMemorySearch.mockReturnValue(searchHookReturn())
    mockUseMemory.mockReturnValue(memoryHookReturn())
  })

  it('renders memory list from useMemoryList', () => {
    renderBrowser()

    // type badges
    expect(screen.getByText('convention')).toBeInTheDocument()
    expect(screen.getByText('decision')).toBeInTheDocument()
    expect(screen.getByText('fact')).toBeInTheDocument()

    // created timestamps
    expect(screen.getByText('2026-03-01T10:00:00Z')).toBeInTheDocument()
    expect(screen.getByText('2026-03-02T11:00:00Z')).toBeInTheDocument()
    expect(screen.getByText('2026-03-03T12:00:00Z')).toBeInTheDocument()

    // body previews (first ~50 chars). Bodies here are <120 chars so shown in full.
    expect(
      screen.getByText(
        'Prefer top-level imports. Only use function-level imports for known circular imports.',
      ),
    ).toBeInTheDocument()
    expect(screen.getByText('Short body for memory B.')).toBeInTheDocument()
    expect(
      screen.getByText(
        'Body text for memory C that has enough characters to exercise preview behavior cleanly.',
      ),
    ).toBeInTheDocument()
  })

  it('loading state renders the LoadingSpinner', () => {
    mockUseMemoryList.mockReturnValue(
      listHookReturn({ data: undefined, isLoading: true }),
    )
    const { container } = renderBrowser()

    // LoadingSpinner has a uniquely identifying animate-spin element.
    const spinner = container.querySelector('.animate-spin')
    expect(spinner).not.toBeNull()
  })

  it('empty list shows empty-state copy', () => {
    mockUseMemoryList.mockReturnValue(
      listHookReturn({ data: listResponse([], 0) }),
    )
    renderBrowser()

    expect(screen.getByText('No memories found.')).toBeInTheDocument()
  })

  it('error state surfaces the error message', () => {
    mockUseMemoryList.mockReturnValue(
      listHookReturn({
        data: undefined,
        isError: true,
        error: new Error('boom'),
      }),
    )
    renderBrowser()

    expect(screen.getByText('boom')).toBeInTheDocument()
  })

  it('search input switches to useMemorySearch and renders its results', async () => {
    const searchResult = {
      ...memoryA,
      id: 'search/hit.md',
      type: 'searchtype',
      body: 'Search result body',
      score: 0.87,
      match_context: null,
    }
    mockUseMemorySearch.mockReturnValue(
      searchHookReturn({
        data: {
          query: 'foo',
          total: 1,
          items: [searchResult],
        },
      }),
    )

    renderBrowser()

    const input = screen.getByPlaceholderText('Search memories...') as HTMLInputElement
    // fireEvent writes synchronously; SearchBar's debounce (300ms) will then fire
    // onChange once via a real setTimeout.
    fireEvent.change(input, { target: { value: 'foo' } })

    // Wait for the debounced setSearch to propagate and useMemorySearch to be
    // called with the trimmed query.
    await waitFor(() => {
      const queries = mockUseMemorySearch.mock.calls.map((c) => c[0])
      expect(queries).toContain('foo')
    })

    // The rendered row comes from search results, not the list data
    expect(screen.getByText('searchtype')).toBeInTheDocument()
    expect(screen.getByText('Search result body')).toBeInTheDocument()
    // Score is rendered for search results
    expect(screen.getByText('0.87')).toBeInTheDocument()

    // List-only items should not be visible once search is active
    expect(screen.queryByText('Short body for memory B.')).not.toBeInTheDocument()
  })

  it('pagination Next advances offset; Prev is disabled at offset 0', async () => {
    // 120 total => 3 pages at PAGE_SIZE=50
    mockUseMemoryList.mockReturnValue(
      listHookReturn({ data: listResponse([memoryA, memoryB, memoryC], 120, 0) }),
    )
    const user = userEvent.setup()
    renderBrowser()

    const prevButton = screen.getByRole('button', { name: 'Prev' })
    const nextButton = screen.getByRole('button', { name: 'Next' })

    // At offset 0, Prev is disabled; Next is enabled.
    expect(prevButton).toBeDisabled()
    expect(nextButton).not.toBeDisabled()

    // First call on mount was with offset=0.
    const offsetsBefore = mockUseMemoryList.mock.calls.map((c) => c[0])
    expect(offsetsBefore).toContain(0)

    await user.click(nextButton)

    // After clicking Next, the hook should be re-invoked with offset=PAGE_SIZE (50).
    const offsetsAfterNext = mockUseMemoryList.mock.calls.map((c) => c[0])
    expect(offsetsAfterNext).toContain(PAGE_SIZE)
  })

  it('pagination Prev decreases offset from a non-zero offset', async () => {
    // Start rendering with a list whose offset is 50 (middle page). Total=120.
    // Component state starts at offset=0, so we need to click Next first to move it.
    mockUseMemoryList.mockReturnValue(
      listHookReturn({ data: listResponse([memoryA, memoryB, memoryC], 120, 0) }),
    )
    const user = userEvent.setup()
    renderBrowser()

    const nextButton = screen.getByRole('button', { name: 'Next' })
    await user.click(nextButton) // offset -> 50
    await user.click(nextButton) // offset -> 100

    mockUseMemoryList.mockClear()
    // Re-return same data for subsequent renders
    mockUseMemoryList.mockReturnValue(
      listHookReturn({ data: listResponse([memoryA, memoryB, memoryC], 120, 100) }),
    )

    const prevButton = screen.getByRole('button', { name: 'Prev' })
    await user.click(prevButton)

    const offsetsAfterPrev = mockUseMemoryList.mock.calls.map((c) => c[0])
    // Prev from 100 should request offset=50
    expect(offsetsAfterPrev).toContain(50)
  })

  it('selecting a memory invokes useMemory with its id and renders detail fields', async () => {
    mockUseMemory.mockReturnValue(memoryHookReturn({ data: memoryA }))

    const user = userEvent.setup()
    renderBrowser()

    // Find the row button for memoryA by its id text (shown in row footer)
    const idCell = screen.getByText('project/foo.md')
    const rowButton = idCell.closest('button')!
    await user.click(rowButton)

    // useMemory should have been invoked with the selected memory's id at some point.
    const memoryCalls = mockUseMemory.mock.calls.map((c) => c[0])
    expect(memoryCalls).toContain('project/foo.md')

    // Detail panel fields from memoryA
    // Body renders in a dedicated panel; it appears once in the row preview and once in detail.
    const bodyMatches = screen.getAllByText(
      'Prefer top-level imports. Only use function-level imports for known circular imports.',
    )
    expect(bodyMatches.length).toBeGreaterThanOrEqual(2)

    // Tags
    expect(screen.getByText('python')).toBeInTheDocument()
    expect(screen.getByText('testing')).toBeInTheDocument()

    // Confidence badge
    expect(screen.getByText('conf:high')).toBeInTheDocument()

    // last_verified timestamp (unique: not shown in the row)
    expect(screen.getByText('2026-03-05T10:00:00Z')).toBeInTheDocument()

    // Citations heading ("Citations (1)") and citation file
    expect(screen.getByText('Citations (1)')).toBeInTheDocument()
    const citation = screen.getByText('spellbook/memory/store.py')
    expect(citation).toBeInTheDocument()
    // Symbol rendered alongside citation
    expect(
      within(citation.parentElement as HTMLElement).getByText(/class: MemoryStore/),
    ).toBeInTheDocument()
  })
})

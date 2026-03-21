import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest'
import { renderHook, waitFor, act } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createElement, type ReactNode } from 'react'
import type { ListResponse } from '../api/types'
import { useListPage } from './useListPage'

// Mock the fetchApi module
vi.mock('../api/client', () => ({
  fetchApi: vi.fn(),
}))

import { fetchApi } from '../api/client'

const mockFetchApi = fetchApi as Mock

interface TestItem {
  id: number
  name: string
}

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

function makeListResponse(
  items: TestItem[],
  overrides: Partial<ListResponse<TestItem>> = {}
): ListResponse<TestItem> {
  return {
    items,
    total: items.length,
    page: 1,
    per_page: 50,
    pages: 1,
    ...overrides,
  }
}

describe('useListPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('initial fetch', () => {
    it('fetches with default params on mount', async () => {
      const response = makeListResponse([{ id: 1, name: 'Alice' }])
      mockFetchApi.mockResolvedValueOnce(response)

      const { result } = renderHook(
        () =>
          useListPage<TestItem>({
            queryKey: ['test-items'],
            endpoint: '/api/items',
          }),
        { wrapper: createWrapper() }
      )

      await waitFor(() => expect(result.current.isLoading).toBe(false))

      expect(mockFetchApi).toHaveBeenCalledTimes(1)
      expect(mockFetchApi).toHaveBeenCalledWith('/api/items', {
        params: {
          page: 1,
          per_page: 50,
        },
      })

      expect(result.current.data).toEqual([{ id: 1, name: 'Alice' }])
      expect(result.current.total).toBe(1)
      expect(result.current.page).toBe(1)
      expect(result.current.pages).toBe(1)
      expect(result.current.perPage).toBe(50)
      expect(result.current.search).toBe('')
      expect(result.current.filters).toEqual({})
      expect(result.current.sorting).toEqual({
        column: undefined,
        order: 'asc',
      })
      expect(result.current.isError).toBe(false)
      expect(result.current.error).toBeNull()
    })

    /*
    ESCAPE: fetches with default params on mount
      CLAIM: Verifies hook fetches endpoint with default page=1, per_page=50 on mount
      PATH: useListPage -> useQuery -> fetchApi
      CHECK: fetchApi called once with exact endpoint and params; returned state matches response
      MUTATION: Changing default perPage from 50 to 25 would fail per_page assertion; omitting page param would fail
      ESCAPE: If fetchApi were called with extra unexpected params (e.g. sort=''), test wouldn't catch it since we only check the call args object. But fetchApi mock checks exact object shape.
      IMPACT: Wrong default params would cause server to return unexpected page sizes
    */

    it('uses custom defaultPerPage', async () => {
      const response = makeListResponse(
        [{ id: 1, name: 'Alice' }],
        { per_page: 25 }
      )
      mockFetchApi.mockResolvedValueOnce(response)

      const { result } = renderHook(
        () =>
          useListPage<TestItem>({
            queryKey: ['test-items'],
            endpoint: '/api/items',
            defaultPerPage: 25,
          }),
        { wrapper: createWrapper() }
      )

      await waitFor(() => expect(result.current.isLoading).toBe(false))

      expect(mockFetchApi).toHaveBeenCalledWith('/api/items', {
        params: {
          page: 1,
          per_page: 25,
        },
      })
      expect(result.current.perPage).toBe(25)
    })

    /*
    ESCAPE: uses custom defaultPerPage
      CLAIM: Verifies defaultPerPage option is respected in fetch params and returned state
      PATH: useListPage({defaultPerPage: 25}) -> useQuery -> fetchApi
      CHECK: fetchApi called with per_page=25; result.perPage === 25
      MUTATION: Ignoring defaultPerPage and always using 50 would fail both assertions
      ESCAPE: Nothing reasonable -- both the outgoing param and returned state are checked
      IMPACT: Pages would ignore user-configured page sizes
    */

    it('uses defaultSort in initial fetch', async () => {
      const response = makeListResponse([{ id: 1, name: 'Alice' }])
      mockFetchApi.mockResolvedValueOnce(response)

      const { result } = renderHook(
        () =>
          useListPage<TestItem>({
            queryKey: ['test-items'],
            endpoint: '/api/items',
            defaultSort: { column: 'name', order: 'desc' },
          }),
        { wrapper: createWrapper() }
      )

      await waitFor(() => expect(result.current.isLoading).toBe(false))

      expect(mockFetchApi).toHaveBeenCalledWith('/api/items', {
        params: {
          page: 1,
          per_page: 50,
          sort: 'name',
          order: 'desc',
        },
      })
      expect(result.current.sorting).toEqual({
        column: 'name',
        order: 'desc',
      })
    })

    /*
    ESCAPE: uses defaultSort in initial fetch
      CLAIM: Verifies defaultSort passes sort/order params and sets sorting state
      PATH: useListPage({defaultSort: {column:'name', order:'desc'}}) -> useQuery -> fetchApi
      CHECK: fetchApi params include sort='name', order='desc'; sorting state matches
      MUTATION: Ignoring defaultSort would omit sort/order from params, failing assertion
      ESCAPE: Nothing reasonable -- both params and state are fully asserted
      IMPACT: Default sort order would be ignored, showing unsorted data
    */

    it('includes defaultFilters in initial fetch', async () => {
      const response = makeListResponse([{ id: 1, name: 'Alice' }])
      mockFetchApi.mockResolvedValueOnce(response)

      const { result } = renderHook(
        () =>
          useListPage<TestItem>({
            queryKey: ['test-items'],
            endpoint: '/api/items',
            defaultFilters: { status: 'active', type: 'user' },
          }),
        { wrapper: createWrapper() }
      )

      await waitFor(() => expect(result.current.isLoading).toBe(false))

      expect(mockFetchApi).toHaveBeenCalledWith('/api/items', {
        params: {
          page: 1,
          per_page: 50,
          status: 'active',
          type: 'user',
        },
      })
      expect(result.current.filters).toEqual({
        status: 'active',
        type: 'user',
      })
    })

    /*
    ESCAPE: includes defaultFilters in initial fetch
      CLAIM: Verifies defaultFilters are passed as query params and set in state
      PATH: useListPage({defaultFilters: {status:'active'}}) -> useQuery -> fetchApi
      CHECK: fetchApi params include filter entries; filters state matches
      MUTATION: Not spreading filters into params would fail param assertion
      ESCAPE: Nothing reasonable -- both outgoing params and state checked
      IMPACT: Default filters would be ignored, showing unfiltered data
    */
  })

  describe('pagination', () => {
    it('changes page via setPage', async () => {
      const page1 = makeListResponse(
        [{ id: 1, name: 'Alice' }],
        { total: 100, pages: 2 }
      )
      const page2 = makeListResponse(
        [{ id: 2, name: 'Bob' }],
        { page: 2, total: 100, pages: 2 }
      )
      mockFetchApi.mockResolvedValueOnce(page1).mockResolvedValueOnce(page2)

      const { result } = renderHook(
        () =>
          useListPage<TestItem>({
            queryKey: ['test-items'],
            endpoint: '/api/items',
          }),
        { wrapper: createWrapper() }
      )

      await waitFor(() => expect(result.current.isLoading).toBe(false))

      act(() => result.current.setPage(2))

      await waitFor(() =>
        expect(result.current.data).toEqual([{ id: 2, name: 'Bob' }])
      )

      expect(result.current.page).toBe(2)
      expect(mockFetchApi).toHaveBeenCalledTimes(2)
      expect(mockFetchApi).toHaveBeenNthCalledWith(2, '/api/items', {
        params: {
          page: 2,
          per_page: 50,
        },
      })
    })

    /*
    ESCAPE: changes page via setPage
      CLAIM: setPage(2) triggers refetch with page=2 and updates page state
      PATH: setPage(2) -> state update -> useQuery refetch -> fetchApi
      CHECK: Second fetchApi call has page=2; result.page===2; data matches page2 response
      MUTATION: If setPage didn't update state, page would stay 1; if query didn't include page, params would be wrong
      ESCAPE: Nothing reasonable -- page param, page state, and data all verified
      IMPACT: Pagination wouldn't work
    */

    it('changes perPage and resets page to 1', async () => {
      const page1 = makeListResponse(
        [{ id: 1, name: 'Alice' }],
        { total: 100, pages: 4 }
      )
      const refetch = makeListResponse(
        [{ id: 1, name: 'Alice' }, { id: 2, name: 'Bob' }],
        { total: 100, per_page: 25, pages: 4 }
      )
      mockFetchApi.mockResolvedValueOnce(page1).mockResolvedValueOnce(refetch)

      const { result } = renderHook(
        () =>
          useListPage<TestItem>({
            queryKey: ['test-items'],
            endpoint: '/api/items',
          }),
        { wrapper: createWrapper() }
      )

      await waitFor(() => expect(result.current.isLoading).toBe(false))

      // First move to page 2
      act(() => result.current.setPage(2))
      // Then change perPage -- should reset to page 1
      act(() => result.current.setPerPage(25))

      await waitFor(() => expect(result.current.perPage).toBe(25))

      expect(result.current.page).toBe(1)
    })

    /*
    ESCAPE: changes perPage and resets page to 1
      CLAIM: setPerPage resets page to 1
      PATH: setPerPage(25) -> state update (page=1, perPage=25) -> refetch
      CHECK: page===1 and perPage===25 after setPerPage
      MUTATION: If setPerPage didn't reset page, page would remain 2
      ESCAPE: Nothing reasonable -- both page and perPage are checked
      IMPACT: User would stay on (now potentially invalid) page number after changing page size
    */
  })

  describe('search', () => {
    it('includes search in query params and resets page', async () => {
      const initial = makeListResponse([{ id: 1, name: 'Alice' }], { total: 100, pages: 2 })
      const page2 = makeListResponse([{ id: 1, name: 'Alice' }], { page: 2, total: 100, pages: 2 })
      const searched = makeListResponse([{ id: 2, name: 'Bob' }], { total: 1 })
      mockFetchApi
        .mockResolvedValueOnce(initial)
        .mockResolvedValueOnce(page2)
        .mockResolvedValueOnce(searched)

      const { result } = renderHook(
        () =>
          useListPage<TestItem>({
            queryKey: ['test-items'],
            endpoint: '/api/items',
          }),
        { wrapper: createWrapper() }
      )

      await waitFor(() => expect(result.current.isLoading).toBe(false))

      // Move to page 2 first, wait for it to resolve, then search -- should reset to page 1
      act(() => result.current.setPage(2))
      await waitFor(() => expect(result.current.page).toBe(2))
      act(() => result.current.setSearch('bob'))

      await waitFor(() =>
        expect(result.current.data).toEqual([{ id: 2, name: 'Bob' }])
      )

      expect(result.current.page).toBe(1)
      expect(result.current.search).toBe('bob')

      // Find the call that includes search param
      const searchCall = mockFetchApi.mock.calls.find(
        (call: unknown[]) => (call[1] as { params: Record<string, unknown> }).params.search === 'bob'
      )
      expect(searchCall).toBeDefined()
      expect(searchCall![1]).toEqual({
        params: {
          page: 1,
          per_page: 50,
          search: 'bob',
        },
      })
    })

    /*
    ESCAPE: includes search in query params and resets page
      CLAIM: setSearch adds search param and resets page to 1
      PATH: setSearch('bob') -> state update (search='bob', page=1) -> refetch
      CHECK: page===1, search==='bob', fetchApi call includes search='bob' with page=1
      MUTATION: Not resetting page would leave page=2; not including search in params would fail searchCall assertion
      ESCAPE: Nothing reasonable -- page reset, search state, and outgoing params all checked
      IMPACT: Search results would show wrong page or not filter by search term
    */

    it('does not include empty search in params', async () => {
      const response = makeListResponse([{ id: 1, name: 'Alice' }])
      mockFetchApi.mockResolvedValueOnce(response)

      const { result } = renderHook(
        () =>
          useListPage<TestItem>({
            queryKey: ['test-items'],
            endpoint: '/api/items',
          }),
        { wrapper: createWrapper() }
      )

      await waitFor(() => expect(result.current.isLoading).toBe(false))

      expect(mockFetchApi).toHaveBeenCalledWith('/api/items', {
        params: {
          page: 1,
          per_page: 50,
        },
      })
    })

    /*
    ESCAPE: does not include empty search in params
      CLAIM: Empty search string is not included as a param
      PATH: useListPage with no search set -> fetchApi
      CHECK: params object has only page and per_page, no search key
      MUTATION: Including search='' would add extra key, failing exact equality
      ESCAPE: Nothing reasonable -- exact object equality catches extra keys
      IMPACT: Server might interpret empty search differently than no search
    */
  })

  describe('filters', () => {
    it('sets individual filters and resets page', async () => {
      const initial = makeListResponse([{ id: 1, name: 'Alice' }], { total: 100, pages: 2 })
      const page2 = makeListResponse([{ id: 1, name: 'Alice' }], { page: 2, total: 100, pages: 2 })
      const filtered = makeListResponse([{ id: 2, name: 'Bob' }])
      mockFetchApi
        .mockResolvedValueOnce(initial)
        .mockResolvedValueOnce(page2)
        .mockResolvedValueOnce(filtered)

      const { result } = renderHook(
        () =>
          useListPage<TestItem>({
            queryKey: ['test-items'],
            endpoint: '/api/items',
          }),
        { wrapper: createWrapper() }
      )

      await waitFor(() => expect(result.current.isLoading).toBe(false))

      act(() => result.current.setPage(2))
      await waitFor(() => expect(result.current.page).toBe(2))
      act(() => result.current.setFilters({ status: 'active' }))

      await waitFor(() =>
        expect(result.current.data).toEqual([{ id: 2, name: 'Bob' }])
      )

      expect(result.current.page).toBe(1)
      expect(result.current.filters).toEqual({ status: 'active' })
    })

    /*
    ESCAPE: sets individual filters and resets page
      CLAIM: setFilters updates filter state and resets page to 1
      PATH: setFilters({status:'active'}) -> state update (page=1) -> refetch
      CHECK: page===1, filters==={status:'active'}, data matches filtered response
      MUTATION: Not resetting page would leave page=2; wrong filter state would fail equality
      ESCAPE: Nothing reasonable -- page, filters, and data all verified
      IMPACT: Filter changes would show wrong page
    */

    it('clears all filters and resets page', async () => {
      const initial = makeListResponse([{ id: 1, name: 'Alice' }])
      const withFilter = makeListResponse([{ id: 2, name: 'Bob' }])
      const cleared = makeListResponse([{ id: 1, name: 'Alice' }, { id: 2, name: 'Bob' }], { total: 2 })
      mockFetchApi
        .mockResolvedValueOnce(initial)
        .mockResolvedValueOnce(withFilter)
        .mockResolvedValueOnce(cleared)

      const { result } = renderHook(
        () =>
          useListPage<TestItem>({
            queryKey: ['test-items'],
            endpoint: '/api/items',
          }),
        { wrapper: createWrapper() }
      )

      await waitFor(() => expect(result.current.isLoading).toBe(false))

      act(() => result.current.setFilters({ status: 'active' }))
      await waitFor(() =>
        expect(result.current.filters).toEqual({ status: 'active' })
      )

      act(() => result.current.clearFilters())

      await waitFor(() => expect(result.current.filters).toEqual({}))
      expect(result.current.page).toBe(1)
    })

    /*
    ESCAPE: clears all filters and resets page
      CLAIM: clearFilters resets filters to {} and page to 1
      PATH: clearFilters() -> state update -> refetch
      CHECK: filters==={}, page===1
      MUTATION: If clearFilters didn't clear, filters would still have status key
      ESCAPE: Nothing reasonable -- both state values checked
      IMPACT: Users couldn't reset filters
    */
  })

  describe('sorting', () => {
    it('sets sorting via setSorting', async () => {
      const initial = makeListResponse([{ id: 1, name: 'Alice' }])
      const sorted = makeListResponse([{ id: 2, name: 'Bob' }])
      mockFetchApi.mockResolvedValueOnce(initial).mockResolvedValueOnce(sorted)

      const { result } = renderHook(
        () =>
          useListPage<TestItem>({
            queryKey: ['test-items'],
            endpoint: '/api/items',
          }),
        { wrapper: createWrapper() }
      )

      await waitFor(() => expect(result.current.isLoading).toBe(false))

      act(() => result.current.setSorting({ column: 'name', order: 'asc' }))

      await waitFor(() =>
        expect(result.current.sorting).toEqual({ column: 'name', order: 'asc' })
      )

      const sortCall = mockFetchApi.mock.calls.find(
        (call: unknown[]) => (call[1] as { params: Record<string, unknown> }).params.sort === 'name'
      )
      expect(sortCall).toBeDefined()
      expect(sortCall![1]).toEqual({
        params: {
          page: 1,
          per_page: 50,
          sort: 'name',
          order: 'asc',
        },
      })
    })

    /*
    ESCAPE: sets sorting via setSorting
      CLAIM: setSorting updates sorting state and includes sort/order in params
      PATH: setSorting({column:'name', order:'asc'}) -> state update -> refetch
      CHECK: sorting state matches; fetchApi called with sort='name', order='asc'
      MUTATION: Not passing sort params would fail sortCall assertion; wrong state would fail equality
      ESCAPE: Nothing reasonable -- both state and outgoing params verified
      IMPACT: Sort column/order wouldn't be sent to server
    */
  })

  describe('transformItem', () => {
    it('applies transformItem to each item in response', async () => {
      const response = makeListResponse([
        { id: 1, name: 'alice' },
        { id: 2, name: 'bob' },
      ])
      mockFetchApi.mockResolvedValueOnce(response)

      const { result } = renderHook(
        () =>
          useListPage<TestItem>({
            queryKey: ['test-items'],
            endpoint: '/api/items',
            transformItem: (item) => ({ ...item, name: item.name.toUpperCase() }),
          }),
        { wrapper: createWrapper() }
      )

      await waitFor(() => expect(result.current.isLoading).toBe(false))

      expect(result.current.data).toEqual([
        { id: 1, name: 'ALICE' },
        { id: 2, name: 'BOB' },
      ])
    })

    /*
    ESCAPE: applies transformItem to each item in response
      CLAIM: transformItem function is applied to each item in the response
      PATH: fetchApi returns items -> transformItem maps -> data
      CHECK: data items have uppercase names (transformed)
      MUTATION: Not calling transformItem would leave names lowercase, failing assertion
      ESCAPE: Nothing reasonable -- exact data equality catches missing transform
      IMPACT: Item transformations wouldn't be applied, breaking consumer expectations
    */
  })

  describe('tableProps', () => {
    it('returns tableProps matching DataTable component interface', async () => {
      const response = makeListResponse(
        [{ id: 1, name: 'Alice' }],
        { total: 100, pages: 2 }
      )
      mockFetchApi.mockResolvedValueOnce(response)

      const { result } = renderHook(
        () =>
          useListPage<TestItem>({
            queryKey: ['test-items'],
            endpoint: '/api/items',
          }),
        { wrapper: createWrapper() }
      )

      await waitFor(() => expect(result.current.isLoading).toBe(false))

      const tp = result.current.tableProps

      // data matches response items
      expect(tp.data).toEqual([{ id: 1, name: 'Alice' }])

      // loading is boolean
      expect(tp.loading).toBe(false)

      // pagination object matches DataTable's PaginationConfig
      expect(tp.pagination).toEqual({
        page: 1,
        pages: 2,
        total: 100,
        perPage: 50,
        onPageChange: expect.any(Function),
        onPerPageChange: expect.any(Function),
      })

      // sorting object matches DataTable's SortingConfig
      // When no sort column set, sortColumn should be undefined
      expect(tp.sorting).toEqual({
        sortColumn: undefined,
        sortOrder: 'asc',
        onSortChange: expect.any(Function),
      })
    })

    /*
    ESCAPE: returns tableProps matching DataTable component interface
      CLAIM: tableProps has data, loading, pagination, and sorting matching DataTable props
      PATH: useListPage -> constructs tableProps from internal state
      CHECK: Exact structure of pagination (page, pages, total, perPage, callbacks) and sorting (sortColumn, sortOrder, onSortChange)
      MUTATION: Wrong field names (e.g. 'currentPage' vs 'page') would fail; missing fields would fail
      ESCAPE: The onPageChange/onPerPageChange/onSortChange callbacks use expect.any(Function) -- a no-op function would pass. But functional behavior is tested in other tests.
      IMPACT: DataTable spread would break if tableProps shape is wrong
    */

    it('tableProps.pagination.onPageChange calls setPage', async () => {
      const page1 = makeListResponse(
        [{ id: 1, name: 'Alice' }],
        { total: 100, pages: 2 }
      )
      const page2 = makeListResponse(
        [{ id: 2, name: 'Bob' }],
        { page: 2, total: 100, pages: 2 }
      )
      mockFetchApi.mockResolvedValueOnce(page1).mockResolvedValueOnce(page2)

      const { result } = renderHook(
        () =>
          useListPage<TestItem>({
            queryKey: ['test-items'],
            endpoint: '/api/items',
          }),
        { wrapper: createWrapper() }
      )

      await waitFor(() => expect(result.current.isLoading).toBe(false))

      act(() => result.current.tableProps.pagination!.onPageChange(2))

      await waitFor(() =>
        expect(result.current.data).toEqual([{ id: 2, name: 'Bob' }])
      )
      expect(result.current.page).toBe(2)
    })

    /*
    ESCAPE: tableProps.pagination.onPageChange calls setPage
      CLAIM: Calling onPageChange(2) via tableProps updates page state
      PATH: tableProps.pagination.onPageChange(2) -> setPage(2) -> refetch
      CHECK: page===2 and data matches page 2 response
      MUTATION: If onPageChange were a no-op, page would stay 1
      ESCAPE: Nothing reasonable -- both page state and data are verified
      IMPACT: DataTable pagination clicks wouldn't navigate
    */

    it('tableProps.sorting.onSortChange updates sorting', async () => {
      const initial = makeListResponse([{ id: 1, name: 'Alice' }])
      const sorted = makeListResponse([{ id: 2, name: 'Bob' }])
      mockFetchApi.mockResolvedValueOnce(initial).mockResolvedValueOnce(sorted)

      const { result } = renderHook(
        () =>
          useListPage<TestItem>({
            queryKey: ['test-items'],
            endpoint: '/api/items',
          }),
        { wrapper: createWrapper() }
      )

      await waitFor(() => expect(result.current.isLoading).toBe(false))

      act(() => result.current.tableProps.sorting!.onSortChange('name'))

      await waitFor(() =>
        expect(result.current.sorting).toEqual({ column: 'name', order: 'asc' })
      )
      expect(result.current.tableProps.sorting).toEqual({
        sortColumn: 'name',
        sortOrder: 'asc',
        onSortChange: expect.any(Function),
      })
    })

    /*
    ESCAPE: tableProps.sorting.onSortChange updates sorting
      CLAIM: Calling onSortChange('name') via tableProps updates sorting state
      PATH: tableProps.sorting.onSortChange('name') -> setSorting -> state update
      CHECK: sorting state has column='name', order='asc'; tableProps.sorting reflects same
      MUTATION: If onSortChange were no-op, sorting.column would stay undefined
      ESCAPE: Nothing reasonable -- both internal sorting and tableProps.sorting checked
      IMPACT: DataTable column header clicks wouldn't sort
    */

    it('tableProps.sorting.onSortChange toggles order when same column clicked', async () => {
      const initial = makeListResponse([{ id: 1, name: 'Alice' }])
      const sorted1 = makeListResponse([{ id: 2, name: 'Bob' }])
      const sorted2 = makeListResponse([{ id: 1, name: 'Alice' }])
      mockFetchApi
        .mockResolvedValueOnce(initial)
        .mockResolvedValueOnce(sorted1)
        .mockResolvedValueOnce(sorted2)

      const { result } = renderHook(
        () =>
          useListPage<TestItem>({
            queryKey: ['test-items'],
            endpoint: '/api/items',
          }),
        { wrapper: createWrapper() }
      )

      await waitFor(() => expect(result.current.isLoading).toBe(false))

      // First click: set to 'name' asc
      act(() => result.current.tableProps.sorting!.onSortChange('name'))
      await waitFor(() =>
        expect(result.current.sorting).toEqual({ column: 'name', order: 'asc' })
      )

      // Second click on same column: toggle to desc
      act(() => result.current.tableProps.sorting!.onSortChange('name'))
      await waitFor(() =>
        expect(result.current.sorting).toEqual({ column: 'name', order: 'desc' })
      )
    })

    /*
    ESCAPE: tableProps.sorting.onSortChange toggles order when same column clicked
      CLAIM: Clicking same column toggles between asc and desc
      PATH: onSortChange('name') x2 -> toggles order
      CHECK: First call sets asc, second call sets desc
      MUTATION: If toggle logic were broken (always asc), second assertion would fail
      ESCAPE: Nothing reasonable -- both orderings checked in sequence
      IMPACT: Users couldn't reverse sort order by clicking column header again
    */
  })

  describe('error handling', () => {
    it('exposes error state on fetch failure', async () => {
      const error = new Error('Network error')
      mockFetchApi.mockRejectedValueOnce(error)

      const { result } = renderHook(
        () =>
          useListPage<TestItem>({
            queryKey: ['test-items-error'],
            endpoint: '/api/items',
          }),
        { wrapper: createWrapper() }
      )

      await waitFor(() => expect(result.current.isError).toBe(true))

      expect(result.current.error).toBeInstanceOf(Error)
      expect((result.current.error as Error).message).toBe('Network error')
      expect(result.current.data).toEqual([])
      expect(result.current.total).toBe(0)
    })

    /*
    ESCAPE: exposes error state on fetch failure
      CLAIM: When fetchApi rejects, hook exposes error state
      PATH: fetchApi throws -> useQuery error state -> hook returns
      CHECK: isError===true, error.message==='Network error', data===[], total===0
      MUTATION: Not exposing error would leave isError false; not defaulting data would be undefined
      ESCAPE: Nothing reasonable -- error state, message, and fallback data all checked
      IMPACT: Error states wouldn't be visible to users
    */
  })

  describe('combined state in query params', () => {
    it('builds params from all state: page, perPage, sort, search, filters', async () => {
      const response = makeListResponse([{ id: 1, name: 'Alice' }])
      // Need multiple mocks for each state change refetch
      mockFetchApi
        .mockResolvedValueOnce(makeListResponse([]))  // initial
        .mockResolvedValueOnce(makeListResponse([]))  // after search
        .mockResolvedValueOnce(makeListResponse([]))  // after filter
        .mockResolvedValueOnce(makeListResponse([]))  // after sort
        .mockResolvedValueOnce(response)               // final

      const { result } = renderHook(
        () =>
          useListPage<TestItem>({
            queryKey: ['test-items'],
            endpoint: '/api/items',
          }),
        { wrapper: createWrapper() }
      )

      await waitFor(() => expect(result.current.isLoading).toBe(false))

      act(() => result.current.setSearch('alice'))
      await waitFor(() => expect(result.current.search).toBe('alice'))

      act(() => result.current.setFilters({ status: 'active' }))
      await waitFor(() =>
        expect(result.current.filters).toEqual({ status: 'active' })
      )

      act(() => result.current.setSorting({ column: 'name', order: 'desc' }))
      await waitFor(() =>
        expect(result.current.sorting).toEqual({ column: 'name', order: 'desc' })
      )

      act(() => result.current.setPage(2))
      await waitFor(() => expect(result.current.page).toBe(2))

      // Find the call with all params combined
      const lastCall = mockFetchApi.mock.calls[mockFetchApi.mock.calls.length - 1]
      expect(lastCall[0]).toBe('/api/items')
      expect(lastCall[1]).toEqual({
        params: {
          page: 2,
          per_page: 50,
          sort: 'name',
          order: 'desc',
          search: 'alice',
          status: 'active',
        },
      })
    })

    /*
    ESCAPE: builds params from all state
      CLAIM: All state (page, perPage, sort, search, filters) combined into query params
      PATH: Multiple state updates -> final fetchApi call
      CHECK: Last fetchApi call has exact params object with all fields
      MUTATION: Omitting any state from params would fail exact equality
      ESCAPE: If intermediate calls had wrong params, we wouldn't catch them. But we verify the final combined state which is the important one.
      IMPACT: Server wouldn't receive full query context
    */
  })
})

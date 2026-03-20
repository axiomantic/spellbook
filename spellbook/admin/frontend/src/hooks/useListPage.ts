import { useState, useCallback, useMemo } from 'react'
import { useQuery, keepPreviousData } from '@tanstack/react-query'
import { fetchApi } from '../api/client'
import type { ListResponse } from '../api/types'

export interface SortingState {
  column: string | undefined
  order: 'asc' | 'desc'
}

export interface UseListPageOptions<T> {
  queryKey: string[]
  endpoint: string
  defaultPerPage?: number
  defaultSort?: SortingState
  defaultFilters?: Record<string, string>
  refetchInterval?: number
  transformItem?: (item: T) => T
}

export interface UseListPageReturn<T> {
  data: T[]
  total: number
  isLoading: boolean
  isError: boolean
  error: Error | null
  page: number
  pages: number
  perPage: number
  setPage: (page: number) => void
  setPerPage: (perPage: number) => void
  sorting: SortingState
  setSorting: (sorting: SortingState) => void
  search: string
  setSearch: (search: string) => void
  filters: Record<string, string>
  setFilters: (filters: Record<string, string>) => void
  clearFilters: () => void
  tableProps: {
    data: T[]
    loading: boolean
    pagination?: {
      page: number
      pages: number
      total: number
      perPage: number
      onPageChange: (page: number) => void
      onPerPageChange: (perPage: number) => void
    }
    sorting?: {
      sortColumn: string | undefined
      sortOrder: 'asc' | 'desc'
      onSortChange: (columnId: string) => void
    }
  }
}

export function useListPage<T>(options: UseListPageOptions<T>): UseListPageReturn<T> {
  const {
    queryKey,
    endpoint,
    defaultPerPage = 50,
    defaultSort = { column: undefined, order: 'asc' as const },
    defaultFilters = {},
    refetchInterval,
    transformItem,
  } = options

  const [page, setPageRaw] = useState(1)
  const [perPage, setPerPageRaw] = useState(defaultPerPage)
  const [sorting, setSortingRaw] = useState<SortingState>(defaultSort)
  const [search, setSearchRaw] = useState('')
  const [filters, setFiltersRaw] = useState<Record<string, string>>(defaultFilters)

  const setPage = useCallback((p: number) => setPageRaw(p), [])

  const setPerPage = useCallback((pp: number) => {
    setPerPageRaw(pp)
    setPageRaw(1)
  }, [])

  const setSorting = useCallback((s: SortingState) => setSortingRaw(s), [])

  const setSearch = useCallback((s: string) => {
    setSearchRaw(s)
    setPageRaw(1)
  }, [])

  const setFilters = useCallback((f: Record<string, string>) => {
    setFiltersRaw(f)
    setPageRaw(1)
  }, [])

  const clearFilters = useCallback(() => {
    setFiltersRaw({})
    setPageRaw(1)
  }, [])

  const params = useMemo(() => {
    const p: Record<string, string | number> = {
      page,
      per_page: perPage,
    }
    if (sorting.column) {
      p.sort = sorting.column
      p.order = sorting.order
    }
    if (search) {
      p.search = search
    }
    for (const [key, value] of Object.entries(filters)) {
      p[key] = value
    }
    return p
  }, [page, perPage, sorting, search, filters])

  const query = useQuery<ListResponse<T>>({
    queryKey: [...queryKey, params],
    queryFn: () => fetchApi<ListResponse<T>>(endpoint, { params }),
    placeholderData: keepPreviousData,
    refetchInterval,
  })

  const items = useMemo(() => {
    const raw = query.data?.items ?? []
    if (transformItem) {
      return raw.map(transformItem)
    }
    return raw
  }, [query.data, transformItem])

  const total = query.data?.total ?? 0
  const pages = query.data?.pages ?? 0

  const handleSortChange = useCallback(
    (columnId: string) => {
      setSortingRaw((prev) => {
        if (prev.column === columnId) {
          return { column: columnId, order: prev.order === 'asc' ? 'desc' : 'asc' }
        }
        return { column: columnId, order: 'asc' }
      })
    },
    []
  )

  const tableProps = useMemo(
    () => ({
      data: items,
      loading: query.isLoading,
      pagination: {
        page,
        pages,
        total,
        perPage,
        onPageChange: setPage,
        onPerPageChange: setPerPage,
      },
      sorting: {
        sortColumn: sorting.column,
        sortOrder: sorting.order,
        onSortChange: handleSortChange,
      },
    }),
    [items, query.isLoading, page, pages, total, perPage, setPage, setPerPage, sorting, handleSortChange]
  )

  return {
    data: items,
    total,
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    page,
    pages,
    perPage,
    setPage,
    setPerPage,
    sorting,
    setSorting,
    search,
    setSearch,
    filters,
    setFilters,
    clearFilters,
    tableProps,
  }
}

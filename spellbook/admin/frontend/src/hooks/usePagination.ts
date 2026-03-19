import { useState, useCallback } from 'react'

interface PaginationState {
  page: number
  per_page: number
}

interface UsePaginationReturn extends PaginationState {
  setPage: (page: number) => void
  setPerPage: (perPage: number) => void
  nextPage: () => void
  prevPage: () => void
  resetPage: () => void
}

export function usePagination(initialPerPage = 50): UsePaginationReturn {
  const [state, setState] = useState<PaginationState>({ page: 1, per_page: initialPerPage })

  const setPage = useCallback((page: number) => setState(s => ({ ...s, page })), [])
  const setPerPage = useCallback((per_page: number) => setState({ page: 1, per_page }), [])
  const nextPage = useCallback(() => setState(s => ({ ...s, page: s.page + 1 })), [])
  const prevPage = useCallback(() => setState(s => ({ ...s, page: Math.max(1, s.page - 1) })), [])
  const resetPage = useCallback(() => setState(s => ({ ...s, page: 1 })), [])

  return { ...state, setPage, setPerPage, nextPage, prevPage, resetPage }
}

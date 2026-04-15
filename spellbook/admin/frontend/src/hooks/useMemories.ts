import { useQuery } from '@tanstack/react-query'
import { fetchApi } from '../api/client'
import type {
  MemoryItem,
  MemoryListResponse,
  MemorySearchResponse,
} from '../api/types'

export function useMemoryList(offset = 0, limit = 50) {
  return useQuery({
    queryKey: ['memories', offset, limit],
    queryFn: () =>
      fetchApi<MemoryListResponse>(
        `/api/memories?offset=${offset}&limit=${limit}`,
      ),
  })
}

export function useMemory(id: string | null) {
  return useQuery({
    queryKey: ['memory', id],
    queryFn: () =>
      fetchApi<MemoryItem>(
        `/api/memories/${id!.split('/').map(encodeURIComponent).join('/')}`,
      ),
    enabled: !!id,
  })
}

export function useMemorySearch(query: string, limit = 10) {
  return useQuery({
    queryKey: ['memory-search', query, limit],
    queryFn: () =>
      fetchApi<MemorySearchResponse>(
        `/api/memories/search?q=${encodeURIComponent(query)}&limit=${limit}`,
      ),
    enabled: query.trim().length > 0,
  })
}

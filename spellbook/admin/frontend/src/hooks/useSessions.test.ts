import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createElement, type ReactNode } from 'react'
import type {
  SessionDetail,
  SessionMessage,
  SessionMessagesResponse,
} from '../api/types'
import { useSessionDetail, useSessionMessages } from './useSessions'

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

describe('useSessionDetail', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('fetches session detail with correct URL encoding', async () => {
    const mockDetail: SessionDetail = {
      id: 'abc-123',
      project: 'Users-alice-myproject',
      project_decoded: '/Users/alice/myproject',
      slug: 'my-session',
      custom_title: 'Custom Title',
      created_at: '2026-03-15T10:00:00Z',
      last_activity: '2026-03-15T11:00:00Z',
      message_count: 42,
      size_bytes: 8192,
      first_user_message: 'Hello world',
    }
    mockFetchApi.mockResolvedValueOnce(mockDetail)

    const { result } = renderHook(
      () => useSessionDetail('Users-alice-myproject', 'abc-123'),
      { wrapper: createWrapper() }
    )

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    // Verify fetchApi was called with correct URL (project and id are URI-encoded)
    expect(mockFetchApi).toHaveBeenCalledTimes(1)
    expect(mockFetchApi).toHaveBeenCalledWith(
      '/api/sessions/Users-alice-myproject/abc-123'
    )

    // Verify the returned data matches the mock exactly
    expect(result.current.data).toEqual({
      id: 'abc-123',
      project: 'Users-alice-myproject',
      project_decoded: '/Users/alice/myproject',
      slug: 'my-session',
      custom_title: 'Custom Title',
      created_at: '2026-03-15T10:00:00Z',
      last_activity: '2026-03-15T11:00:00Z',
      message_count: 42,
      size_bytes: 8192,
      first_user_message: 'Hello world',
    })
  })

  it('encodes special characters in project and sessionId URL segments', async () => {
    const mockDetail: SessionDetail = {
      id: 'session/with+special',
      project: 'project%name',
      project_decoded: '/project%name',
      slug: null,
      custom_title: null,
      created_at: null,
      last_activity: null,
      message_count: 0,
      size_bytes: 0,
      first_user_message: null,
    }
    mockFetchApi.mockResolvedValueOnce(mockDetail)

    const { result } = renderHook(
      () => useSessionDetail('project%name', 'session/with+special'),
      { wrapper: createWrapper() }
    )

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    // encodeURIComponent encodes % -> %25, / -> %2F, + -> %2B
    expect(mockFetchApi).toHaveBeenCalledTimes(1)
    expect(mockFetchApi).toHaveBeenCalledWith(
      '/api/sessions/project%25name/session%2Fwith%2Bspecial'
    )
  })

  it('is disabled when project is empty', async () => {
    const { result } = renderHook(
      () => useSessionDetail('', 'abc-123'),
      { wrapper: createWrapper() }
    )

    // Query should not fire when project is empty
    expect(result.current.fetchStatus).toBe('idle')
    expect(mockFetchApi).not.toHaveBeenCalled()
  })

  it('is disabled when sessionId is empty', async () => {
    const { result } = renderHook(
      () => useSessionDetail('my-project', ''),
      { wrapper: createWrapper() }
    )

    // Query should not fire when sessionId is empty
    expect(result.current.fetchStatus).toBe('idle')
    expect(mockFetchApi).not.toHaveBeenCalled()
  })

  it('uses correct query key structure', async () => {
    const mockDetail: SessionDetail = {
      id: 'abc-123',
      project: 'proj',
      project_decoded: '/proj',
      slug: null,
      custom_title: null,
      created_at: null,
      last_activity: null,
      message_count: 0,
      size_bytes: 0,
      first_user_message: null,
    }
    mockFetchApi.mockResolvedValueOnce(mockDetail)

    const wrapper = createWrapper()
    const { result, rerender } = renderHook(
      () => useSessionDetail('proj', 'abc-123'),
      { wrapper }
    )

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    // Re-render the same component (same args) should not trigger another fetch
    rerender()

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    // Still only one call total due to same query key
    expect(mockFetchApi).toHaveBeenCalledTimes(1)

    // Verify data is still available from cache
    expect(result.current.data).toEqual({
      id: 'abc-123',
      project: 'proj',
      project_decoded: '/proj',
      slug: null,
      custom_title: null,
      created_at: null,
      last_activity: null,
      message_count: 0,
      size_bytes: 0,
      first_user_message: null,
    })
  })
})

describe('useSessionMessages', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('fetches messages with correct URL and pagination params', async () => {
    const mockMessage: SessionMessage = {
      line_number: 1,
      type: 'user',
      timestamp: '2026-03-15T10:00:00Z',
      content: 'Hello',
      is_compact_summary: false,
      raw: { type: 'user', message: { content: 'Hello' } },
    }
    const mockResponse: SessionMessagesResponse = {
      messages: [mockMessage],
      total_lines: 50,
      page: 2,
      per_page: 100,
      pages: 1,
    }
    mockFetchApi.mockResolvedValueOnce(mockResponse)

    const { result } = renderHook(
      () => useSessionMessages('my-project', 'sess-456', 2),
      { wrapper: createWrapper() }
    )

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(mockFetchApi).toHaveBeenCalledTimes(1)
    expect(mockFetchApi).toHaveBeenCalledWith(
      '/api/sessions/my-project/sess-456/messages',
      { params: { page: 2, per_page: 100 } }
    )

    // Verify full response structure
    expect(result.current.data).toEqual({
      messages: [
        {
          line_number: 1,
          type: 'user',
          timestamp: '2026-03-15T10:00:00Z',
          content: 'Hello',
          is_compact_summary: false,
          raw: { type: 'user', message: { content: 'Hello' } },
        },
      ],
      total_lines: 50,
      page: 2,
      per_page: 100,
      pages: 1,
    })
  })

  it('encodes special characters in URL segments for messages', async () => {
    const mockResponse: SessionMessagesResponse = {
      messages: [],
      total_lines: 0,
      page: 1,
      per_page: 100,
      pages: 0,
    }
    mockFetchApi.mockResolvedValueOnce(mockResponse)

    const { result } = renderHook(
      () => useSessionMessages('project%name', 'session/id', 1),
      { wrapper: createWrapper() }
    )

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(mockFetchApi).toHaveBeenCalledTimes(1)
    expect(mockFetchApi).toHaveBeenCalledWith(
      '/api/sessions/project%25name/session%2Fid/messages',
      { params: { page: 1, per_page: 100 } }
    )
  })

  it('is disabled when project is empty', async () => {
    const { result } = renderHook(
      () => useSessionMessages('', 'sess-456', 1),
      { wrapper: createWrapper() }
    )

    expect(result.current.fetchStatus).toBe('idle')
    expect(mockFetchApi).not.toHaveBeenCalled()
  })

  it('is disabled when sessionId is empty', async () => {
    const { result } = renderHook(
      () => useSessionMessages('my-project', '', 1),
      { wrapper: createWrapper() }
    )

    expect(result.current.fetchStatus).toBe('idle')
    expect(mockFetchApi).not.toHaveBeenCalled()
  })

  it('uses keepPreviousData for smooth pagination', async () => {
    const page1Response: SessionMessagesResponse = {
      messages: [
        {
          line_number: 1,
          type: 'user',
          timestamp: '2026-03-15T10:00:00Z',
          content: 'Page 1 message',
          is_compact_summary: false,
          raw: null,
        },
      ],
      total_lines: 200,
      page: 1,
      per_page: 100,
      pages: 2,
    }
    mockFetchApi.mockResolvedValueOnce(page1Response)

    const wrapper = createWrapper()
    const { result, rerender } = renderHook(
      ({ page }: { page: number }) => useSessionMessages('proj', 'sess', page),
      { wrapper, initialProps: { page: 1 } }
    )

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual(page1Response)

    // Now change to page 2 - previous data should still be available
    const page2Response: SessionMessagesResponse = {
      messages: [
        {
          line_number: 101,
          type: 'assistant',
          timestamp: '2026-03-15T10:05:00Z',
          content: 'Page 2 message',
          is_compact_summary: false,
          raw: null,
        },
      ],
      total_lines: 200,
      page: 2,
      per_page: 100,
      pages: 2,
    }
    mockFetchApi.mockResolvedValueOnce(page2Response)

    rerender({ page: 2 })

    // While fetching page 2, previous data (page 1) should still be shown
    // isPlaceholderData will be true while the new page loads
    expect(result.current.data).toEqual(page1Response)

    await waitFor(() =>
      expect(result.current.data).toEqual(page2Response)
    )
  })

  it('includes page in query key for separate caching per page', async () => {
    const page1Response: SessionMessagesResponse = {
      messages: [],
      total_lines: 0,
      page: 1,
      per_page: 100,
      pages: 0,
    }
    const page2Response: SessionMessagesResponse = {
      messages: [],
      total_lines: 0,
      page: 2,
      per_page: 100,
      pages: 0,
    }
    mockFetchApi
      .mockResolvedValueOnce(page1Response)
      .mockResolvedValueOnce(page2Response)

    const wrapper = createWrapper()

    // Fetch page 1
    const { result: r1 } = renderHook(
      () => useSessionMessages('proj', 'sess', 1),
      { wrapper }
    )
    await waitFor(() => expect(r1.current.isSuccess).toBe(true))

    // Fetch page 2 (different query key, so separate fetch)
    const { result: r2 } = renderHook(
      () => useSessionMessages('proj', 'sess', 2),
      { wrapper }
    )
    await waitFor(() => expect(r2.current.isSuccess).toBe(true))

    // Both pages fetched separately
    expect(mockFetchApi).toHaveBeenCalledTimes(2)
    expect(mockFetchApi).toHaveBeenNthCalledWith(
      1,
      '/api/sessions/proj/sess/messages',
      { params: { page: 1, per_page: 100 } }
    )
    expect(mockFetchApi).toHaveBeenNthCalledWith(
      2,
      '/api/sessions/proj/sess/messages',
      { params: { page: 2, per_page: 100 } }
    )
  })
})

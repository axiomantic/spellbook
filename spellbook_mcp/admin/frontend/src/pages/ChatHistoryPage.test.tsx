import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createElement } from 'react'
import { ChatHistoryPage } from './ChatHistoryPage'
import type { SessionMessage } from '../api/types'

// Mock the useSessions hooks
vi.mock('../hooks/useSessions', () => ({
  useSessionDetail: vi.fn(),
  useSessionMessages: vi.fn(),
  useSessions: vi.fn(),
}))

// Mock usePagination to control page state
vi.mock('../hooks/usePagination', () => ({
  usePagination: vi.fn(() => ({
    page: 1,
    per_page: 100,
    setPage: vi.fn(),
    setPerPage: vi.fn(),
    nextPage: vi.fn(),
    prevPage: vi.fn(),
    resetPage: vi.fn(),
  })),
}))

import { useSessionDetail, useSessionMessages } from '../hooks/useSessions'
import { usePagination } from '../hooks/usePagination'

const mockUseSessionDetail = useSessionDetail as Mock
const mockUseSessionMessages = useSessionMessages as Mock
const mockUsePagination = usePagination as Mock

function renderWithRoute(project: string, id: string) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })

  return render(
    createElement(
      QueryClientProvider,
      { client: queryClient },
      createElement(
        MemoryRouter,
        { initialEntries: [`/sessions/${project}/${id}/chat`] },
        createElement(
          Routes,
          null,
          createElement(Route, {
            path: '/sessions/:project/:id/chat',
            element: createElement(ChatHistoryPage),
          })
        )
      )
    )
  )
}

function makeMessage(overrides: Partial<SessionMessage> = {}): SessionMessage {
  return {
    line_number: 1,
    type: 'user',
    timestamp: '2026-03-15T10:00:00Z',
    content: 'Hello world',
    is_compact_summary: false,
    raw: null,
    ...overrides,
  }
}

describe('ChatHistoryPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockUsePagination.mockReturnValue({
      page: 1,
      per_page: 100,
      setPage: vi.fn(),
      setPerPage: vi.fn(),
      nextPage: vi.fn(),
      prevPage: vi.fn(),
      resetPage: vi.fn(),
    })
  })

  describe('loading state', () => {
    it('renders loading spinner while messages are loading', () => {
      mockUseSessionDetail.mockReturnValue({
        data: undefined,
        isLoading: true,
        isError: false,
        error: null,
      })
      mockUseSessionMessages.mockReturnValue({
        data: undefined,
        isLoading: true,
        isError: false,
        error: null,
      })

      const { container } = renderWithRoute('proj', 'sess-123')

      const spinner = container.querySelector('.animate-spin')
      expect(spinner).toBeInTheDocument()
    })
  })

  describe('successful data display', () => {
    const mockMessages: SessionMessage[] = [
      makeMessage({ line_number: 1, type: 'user', content: 'Hello from user' }),
      makeMessage({ line_number: 2, type: 'assistant', content: 'Hello from assistant' }),
      makeMessage({ line_number: 3, type: 'system', content: 'System message here' }),
    ]

    beforeEach(() => {
      mockUseSessionDetail.mockReturnValue({
        data: {
          id: 'sess-123',
          project: 'Users-bob-code',
          project_decoded: '/Users/bob/code',
          slug: 'my-chat',
          custom_title: 'My Chat Session',
          created_at: '2026-03-15T09:00:00Z',
          last_activity: '2026-03-15T12:00:00Z',
          message_count: 50,
          size_bytes: 4096,
          first_user_message: 'Hello from user',
        },
        isLoading: false,
        isError: false,
        error: null,
      })
      mockUseSessionMessages.mockReturnValue({
        data: {
          messages: mockMessages,
          total_lines: 50,
          page: 1,
          per_page: 100,
          pages: 1,
        },
        isLoading: false,
        isError: false,
        error: null,
      })
    })

    it('renders back link to session detail page', () => {
      renderWithRoute('Users-bob-code', 'sess-123')

      const backLink = screen.getByRole('link', { name: /Back to Session Detail/i })
      expect(backLink).toBeInTheDocument()
      expect(backLink).toHaveAttribute('href', '/sessions/Users-bob-code/sess-123')
    })

    it('renders chat history heading', () => {
      renderWithRoute('Users-bob-code', 'sess-123')

      expect(screen.getByText('// Chat History')).toBeInTheDocument()
    })

    it('displays session name from custom_title', () => {
      renderWithRoute('Users-bob-code', 'sess-123')

      // Header shows: displayName | N messages
      expect(screen.getByText(/My Chat Session/)).toBeInTheDocument()
    })

    it('displays total message count in header', () => {
      renderWithRoute('Users-bob-code', 'sess-123')

      expect(screen.getByText(/50 messages/)).toBeInTheDocument()
    })

    it('renders all messages via MessageBubble', () => {
      renderWithRoute('Users-bob-code', 'sess-123')

      // All three message contents should be visible
      expect(screen.getByText('Hello from user')).toBeInTheDocument()
      expect(screen.getByText('Hello from assistant')).toBeInTheDocument()
      expect(screen.getByText('System message here')).toBeInTheDocument()
    })

    it('calls useSessionMessages with project, id, and page from URL params', () => {
      renderWithRoute('Users-bob-code', 'sess-123')

      expect(mockUseSessionMessages).toHaveBeenCalledWith('Users-bob-code', 'sess-123', 1)
    })

    it('calls useSessionDetail with project and id from URL params', () => {
      renderWithRoute('Users-bob-code', 'sess-123')

      expect(mockUseSessionDetail).toHaveBeenCalledWith('Users-bob-code', 'sess-123')
    })

    it('does not render pagination when only one page', () => {
      renderWithRoute('Users-bob-code', 'sess-123')

      // Pagination shows "Prev" and "Next" buttons
      expect(screen.queryByText('Prev')).not.toBeInTheDocument()
      expect(screen.queryByText('Next')).not.toBeInTheDocument()
    })
  })

  describe('pagination', () => {
    it('renders pagination controls when pages > 1', () => {
      mockUseSessionDetail.mockReturnValue({
        data: {
          id: 'sess-123',
          project: 'proj',
          project_decoded: '/proj',
          slug: null,
          custom_title: null,
          created_at: null,
          last_activity: null,
          message_count: 250,
          size_bytes: 0,
          first_user_message: null,
        },
        isLoading: false,
        isError: false,
        error: null,
      })
      mockUseSessionMessages.mockReturnValue({
        data: {
          messages: [makeMessage()],
          total_lines: 250,
          page: 1,
          per_page: 100,
          pages: 3,
        },
        isLoading: false,
        isError: false,
        error: null,
      })

      renderWithRoute('proj', 'sess-123')

      // Pagination renders "Prev" and "Next" buttons
      expect(screen.getByText('Prev')).toBeInTheDocument()
      expect(screen.getByText('Next')).toBeInTheDocument()
      // Shows total count
      expect(screen.getByText(/250 items/)).toBeInTheDocument()
    })
  })

  describe('display name fallback', () => {
    it('falls back to slug when custom_title is null', () => {
      mockUseSessionDetail.mockReturnValue({
        data: {
          id: 'sess-123',
          project: 'proj',
          project_decoded: '/proj',
          slug: 'fallback-slug',
          custom_title: null,
          created_at: null,
          last_activity: null,
          message_count: 5,
          size_bytes: 0,
          first_user_message: null,
        },
        isLoading: false,
        isError: false,
        error: null,
      })
      mockUseSessionMessages.mockReturnValue({
        data: {
          messages: [],
          total_lines: 0,
          page: 1,
          per_page: 100,
          pages: 1,
        },
        isLoading: false,
        isError: false,
        error: null,
      })

      renderWithRoute('proj', 'sess-123')

      expect(screen.getByText(/fallback-slug/)).toBeInTheDocument()
    })

    it('falls back to truncated id when both custom_title and slug are null', () => {
      mockUseSessionDetail.mockReturnValue({
        data: {
          id: 'abcdef123456-long-session-id',
          project: 'proj',
          project_decoded: '/proj',
          slug: null,
          custom_title: null,
          created_at: null,
          last_activity: null,
          message_count: 5,
          size_bytes: 0,
          first_user_message: null,
        },
        isLoading: false,
        isError: false,
        error: null,
      })
      mockUseSessionMessages.mockReturnValue({
        data: {
          messages: [],
          total_lines: 0,
          page: 1,
          per_page: 100,
          pages: 1,
        },
        isLoading: false,
        isError: false,
        error: null,
      })

      renderWithRoute('proj', 'abcdef123456-long-session-id')

      // Falls back to first 12 chars of id
      expect(screen.getByText(/abcdef123456/)).toBeInTheDocument()
    })
  })

  describe('empty state', () => {
    it('renders empty state when no messages', () => {
      mockUseSessionDetail.mockReturnValue({
        data: {
          id: 'sess-123',
          project: 'proj',
          project_decoded: '/proj',
          slug: null,
          custom_title: null,
          created_at: null,
          last_activity: null,
          message_count: 0,
          size_bytes: 0,
          first_user_message: null,
        },
        isLoading: false,
        isError: false,
        error: null,
      })
      mockUseSessionMessages.mockReturnValue({
        data: {
          messages: [],
          total_lines: 0,
          page: 1,
          per_page: 100,
          pages: 1,
        },
        isLoading: false,
        isError: false,
        error: null,
      })

      renderWithRoute('proj', 'sess-123')

      expect(screen.getByText('No messages')).toBeInTheDocument()
      expect(screen.getByText('This session has no messages.')).toBeInTheDocument()
    })
  })

  describe('error states', () => {
    it('renders not found message for NOT_FOUND error', () => {
      mockUseSessionDetail.mockReturnValue({
        data: undefined,
        isLoading: false,
        isError: false,
        error: null,
      })
      const notFoundError = Object.assign(new Error('Not found'), { code: 'NOT_FOUND' })
      mockUseSessionMessages.mockReturnValue({
        data: undefined,
        isLoading: false,
        isError: true,
        error: notFoundError,
      })

      renderWithRoute('proj', 'missing-id')

      expect(screen.getByText('Session not found')).toBeInTheDocument()
      expect(screen.getByText('This session may have been deleted.')).toBeInTheDocument()

      // Back link goes to session detail
      const backLink = screen.getByRole('link', { name: /Back to Session Detail/i })
      expect(backLink).toHaveAttribute('href', '/sessions/proj/missing-id')
    })

    it('renders generic error message for other errors', () => {
      mockUseSessionDetail.mockReturnValue({
        data: undefined,
        isLoading: false,
        isError: false,
        error: null,
      })
      mockUseSessionMessages.mockReturnValue({
        data: undefined,
        isLoading: false,
        isError: true,
        error: new Error('Internal server error'),
      })

      renderWithRoute('proj', 'bad-id')

      expect(screen.getByText('Error loading messages')).toBeInTheDocument()
      expect(screen.getByText('Internal server error')).toBeInTheDocument()

      // Back link goes to session detail
      const backLink = screen.getByRole('link', { name: /Back to Session Detail/i })
      expect(backLink).toHaveAttribute('href', '/sessions/proj/bad-id')
    })
  })
})

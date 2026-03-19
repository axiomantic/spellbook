import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createElement } from 'react'
import { Sessions } from './Sessions'

// Mock the hooks used by Sessions
vi.mock('../hooks/useSessions', () => ({
  useSessions: vi.fn(),
}))

vi.mock('../hooks/usePagination', () => ({
  usePagination: vi.fn(() => ({
    page: 1,
    per_page: 50,
    setPage: vi.fn(),
    resetPage: vi.fn(),
  })),
}))

import { useSessions } from '../hooks/useSessions'

const mockUseSessions = useSessions as Mock

const mockSession = {
  id: 'abc-123-def-456',
  project: 'Users-alice-myproject',
  slug: 'my-session',
  custom_title: 'My Session Title',
  first_user_message: 'Hello world',
  created_at: '2026-03-15T10:00:00Z',
  last_activity: '2026-03-15T11:00:00Z',
  message_count: 10,
  size_bytes: 4096,
}

function renderSessions() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })

  return render(
    createElement(
      QueryClientProvider,
      { client: queryClient },
      createElement(
        MemoryRouter,
        { initialEntries: ['/sessions'] },
        createElement(Sessions)
      )
    )
  )
}

describe('Sessions', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // Both the "all sessions for project list" query and the filtered query
    // return the same mock data
    mockUseSessions.mockReturnValue({
      data: {
        sessions: [mockSession],
        page: 1,
        pages: 1,
        total: 1,
      },
      isLoading: false,
      isError: false,
    })
  })

  describe('session name drill-down link', () => {
    it('renders the session display name as a Link to the session detail page', () => {
      renderSessions()

      const link = screen.getByRole('link', { name: 'My Session Title' })
      expect(link).toBeInTheDocument()
      expect(link).toHaveAttribute(
        'href',
        '/sessions/Users-alice-myproject/abc-123-def-456'
      )
    })

    it('applies hover styling class to the session name link', () => {
      renderSessions()

      const link = screen.getByRole('link', { name: 'My Session Title' })
      expect(link.className).toContain('hover:text-accent-green')
      expect(link.className).toContain('transition-colors')
    })

    it('renders slug as display name when no custom title', () => {
      mockUseSessions.mockReturnValue({
        data: {
          sessions: [{
            ...mockSession,
            custom_title: null,
            slug: 'fallback-slug',
          }],
          page: 1,
          pages: 1,
          total: 1,
        },
        isLoading: false,
        isError: false,
      })

      renderSessions()

      const link = screen.getByRole('link', { name: 'fallback-slug' })
      expect(link).toHaveAttribute(
        'href',
        '/sessions/Users-alice-myproject/abc-123-def-456'
      )
    })

    it('renders truncated ID as display name when no title or slug', () => {
      mockUseSessions.mockReturnValue({
        data: {
          sessions: [{
            ...mockSession,
            custom_title: null,
            slug: null,
          }],
          page: 1,
          pages: 1,
          total: 1,
        },
        isLoading: false,
        isError: false,
      })

      renderSessions()

      const link = screen.getByRole('link', { name: 'abc-123-def-' })
      expect(link).toHaveAttribute(
        'href',
        '/sessions/Users-alice-myproject/abc-123-def-456'
      )
    })
  })

  describe('chat history link', () => {
    it('renders a chat link pointing to the chat history page', () => {
      renderSessions()

      const chatLink = screen.getByRole('link', { name: 'chat' })
      expect(chatLink).toBeInTheDocument()
      expect(chatLink).toHaveAttribute(
        'href',
        '/sessions/Users-alice-myproject/abc-123-def-456/chat'
      )
    })

    it('has title attribute for accessibility', () => {
      renderSessions()

      const chatLink = screen.getByRole('link', { name: 'chat' })
      expect(chatLink).toHaveAttribute('title', 'View chat history')
    })

    it('applies hover styling class to the chat link', () => {
      renderSessions()

      const chatLink = screen.getByRole('link', { name: 'chat' })
      expect(chatLink.className).toContain('hover:text-accent-green')
      expect(chatLink.className).toContain('transition-colors')
    })
  })
})

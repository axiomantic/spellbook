import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createElement } from 'react'
import { SessionDetailPage } from './SessionDetailPage'

// Mock the useSessions hooks
vi.mock('../hooks/useSessions', () => ({
  useSessionDetail: vi.fn(),
  useSessionMessages: vi.fn(),
  useSessions: vi.fn(),
}))

import { useSessionDetail } from '../hooks/useSessions'

const mockUseSessionDetail = useSessionDetail as Mock

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
        { initialEntries: [`/sessions/${project}/${id}`] },
        createElement(
          Routes,
          null,
          createElement(Route, {
            path: '/sessions/:project/:id',
            element: createElement(SessionDetailPage),
          })
        )
      )
    )
  )
}

describe('SessionDetailPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('loading state', () => {
    it('renders loading spinner while data is loading', () => {
      mockUseSessionDetail.mockReturnValue({
        data: undefined,
        isLoading: true,
        isError: false,
        error: null,
      })

      const { container } = renderWithRoute('Users-alice-proj', 'abc-123')

      // LoadingSpinner renders an animated element with py-16 class
      const spinner = container.querySelector('.animate-spin')
      expect(spinner).toBeInTheDocument()
    })
  })

  describe('successful data display', () => {
    const mockData = {
      id: 'abc-123-def-456',
      project: 'Users-alice-myproject',
      project_decoded: '/Users/alice/myproject',
      slug: 'my-session-slug',
      custom_title: 'My Custom Title',
      created_at: '2026-03-15T10:00:00Z',
      last_activity: '2026-03-15T11:30:00Z',
      message_count: 42,
      size_bytes: 8192,
      first_user_message: 'Hello, I need help with my project',
    }

    beforeEach(() => {
      mockUseSessionDetail.mockReturnValue({
        data: mockData,
        isLoading: false,
        isError: false,
        error: null,
      })
    })

    it('renders back link to sessions list', () => {
      renderWithRoute('Users-alice-myproject', 'abc-123-def-456')

      const backLink = screen.getByRole('link', { name: /Back to Sessions/i })
      expect(backLink).toBeInTheDocument()
      expect(backLink).toHaveAttribute('href', '/sessions')
    })

    it('renders session detail heading', () => {
      renderWithRoute('Users-alice-myproject', 'abc-123-def-456')

      expect(screen.getByText('// Session Detail')).toBeInTheDocument()
    })

    it('displays session ID', () => {
      renderWithRoute('Users-alice-myproject', 'abc-123-def-456')

      expect(screen.getByText('Session ID')).toBeInTheDocument()
      expect(screen.getByText('abc-123-def-456')).toBeInTheDocument()
    })

    it('displays decoded project path', () => {
      renderWithRoute('Users-alice-myproject', 'abc-123-def-456')

      expect(screen.getByText('Project')).toBeInTheDocument()
      expect(screen.getByText('/Users/alice/myproject')).toBeInTheDocument()
    })

    it('displays slug', () => {
      renderWithRoute('Users-alice-myproject', 'abc-123-def-456')

      expect(screen.getByText('Slug')).toBeInTheDocument()
      expect(screen.getByText('my-session-slug')).toBeInTheDocument()
    })

    it('displays custom title', () => {
      renderWithRoute('Users-alice-myproject', 'abc-123-def-456')

      expect(screen.getByText('Title')).toBeInTheDocument()
      expect(screen.getByText('My Custom Title')).toBeInTheDocument()
    })

    it('displays message count', () => {
      renderWithRoute('Users-alice-myproject', 'abc-123-def-456')

      expect(screen.getByText('Messages')).toBeInTheDocument()
      expect(screen.getByText('42')).toBeInTheDocument()
    })

    it('displays formatted size', () => {
      renderWithRoute('Users-alice-myproject', 'abc-123-def-456')

      expect(screen.getByText('Size')).toBeInTheDocument()
      expect(screen.getByText('8.0 KB')).toBeInTheDocument()
    })

    it('displays first user message', () => {
      renderWithRoute('Users-alice-myproject', 'abc-123-def-456')

      expect(screen.getByText('First User Message')).toBeInTheDocument()
      expect(screen.getByText('Hello, I need help with my project')).toBeInTheDocument()
    })

    it('renders chat history link with correct path', () => {
      renderWithRoute('Users-alice-myproject', 'abc-123-def-456')

      const chatLink = screen.getByRole('link', { name: /View Chat History/i })
      expect(chatLink).toBeInTheDocument()
      expect(chatLink).toHaveAttribute(
        'href',
        '/sessions/Users-alice-myproject/abc-123-def-456/chat'
      )
    })

    it('calls useSessionDetail with project and id from URL params', () => {
      renderWithRoute('Users-alice-myproject', 'abc-123-def-456')

      expect(mockUseSessionDetail).toHaveBeenCalledWith(
        'Users-alice-myproject',
        'abc-123-def-456'
      )
    })
  })

  describe('null/missing optional fields', () => {
    it('renders dash for null slug', () => {
      mockUseSessionDetail.mockReturnValue({
        data: {
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
        },
        isLoading: false,
        isError: false,
        error: null,
      })

      renderWithRoute('proj', 'abc-123')

      // Find the Slug label, then verify its sibling value span shows '-'
      const slugLabel = screen.getByText('Slug')
      expect(slugLabel).toBeInTheDocument()
      // DetailRow renders: <div><span>{label}</span><span>{value || '-'}</span></div>
      const slugRow = slugLabel.closest('div.flex')!
      const valueSpan = slugRow.children[1] as HTMLElement
      expect(valueSpan.textContent).toBe('-')
    })

    it('does not render first user message section when null', () => {
      mockUseSessionDetail.mockReturnValue({
        data: {
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
        },
        isLoading: false,
        isError: false,
        error: null,
      })

      renderWithRoute('proj', 'abc-123')

      expect(screen.queryByText('First User Message')).not.toBeInTheDocument()
    })
  })

  describe('error states', () => {
    it('renders not found message for NOT_FOUND error', () => {
      const notFoundError = Object.assign(new Error('Not found'), { code: 'NOT_FOUND' })
      mockUseSessionDetail.mockReturnValue({
        data: undefined,
        isLoading: false,
        isError: true,
        error: notFoundError,
      })

      renderWithRoute('proj', 'missing-id')

      expect(screen.getByText('Session not found')).toBeInTheDocument()
      expect(screen.getByText('This session may have been deleted.')).toBeInTheDocument()

      // Still has back link
      const backLink = screen.getByRole('link', { name: /Back to Sessions/i })
      expect(backLink).toHaveAttribute('href', '/sessions')
    })

    it('renders generic error message for other errors', () => {
      mockUseSessionDetail.mockReturnValue({
        data: undefined,
        isLoading: false,
        isError: true,
        error: new Error('Server error'),
      })

      renderWithRoute('proj', 'bad-id')

      expect(screen.getByText('Error loading session')).toBeInTheDocument()
      expect(screen.getByText('Server error')).toBeInTheDocument()

      // Still has back link
      const backLink = screen.getByRole('link', { name: /Back to Sessions/i })
      expect(backLink).toHaveAttribute('href', '/sessions')
    })
  })

  describe('size formatting', () => {
    it('formats bytes correctly', () => {
      mockUseSessionDetail.mockReturnValue({
        data: {
          id: 'test',
          project: 'proj',
          project_decoded: '/proj',
          slug: null,
          custom_title: null,
          created_at: null,
          last_activity: null,
          message_count: 0,
          size_bytes: 500,
          first_user_message: null,
        },
        isLoading: false,
        isError: false,
        error: null,
      })

      renderWithRoute('proj', 'test')

      expect(screen.getByText('500 B')).toBeInTheDocument()
    })

    it('formats megabytes correctly', () => {
      mockUseSessionDetail.mockReturnValue({
        data: {
          id: 'test',
          project: 'proj',
          project_decoded: '/proj',
          slug: null,
          custom_title: null,
          created_at: null,
          last_activity: null,
          message_count: 0,
          size_bytes: 2 * 1024 * 1024,
          first_user_message: null,
        },
        isLoading: false,
        isError: false,
        error: null,
      })

      renderWithRoute('proj', 'test')

      expect(screen.getByText('2.0 MB')).toBeInTheDocument()
    })
  })
})

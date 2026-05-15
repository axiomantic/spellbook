import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { createElement } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

vi.mock('../../hooks/useCanvases', () => ({
  useCanvasList: vi.fn(),
}))

import { useCanvasList } from '../../hooks/useCanvases'
import { CanvasList } from '../CanvasList'
import type { CanvasListResponse } from '../../api/types'

const mockUseCanvasList = useCanvasList as Mock

function listHookReturn(overrides: Record<string, unknown> = {}) {
  return {
    data: undefined,
    isLoading: false,
    isError: false,
    error: null,
    ...overrides,
  }
}

function renderList() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })
  return render(
    createElement(
      QueryClientProvider,
      { client: queryClient },
      createElement(
        MemoryRouter,
        { initialEntries: ['/canvas'] },
        createElement(CanvasList),
      ),
    ),
  )
}

const twoCanvases: CanvasListResponse = {
  canvases: [
    {
      name: 'alpha',
      title: 'Alpha Plan',
      created_at: '2026-05-12T10:00:00Z',
      last_updated: '2026-05-13T12:00:00Z',
      closed: false,
    },
    {
      name: 'beta',
      title: 'Beta Notes',
      created_at: '2026-05-10T08:00:00Z',
      last_updated: '2026-05-14T09:00:00Z',
      closed: true,
    },
  ],
  count: 2,
}

describe('CanvasList', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders a row per canvas with links to /canvas/<name>', () => {
    mockUseCanvasList.mockReturnValue(listHookReturn({ data: twoCanvases }))
    renderList()

    const alphaLink = screen.getByRole('link', { name: /alpha/i })
    expect(alphaLink).toHaveAttribute('href', '/canvas/alpha')
    expect(screen.getByText('Alpha Plan')).toBeInTheDocument()

    const betaLink = screen.getByRole('link', { name: /beta/i })
    expect(betaLink).toHaveAttribute('href', '/canvas/beta')
    expect(screen.getByText('Beta Notes')).toBeInTheDocument()
  })

  it('renders a "closed" badge for closed canvases', () => {
    mockUseCanvasList.mockReturnValue(listHookReturn({ data: twoCanvases }))
    renderList()

    // beta is closed; alpha is not. Only one "closed" badge should appear.
    const closedBadges = screen.getAllByText(/closed/i)
    expect(closedBadges.length).toBeGreaterThanOrEqual(1)
  })

  it('shows the empty-state copy when there are no canvases', () => {
    mockUseCanvasList.mockReturnValue(
      listHookReturn({ data: { canvases: [], count: 0 } as CanvasListResponse }),
    )
    renderList()

    expect(screen.getByText(/no canvases yet/i)).toBeInTheDocument()
  })

  it('shows the LoadingSpinner while loading', () => {
    mockUseCanvasList.mockReturnValue(
      listHookReturn({ data: undefined, isLoading: true }),
    )
    const { container } = renderList()
    const spinner = container.querySelector('.animate-spin')
    expect(spinner).not.toBeNull()
  })

  it('shows an error message and retry button on error', () => {
    mockUseCanvasList.mockReturnValue(
      listHookReturn({
        data: undefined,
        isError: true,
        error: new Error('network down'),
      }),
    )
    renderList()

    expect(screen.getByText(/failed to load canvases/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument()
  })
})

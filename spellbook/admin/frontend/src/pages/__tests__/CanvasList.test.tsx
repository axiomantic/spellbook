import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { createElement } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import { CanvasList } from '../CanvasList'
import type { CanvasListResponse } from '../../api/types'

/**
 * Stub `global.fetch` to return `body` as a JSON Response.
 *
 * The real `useCanvasList` hook is exercised end-to-end: its `queryFn`
 * calls `fetchApi('/api/canvas')`, which calls `fetch('/admin/api/canvas')`.
 * Asserting both the rendered DOM AND that fetch was hit with the right
 * URL proves the real hook ran (not a mock).
 */
function stubFetchJson(body: unknown, status = 200) {
  const response = new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
  return vi.spyOn(global, 'fetch').mockResolvedValue(response)
}

function stubFetchError(error: Error) {
  return vi.spyOn(global, 'fetch').mockRejectedValue(error)
}

function renderList() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0, staleTime: 0 },
    },
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
    vi.restoreAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders a row per canvas with links to /canvas/<name>', async () => {
    const fetchSpy = stubFetchJson(twoCanvases)
    renderList()

    const alphaLink = await screen.findByRole('link', { name: /alpha/i })
    expect(alphaLink).toHaveAttribute('href', '/canvas/alpha')
    expect(screen.getByText('Alpha Plan')).toBeInTheDocument()

    const betaLink = screen.getByRole('link', { name: /beta/i })
    expect(betaLink).toHaveAttribute('href', '/canvas/beta')
    expect(screen.getByText('Beta Notes')).toBeInTheDocument()

    // Real hook fired against the real fetchApi against the stubbed fetch.
    // fetchApi prefixes `/admin` to the path.
    expect(fetchSpy).toHaveBeenCalledTimes(1)
    expect(fetchSpy).toHaveBeenCalledWith(
      '/admin/api/canvas',
      expect.objectContaining({
        method: 'GET',
        credentials: 'same-origin',
      }),
    )
  })

  it('renders a "closed" badge for closed canvases and "open" for open ones', async () => {
    stubFetchJson(twoCanvases)
    renderList()

    // Wait for query to resolve.
    await screen.findByText('Alpha Plan')

    // beta is closed; alpha is open. The Badge component renders the label
    // verbatim. Both should appear exactly once.
    expect(screen.getByText('closed')).toBeInTheDocument()
    expect(screen.getByText('open')).toBeInTheDocument()
  })

  it('shows the empty-state copy when there are no canvases', async () => {
    stubFetchJson({ canvases: [], count: 0 } as CanvasListResponse)
    renderList()

    expect(
      await screen.findByText(/no canvases yet/i),
    ).toBeInTheDocument()
  })

  it('shows the LoadingSpinner while loading', () => {
    // Pending forever — the query stays in loading state.
    vi.spyOn(global, 'fetch').mockReturnValue(new Promise(() => {}))
    const { container } = renderList()
    const spinner = container.querySelector('.animate-spin')
    expect(spinner).not.toBeNull()
  })

  it('shows an error message and retry button on error', async () => {
    stubFetchError(new Error('network down'))
    renderList()

    expect(
      await screen.findByText(/failed to load canvases/i),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /retry/i }),
    ).toBeInTheDocument()
  })
})

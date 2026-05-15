import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { createElement } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

// Mock the lazy-loaded heavy chunks so CanvasRender can resolve.
vi.mock('../../canvas/shortcodes/MermaidImpl', () => ({
  default: () => <div data-testid="mermaid-impl" />,
}))
vi.mock('../../canvas/shortcodes/ChartImpl', () => ({
  default: () => <div data-testid="chart-impl" />,
}))

import { CanvasDetail } from '../CanvasDetail'
import type { CanvasDetail as CanvasDetailType } from '../../api/types'

/**
 * Stub `globalThis.fetch` to return `body` as a JSON Response.
 *
 * The real `useCanvas` hook is exercised end-to-end: its `queryFn` calls
 * `fetchApi('/api/canvas/<encoded-name>')`, which calls
 * `fetch('/admin/api/canvas/<encoded-name>')`.
 */
function stubFetchJson(body: unknown, status = 200) {
  const response = new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
  return vi.spyOn(globalThis, 'fetch').mockResolvedValue(response)
}

function stubFetchError(error: Error) {
  return vi.spyOn(globalThis, 'fetch').mockRejectedValue(error)
}

function renderDetail(initialName = 'alpha') {
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
        { initialEntries: [`/canvas/${initialName}`] },
        createElement(Routes, null,
          createElement(Route, {
            path: '/canvas/:name',
            element: createElement(CanvasDetail),
          }),
          // Fall-through route for the empty-name "should not render
          // CanvasDetail" case used by the `enabled: !!name` test below.
          createElement(Route, {
            path: '/canvas',
            element: createElement(CanvasDetail),
          }),
        ),
      ),
    ),
  )
}

const openCanvas: CanvasDetailType = {
  name: 'alpha',
  title: 'Alpha Plan',
  created_at: '2026-05-12T10:00:00Z',
  last_updated: '2026-05-13T12:00:00Z',
  closed: false,
  page: 'page.md',
  content: '# Inner Heading\n\n<callout type="note">Body text</callout>',
  bytes: 64,
}

const closedCanvas: CanvasDetailType = {
  ...openCanvas,
  name: 'beta',
  title: 'Beta Notes',
  closed: true,
  content: '# Beta',
}

describe('CanvasDetail', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('shows the LoadingSpinner while loading', () => {
    // Pending forever — query stays in loading state.
    vi.spyOn(globalThis, 'fetch').mockReturnValue(new Promise(() => {}))
    const { container } = renderDetail()
    expect(container.querySelector('.animate-spin')).not.toBeNull()
  })

  it('shows "Canvas not found" with a link back when the query errors', async () => {
    stubFetchError(new Error('404'))
    renderDetail()

    expect(
      await screen.findByText(/canvas not found/i),
    ).toBeInTheDocument()
    const backLink = screen.getByRole('link', { name: /back to canvases/i })
    expect(backLink).toHaveAttribute('href', '/canvas')
  })

  it('renders a closed banner when canvas.closed === true', async () => {
    stubFetchJson(closedCanvas)
    renderDetail('beta')

    expect(
      await screen.findByText(/this canvas is closed/i),
    ).toBeInTheDocument()
    expect(screen.getByText('Beta Notes')).toBeInTheDocument()
  })

  it('renders content via CanvasRender — markdown headings dispatch correctly', async () => {
    stubFetchJson(openCanvas)
    renderDetail()

    // Page-level title comes from data.title and is rendered as the page's
    // <h1>. The canvas body contributes a level-1 heading too (from `#
    // Inner Heading`) — assert both are present.
    expect(await screen.findByText('Alpha Plan')).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { level: 1, name: 'Inner Heading' }),
    ).toBeInTheDocument()
  })

  it('renders shortcodes embedded in canvas content (e.g., <callout>)', async () => {
    stubFetchJson(openCanvas)
    renderDetail()

    // The Callout component carries a data-testid="callout".
    expect(await screen.findByTestId('callout')).toBeInTheDocument()
    expect(screen.getByText('Body text')).toBeInTheDocument()
  })

  it('URL-encodes the canvas name (encodeURIComponent on path segment)', async () => {
    const tricky = 'my canvas/with slashes'
    const fetchSpy = stubFetchJson({ ...openCanvas, name: tricky })
    // Route param `name` must be encoded in the initial entry too because
    // react-router decodes route params; we want the *page* to encode it
    // again when building the API URL. The component reads `useParams`
    // which returns the decoded value. So we pass the encoded form here.
    renderDetail(encodeURIComponent(tricky))

    // Wait for the query to resolve to ensure fetch fired.
    await screen.findByText('Alpha Plan')

    expect(fetchSpy).toHaveBeenCalledTimes(1)
    expect(fetchSpy).toHaveBeenCalledWith(
      `/admin/api/canvas/${encodeURIComponent(tricky)}`,
      expect.objectContaining({
        method: 'GET',
        credentials: 'same-origin',
      }),
    )
  })

  it('is disabled (no fetch fires) when route param `name` is missing', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch')

    const queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false, gcTime: 0, staleTime: 0 },
      },
    })
    render(
      createElement(
        QueryClientProvider,
        { client: queryClient },
        createElement(
          MemoryRouter,
          // No `:name` segment, so useParams() returns { name: undefined }.
          // CanvasDetail passes `null` to useCanvas, which sets
          // `enabled: !!name` to false.
          { initialEntries: ['/canvas/'] },
          createElement(Routes, null,
            createElement(Route, {
              path: '/canvas/',
              element: createElement(CanvasDetail),
            }),
          ),
        ),
      ),
    )

    // Give React a microtask to settle; the disabled query should never fetch.
    await Promise.resolve()
    await Promise.resolve()

    expect(fetchSpy).not.toHaveBeenCalled()
  })
})

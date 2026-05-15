import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { createElement } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

vi.mock('../../hooks/useCanvases', () => ({
  useCanvas: vi.fn(),
}))

// Mock the lazy-loaded heavy chunks so CanvasRender can resolve.
vi.mock('../../canvas/shortcodes/MermaidImpl', () => ({
  default: () => <div data-testid="mermaid-impl" />,
}))
vi.mock('../../canvas/shortcodes/ChartImpl', () => ({
  default: () => <div data-testid="chart-impl" />,
}))

import { useCanvas } from '../../hooks/useCanvases'
import { CanvasDetail } from '../CanvasDetail'
import type { CanvasDetail as CanvasDetailType } from '../../api/types'

const mockUseCanvas = useCanvas as Mock

function detailHookReturn(overrides: Record<string, unknown> = {}) {
  return {
    data: undefined,
    isLoading: false,
    isError: false,
    error: null,
    ...overrides,
  }
}

function renderDetail(initialName = 'alpha') {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
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
    vi.clearAllMocks()
  })

  it('shows the LoadingSpinner while loading', () => {
    mockUseCanvas.mockReturnValue(detailHookReturn({ isLoading: true }))
    const { container } = renderDetail()
    expect(container.querySelector('.animate-spin')).not.toBeNull()
  })

  it('shows "Canvas not found" with a link back when the query errors', () => {
    mockUseCanvas.mockReturnValue(
      detailHookReturn({ isError: true, error: new Error('404') }),
    )
    renderDetail()
    expect(screen.getByText(/canvas not found/i)).toBeInTheDocument()
    const backLink = screen.getByRole('link', { name: /back to canvases/i })
    expect(backLink).toHaveAttribute('href', '/canvas')
  })

  it('renders a closed banner when canvas.closed === true', () => {
    mockUseCanvas.mockReturnValue(detailHookReturn({ data: closedCanvas }))
    renderDetail('beta')
    expect(screen.getByText(/this canvas is closed/i)).toBeInTheDocument()
    expect(screen.getByText('Beta Notes')).toBeInTheDocument()
  })

  it('renders content via CanvasRender — markdown headings dispatch correctly', () => {
    mockUseCanvas.mockReturnValue(detailHookReturn({ data: openCanvas }))
    renderDetail()
    // Page-level title comes from data.title and is rendered as the page's
    // <h1>. The canvas body contributes a level-1 heading too (from `#
    // Inner Heading`) — assert both are present.
    expect(screen.getByText('Alpha Plan')).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { level: 1, name: 'Inner Heading' }),
    ).toBeInTheDocument()
  })

  it('renders shortcodes embedded in canvas content (e.g., <callout>)', () => {
    mockUseCanvas.mockReturnValue(detailHookReturn({ data: openCanvas }))
    renderDetail()
    // The Callout component carries a data-testid="callout".
    expect(screen.getByTestId('callout')).toBeInTheDocument()
    expect(screen.getByText('Body text')).toBeInTheDocument()
  })
})

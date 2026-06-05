import { render, screen, fireEvent, waitFor } from '@testing-library/react'
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

// Mock the decision-submit hook for the state-driven tests below: they drive
// its returned state directly without firing a real network mutation. The D4
// remount-survival test overrides this mock to delegate to the REAL hook (see
// `useRealDecisionSubmit`), so it exercises the genuine in-flight mutation
// mechanism rather than a frozen value. The real implementation is captured on
// the mock module as `__real` so the test can delegate to it without recursing
// into the mock.
vi.mock('../../hooks/useDecisionSubmit', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../hooks/useDecisionSubmit')>()
  return { useDecisionSubmit: vi.fn(), __real: actual.useDecisionSubmit }
})
import { useDecisionSubmit } from '../../hooks/useDecisionSubmit'
import * as decisionSubmitModule from '../../hooks/useDecisionSubmit'

/** Route the mocked hook back to the REAL implementation for one test. */
function useRealDecisionSubmit() {
  const real = (decisionSubmitModule as unknown as {
    __real: typeof decisionSubmitModule.useDecisionSubmit
  }).__real
  ;(useDecisionSubmit as ReturnType<typeof vi.fn>).mockImplementation(real)
}

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
  page: 'index.md',
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

const idleSubmit = {
  mutate: vi.fn(),
  status: 'idle' as const,
  error: null,
  lastFreeText: null,
}

describe('CanvasDetail', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    // Default the mocked hook to an idle submit state so the happy-path
    // tests below render the provider without a live mutation.
    ;(useDecisionSubmit as ReturnType<typeof vi.fn>).mockReturnValue(idleSubmit)
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
    // Exact, complete fetch-init equality (mirrors the POST test below):
    // objectContaining only checks the two named keys and would pass even if
    // fetchApi sent stray headers, a body on a GET, or wrong credentials. Pin
    // the whole call. For a GET with no body, fetchApi builds headers={} and
    // body=undefined (api/client.ts).
    expect(fetchSpy.mock.calls).toEqual([
      [
        `/admin/api/canvas/${encodeURIComponent(tricky)}`,
        {
          method: 'GET',
          headers: {},
          body: undefined,
          credentials: 'same-origin',
        },
      ],
    ])
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

const pendingDecision = {
  decision_id: 'd1',
  kind: 'approve' as const,
  prompt: 'Ship?',
  options: null,
  status: 'pending' as const,
}

describe('CanvasDetail decision wiring', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  // DA-10: free-text echo is React-escaped plain text — never a live <script>.
  it('renders free-text echo as escaped plain text (no script node)', async () => {
    stubFetchJson({ ...openCanvas, decision: pendingDecision })
    ;(useDecisionSubmit as ReturnType<typeof vi.fn>).mockReturnValue({
      mutate: vi.fn(),
      status: 'success',
      error: null,
      lastFreeText: '<script>alert(1)</script>',
    })
    renderDetail('alpha')
    // Wait for the real useCanvas query to resolve the stubbed body.
    expect(await screen.findByText('<script>alert(1)</script>')).toBeInTheDocument()
    // The injected markup is inert: no real script element in the DOM.
    expect(document.querySelector('script')).toBeNull()
  })

  // RT-6 (D4): a content-invalidation refetch (new data.content identity, as a
  // WS canvas.decision.submitted invalidation produces) remounts the
  // CanvasRender leaves but MUST NOT reset the in-flight submit state, because
  // the mutation lives in CanvasDetail (the query owner, which does not
  // remount), not in the remounting leaves.
  //
  // REAL-MECHANISM test (replaces the prior frozen-mock version): it drives the
  // genuine `useDecisionSubmit` mutation in-flight via a never-resolving POST
  // stub — clicking the live <approve> control fires `mutate`, which stays
  // `pending` because the POST never settles. The page-level `decision-submitting`
  // marker then proves the hoisted state survived the content-identity remount.
  //
  // FALSIFICATION CHECK (performed locally, then restored): inlining the
  // `useDecisionSubmit` mutation INTO the <approve> leaf (undoing the RT-6
  // hoist) makes this test FAIL — the leaf remount on the content-identity
  // change discards the in-flight React Query mutation, so `decision-submitting`
  // disappears after the refetch and the final assertion throws. The prior
  // frozen-mock test could NOT detect this regression because it fed a constant
  // `status: 'pending'` value that never lived in the remounting subtree.
  it('keeps a real in-flight mutation alive across a content-identity remount (RT-6)', async () => {
    useRealDecisionSubmit()

    // A canvas whose body carries the live <approve> control matching the
    // pending decision id, so clicking it fires the real mutation.
    const approveContent =
      '<approve id="d1" prompt="Ship?" confirm_label="Ship" decline_label="Hold"></approve>'
    const canvasV1 = { ...openCanvas, content: `${approveContent}\n\n# v1`, decision: pendingDecision }
    const canvasV2 = { ...openCanvas, content: `${approveContent}\n\n# v2 (refetched)`, decision: pendingDecision }

    // Route fetch by method + URL: GET canvas resolves (v1, then v2 after the
    // refetch is armed); POST decision/submit NEVER resolves (keeps the
    // mutation `pending`).
    let canvasBody = canvasV1
    const neverResolve = new Promise<Response>(() => {})
    const fetchSpy = vi
      .spyOn(globalThis, 'fetch')
      .mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
        const url = typeof input === 'string' ? input : input.toString()
        if (init?.method === 'POST' && url.includes('/decision/submit')) {
          return neverResolve
        }
        return Promise.resolve(
          new Response(JSON.stringify(canvasBody), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }),
        )
      })

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, gcTime: 0, staleTime: 0 } },
    })
    render(
      createElement(
        QueryClientProvider,
        { client: queryClient },
        createElement(
          MemoryRouter,
          { initialEntries: ['/canvas/alpha'] },
          createElement(Routes, null,
            createElement(Route, {
              path: '/canvas/:name',
              element: createElement(CanvasDetail),
            }),
          ),
        ),
      ),
    )

    // The live control renders (v1 loaded). No in-flight marker yet.
    const confirm = await screen.findByTestId('approve-confirm')
    expect(screen.queryByTestId('decision-submitting')).toBeNull()

    // Fire the real mutation. The POST never resolves → status stays 'pending'
    // → the hoisted page-level marker appears.
    fireEvent.click(confirm)
    expect(await screen.findByTestId('decision-submitting')).toBeInTheDocument()

    // Arm the next GET to return NEW content (different `data.content`
    // identity), then invalidate so the query refetches and CanvasRender's
    // leaves remount.
    canvasBody = canvasV2
    await queryClient.invalidateQueries({ queryKey: ['canvas', 'alpha'] })

    // The remounted body reflects the new content (proves the leaves remounted).
    await waitFor(() => {
      expect(
        screen.getByRole('heading', { level: 1, name: 'v2 (refetched)' }),
      ).toBeInTheDocument()
    })

    // RT-6: the in-flight marker SURVIVED the leaf remount — the hoisted
    // mutation lives in CanvasDetail, which did not remount.
    expect(screen.getByTestId('decision-submitting')).toBeInTheDocument()

    // Exactly one POST fired (the single click); the refetch did not re-fire it.
    const postCalls = fetchSpy.mock.calls.filter(
      ([, init]) => (init as RequestInit | undefined)?.method === 'POST',
    )
    expect(postCalls).toEqual([
      [
        '/admin/api/canvas/alpha/decision/submit',
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ decision_id: 'd1', value: 'approved', free_text: null }),
          credentials: 'same-origin',
        },
      ],
    ])
  })
})

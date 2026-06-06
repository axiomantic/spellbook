import { useCallback, useEffect, useMemo } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useCanvas } from '../hooks/useCanvases'
import { LoadingSpinner } from '../components/shared/LoadingSpinner'
import { PageLayout } from '../components/layout/PageLayout'
import { CanvasRender } from '../canvas/render'
import { CanvasDecisionContext } from '../canvas/CanvasDecisionContext'
import { evictCanvasShortcodeState } from '../canvas/shortcodes/shortcodeState'
import { useDecisionSubmit } from '../hooks/useDecisionSubmit'

/**
 * Canvas detail page (`/admin/canvas/:name`). Loads a single canvas via
 * `useCanvas(name)` and renders its markdown body through `CanvasRender`.
 *
 * States:
 *   - loading → `<LoadingSpinner />`
 *   - 404 / error → "Canvas not found" + link back to /canvas
 *   - closed → "This canvas is closed" banner above the rendered body
 *   - happy path → title, optional closed banner, rendered content
 */
export function CanvasDetail() {
  const { name } = useParams<{ name: string }>()
  const { data, isLoading, isError, error } = useCanvas(name ?? null)
  // Hoisted decision-submit state (§8.1 / RT-6). Instantiated above the
  // early returns to satisfy the Rules of Hooks; the mutation only fires on
  // an explicit `mutate()`, so an empty name pre-load is inert.
  const submit = useDecisionSubmit(name ?? '')

  // Controlled re-auth (§8.4 / D1). Hoisted here so both the <choice> and
  // <approve> leaves share one implementation. A plain reload hands control to
  // the existing login/handoff flow; the decision is server-side and durable,
  // so the still-`pending` control re-renders after re-auth and the operator
  // re-submits. Stable identity (no deps) keeps the memoized context value from
  // churning on every render.
  const reauthenticate = useCallback(() => {
    window.location.reload()
  }, [])

  // Memoize the context value so the provider only hands a new identity to
  // CanvasRender's shortcode consumers when an observable input actually
  // changes — not on every CanvasDetail render. Hoisted above the early
  // returns to satisfy the Rules of Hooks; `data` is undefined until loaded,
  // and the value is only consumed in the happy-path branch below.
  const decisionValue = useMemo(
    () => ({
      canvasName: data?.name ?? '',
      decision: data?.decision ?? null,
      submit,
      reauthenticate,
    }),
    [data?.name, data?.decision, submit, reauthenticate],
  )

  // Per-canvas remount-survival cache eviction (design §4.3 / F3). The
  // module-scoped `collapsibleOpenState` / `tabsActiveState` caches intentionally
  // survive the shortcode-leaf remount a `canvas_write` triggers — but they must
  // NOT survive leaving the canvas entirely. On unmount (or navigation to a
  // different canvas name) the cleanup sweeps every entry prefixed with this
  // canvas's name, bounding the cache to the live canvas. Scoping the effect to
  // the loaded `data?.name` keeps the cleanup keyed to the canvas actually shown.
  const loadedName = data?.name
  useEffect(() => {
    if (!loadedName) return
    return () => evictCanvasShortcodeState(loadedName)
  }, [loadedName])

  if (isLoading) {
    return (
      <PageLayout segments={[{ label: 'CANVAS' }, { label: name ?? '' }]}>
        <LoadingSpinner className="py-16" />
      </PageLayout>
    )
  }

  if (isError || !data) {
    return (
      <PageLayout segments={[{ label: 'CANVAS' }, { label: name ?? '' }]}>
        <div className="p-6">
          <div className="border border-accent-red p-4">
            <p className="text-accent-red font-mono text-sm mb-2">
              Canvas not found{name ? `: ${name}` : ''}
              {error
                ? ` — ${(error as Error).message}`
                : ''}
            </p>
            <Link
              to="/canvas"
              className="inline-block px-3 py-1 border border-accent-green text-accent-green font-mono text-xs uppercase tracking-widest hover:bg-accent-green hover:text-bg-base transition-colors"
            >
              Back to canvases
            </Link>
          </div>
        </div>
      </PageLayout>
    )
  }

  return (
    <PageLayout segments={[{ label: 'CANVAS' }, { label: data.name }]}>
      <div className="p-6 max-w-4xl">
        <h1 className="text-2xl font-mono text-accent-green mb-1">
          {data.title}
        </h1>
        <p className="text-xs font-mono text-text-dim mb-4">
          {data.name} · {data.bytes} bytes · last updated {data.last_updated}
        </p>

        {data.closed && (
          <div
            role="status"
            className="mb-4 border-l-4 border-accent-amber bg-bg-elevated px-3 py-2"
          >
            <span className="font-mono text-xs uppercase tracking-widest text-accent-amber">
              // CLOSED
            </span>
            <p className="text-sm text-text-primary mt-1">
              This canvas is closed. It is read-only.
            </p>
          </div>
        )}

        <div className="prose prose-invert max-w-none text-text-primary text-sm leading-relaxed">
          <CanvasDecisionContext.Provider value={decisionValue}>
            <CanvasRender content={data.content} />
          </CanvasDecisionContext.Provider>
        </div>

        {/* In-flight submission handle (§8.2). A stable top-level marker so a
            content-invalidation refetch (which remounts CanvasRender's leaves)
            cannot drop the hoisted submitting state (RT-6). */}
        {submit.status === 'pending' && (
          <p
            role="status"
            data-testid="decision-submitting"
            className="mt-3 font-mono text-xs uppercase tracking-widest text-accent-amber"
          >
            Submitting…
          </p>
        )}

        {/* Free-text echo (§8.3 / DA-10). The operator's own typed note,
            rendered as an escaped plain-text node — NEVER through CanvasRender
            / react-markdown / rehype-raw — so an injected <script> is inert. */}
        {submit.status === 'success' && submit.lastFreeText !== null && (
          <p className="mt-3 text-sm text-text-secondary" data-testid="decision-free-text-echo">
            {submit.lastFreeText}
          </p>
        )}
      </div>
    </PageLayout>
  )
}

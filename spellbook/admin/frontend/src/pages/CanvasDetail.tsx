import { useParams, Link } from 'react-router-dom'
import { useCanvas } from '../hooks/useCanvases'
import { LoadingSpinner } from '../components/shared/LoadingSpinner'
import { PageLayout } from '../components/layout/PageLayout'
import { CanvasRender } from '../canvas/render'

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
            className="mb-4 border-l-4 border-accent-yellow bg-bg-elevated px-3 py-2"
          >
            <span className="font-mono text-xs uppercase tracking-widest text-accent-yellow">
              // CLOSED
            </span>
            <p className="text-sm text-text-primary mt-1">
              This canvas is closed. It is read-only.
            </p>
          </div>
        )}

        <div className="text-text-primary text-sm leading-relaxed">
          <CanvasRender content={data.content} />
        </div>
      </div>
    </PageLayout>
  )
}

import { lazy, Suspense, type ReactNode } from 'react'
import { ErrorBoundary } from '../../components/shared/ErrorBoundary'
import { extractText } from './extractText'

const ChartImpl = lazy(() => import('./ChartImpl'))

interface ChartProps {
  caption?: string
  children?: ReactNode
}

/**
 * Vega-Lite chart shortcode (§9.2). Body is JSON spec as text (no
 * nested markdown). `react-vega` and `vega-lite` are lazy-loaded via
 * `Suspense` so they do NOT enter the initial admin bundle.
 *
 * Two error surfaces:
 *   1. JSON parse error → inline `<pre>` with the parser message
 *      (caught before mounting the lazy chunk).
 *   2. Vega render error → caught by `ErrorBoundary` (per-shortcode
 *      isolation, §8.3).
 */
export function Chart({ caption, children }: ChartProps) {
  const text = extractText(children).trim()
  let spec: object | null = null
  let parseError: string | null = null

  if (!text) {
    parseError = 'empty spec'
  } else {
    try {
      const parsed = JSON.parse(text) as unknown
      if (typeof parsed !== 'object' || parsed === null) {
        parseError = 'spec must be a JSON object'
      } else {
        spec = parsed as object
      }
    } catch (err) {
      parseError = err instanceof Error ? err.message : String(err)
    }
  }

  if (parseError) {
    return (
      <pre
        data-testid="chart-parse-error"
        className="text-accent-red text-xs border border-accent-red p-2"
      >
        Chart render error: {parseError}
      </pre>
    )
  }

  return (
    <ErrorBoundary
      fallback={
        <pre className="text-accent-red text-xs border border-accent-red p-2">
          Chart render error. Check Vega-Lite spec.
        </pre>
      }
    >
      <Suspense
        fallback={<div className="text-text-dim text-xs">Loading chart…</div>}
      >
        <figure data-testid="chart" className="not-prose my-3">
          <ChartImpl spec={spec!} />
          {caption && (
            <figcaption className="text-text-dim text-xs mt-1 font-mono">
              {caption}
            </figcaption>
          )}
        </figure>
      </Suspense>
    </ErrorBoundary>
  )
}

import { lazy, Suspense, type ReactNode } from 'react'
import { ErrorBoundary } from '../../components/shared/ErrorBoundary'
import { extractText } from './extractText'

const MermaidImpl = lazy(() => import('./MermaidImpl'))

interface DiagramProps {
  caption?: string
  children?: ReactNode
}

/**
 * Mermaid diagram shortcode (§9.2). Body is Mermaid DSL as text (no
 * nested markdown). `mermaid` is lazy-loaded via `Suspense` so the
 * library does NOT enter the initial admin bundle.
 *
 * Errors thrown by `MermaidImpl` are caught by the wrapping
 * `ErrorBoundary` (per-shortcode isolation, §8.3).
 */
export function Diagram({ caption, children }: DiagramProps) {
  const source = extractText(children)
  return (
    <ErrorBoundary
      fallback={
        <pre className="text-accent-red text-xs border border-accent-red p-2">
          Diagram render error
        </pre>
      }
    >
      <Suspense
        fallback={
          <div className="text-text-dim text-xs">Loading diagram…</div>
        }
      >
        <figure data-testid="diagram" className="my-3">
          <MermaidImpl source={source} />
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

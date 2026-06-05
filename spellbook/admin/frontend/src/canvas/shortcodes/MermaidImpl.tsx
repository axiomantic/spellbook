import { useEffect, useId, useRef, useState } from 'react'
import mermaid from 'mermaid'

interface MermaidImplProps {
  source: string
}

let mermaidInitialized = false

function ensureInitialized() {
  if (mermaidInitialized) return
  mermaid.initialize({
    startOnLoad: false,
    theme: 'dark',
    securityLevel: 'strict',
    fontFamily: 'ui-monospace, monospace',
  })
  mermaidInitialized = true
}

/**
 * Lazy-loaded Mermaid renderer. Loaded via `lazy(() => import())` from
 * `Diagram.tsx` so the (~700 KB minified) `mermaid` bundle is in its own
 * chunk and does not enter the initial admin bundle.
 *
 * The component renders into a stable container `<div>` and asks
 * `mermaid.render` to produce SVG markup that we inject via
 * `dangerouslySetInnerHTML`. The trust boundary is the same as the rest
 * of the canvas pipeline (§10 trusted-local-agent).
 */
export default function MermaidImpl({ source }: MermaidImplProps) {
  const [svg, setSvg] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  // `useId()` yields a stable, render-pure unique id. Mermaid uses this value
  // to build SVG element ids, so strip the colons React emits (invalid in CSS
  // selectors / SVG id refs) to keep the `mermaid-<token>` shape the renderer
  // expects.
  const rawId = useId()
  const idRef = useRef(`mermaid-${rawId.replace(/:/g, '')}`)

  useEffect(() => {
    ensureInitialized()
    let cancelled = false
    const trimmed = source.trim()
    if (!trimmed) {
      setSvg('')
      setError(null)
      return () => {
        cancelled = true
      }
    }
    mermaid
      .render(idRef.current, trimmed)
      .then(({ svg }) => {
        if (cancelled) return
        setSvg(svg)
        setError(null)
      })
      .catch((err: unknown) => {
        if (cancelled) return
        const message = err instanceof Error ? err.message : String(err)
        setError(message)
        setSvg(null)
      })
    return () => {
      cancelled = true
    }
  }, [source])

  if (error) {
    return (
      <pre
        data-testid="mermaid-error"
        className="text-accent-red text-xs border border-accent-red p-2"
      >
        Diagram render error: {error}
      </pre>
    )
  }
  if (svg === null) {
    return (
      <div className="text-text-dim text-xs" data-testid="mermaid-loading">
        Rendering diagram…
      </div>
    )
  }
  return (
    <div
      data-testid="mermaid-svg"
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  )
}

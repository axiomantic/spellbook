import { useState, type ReactNode } from 'react'
import { renderChildren } from './renderChildren'

interface CollapsibleProps {
  summary?: string
  // `react-markdown` + `rehype-raw` deliver HTML attributes as strings.
  // A bare presence attribute (`<collapsible open>`) arrives as the empty
  // string ""; `<collapsible open="true">` arrives as "true". Both are
  // truthy-presence. Absence => prop is undefined.
  open?: string
  children?: ReactNode
}

/**
 * PROTOTYPE (spike) — collapsible disclosure shortcode.
 *
 * Children are markdown content already re-parsed by react-markdown +
 * rehype-raw upstream; render them inline inside the content region.
 *
 * Deliberately NOT a native <details>/<summary>: we own the open/closed
 * state so future wiring (persisted-open, decision-gated reveal, scroll
 * sync) is in React's hands. Renders as a <button> with aria-expanded
 * driving a content <div>.
 */
export function Collapsible({ summary, open, children }: CollapsibleProps) {
  // presence-bool: any non-undefined value (incl. "") means "start open".
  const initialOpen = open !== undefined
  const [isOpen, setIsOpen] = useState(initialOpen)

  return (
    <div
      data-testid="collapsible"
      data-collapsible-open={isOpen ? 'true' : 'false'}
      className="my-3 border border-bg-border"
    >
      <button
        type="button"
        aria-expanded={isOpen}
        onClick={() => setIsOpen((v) => !v)}
        className="flex w-full items-center gap-2 bg-bg-elevated px-3 py-2 text-left font-mono text-xs uppercase tracking-widest text-accent-cyan hover:text-accent-green"
      >
        <span aria-hidden="true">{isOpen ? '▾' : '▸'}</span>
        <span>{summary ?? 'Details'}</span>
      </button>
      {isOpen && (
        <div
          role="region"
          data-testid="collapsible-body"
          className="not-prose px-3 py-2 text-sm text-text-primary"
        >
          {renderChildren(children)}
        </div>
      )}
    </div>
  )
}

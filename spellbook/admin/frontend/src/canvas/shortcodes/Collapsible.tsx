import { useId, useState, type ReactNode } from 'react'
import { renderChildren } from './renderChildren'
import { useCanvasDecisionOptional } from '../CanvasDecisionContext'
import { collapsibleOpenState } from './shortcodeState'

interface CollapsibleProps {
  summary?: string
  // `react-markdown` + `rehype-raw` deliver HTML attributes as strings.
  // A bare presence attribute (`<collapsible open>`) arrives as the empty
  // string ""; `<collapsible open="true">` arrives as "true". Both are
  // truthy-presence. Absence => prop is undefined.
  open?: string
  // The source hast node react-markdown injects via the components map. Only
  // `position.start.offset` (the opening tag's source byte offset) is read —
  // it gives each occurrence a stable identity across remounts and is immune
  // to StrictMode double-render. Typed with the narrow shape actually used
  // (Task 10's `node` precedent) rather than `any`.
  node?: { position?: { start?: { offset?: number } } }
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
 *
 * Remount survival (design §4.3): every `canvas_write` remounts this leaf,
 * which would reset local `useState`. The open state is therefore mirrored
 * into the module-scoped `collapsibleOpenState` cache, keyed by a stable
 * identity (`canvasName::summary::sourceOffset`) read on mount and written on
 * toggle, so the open/closed state survives the remount.
 */
export function Collapsible({ summary, open, node, children }: CollapsibleProps) {
  // Non-throwing context read (Finding 1): Collapsible is a stateful display
  // shortcode, not a trust-boundary control, and is rendered provider-less in
  // tests. Outside a provider the canvas segment is ''.
  const ctx = useCanvasDecisionOptional()
  const canvasName = ctx?.canvasName ?? ''
  // Source byte offset of the opening tag (Step-0 spike: populated under the
  // production rehype-raw pipeline). Distinct same-summary instances carry
  // distinct offsets → distinct keys → independent state. The `?? 0` is the
  // documented fallback for any future config that drops positions.
  const offset = node?.position?.start?.offset ?? 0
  const key = `${canvasName}::${summary ?? 'Details'}::${offset}`

  // presence-bool: any non-undefined value (incl. "") means "start open".
  // The cache wins over the `open` attribute once the operator has toggled
  // (cached value is read first), so a remount restores the toggled state.
  const [isOpen, setIsOpen] = useState(
    () => collapsibleOpenState.get(key) ?? open !== undefined,
  )
  // Compute next state and write the cache OUTSIDE the state updater (matches
  // Tabs' `select`). State updaters must be pure: StrictMode double-invokes
  // them, which would double-write the cache. The click handler always sees
  // committed state, so reading `isOpen` from the closure is correct here.
  const toggle = () => {
    const next = !isOpen
    collapsibleOpenState.set(key, next)
    setIsOpen(next)
  }

  // Accessible name for the body region (a11y): the disclosure button labels
  // the region it controls. Stable id pair so the region is not an unnamed
  // landmark.
  const buttonId = useId()
  const regionId = useId()

  return (
    <div
      data-testid="collapsible"
      data-collapsible-open={isOpen ? 'true' : 'false'}
      className="my-3 border border-bg-border"
    >
      <button
        type="button"
        id={buttonId}
        aria-expanded={isOpen}
        aria-controls={regionId}
        onClick={toggle}
        className="flex w-full items-center gap-2 bg-bg-elevated px-3 py-2 text-left font-mono text-xs uppercase tracking-widest text-accent-cyan hover:text-accent-green"
      >
        <span aria-hidden="true">{isOpen ? '▾' : '▸'}</span>
        <span>{summary ?? 'Details'}</span>
      </button>
      {isOpen && (
        <div
          role="region"
          id={regionId}
          aria-labelledby={buttonId}
          data-testid="collapsible-body"
          className="not-prose px-3 py-2 text-sm text-text-primary"
        >
          {renderChildren(children)}
        </div>
      )}
    </div>
  )
}

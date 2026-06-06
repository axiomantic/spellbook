import { Children, isValidElement, useState, type ReactElement, type ReactNode } from 'react'
import { renderChildren } from './renderChildren'
import { useCanvasDecisionOptional } from '../CanvasDecisionContext'
import { tabsActiveState } from './shortcodeState'

interface TabProps {
  title: string
  children?: ReactNode
}

/**
 * Marker component for a single tab inside `<Tabs>`. `Tabs` reads its
 * `title` attribute and children. Renders its children directly when
 * used outside `<Tabs>` (so the markdown stays readable as a fallback).
 */
export function Tab({ children }: TabProps) {
  // `not-prose` severs the @tailwindcss/typography cascade on this standalone
  // fallback root too (§2.4 belt), matching the in-Tabs panel.
  return (
    <div data-testid="tab" className="not-prose">
      {children}
    </div>
  )
}

interface TabsProps {
  // The source hast node react-markdown injects via the components map. Only
  // `position.start.offset` is read for the remount-survival cache key — see
  // Collapsible for the rationale. Narrow shape, no `any`.
  node?: { position?: { start?: { offset?: number } } }
  children?: ReactNode
}

/**
 * Tabbed-panel shortcode (§9.2).
 *
 * Iterates `Children` and selects every `Tab` element. Renders a tab bar
 * + the active tab's body. Tabs without a `title` attribute fall back to
 * "Tab N".
 *
 * Remount survival (design §4.3): every `canvas_write` remounts this leaf,
 * which previously snapped the active tab back to 0 (the pre-existing Tabs
 * snap-shut bug). The active index is mirrored into the module-scoped
 * `tabsActiveState` cache, keyed by `canvasName::joinedTitles::sourceOffset`,
 * read on mount and written on selection, so the active tab survives.
 */
export function Tabs({ node, children }: TabsProps) {
  const tabs: Array<{ title: string; body: ReactNode }> = []
  Children.forEach(children, (child) => {
    if (!isValidElement(child)) return
    // `react-markdown` passes the component back through; check by
    // function identity.
    const el = child as ReactElement<TabProps>
    if (el.type !== Tab) return
    const title = el.props?.title ?? `Tab ${tabs.length + 1}`
    tabs.push({ title, body: el.props?.children })
  })

  // Non-throwing context read (Finding 1): Tabs is a stateful display
  // shortcode, not a trust-boundary control, and is rendered provider-less in
  // tests. Outside a provider the canvas segment is ''.
  const ctx = useCanvasDecisionOptional()
  const canvasName = ctx?.canvasName ?? ''
  const offset = node?.position?.start?.offset ?? 0
  // Accepted ambiguity: a literal '|' in a tab title could collide with the
  // joined form, but the trailing `::offset` segment means a real collision
  // requires the same canvas AND the same source offset — effectively
  // impossible for two distinct Tabs occurrences.
  const key = `${canvasName}::${tabs.map((t) => t.title).join('|')}::${offset}`

  const [active, setActive] = useState(() => tabsActiveState.get(key) ?? 0)
  const select = (i: number) => {
    tabsActiveState.set(key, i)
    setActive(i)
  }

  if (tabs.length === 0) {
    // No <tab> children — render the raw content so the agent still sees
    // its body. `not-prose` severs the prose cascade on this fallback root.
    return (
      <div data-testid="tabs-empty" className="not-prose">
        {children}
      </div>
    )
  }

  const safeActive = Math.min(active, tabs.length - 1)

  return (
    <div data-testid="tabs" className="my-3 border border-bg-border">
      <div
        role="tablist"
        className="flex border-b border-bg-border bg-bg-elevated"
      >
        {tabs.map((tab, i) => (
          <button
            key={i}
            type="button"
            role="tab"
            aria-selected={i === safeActive}
            onClick={() => select(i)}
            className={`px-3 py-1.5 font-mono text-xs uppercase tracking-widest ${
              i === safeActive
                ? 'text-accent-green border-b-2 border-accent-green'
                : 'text-text-secondary hover:text-accent-cyan'
            }`}
          >
            {tab.title}
          </button>
        ))}
      </div>
      <div role="tabpanel" className="not-prose p-3 text-sm text-text-primary">
        {renderChildren(tabs[safeActive].body)}
      </div>
    </div>
  )
}

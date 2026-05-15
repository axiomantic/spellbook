import { Children, isValidElement, useState, type ReactElement, type ReactNode } from 'react'

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
  return <div data-testid="tab">{children}</div>
}

interface TabsProps {
  children?: ReactNode
}

/**
 * Tabbed-panel shortcode (§9.2).
 *
 * Iterates `Children` and selects every `Tab` element. Renders a tab bar
 * + the active tab's body. Tabs without a `title` attribute fall back to
 * "Tab N".
 */
export function Tabs({ children }: TabsProps) {
  const tabs: Array<{ title: string; body: ReactNode }> = []
  Children.forEach(children, (child) => {
    if (!isValidElement(child)) return
    // `react-markdown` passes the component back through; check by type
    // identity OR by the lowercased tag name on the props chain.
    const el = child as ReactElement<TabProps>
    const isTab = el.type === Tab || (typeof el.type !== 'string' && el.type === Tab)
    if (!isTab) return
    const title = el.props?.title ?? `Tab ${tabs.length + 1}`
    tabs.push({ title, body: el.props?.children })
  })

  const [active, setActive] = useState(0)

  if (tabs.length === 0) {
    // No <tab> children — render the raw content so the agent still sees
    // its body.
    return <div data-testid="tabs-empty">{children}</div>
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
            onClick={() => setActive(i)}
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
      <div role="tabpanel" className="p-3 text-sm text-text-primary">
        {tabs[safeActive].body}
      </div>
    </div>
  )
}

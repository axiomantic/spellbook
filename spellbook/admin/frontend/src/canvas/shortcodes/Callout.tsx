import type { ReactNode } from 'react'

export type CalloutType = 'note' | 'tip' | 'warning' | 'danger'

interface CalloutProps {
  type?: CalloutType | string
  title?: string
  children?: ReactNode
}

const TYPE_STYLES: Record<CalloutType, { border: string; label: string }> = {
  note: { border: 'border-accent-cyan', label: 'text-accent-cyan' },
  tip: { border: 'border-accent-green', label: 'text-accent-green' },
  warning: { border: 'border-accent-yellow', label: 'text-accent-yellow' },
  danger: { border: 'border-accent-red', label: 'text-accent-red' },
}

function normalizeType(t: string | undefined): CalloutType {
  if (t === 'tip' || t === 'warning' || t === 'danger' || t === 'note') {
    return t
  }
  return 'note'
}

/**
 * Markdown aside / callout shortcode.
 *
 * Children are markdown content that has already been re-parsed by
 * `react-markdown` + `rehype-raw` upstream; render them inline.
 */
export function Callout({ type, title, children }: CalloutProps) {
  const t = normalizeType(type)
  const styles = TYPE_STYLES[t]
  return (
    <aside
      role="note"
      data-testid="callout"
      data-callout-type={t}
      className={`my-3 border-l-4 ${styles.border} bg-bg-elevated px-3 py-2`}
    >
      <div
        className={`font-mono text-xs uppercase tracking-widest mb-1 ${styles.label}`}
      >
        {`// ${t.toUpperCase()}${title ? ` — ${title}` : ''}`}
      </div>
      <div className="text-sm text-text-primary">{children}</div>
    </aside>
  )
}

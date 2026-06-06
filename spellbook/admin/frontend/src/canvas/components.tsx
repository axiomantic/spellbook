import { Chart } from './shortcodes/Chart'
import { Diagram } from './shortcodes/Diagram'
import { Callout } from './shortcodes/Callout'
import { Tabs, Tab } from './shortcodes/Tabs'
import { Choice } from './shortcodes/Choice'
import { Approve } from './shortcodes/Approve'
import { Collapsible } from './shortcodes/Collapsible'

/**
 * Components-prop dispatch table (§2.2 override mechanism; §7.1 grammar lock).
 *
 * Keys are the lowercased HTML tag names that `rehype-raw` passes
 * through. Values are the React components defined under
 * `./shortcodes/`. The map covers all eight shortcodes from the locked
 * grammar (§7.1): chart, diagram, callout, tabs, tab, choice, approve, collapsible.
 *
 * Hoisted into its own module (§4.6 GATE-2) so the `renderChildren`
 * re-parse fix can import the shared map without forming an import
 * cycle through `render.tsx`.
 *
 * Base-HTML element overrides (a, code, pre, table, th, td) carry
 * token-exact classNames per the §2.2 recipes. These six surfaces are
 * owned SOLELY by this map: Task 3 nulled the @tailwindcss/typography
 * plugin's competing rules for them (§2.1 partition), so there is no
 * specificity fight. Every override-owned element carries `not-prose`
 * (§2.3 belt) except `a` and the bare block `code`, which sit inside
 * already-severed contexts.
 *
 * The `code`/`pre` split uses the react-markdown 9.1.0 detection pinned
 * in Task 6's spike: the v8 `inline` boolean prop is GONE. A fenced
 * block delivers `code` with `className="language-<lang>"`; inline code
 * delivers `className` undefined. The hast node carries no `parent` key
 * in 9.1.0, so `node.parent?.tagName === 'pre'` never fires here — it is
 * retained only as the design's documented forward-compat disjunct. The
 * reliable block predicate is `/language-/.test(className ?? '')`.
 */
/**
 * react-markdown passes the source hast node to every component override as a
 * `node` prop. It must NOT be spread onto a DOM element (React rejects the
 * unknown prop), so overrides that forward author-supplied rest props strip it
 * first. `omitNode` returns the rest props with `node` removed, preserving
 * everything else (href, title, style, …) for faithful forwarding.
 */
const omitNode = <T extends { node?: unknown }>(props: T): Omit<T, 'node'> => {
  const { node: _node, ...rest } = props
  void _node
  return rest
}

const a = ({
  href,
  children,
  ...rest
}: {
  node?: unknown
  href?: string
  children?: unknown
}) => (
  <a
    href={href}
    className="text-accent-cyan hover:text-accent-green underline"
    {...omitNode(rest)}
  >
    {children as never}
  </a>
)

const pre = ({
  children,
  ...rest
}: {
  node?: unknown
  children?: unknown
}) => (
  <pre
    className="not-prose bg-bg-elevated border border-bg-border rounded p-3 overflow-x-auto text-sm"
    {...omitNode(rest)}
  >
    {children as never}
  </pre>
)

const code = ({
  node,
  className,
  children,
  ...props
}: {
  node?: { parent?: { tagName?: string } }
  className?: string
  children?: unknown
}) => {
  const parentTag = node?.parent?.tagName
  const isBlock = /language-/.test(className ?? '') || parentTag === 'pre'
  if (isBlock) {
    return (
      <code className={className} {...props}>
        {children as never}
      </code>
    )
  }
  return (
    <code
      className="not-prose text-accent-cyan bg-bg-elevated px-1 py-0.5 rounded text-sm"
      {...props}
    >
      {children as never}
    </code>
  )
}

const table = ({
  children,
  ...rest
}: {
  node?: unknown
  children?: unknown
}) => (
  <table
    className="not-prose w-full border-collapse border border-bg-border my-3"
    {...omitNode(rest)}
  >
    {children as never}
  </table>
)

// GFM column alignment (`| :-: |`) is emitted by mdast-util-to-hast 13.x as the
// hast `align` property on th/td, but react-markdown's JSX runtime
// (hast-util-to-jsx-runtime, tableCellAlignToStyle defaulting to true) converts
// it into an inline `style={{ textAlign }}` prop rather than an `align` prop.
// The override must forward that style (and any other rest props) so authored
// alignment survives; an inline text-align style outranks the recipe's
// text-left class in the cascade, so the recipe's default stays correct for
// unaligned columns. `node` is destructured OUT — it must never reach the DOM.
const th = ({
  children,
  ...rest
}: {
  node?: unknown
  children?: unknown
}) => (
  <th
    className="border border-bg-border bg-bg-elevated px-3 py-1.5 text-left font-mono text-xs uppercase tracking-widest text-text-secondary"
    {...omitNode(rest)}
  >
    {children as never}
  </th>
)

const td = ({
  children,
  ...rest
}: {
  node?: unknown
  children?: unknown
}) => (
  <td
    className="border border-bg-border px-3 py-1.5 text-sm text-text-primary"
    {...omitNode(rest)}
  >
    {children as never}
  </td>
)

export const components = {
  chart: Chart,
  diagram: Diagram,
  callout: Callout,
  tabs: Tabs,
  tab: Tab,
  choice: Choice,
  approve: Approve,
  collapsible: Collapsible,
  a,
  code,
  pre,
  table,
  th,
  td,
}

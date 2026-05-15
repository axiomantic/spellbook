import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeRaw from 'rehype-raw'
import { Chart } from './shortcodes/Chart'
import { Diagram } from './shortcodes/Diagram'
import { Callout } from './shortcodes/Callout'
import { Tabs, Tab } from './shortcodes/Tabs'
import { Choice } from './shortcodes/Choice'
import { Approve } from './shortcodes/Approve'

/**
 * Components-prop dispatch table (§8.2).
 *
 * Keys are the lowercased HTML tag names that `rehype-raw` passes
 * through. Values are the React components defined under
 * `./shortcodes/`. The map covers all seven shortcodes from the locked
 * §9 grammar: chart, diagram, callout, tabs, tab, choice, approve.
 */
const components = {
  chart: Chart,
  diagram: Diagram,
  callout: Callout,
  tabs: Tabs,
  tab: Tab,
  choice: Choice,
  approve: Approve,
}

interface CanvasRenderProps {
  content: string
}

/**
 * Render canvas markdown via `react-markdown` with the locked §9
 * shortcode dispatch table.
 *
 * Pipeline:
 *   raw markdown → react-markdown → remark-gfm (tables, task lists)
 *     → rehype-raw (allow raw HTML) → components-prop dispatch
 *
 * Trust boundary: §10 trusted-local-agent. `rehype-raw` will execute
 * raw `<script>` tags. Do NOT pass unsanitized external content into a
 * canvas; the constraint is enforced by convention, not sanitization.
 */
export function CanvasRender({ content }: CanvasRenderProps) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      rehypePlugins={[rehypeRaw]}
      components={components as never}
    >
      {content}
    </ReactMarkdown>
  )
}

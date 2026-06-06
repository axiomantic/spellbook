import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeRaw from 'rehype-raw'
import { components } from './components'

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
 * Trust boundary: trusted-local-agent (see skills/canvas/SKILL.md threat model). `rehype-raw` will execute
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

import { Children, type ReactNode } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeRaw from 'rehype-raw'
import { components } from '../components'
import { extractText } from './extractText'

/**
 * GATE-2 (design §4.6) — raw-string shortcode children re-parse.
 *
 * Content on the line IMMEDIATELY after an opening children-content
 * shortcode tag (no blank line) is swallowed by CommonMark's raw-HTML-block
 * rule: `react-markdown` + `rehype-raw` deliver the entire body as ONE plain
 * string child, with its markdown left UNPARSED (literal `**bold**`,
 * `` `code` ``, etc. on screen).
 *
 * This helper detects raw-string-only children and re-parses them through the
 * SAME pipeline (`remark-gfm` + `rehype-raw`) using the SHARED `components`
 * map, so the element overrides (a, code, pre, table, th, td) apply to the
 * nested content too. Element children (the healthy blank-line-separated
 * case, already parsed upstream) pass through untouched.
 *
 * Recursion is self-terminating: once re-parsed, children are elements, not
 * strings, so a nested `renderChildren` call would short-circuit at the
 * pass-through branch. No depth counter is needed (§4.6 step 3).
 *
 * The shared-map import does not form a cycle: `components.tsx` was hoisted
 * out of `render.tsx` (Task 4 / §4.6) precisely so this module can import the
 * map without routing through the top-level render entry point.
 *
 * MIXED children (a raw-string sibling alongside an element sibling — e.g. the
 * author wrote one line tight and another blank-line-separated) pass through
 * VERBATIM: `isRawStringChildren`'s `.every()` fails on the element sibling, so
 * the array is returned unchanged and the tight string portion stays literal,
 * unparsed markdown on screen. This is correct under §4.6's two-state model;
 * the blank-line authoring discipline is the author-side mitigation.
 */
function isRawStringChildren(children: ReactNode): boolean {
  const arr = Children.toArray(children)
  return arr.length > 0 && arr.every((c) => typeof c === 'string' || typeof c === 'number')
}

export function renderChildren(children: ReactNode): ReactNode {
  if (!isRawStringChildren(children)) return children
  const raw = extractText(children)
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      rehypePlugins={[rehypeRaw]}
      components={components as never}
    >
      {raw}
    </ReactMarkdown>
  )
}

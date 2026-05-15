import { Children, isValidElement, type ReactNode } from 'react'

/**
 * Extract text content from `react-markdown` children, joining all string
 * children into a single string.
 *
 * Used by `<chart>` and `<diagram>` whose body is raw JSON / DSL that
 * must NOT be re-parsed as markdown. Mirrors the §12 spike helper that
 * was validated against `react-markdown@9` + `remark-gfm@4` +
 * `rehype-raw@7` (see `docs/spellbook-canvas-shortcode-spike/`).
 *
 * `react-markdown` wraps inline content in `<p>` elements; recurse into
 * those so the spec body survives a paragraph wrapper.
 */
export function extractText(children: ReactNode): string {
  let out = ''
  Children.forEach(children, (child) => {
    if (typeof child === 'string') {
      out += child
    } else if (typeof child === 'number') {
      out += String(child)
    } else if (isValidElement(child)) {
      const childProps = child.props as { children?: ReactNode } | null
      if (childProps && 'children' in childProps) {
        out += extractText(childProps.children)
      }
    }
  })
  return out
}

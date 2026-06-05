import { describe, it, expect } from 'vitest'

/**
 * D3 / DA-10 invariant guard (source-level).
 *
 * The operator's free-text note (`free_text` on submit, surfaced as
 * `lastFreeText`) is terminal-input trust class. It must be rendered ONLY as a
 * React-escaped plain-text node in `CanvasDetail`, and must NEVER flow through
 * `CanvasRender` / `react-markdown` / `rehype-raw`, where an injected
 * `<script>` would execute.
 *
 * The cheapest durable guard is structural: pin the exact set of source files
 * (excluding tests) allowed to reference `lastFreeText`. Crucially, NO file
 * under `src/canvas/` (the CanvasRender subtree: `render.tsx` + `shortcodes/`)
 * may reference it — that is the load-bearing assertion. If a future edit pipes
 * the echo into a shortcode or into `CanvasRender`, a new `src/canvas/...`
 * reference appears and this test fails.
 *
 * Source files are loaded as raw text via Vite's `import.meta.glob('?raw')`, so
 * the guard needs no Node `fs`/`path` (the SPA carries no `@types/node`).
 *
 * FALSIFICATION: adding `lastFreeText` to `src/canvas/render.tsx` (or any
 * shortcode) makes `references` include a `src/canvas/...` path absent from
 * `ALLOWED`, so the assertion throws. Verified locally by temporarily reading
 * `submit.lastFreeText` inside `CanvasRender`.
 */

// All SPA source files as raw text, keyed by `/src/...`-relative path. The glob
// patterns intentionally exclude the `__tests__` directories (test fixtures
// legitimately reference the field).
const rawModules = import.meta.glob('/src/**/*.{ts,tsx}', {
  query: '?raw',
  import: 'default',
  eager: true,
}) as Record<string, string>

// Exact allowed reference sites (relative to `src/`), and WHY each is safe.
const ALLOWED = [
  // Type definition of the field on the submit projection.
  'canvas/CanvasDecisionContext.tsx',
  // Hook that derives the field from the mutation variables (no render).
  'hooks/useDecisionSubmit.ts',
  // The single render site: escaped plain-text node, never CanvasRender.
  'pages/CanvasDetail.tsx',
].sort()

describe('free_text / lastFreeText render-site invariant (D3)', () => {
  it('references lastFreeText only in the pinned allowed files, never in the CanvasRender subtree', () => {
    const references = Object.entries(rawModules)
      .filter(([path]) => !path.includes('/__tests__/'))
      .filter(([, source]) => source.includes('lastFreeText'))
      .map(([path]) => path.replace(/^\/src\//, ''))
      .sort()

    // Exact-equality on the complete set of non-test reference sites.
    expect(references).toEqual(ALLOWED)

    // Explicit load-bearing sub-assertion: nothing in the CanvasRender subtree
    // (render.tsx + shortcodes/) references it.
    const inRenderSubtree = references.filter(
      (r) => r === 'canvas/render.tsx' || r.startsWith('canvas/shortcodes/'),
    )
    expect(inRenderSubtree).toEqual([])
  })
})

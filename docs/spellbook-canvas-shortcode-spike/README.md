# Spellbook Canvas — Shortcode Spike Reproducer

This directory contains the Phase 2 shortcode spike that locked the §9 grammar
in the canvas design. It is kept as a permanent reproducer: if `rehype-raw` or
`react-markdown` ever regresses the shortcode contract, run these files locally
to identify the regression.

## Contents

- `canvas-shortcode-spike.html` — self-contained ESM page that imports
  `react@19`, `react-markdown@9`, `remark-gfm@4`, `rehype-raw@7` via
  `importmap` from `esm.sh` and renders the canonical shortcode sample
  (`<chart>` with multiline JSON nested inside `<tabs>`, plus a `<chart>` in
  a GFM table cell).
- `spike-result.md` — the original PASS/FAIL verdict, dated, with package
  versions and rendered-DOM evidence.

## How to run (browser)

```bash
cd docs/spellbook-canvas-shortcode-spike
python3 -m http.server 7777
# open http://localhost:7777/canvas-shortcode-spike.html
```

Then verify, in DevTools "Elements":

1. A green-bordered `TABS:` container holds two `<tab>` children (`Alpha`, `Beta`).
2. Inside the `Alpha` tab, a blue-bordered `CHART:` block contains
   `caption="multiline spec"` and the literal Vega-Lite JSON
   `{"mark":"bar","encoding":...}` with no characters lost.
3. The GFM table at the bottom renders intact, and its `viz` cell either
   shows a `CHART:` block or inline text — both pass.

If any of those three checks fail, the upstream package upgrade has regressed
the §9 grammar; consult `spike-result.md` for the locked baseline and the
§12.6 fallback paths in the design doc
(`2026-05-14-spellbook-canvas-design.md`).

## How to re-verify headlessly

`spike-result.md` was captured via `react-dom/server.renderToStaticMarkup`
running the same `react-markdown` + `remark-gfm` + `rehype-raw` chain under
Node. The HTML reproducer above is the canonical baseline; a headless
re-verification is straightforward but not committed to the repo (it would
add a transient `node_modules/` dependency that this directory deliberately
avoids — the spike is meant to be runnable with nothing but Python's stdlib
HTTP server and a browser).

See `spike-result.md` for the original verdict and the locked-in §9 grammar.

# Phase 2 Shortcode Spike Result

**Date:** 2026-05-14
**Tested with:** react-markdown@9.1.0, remark-gfm@4.0.1, rehype-raw@7.0.0
**React:** 19.2.6 (`react-dom@19.2.6` for `renderToStaticMarkup`)
**Browser:** N/A — verified via Node 25.9.0 + `react-dom/server.renderToStaticMarkup`
  using the same `react-markdown` + `remark-gfm` + `rehype-raw` versions from
  the import-map'd spike HTML (`spellbook/admin/frontend/spike/canvas-shortcode-spike.html`).
  Verification methodology: render the exact markdown sample from design §12.3
  through the same pipeline, then inspect the serialized DOM string. The
  browser path uses identical packages via `esm.sh` — the rendered DOM tree
  is the same artifact, only the serialization differs.

## Criteria

| # | Criterion | Result | Notes |
|---|---|---|---|
| 1 | `<tabs>` preserves `<tab>` children container semantics | PASS | The rendered DOM has one `data-shortcode="tabs"` container whose subtree contains exactly two `data-shortcode="tab"` children (`Alpha` and `Beta`). Tabs container did NOT collapse — children were not flattened into siblings. |
| 2 | Multiline JSON survives inside `<chart>` children | PASS | All five JSON fragments from the Vega-Lite spec (`"mark":"bar"`, `"encoding"`, `"x":{"field":"a"}`, `"y":{"field":"b"}`, `"data":{"values":[{"a":1,"b":2},{"a":3,"b":4}]}`) appear verbatim inside the `<pre data-shortcode="chart">` block of the `Alpha` tab. The `caption="multiline spec"` attribute is correctly extracted to the rendered output. No JSON characters were lost or corrupted; HTML-entity escaping (`&quot;`) is applied at serialization time by React, which is the expected and reversible round-trip. |
| 3 | Table-cell `<chart>` renders or falls back without breaking layout | PASS (case a) | The `<chart>` inside the GFM table cell renders as a full `<pre data-shortcode="chart">` block containing `CHART: caption="inline"\n{"mark":"point"}`. The surrounding `<table>` element is preserved with `<thead>`, `<tbody>`, and the original `name`/`viz` cells intact. Per design §9.4, case (a) is the strict-rendering pass; the documented "inline-only in table cells" posture remains the recommended convention for agent authors, but the spike confirms the pipeline does NOT break on block shortcodes inside cells. |

## Verdict

**OVERALL: PASS** → §9 contract LOCKED as designed (children-content + attribute-content hybrid).

The shortcode grammar from design §9 (`<chart caption="...">{multiline JSON}</chart>`
nested inside `<tabs><tab title="...">...</tab></tabs>`) survives the
`react-markdown@9` + `remark-gfm@4` + `rehype-raw@7` pipeline intact. Tracks
A, B, and C may proceed with the §9 grammar as written.

## Evidence transcript

Rendered DOM (entity-decoded) for the `<tabs>` / `<chart>` portion:

```html
<div style="border:1px solid green;padding:8px" data-shortcode="tabs">TABS:
  <div style="margin-left:16px" data-shortcode="tab"><strong>Alpha</strong>:
    <pre style="border:1px solid blue;padding:8px" data-shortcode="chart">CHART: caption="multiline spec"

{"mark":"bar","encoding":{"x":{"field":"a"},"y":{"field":"b"}},"data":{"values":[{"a":1,"b":2},{"a":3,"b":4}]}}
    </pre>
  </div>
  <div style="margin-left:16px" data-shortcode="tab"><strong>Beta</strong>:
    just text
  </div>
</div>
```

Rendered DOM for the table-cell portion:

```html
<table>
  <thead><tr><th>name</th><th>viz</th></tr></thead>
  <tbody>
    <tr>
      <td>foo</td>
      <td><pre style="border:1px solid blue;padding:8px" data-shortcode="chart">CHART: caption="inline"
{"mark":"point"}</pre></td>
    </tr>
  </tbody>
</table>
```

Full transcript including the unescaped HTML and the per-criterion checker
output is preserved in this repo via the spike HTML reproducer
(`./canvas-shortcode-spike.html`, moved here from
`spellbook/admin/frontend/spike/` in Task D.4) — see the README in this
directory for how to re-run it.

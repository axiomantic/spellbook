# §9 Shortcode Grammar — LOCKED

**Date:** 2026-05-14
**Locked by:** Phase 2 shortcode spike (Track D, this directory)
**Spike verdict:** PASS (all three §12.5 criteria — see `spike-result.md`)
**Grammar selected:** **children-content** (children-content + attribute-content
  hybrid, exactly as originally specified in design §9.2).

## What this means for downstream tracks

- **Track A (Backend):** No grammar-driven changes to the MCP tools or
  Pydantic models. `canvas_write` accepts the markdown body unchanged; the
  filesystem store treats canvas content as opaque text.
- **Track B (Frontend):** Implement the shortcode dispatch table at §9.2 as
  written. `<chart>` and `<diagram>` parse multiline content via
  `React.Children.toArray(children).join('')`. `<tabs>` / `<tab>` use the
  child-element container pattern (verified to survive `react-markdown@9` +
  `remark-gfm@4` + `rehype-raw@7`).
- **Track C (Skill / Slash command):** Document the §9.2 grammar in
  `skills/canvas/SKILL.md` Shortcode Reference. The grammar is final;
  no fenced-code-block fallback is needed.

## Snapshot of the §9 annotation in the design doc

The following block was added at the very top of §9 in
`/Users/eek/.local/spellbook/docs/Users-eek-Development-spellbook/plans/2026-05-14-spellbook-canvas-design.md`
on 2026-05-14:

```markdown
> **§9 GRAMMAR LOCKED** (2026-05-14 per Phase 2 spike result):
> Grammar in effect for MVP: **children-content** (children-content + attribute-content hybrid as originally specified in §9.2).
> Verified against `react-markdown@9.1.0` + `remark-gfm@4.0.1` + `rehype-raw@7.0.0` on React 19.2.6.
> All three §12.5 criteria PASS — see `docs/spellbook-canvas-shortcode-spike/spike-result.md`
> for the verdict transcript and rendered-DOM evidence. The permanent reproducer
> (`docs/spellbook-canvas-shortcode-spike/canvas-shortcode-spike.html`) is preserved
> as the baseline for future `rehype-raw` / `react-markdown` upgrade validation.
> Tracks A, B, and C are UNBLOCKED.
```

(The design doc itself lives outside this repo, under the user's local
spellbook plans area; this in-repo file is the canonical, version-controlled
record of the lock event so Track A/B/C reviewers can see it without
chasing the out-of-tree path.)

## Tracks A, B, C are UNBLOCKED.

---

## Amendment 2026-06-05 — <collapsible> added (children-content)

**Spike verdict:** PASS. Verified against react-markdown@9 + remark-gfm@4 +
rehype-raw@7 via renderToStaticMarkup (spike: spellbook/admin/frontend/spike/
collapsible.spike.test.tsx, this branch).

Criteria met:
- summary attr survives onto button label; default collapsed (body absent).
- open presence-attr toggles initial state; body renders.
- children RE-PARSED as markdown: bold, nested <callout>, GFM table.
- nests inside <tab> (CRIT 6).

Grammar class: children-content (Callout pattern). Attributes: summary?: string,
open?: presence-bool. Children: markdown, re-parsed recursively.

Known cosmetic artifact (pre-existing, NOT introduced here): block shortcodes on
their own line in re-parsed children get <p>-wrapped by react-markdown (block-in-p,
browser-tolerated). Same as <callout> today. Not fixed in this run (render-engine
change is out of scope).

The eight-shortcode grammar (chart, diagram, callout, tabs, tab, choice, approve,
collapsible) is the new locked set.

### Status primitives = render-layer only, NO grammar change

The `components.input` task-list override is a **render-layer change, NOT a
grammar change.** No new shortcode, no new tag, no lock amendment for status
primitives. GFM `- [x]` syntax is already in the locked grammar (remark-gfm); the
override only restyles its emitted DOM. This amendment covers `<collapsible>`
ONLY.

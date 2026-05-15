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

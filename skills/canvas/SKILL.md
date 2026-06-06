---
name: canvas
description: "Use when the user wants to present rendered output (diagrams, plans, charts, status, side-by-side options) outside the terminal. Triggers: 'open a canvas', '/canvas', 'put this in a canvas', 'visualize this', 'render this in the browser', 'canvas name', 'close the canvas'. NOT for: live-editable artifacts where the browser writes (use a2a for that), persisted documents (use ~/.local/spellbook/docs/), or anything requiring SSR."
intro: |
  Spellbook canvas is a live-updating presentation surface served at
  /admin/canvas/<name> in the admin SPA. Agents call canvas_open + canvas_write
  via MCP; the browser renders markdown + curated shortcodes and live-updates
  on each write.
---

## Overview

A canvas is a named, agent-owned presentation surface backed by a small
filesystem tree under `~/.local/spellbook/canvas/<name>/`:

```
<name>/
  meta.json         # name, title, created_at, last_updated, closed
  pages/index.md    # markdown body (MVP is single-page)
  inbox/            # live submission store: one JSON per submitted decision
```

The agent drives the canvas with three MCP tools (`canvas_open`,
`canvas_write`, `canvas_close`) and observes the catalog via a fourth
(`canvas_list`). The admin SPA at `/admin/canvas/<name>` subscribes to a
`CANVAS` WebSocket subsystem; every `canvas.updated` / `canvas.opened` /
`canvas.closed` event invalidates the relevant React Query cache key and
re-fetches the page. The render path is `react-markdown@9` + `remark-gfm` +
`rehype-raw`, with a curated `components` prop dispatching the shortcodes
listed below.

Canvas lifecycle:

1. `canvas_open("plan-x")` — idempotent claim. Creates the tree on first
   call; returns the existing metadata on subsequent calls. The returned
   `url` is the page the operator opens in a browser tab.
2. `canvas_write("plan-x", markdown_body)` — last-write-wins atomic replace
   of `pages/index.md`. Publishes `canvas.updated` on the event bus, which
   the SPA picks up within ~100ms.
3. `canvas_close("plan-x")` — marks the canvas closed in `meta.json`.
   Subsequent `canvas_write` calls return `{"code": "closed"}`. Files are
   NOT deleted; closure is a soft state.

The agent owns page writes; the browser can submit DECISIONS via
`<choice>`/`<approve>` when a decision is declared. See the
**Two-Way Decisions** section below and the `canvas-decision` skill.

## Invariant Principles

1. **Decisions are two-way; the agent declares and awaits.** When you need an
   operator decision, the agent declares it (`canvas_decision_open`), renders a
   live `<choice>`/`<approve>` control, and awaits the submission
   (`canvas_decision_await`); the browser submits back to the awaiting session.
   Only the session **main context** declares and awaits — never a subagent.
   See the `canvas-decision` skill for the full when-to-use boundary.
2. **Writes are full-body, last-write-wins — but decision state is exempt.**
   `canvas_write` atomically replaces all of `pages/index.md`; there are no
   incremental patches. Each call MUST carry the complete intended page,
   because the previous content is discarded. Sending a partial body silently
   erases the rest of the page. Declared-decision state lives in `meta.json`,
   NOT in the page body, so `canvas_write` does NOT touch it: a pending
   decision survives every page rewrite.
3. **Never pass external content to `canvas_write`.** `rehype-raw` is in the
   render path by design (the shortcode grammar depends on it), so raw
   `<script>` in the markdown WILL execute under the admin's authenticated
   origin. Web fetches, external transcripts, unvetted MCP output, and pasted
   third-party strings must be summarized/paraphrased in your own words and
   stripped of literal markup before they reach a canvas. Mitigation is agent
   discipline, not sanitization.
4. **A canvas is ephemeral working memory, not a persisted artifact.** It is
   scoped to the current session and is not the place for docs that must
   survive compaction or be checked in — those go to `~/.local/spellbook/docs/`
   via the artifact conventions.
5. **`canvas_open` is idempotent; `canvas_close` is a soft state.** Opening an
   existing name returns its metadata rather than recreating it, so re-opening
   is safe. Closing marks `meta.json` closed (writes then return
   `{"code": "closed"}`) but never deletes files.

<analysis>
Before rendering anything to a canvas, settle three questions:

- **Is a canvas the right surface at all?** Canvas earns its cost only when
  the output is visual or benefits from a browser tab the operator keeps open
  (diagrams, charts, multi-section plans, side-by-side options, rolling
  status). For a short answer or a document that must persist, the terminal or
  `~/.local/spellbook/docs/` is correct — do not reach for a canvas reflexively.
- **What is the provenance of every byte in the payload?** Trace each section
  of the markdown back to its source. Anything originating outside this agent
  (WebFetch, external transcript, pasted text, upstream MCP output) is
  untrusted and cannot go in verbatim — it must be paraphrased and de-marked-up
  first, because rehype-raw executes raw HTML under the admin origin.
- **Does the rendering need anything the grammar forbids?** Block shortcodes
  in table cells, browser write-back, SSR/OG unfurls, and nesting beyond the
  documented matrix are out of scope. If the desired layout needs one of
  these, redesign within the grammar rather than emitting markup that renders
  broken.
</analysis>

<reflection>
Before declaring a canvas turn complete, self-check:

- Did I send the **complete** page body, or did a last-write-wins call
  silently truncate the canvas to a partial?
- Did any external-provenance content reach `canvas_write` un-paraphrased? If
  so, that is a same-origin script-execution risk, not a cosmetic issue — fix
  it.
- Did I surface the canvas URL to the operator so they can actually open the
  tab, or did I write into the void?
- For an operator decision that belongs on a canvas, did I declare and await it
  (`canvas_decision_open` → render a live `<choice>`/`<approve>` →
  `canvas_decision_await`) so the live control can submit back, rather than
  rendering an inert control no one consumes?
- Did I conflate ephemeral canvas state with a durable artifact that should
  have been written to `~/.local/spellbook/docs/` instead?
</reflection>

## When to Use

- **Diagrams.** Mermaid flowcharts, sequence diagrams, ER diagrams that
  belong in a browser tab rather than a terminal ASCII rendering.
- **Plans.** Multi-section implementation plans, design docs, or research
  digests where headings, tables, and side-by-side options improve
  readability over scrollback.
- **Charts.** Vega-Lite specs for latency timelines, cost breakdowns,
  benchmark comparisons — anything the operator wants to look at, not just
  read.
- **Side-by-side options.** Tab panels comparing approaches (e.g. "Option A
  vs Option B") where the operator picks visually rather than scrolling.
- **Live status.** Long-running orchestrations that want to surface a
  rolling summary the operator can keep open in a tab while you work.

## NOT For

- **Persisted documents.** A canvas is ephemeral working memory for the
  current session, not a long-lived artifact. For docs that should survive
  session compaction or be checked in, write to `~/.local/spellbook/docs/`
  via the artifact conventions instead.
- **Anything requiring SSR.** Canvas is a client-rendered SPA route.
  External link unfurls, OG metadata, and pre-rendered HTML for crawlers
  are not in scope.

## Two-Way Decisions

A canvas can take a decision back from the operator. The agent declares a
decision (`canvas_decision_open`), renders a live `<choice>` or `<approve>`
control on the page, surfaces the URL, then awaits the operator's submission
(`canvas_decision_await`) — which flows back to the awaiting session. Decision
state lives in `meta.json` and survives page rewrites (see Invariant 2).

This is a distinct workflow with its own when-to-use boundary (a canvas
decision is for context-heavy forks, not quick yes/no gates) and a
main-context-only rule. **Use the `canvas-decision` skill** for the full
boundary, the declare→render→await mechanics, and the trust-class cautions on
submitted answers.

## Quick Reference

| Command | Purpose |
|---|---|
| `/canvas open <name>` | Idempotent open. Calls `canvas_open` MCP tool. Returns the admin URL. |
| `/canvas close <name>` | Marks closed. Calls `canvas_close` MCP tool. Files are not deleted. |
| `/canvas list` | Lists known canvases (open + closed). Calls `canvas_list` MCP tool. |

Writes are NOT a slash command. The agent calls `canvas_write` directly via
MCP, passing the full markdown body each time (last-write-wins, no
incremental patches).

`canvas_list` returns a small JSON envelope describing every canvas under
the configured root; the admin SPA's `/admin/canvas` index page is backed
by the same data.

## Shortcode Reference

Grammar locked 2026-05-14 by the Phase 2 spike. Verified against
`react-markdown@9.1.0` + `remark-gfm@4.0.1` + `rehype-raw@7.0.0` on React
19.2.6. See `docs/spellbook-canvas-shortcode-spike/spike-result.md` for the
verdict transcript and rendered-DOM evidence; the in-repo
`docs/spellbook-canvas-shortcode-spike/GRAMMAR-LOCK.md` is the canonical
lock record.

Tag names are lowercase HTML-style. The fundamental rule: short string
props go in attributes; multi-line content (JSON specs, DSL sources,
markdown bodies) goes in children.

| Shortcode | Attributes | Children |
|---|---|---|
| `<chart>` | `caption?: string` | Vega-Lite JSON spec as text (NOT re-parsed as markdown). |
| `<diagram>` | `caption?: string` | Mermaid DSL source as text (NOT re-parsed as markdown). |
| `<callout>` | `type: "note" \| "tip" \| "warning" \| "danger"` (default `"note"`), `title?: string` | Markdown content (re-rendered recursively). |
| `<tabs>` | — | Must contain `<tab>` elements only. `<tab>` takes `title: string`; tab children are markdown. |
| `<choice>` | `id: string`, `prompt: string`, `options: string` (JSON-encoded `[{value, label}]`) | — (self-closing; renders a live control when a decision with this `id` is declared, disabled otherwise). |
| `<approve>` | `id: string`, `prompt: string`, `confirm_label?: string`, `decline_label?: string` | — (self-closing; renders a live control when a decision with this `id` is declared, disabled otherwise). |
| `<collapsible>` | `summary?: string` (default `"Details"`), `open?: presence-bool` | Markdown content (re-rendered recursively). |

Nesting rules:

| Container | Allowed nested shortcodes |
|---|---|
| `<callout>` | All, including `<collapsible>`. Don't abuse — a callout nested three deep is a smell. |
| `<tabs>` / `<tab>` | All, including `<collapsible>`. A `<chart>` inside a `<tab>` is the canonical use case. |
| `<collapsible>` | All. Don't nest 3-deep — same smell rule as `<callout>`. |
| `<chart>`, `<diagram>` | None. Children are raw text only. |
| `<choice>`, `<approve>` | None. Self-closing. |

Block shortcodes (`<chart>`, `<diagram>`, `<tabs>`) inside markdown table
cells are NOT supported. Inline `<callout>` and plain text are fine in
table cells.

GFM task-list items (`- [x]` / `- [ ]`) render as status icons (done /
pending), NOT interactive checkboxes — the operator cannot toggle them.
Use them to show completion state, not to collect input.

`<collapsible>` open/closed state is cached per `summary` string, so give
sibling collapsibles distinct summaries; otherwise they share one cache
entry and toggle together.

Example markdown an agent might emit via `canvas_write`:

````markdown
# Plan: Feature X

<callout type="warning" title="Heads up">
This change touches the auth path. Review carefully.
</callout>

## Architecture

<diagram caption="Request flow">
flowchart LR
  A --> B
  B --> C
</diagram>

## Metrics

<chart caption="Daily p99 latency">
{"mark":"line","encoding":{"x":{"field":"date","type":"temporal"},"y":{"field":"p99","type":"quantitative"}},"data":{"values":[{"date":"2026-05-01","p99":120},{"date":"2026-05-02","p99":135}]}}
</chart>

## Options

<tabs>
  <tab title="Option A">
    Single-table schema. Simpler to query.
  </tab>
  <tab title="Option B">
    Star schema. More flexible for analytics.
  </tab>
</tabs>

## Progress

- [x] Schema drafted
- [x] Migration written
- [ ] Backfill verified

<collapsible summary="Migration details">

The migration runs in two phases to avoid a long table lock.

```sql
ALTER TABLE events ADD COLUMN region text;
```

</collapsible>
````

## Threat Model

Canvas content is **trusted-local-agent** output. It is treated with the
same trust posture as agent-emitted memory files, agent-written code, or
agent-spawned subprocesses: the local agent runs with the operator's
privileges, and what it writes is what gets rendered.

`rehype-raw` is in the render pipeline by design — `<chart>`, `<diagram>`,
`<callout>`, and `<tabs>` are raw HTML-shaped tags that the
react-markdown `components` prop dispatches on. Removing rehype-raw would
break the entire shortcode grammar. As a direct consequence, **raw
`<script>` tags in canvas markdown WILL execute under the admin origin**
(`http://127.0.0.1:8765`), which is the admin's HMAC-cookie-authenticated
origin. A malicious script can read the admin's HttpOnly cookie via
same-origin XHR/fetch, exfiltrate session tokens, or call admin API
endpoints with the operator's auth.

The mitigation is **agent discipline, not sanitization**. When the user
gives you content that came from an external source, do NOT pass it to
`canvas_write` without sanitization. Treat external content as untrusted
input. Specifically, the following are forbidden as direct
`canvas_write` payloads:

- Chat transcripts from external systems.
- Web pages fetched via `WebFetch` or similar tools.
- MCP tool outputs from upstream tools whose provenance you can't vouch
  for.
- User-pasted strings from another session's clipboard, untrusted email,
  or third-party documents.

If you need to surface external content on a canvas, **summarize and
paraphrase it in your own words first**, dropping any literal HTML.
Quoting verbatim is fine for prose — it is NOT fine for anything that
might contain markup. If the operator explicitly asks you to render
untrusted HTML in a canvas, STOP and confirm — that path is reserved for
v2's `rehype-sanitize` layer.

**Operator-submitted answers are a second trust class.** When a decision is
declared, the operator submits a value (and optionally `free_text`) from the
browser. That submission is **terminal-input trust class** — the same trust you
give anything the operator types in the terminal. Two rules follow:

- `free_text` is rendered as **plain text**, never as markup. Do not interpret
  it as shortcodes or HTML.
- **Never round-trip a submission into `canvas_write`.** Treat the submitted
  value/`free_text` as plain-text data to act on; do NOT echo it verbatim back
  into a page body, where it would re-enter the `rehype-raw` render path. The
  `canvas-decision` skill states this caution (DA-10).

The `canvas_open` and `canvas_write` MCP tool docstrings repeat this
threat model so an agent sees it at the call site; the same boundary is
documented in `spellbook/canvas/store.py`. This SKILL.md is the
agent-facing primary source.

## Worked Example

A ten-line agent transcript that opens a canvas, writes a small plan to
it, and surfaces the URL to the operator:

```python
# 1. Claim the name (idempotent — safe to call again later).
canvas_open(name="plan-x", title="Refactor: extract auth module")

# 2. Write the body. Last-write-wins; the whole markdown payload goes
#    in `content` on every call.
canvas_write(
    canvas="plan-x",
    content="""# Refactor: extract auth module

<callout type="note" title="Scope">
Move `auth/*` out of `core/` into a new top-level package.
</callout>

## Steps

1. Move files.
2. Update imports.
3. Run the test suite.
""",
)

# 3. Surface the canvas URL to the operator (returned by canvas_open
#    above) so they can open it in a browser tab.
```

After this turn the operator sees `http://127.0.0.1:8765/admin/canvas/plan-x`
in the terminal; opening it shows the rendered plan, and any subsequent
`canvas_write("plan-x", ...)` call updates the page live without a
refresh.

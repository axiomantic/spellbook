# canvas-decision

**Auto-invocation:** Your coding assistant will automatically invoke this skill when it detects a matching trigger.

> Use when an operator decision belongs on a browser page rather than a terminal
prompt. Triggers: "present a decision in the browser", "ask via a canvas page",
"interactive decision page", "let me decide in the browser", "render the choice
visually". Also invoked by develop when the decision-surface preference is
`canvas` (feature-config Question 8). NOT for: quick yes/no with no context
(use terminal `AskUserQuestion`), read-only presentation (use `canvas`), or
subagent-internal choices with no operator (decide in-context).
## Skill Content

``````````markdown
# Canvas Decision

<ROLE>
Decision-surface steward. Reputation depends on routing each fork to the surface
that serves the operator — never spamming a browser page for a trivial gate, and
never burying a context-heavy fork in a terminal one-liner.
</ROLE>

## Invariant Principles

1. **Main context only** - Only the session main context declares and awaits a
   decision. A subagent has no operator and no path to receive the submission, so
   awaiting from one deadlocks until timeout. The declare→await pair is a
   main-context capability, full stop.
2. **The surface must earn its cost** - A browser round-trip is justified only by
   context that a terminal prompt cannot carry well (options with real
   trade-offs, an explanatory diagram, an irreversible choice). When context is
   thin, terminal or autonomous-proceed is the correct surface, not canvas.
3. **The binding never leaves the daemon** - The agent declares with a session
   binding; the await consumes a submission matched to that binding. You handle
   the answer as plain-text data, not the binding.
4. **Submitted answers are terminal-input trust class** - A value or `free_text`
   the operator submits is treated like terminal input: acted on as data, never
   echoed verbatim back into `canvas_write`, never interpreted as markup.

## Reasoning Schema

<analysis>
Before opening a canvas decision, settle:

- **Is this even a real fork?** If there is one correct path, proceed
  autonomously — declare nothing.
- **Does the surface preference or an explicit ask point at canvas?** Either
  `SESSION_PREFERENCES.decision_surface == "canvas"` (feature-config Q8) OR the
  operator explicitly asked for a visual/interactive decision.
- **Is the decision context-heavy?** At least TWO of: multiple options with
  non-obvious trade-offs; explanatory prose or a diagram/chart materially aids
  the choice; the decision is hard to reverse (architecture, schema, public
  contract).
- **Am I the main context?** If a subagent, do not await — surface the fork to
  the orchestrator instead.
</analysis>

<reflection>
After the decision resolves, verify:

- Did I await the submission rather than render an inert control and move on?
- Did I treat the submitted value/`free_text` as plain-text data, never echoing
  it back into `canvas_write`?
- If the boundary was NOT met, did I use terminal `AskUserQuestion` (quick gate)
  or proceed autonomously (no real fork) instead of forcing a canvas?
IF NO to any: stop, correct the surface, do not ship the wrong-surface decision.
</reflection>

## When to Use (testable boundary)

Use a canvas decision **iff ALL** of the following hold:

1. **Gate 1 (routing) — Surface routed to canvas:** `decision_surface == "canvas"`
   (feature-config Q8) **OR** the operator explicitly asked for an
   interactive/visual decision; AND
2. **Gate 2 (context-heaviness, ≥2 of 3) — Context-heavy:** at least **two** of
   - multiple options with non-obvious trade-offs;
   - explanatory prose or a diagram/chart materially aids the choice;
   - the decision is hard to reverse (architectural, schema, public contract).

When the boundary is NOT met:

- **Terminal `AskUserQuestion` stays correct** for quick gates — a yes/no, an
  approval the operator can grasp in one line, anything where the cost of a
  browser round-trip exceeds its value. Quick gates stay terminal even when
  `decision_surface == "canvas"`.
- **Autonomous-proceed stays correct** when there is no real fork — one sound
  path, or a reversible default you can revisit. Do not manufacture a decision
  to render.

This boundary keeps "any turning point" from degenerating into canvas spam (every
gate rendered) or under-fire (a context-heavy fork buried in a one-liner).

## Inputs

| Input | Required | Description |
|-------|----------|-------------|
| `decision` | Yes | The fork: a prompt plus `choice` options or an `approve` confirmation |
| `canvas` name | Yes | The canvas the decision renders on (open it first) |
| `SESSION_PREFERENCES.decision_surface` | No | `terminal` (default) or `canvas`; routes the surface |

## Outputs

| Output | Type | Description |
|--------|------|-------------|
| Operator answer | Inline | The submitted value (and optional `free_text`) as plain-text data |
| Rendered decision page | Canvas | The live `<choice>`/`<approve>` control on the canvas |

## Mechanics

Main context only. The loop:

1. **Declare** — `canvas_decision_open(canvas, decision_id, kind, prompt,
   options?)`. `kind` is `choice` (with `options`) or `approve`. Returns an
   `await_token` — **KEEP IT**; you pass it back in step 4. It is the robust
   binding identity (bearer-style: only you hold it).
2. **Render** — `canvas_write` a page body containing the live `<choice id=...>`
   or `<approve id=...>` control whose `id` matches `decision_id`. The control is
   live because the decision is declared.
3. **Surface the URL** — give the operator the canvas URL so they can open the
   tab and submit.
4. **Await** — loop `canvas_decision_await(canvas, decision_id, timeout_s=15,
   await_token=<token from step 1>)` until the result is `submitted`/`consumed`.
   PASS THE `await_token`: under `stateless_http=True` the daemon assigns a fresh
   `ctx.session_id` to every request, so session-id-only binding spuriously fails
   with `binding_mismatch`. The token is stable across requests and is the
   PRIMARY binding. Loop with the SAME token; each call bounded long-polls,
   re-issue on timeout until the operator answers (or you choose to cancel).
5. **Proceed** — act on the returned value as plain-text data.

<FORBIDDEN>
- Awaiting a decision from a subagent (no operator; deadlocks to timeout).
- Echoing the submitted `free_text` verbatim into `canvas_write` (DA-10 — it
  re-enters the rehype-raw render path).
- Rendering a canvas decision for a quick yes/no gate, or for a non-fork you
  should just proceed through.
- Treating a submitted value as anything but plain-text data.
</FORBIDDEN>

## Decision Page Anatomy

**Doctrine: don't ship a bare control.** A canvas decision that is just a
`<choice>`/`<approve>` with a one-line prompt is "a dressed-up AskUserQuestion" —
if that is all the context needed, use terminal `AskUserQuestion` instead (the
boundary in "When to Use"). A canvas decision EARNS its surface by carrying
context a terminal cannot.

**Anatomy (top-to-bottom order):**

1. **Context summary** — a `<callout type="note">` framing the decision: what is
   being decided, why now, what is at stake.
2. **Diagram when architecture is involved** — a `<diagram>` (mermaid) when the
   fork is structural (data flow, component boundaries, sequence). Skip when the
   decision is non-spatial.
3. **Per-option detail** — `<tabs>` (one tab per option) OR a `<collapsible>` per
   option, each with: the option's approach, its trade-offs, and (when useful) a
   `<chart>` or table. Use `<collapsible open>` for the recommended option,
   collapsed for alternatives, so the page is scannable but complete.
4. **The control LAST** — `<choice>`/`<approve>` at the bottom, after the operator
   has the context to decide. Never lead with the control.

**Author distinct `<collapsible>` summaries (F2/RT-2).** Give every `<collapsible>`
a unique, descriptive `summary` string rather than relying on the default
`"Details"`. This is not just labeling — it makes the operator's open/closed state
survive `canvas_write` reliably (the state cache keys on the summary). Multiple
collapsibles all defaulting to `"Details"` can swap their remembered open-state if
the page is reordered (the accepted multi-instance limitation). Distinct summaries
make that footgun structurally impossible.

**Use the self-closing control form (not children-content).** A `<choice>` or
`<approve>` is an attribute-only, self-closing control. Write it as
`<choice id="..." prompt="..." options='[...]' />` (or `<approve id="..." prompt="..." />`).
Do NOT compose it as a children-content element — `<choice id="...">...</choice>`
renders an INERT control (no radio group, nothing to submit). The `id` MUST match
the declared `decision_id`, and for `<choice>` the option `value`s in `options='[...]'`
MUST match the options declared in `canvas_decision_open`.

**Blank line after every opening shortcode tag and before every closing tag
(GATE-2).** Always put a blank line between a shortcode's opening tag and its body,
and between the body and the closing tag:

```
<collapsible open summary="Recommended: approach C">

**What:** the rationale prose, which now parses as bold.

- trade-off one
- trade-off two

</collapsible>
```

NOT (the hazard):

```
<collapsible open summary="Recommended: approach C">
**What:** swallowed into a raw HTML block — renders as literal asterisks
</collapsible>
```

**Why:** CommonMark treats a line that opens with a block-level HTML tag as the
start of a *raw HTML block* — content on the line *immediately after* the opening
tag is emitted verbatim with markdown parsing suppressed (the operator saw literal
markdown markers and unbroken text at the live gate). The blank line ends the raw
HTML block so the body is parsed as markdown. The renderer-side re-parse fix
recovers this even when the blank line is missing (suspenders); the blank-line
discipline is the belt that keeps old bundles correct and the markdown clean.
Apply to `<collapsible>`, `<callout>`, `<tabs>/<tab>`, and any children-content
shortcode.

**Never write a literal shortcode tag inside a shortcode body (GATE-3).** Do NOT
write a literal `<tag ...>` — not even inside an inline code span (backticks) or
fenced code block — within the body of another shortcode. `rehype-raw` re-parses
the body's raw HTML and consumes the literal `<tag ...>` as a REAL tag, NOT as
code-span text. At the live gate this clipped the operator's page at the opening
backtick and spawned a phantom nested widget that swallowed several following
sections. To name a shortcode in prose inside a body, use the bare prose name
(`collapsible`, `the collapsible shortcode`) or HTML-escaped entities
(`&lt;collapsible&gt;`) — never the raw angle-bracket form. (This is a
body-of-a-shortcode constraint; at the TOP level of a canvas, a code span
containing a shortcode tag is fine because it is not being re-parsed by
`rehype-raw` as a nested body.)

## Worked Examples

### 1. Design approval — FULL (this IS a dogfood page)

A complete, copy-pasteable `canvas_write` body: context callout → architecture
diagram → per-option detail with the recommended option signposted → control LAST.
Note the blank line after every opening tag and before every closing tag (GATE-2),
the distinct authored summaries (F2/RT-2), the GFM trade-off table inside a
collapsible, and the self-closing `<approve>` control whose `id` matches the
declared `decision_id`.

````
<callout type="note">

**Decision:** how the canvas prose baseline is styled. Trade-off: a Tailwind
typography plugin gives vertical rhythm for free but its tokens may not match our
design tokens exactly.

</callout>

<diagram>

graph LR
  md[Markdown] --> plugin[Typography plugin]
  plugin --> overrides[Targeted token overrides]
  overrides --> page[Rendered page]

</diagram>

<collapsible open summary="Recommended: approach C">

**What:** plugin baseline + targeted overrides. Rhythm for free; tokens exact.

| Approach | Verdict |
| --- | --- |
| A. Plugin only | Token gaps |
| C. Both | Selected |

</collapsible>

<collapsible summary="Rejected: approach A — plugin only">

**Why it loses:** inherited token values drift from our design tokens; we would
chase visual mismatches with no override seam.

</collapsible>

<collapsible summary="Rejected: approach B — hand-rolled rhythm">

**Why it loses:** re-implements what the plugin already gives us, and the rhythm
math has to be maintained by hand forever.

</collapsible>

<approve id="design-2.3" prompt="Approve this design?" />
````

### 2. Scope fork — SKETCH

Anatomy outline (not written out in full):

- **Context callout** — the scope question and why it matters now.
- **`<tabs>`**, one tab per scope option, each listing what is IN / OUT plus an
  effort note.
- **Control LAST** — `<choice id="scope-fork" prompt="Pick the scope" options='[{"value":"minimal","label":"Minimal"},{"value":"full","label":"Full"}]' />`,
  self-closing, with `value`s matching the declared options.

### 3. Plan approval — SKETCH

Anatomy outline:

- **Context callout** — the plan summary and the headline risk.
- **Task list** — GFM `- [x]` / `- [ ]` of the plan steps, showing done/pending
  (renders as status icons, not interactive checkboxes).
- **`<collapsible summary="Full step detail">`** — the ordered plan in full.
- **Control LAST** — `<approve id="plan-3.3" prompt="Approve this plan?" />`.

Each example demonstrates control-last, context-first, the `<collapsible>` and
task-list primitives, and the anatomy order. Example 1 is intentionally fuller than
2/3 — it is the dogfood page; the sketches teach the pattern without bloat.

## Known Limitation

No GC/reaper exists for abandoned pending decisions: if a decision is declared
but never submitted/consumed, its inbox JSON and `meta.decision` persist (bounded
by operator usage, not unbounded). This is a documented follow-up, not shipped in
this branch. Cancel an abandoned decision (`canvas_decision_*` cancel path) when
you know it will not be answered.

## Self-Check

Before completing a canvas decision:
- [ ] I am the session main context (not a subagent).
- [ ] The ALL-of when-to-use boundary is met (surface routed AND context-heavy).
- [ ] A thin/quick gate went to terminal `AskUserQuestion` instead.
- [ ] A non-fork proceeded autonomously instead of rendering a decision.
- [ ] I awaited the submission, not just rendered an inert control.
- [ ] The submitted value/`free_text` was handled as plain-text data, never
      round-tripped into `canvas_write`.
- [ ] Context callout present (what/why/stakes)?
- [ ] Diagram included if the fork is architectural?
- [ ] Each option has rationale + trade-offs (not just a label)?
- [ ] Recommended option signposted (e.g. `<collapsible open>` or first tab)?
- [ ] Each `<collapsible>` has a distinct authored `summary` (not bare `"Details"`)?
- [ ] Control is LAST, self-closing (`<choice ... />` / `<approve ... />`, NOT a
      children-content `<choice>...</choice>`), and `id` matches the declared
      `decision_id` (and `<choice>` option `value`s match the declared options)?
- [ ] No bare control: would this lose nothing as a terminal `AskUserQuestion`? If
      so, use terminal instead.
- [ ] Blank line after every opening shortcode tag and before every closing tag
      (GATE-2 — body parses as markdown, not raw HTML)?
- [ ] No literal `<tag ...>` written inside any shortcode body — not even in a code
      span (GATE-3 — `rehype-raw` consumes it as a real tag; use prose names or
      `&lt;...&gt;`)?

If ANY unchecked: STOP and fix before proceeding.
``````````

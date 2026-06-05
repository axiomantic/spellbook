---
name: canvas-decision
description: |
  Use when an operator decision belongs on a browser page rather than a terminal
  prompt. Triggers: "present a decision in the browser", "ask via a canvas page",
  "interactive decision page", "let me decide in the browser", "render the choice
  visually". Also invoked by develop when the decision-surface preference is
  `canvas` (feature-config Question 8). NOT for: quick yes/no with no context
  (use terminal `AskUserQuestion`), read-only presentation (use `canvas`), or
  subagent-internal choices with no operator (decide in-context).
version: 1.0.0
depends_on: [canvas]
---

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
   `await_token`; the binding stays in the daemon.
2. **Render** — `canvas_write` a page body containing the live `<choice id=...>`
   or `<approve id=...>` control whose `id` matches `decision_id`. The control is
   live because the decision is declared.
3. **Surface the URL** — give the operator the canvas URL so they can open the
   tab and submit.
4. **Await** — loop `canvas_decision_await(canvas, decision_id, timeout_s=15)`
   until the result is `submitted`/`consumed`. Each call bounded long-polls;
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

If ANY unchecked: STOP and fix before proceeding.

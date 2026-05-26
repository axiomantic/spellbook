# /canvas
## Command Content

``````````markdown
# Canvas

Usage: `/canvas <subcommand> [args]`

`/canvas` is a thin slash-command shell over the canvas MCP tools. The
heavy lifting — guidance on when to use a canvas, the shortcode grammar,
and the threat model — lives in `skills/canvas/SKILL.md`. Read that skill
when the operator asks you to put substantive content on a canvas.

<ROLE>Presentation-surface router. You connect operator intent to the right canvas MCP tool, and you are the last line of defense against rendering untrusted markup under the admin's authenticated origin.</ROLE>

## Invariant Principles

1. **Route, do not improvise.** Each subcommand maps to exactly one MCP tool
   (`open`->`canvas_open`, `close`->`canvas_close`, `list`->`canvas_list`).
   `write` is deliberately not a slash command — agents call `canvas_write`
   directly. Never substitute one tool for another or invent a subcommand.
2. **Unknown subcommand means ask, not guess.** With no subcommand or an
   unrecognized one, print usage and stop. Do not infer intent from a partial
   or misspelled command.
3. **Trusted-local-agent content only.** Never write unsanitized external
   content (transcripts, fetched pages, unvetted MCP output) to a canvas. Raw
   HTML executes under the admin auth context; a `<script>` tag is a
   session-takeover primitive. Defer to `skills/canvas/SKILL.md` for the full
   forbidden-payload list.
4. **Surface the URL after `open`.** The whole point of opening is to give the
   operator a browser tab. Always echo the returned `url`; an open whose URL
   is never surfaced is a no-op to the operator.

<analysis>
Before acting, parse the subcommand and validate it against the routing table.
Confirm the operator actually wants a canvas (browser presentation) rather
than terminal output or a persisted doc. For `open`, capture the `url` the MCP
tool returns so it can be surfaced. Substantive content writes are out of
band: this command never carries the markdown body — that flows through
`canvas_write` after reading the skill's grammar and threat model.
</analysis>

<reflection>
Before reporting the turn done: Did I route to the correct MCP tool? For an
unknown subcommand, did I print usage instead of guessing? For `open`, did I
surface the URL? Did I avoid passing any external/untrusted content toward a
canvas?
</reflection>

Subcommands:

- `open <name>` — open or attach to a named canvas. Returns the URL.
- `close <name>` — mark a canvas as closed (files are not deleted).
- `list` — list all known canvases (open and closed).
- `write` is intentionally NOT a slash command. Agents call `canvas_write`
  directly via MCP, passing the full markdown body each time.

## Routing

| Input | Action |
|---|---|
| `/canvas open <name>` | Invoke MCP tool `canvas_open(name=<name>)`. Surface the returned `url` to the operator. |
| `/canvas close <name>` | Invoke MCP tool `canvas_close(name=<name>)`. |
| `/canvas list` | Invoke MCP tool `canvas_list()` and render the result as a table. |

If the user passes no subcommand or an unknown one, print this usage and
exit. Do not guess at intent; ask the operator which subcommand they meant.

## Threat Model

Canvas content is **trusted-local-agent** only. Agents MUST NOT write
unsanitized external content (chat transcripts, fetched web pages,
untrusted MCP tool outputs) into a canvas. Raw HTML in canvas markdown
executes under the admin's auth context — a `<script>` tag is a
session-takeover primitive. See `skills/canvas/SKILL.md` for the full
threat model and the list of forbidden direct payloads.

## Examples

```
/canvas open plan-x
```
Opens (or re-attaches to) `plan-x`. Surfaces
`http://127.0.0.1:8765/admin/canvas/plan-x` so the operator can open it in
a browser tab. Subsequent agent-side `canvas_write("plan-x", ...)` calls
update the page live.

```
/canvas list
```
Prints a table of every canvas under the configured root, including
closed ones, with `last_updated` timestamps.

```
/canvas close plan-x
```
Marks `plan-x` closed in its `meta.json`. Files remain on disk; further
`canvas_write` calls return `{"code": "closed"}`. Re-open with
`/canvas open plan-x`.
``````````

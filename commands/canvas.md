---
description: Open, write to, list, or close a canvas — a live-updating presentation surface served at /admin/canvas/<name>.
---

# /canvas <subcommand> [args]

`/canvas` is a thin slash-command shell over the canvas MCP tools. The
heavy lifting — guidance on when to use a canvas, the shortcode grammar,
and the threat model — lives in `skills/canvas/SKILL.md`. Read that skill
when the operator asks you to put substantive content on a canvas.

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

---
name: session-pull
description: Pull chat history and hidden context out of Claude Code / Claude Desktop (local), OpenCode, AionUi, and Antigravity sessions, and render a handoff document another coding assistant can pick up exactly where the session left off. Use when the user asks to export a session, hand off work between tools, resume a session in a different assistant, extract conversation history, or transfer context from one coding agent to another.
---

# Session Pull

Extract a coding-agent session — chat history, tool activity, todos, compaction
summaries, file state — from its native store and re-emit it in a portable
format the next assistant can consume directly.

<ROLE>
Context courier. Your job is lossless *enough*: the next agent must be able to
continue the work without re-deriving what was already decided, tried, or
broken. When in doubt, include more context and say what was truncated.
</ROLE>

## Invariant Principles

1. **Read-only, always.** Never open a live store in place; the script
   snapshot-copies SQLite databases and never writes to any source directory.
2. **Honesty over completeness.** Unknown roles, unmappable records, and
   reverse-engineered extractions are labeled as such (warnings, `role: null`)
   rather than guessed.
3. **Compaction-anchored reconstruction.** The default `compact` mode emits
   the latest compaction summary verbatim plus every event after its boundary
   — that is the true current position of the session, not the whole history.
4. **The envelope is the contract.** Every mode except `handoff` emits exactly
   one JSON object with `schema_version`, `source`, `session`, `summary`,
   `events`, `warnings`. Never invent ad-hoc output shapes.
5. **Privacy is the operator's call, not yours.** Transcripts contain
   everything typed plus tool output. Suggest `--redact` for anything that
   will leave the machine; never silently widen distribution.

## CLI

Single entry point, stdlib-only (no runtime deps), Python 3.11+:

```
skills/session-pull/session_pull.py <subcommand> [flags]
```

| Command | Purpose |
|---------|---------|
| `sources` | Which stores are present on this machine |
| `list --source S [--cwd DIR] [--since ISO] [--lookback-hours N] [--limit N]` | Discover sessions (`--source all` for a union) |
| `pull --source S --id ID [--mode compact\|full\|handoff] [--budget-chars N] [--out PATH] [--redact] [--include-thinking]` | Export one session |
| `debug-dump --source antigravity --id ID` | Schema archaeology for the protobuf blobs |

Modes:

- `compact` (default): latest compaction summary verbatim + all post-boundary
  events + todos + file state. Equals `full` when the session has no
  compaction point.
- `full`: every reconstructed event.
- `handoff`: Markdown document for direct consumption by the next assistant
  (Position → Pending work → Recent transcript, newest first, char-budgeted).

`--out PATH` writes 0600 and refuses to overwrite without `--force`.

## Workflow

<analysis>
Determine, before touching the script: which assistant produced the session
(`sources`), which session (`list`, filtered to the repo with `--cwd`), and
where the output must land (stdout pipe vs `--out` file). If the user did not
name the session, show them the `list` candidates and let them pick — never
guess between similarly-titled sessions.
</analysis>

<reflection>
Before emitting, verify: did the source store actually exist (`sources`)? Are
`warnings` empty enough to trust the output? In compact mode, is `summary`
present or was there no compaction anchor (in which case the export is the
whole transcript)? Did events survive at all for reverse-engineered sources?
</reflection>

<step number="1">
Run `sources`. Report which of claude_code / opencode / aionui / antigravity
are available. claude_code covers Claude Code CLI **and** Claude Code Desktop
local sessions (same `~/.claude` store); Claude Desktop *remote* (claude.ai)
chats are out of scope by design.
</step>

<step number="2">
Run `list` for the relevant source, filtered with `--cwd` when the session
belongs to a repo. Present candidates (title, last activity, source, whether
it appears to be running right now) and confirm which one to pull.
</step>

<step number="3">
Run `pull --mode compact`. Summarize for the user: how many events, whether a
compaction anchor was used (and its boundary), todos found, truncation
warnings. If the user needs the complete record, rerun with `--mode full`.
</step>

<step number="4">
Deliver the context:
- Piping into another assistant: feed the JSON envelope (or handoff markdown)
  as context in the new conversation, then state the task to continue.
- Claude Code target: if the session itself should be *resumed natively*,
  `claude --resume <session-id>` is available; the handoff doc is for
  cross-tool transfers.
- Aion target: hand the handoff doc to the target conversation, optionally
  via the agent2agent / session-message machinery for cross-session delivery.
</step>

<step number="5" optional="true">
If the user asks for Antigravity detail the extractor missed, run `debug-dump`
and inspect the carved strings; refine classifier constants only with that
evidence, and record what you learned in the script's calibration docstrings.
</step>

## FORBIDDEN

- NEVER write to any source store, config, or state directory. Export only.
- NEVER pull and share a session the user did not ask about; transcripts are
  sensitive by default.
- NEVER claim an extraction is complete when `warnings` say otherwise — say
  what was skipped and why.
- NEVER pipe a session into another assistant without the user knowing where
  its content will land.

## Output Format

The canonical JSON envelope (`compact`/`full`) normalizes across sources:

| event type | meaning |
|------------|---------|
| `message` | chat text (`role`: user/assistant/unknown) |
| `thinking` | model reasoning (only with `--include-thinking`) |
| `tool_call` | tool name + input |
| `tool_result` | tool output |
| `compaction` | compaction summary record (`meta.anchor: true`) |
| `file_state` | snapshot/file metadata |
| `meta` | tips, agent notices, unmappable-but-kept records |

`hidden: true` marks UI-hidden rows (AionUi `messages.hidden`); `sidechain:
true` marks subagent traffic (Claude Code). Source quirks that survived
verification are documented per-parser in the script docstrings — read them
before changing extraction logic.

## Known limits

- **Antigravity**: payloads are protobuf with no public schema; extraction is
  heuristic string carving calibrated on live dbs (2026-09-10). Roles, tool
  names (`manage_task` fragments to `anag`/`task_description`), and tool
  *results* are partially recoverable; unknown shapes degrade to meta events.
- **AionUi**: text rows carry no user/assistant marker — roles are left unset.
- **OpenCode**: current SQLite schema only; legacy `storage/` JSON is
  deliberately unsupported.
- **Claude Desktop remote** (claude.ai chats): out of scope by design.
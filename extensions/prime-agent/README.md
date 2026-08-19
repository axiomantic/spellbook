# Spellbook Rules Extension (Prime Agent)

This directory ships the TypeScript extension the spellbook installer
deploys to Prime Agent to auto-inject the modular rule set into every
session's system prompt.

## Why an extension instead of `AGENTS.md`

Prime Agent has two adjacent mechanisms that look like they would solve this
problem but do not:

- **Auto-loading `AGENTS.md`** from `~/.prime/agent/` is real, but a user
  owns that file. Writing it would clobber their context.
- **`SYSTEM.md` / `APPEND_SYSTEM.md`** are documented in
  [`packages/coding-agent/docs/usage.md`](https://github.com/PrimeIntellect-ai/prime-agent/blob/main/packages/coding-agent/docs/usage.md)
  but the corresponding loaders are not implemented in
  `packages/coding-agent/src/core/system-prompt.ts` on `main` as of
  this writing. The docs describe the intended behavior; the code
  does not yet execute it.

The extension system in
[`packages/coding-agent/src/core/extensions`](https://github.com/PrimeIntellect-ai/prime-agent/tree/main/packages/coding-agent/src/core)
is implemented. Prime Agent auto-discovers `~/.prime/agent/extensions/*.ts`
at session start, hooks `session_start` to pre-load data, and exposes
`before_agent_start` for prompt mutation. This extension uses that
mechanism to deliver every selected rule module as content, not as a list
to be dynamically fetched -- the rules are part of the prompt, not skills
the agent has to remember to load.

## Files

- `spellbook-rules.ts` -- the extension itself. ~230 lines. No runtime
  dependencies beyond Prime Agent's built-in Node APIs (`node:fs`,
  `node:path`).

## What the installer does

The spellbook installer (`installer/platforms/prime_agent.py`) places two
things in `~/.prime/agent/` on every install or upgrade:

1. **Rule modules** as one symlink each, at
   `~/.prime/agent/rules/<XX>-spellbook-<id>.md`. Selection honors
   `rules.module.<id>` config keys (mandatory modules always; preference
   modules gated on the user's recorded `true` / `false`). Declining a
   preference removes its symlink on the next install.
2. **This extension file** at
   `~/.prime/agent/extensions/spellbook-rules.ts`, as a symlink into the
   spellbook checkout so upgrades flow through.

Neither artifact touches `~/.prime/agent/AGENTS.md`. The user's file is
untouched.

## What the extension does at session start

1. `session_start`: reads every `XX-spellbook-*.md` in
   `$PRIME_AGENT_CONFIG_DIR/rules/` (default `~/.prime/agent/rules/`).
   Parses YAML frontmatter, captures the rule id / name / body, and
   sorts by `(prefix, id)` to match the canonical delivery order.
2. `before_agent_start`: appends a `# Spellbook Rules` section to the
   system prompt containing every rule body in order. A small
   `## <id> -- <name>` header precedes each rule.
3. **Safety cap**: if the total body size exceeds 80 KiB, the extension
   falls back to a short listing and instructs the agent to use
   `ipython` to read whichever rule it needs. The shipped ruleset is
   ~60 KiB today; the cap is a safety belt, not a normal path.

## Configuration

The extension reads one environment variable:

| Variable | Default | Purpose |
|----------|---------|---------|
| `PRIME_AGENT_CONFIG_DIR` | `~/.prime/agent/` | Where Prime Agent stores its config. Honors the same env var Prime Agent itself uses. |

Rule selection is driven by spellbook's normal config layer
(`rules.module.<id>`), not by anything inside this extension.

## Versioning

This file is shipped from the spellbook repository and symlinked into
Prime Agent's extensions directory. It is updated alongside rule module
changes. If a user's spellbook checkout moves, the symlink target moves
with it on the next install.

## Failure modes

- **Rules directory missing** -- `loadedRules` is empty, the extension
  is a no-op. The user's install simply has no rules.
- **Rules directory unreadable** -- `loadError` is set; the extension
  injects a short error banner into the prompt and asks the user to
  rerun the installer or `/reload`.
- **User-owned rule file present** -- filtered out by filename pattern
  (`XX-spellbook-<id>.md`); only symlinks the installer created are
  loaded.
- **Cap exceeded** -- listing injected instead of bodies; agent
  fetches on demand.

## Testing

`tests/integration/test_prime_agent_rules_install.py` covers the installer
side: selection honored, symlinks created, deselection removes stale
symlinks, extension file present, idempotent reinstall.

The TypeScript extension itself is not unit-tested in spellbook's Python
test suite (it runs inside Prime Agent, not the installer). Its behavior
is simple enough that the value of a Node-side test suite is low; the
filename regex, the frontmatter parser, and the cap-fallback path are
all small enough to read in a code review.

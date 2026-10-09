# Spellbook Development

## Quick Start

```bash
# Install dependencies
uv pip install -e ".[dev,test]"

# Run tests (targeted)
uv run pytest tests/test_specific_file.py -x

# Run fast tests (default - skips docker, integration, slow, external)
uv run pytest tests/ -x

# Run ALL tests including slow/integration (as CI does)
uv run pytest tests/ -x --override-ini="addopts=" -m "not docker"

# Run linting
uv run ruff check .

# Generate documentation (pre-commit only checks freshness; run this yourself)
uv run scripts/generate_docs.py
```

## Session Start: Pre-release Check

On session start in this project, check if there's a GitHub pre-release newer than the latest full release:

```bash
gh release list --limit 5 --repo axiomantic/spellbook
```

If a pre-release exists that is newer than the last actual release, ask: "There's a pre-release (`vX.Y.Z`) ready. Want to promote it to a full release?"

## Key Conventions

- **AGENTS.md** (this file) is for working **on the spellbook repo itself**. Only update it when changing the development workflow for this specific project (build commands, test conventions, architecture notes). It is NOT installed anywhere.
- **`rules/*.md`** are the **global user-facing rule modules** that the spellbook installer ships. Directory-capable platforms receive one symlink per selected module in the platform's rules directory (`~/.claude/rules/` for Claude Code); flat platforms receive a generated concatenation at their real instruction path. Each module carries YAML frontmatter (`id`, `class`, `default`, `benefit`) and holds global directives, instructions, and behavioral rules that apply to ALL projects. This is where cross-project instructions belong.
  - **Editing an existing `rules/*.md` file takes effect immediately** on directory-capable platforms — the installed file is a symlink to the source, so no reinstall step is needed.
  - **Adding a NEW file under `rules/`** does need a step: run `uv run install.py` to create its symlink (or regenerate the flat-platform concatenation) before the new module reaches any installed platform. `MANIFEST.md` does not track `rules/*.md` — it only registers skills, commands, and agents — so there is no manifest entry to add for a new rule module, just the install step.
- **Skills** go in `skills/<name>/SKILL.md` with YAML frontmatter
- **Commands** go in `commands/<name>.md` with YAML frontmatter
- **Hooks** go in `hooks/` and must be registered in `installer/components/hooks.py`
- **MCP tools** are defined in `spellbook/mcp/server.py` and `spellbook/mcp/tools/` modules

## Pre-commit Hooks

Only `doctoc` writes files. Every other hook reports and leaves the tree alone. If a hook fails:
- `doctoc` failures: Table of contents in markdown files needs regeneration. Usually fixes itself on re-commit.
- `Check generated documentation is current`: The `docs/` mirror is stale. The hook runs `scripts/generate_docs.py --check`, which names each stale page and writes nothing. Run `uv run scripts/generate_docs.py`, stage the regenerated files, and re-commit.
- `Check documentation completeness`: A skill/command has no generated doc page. Run `uv run scripts/generate_docs.py` and stage the result; the hook only checks.
- `Validate skill/command/agent/rule schemas`: Checks YAML frontmatter in skills, commands, agents, and rule modules. Fix the frontmatter.

Apart from `doctoc`, a failing hook does not repair anything for you. Run the command it names, stage the result (`git add`), and commit again.

## Switching Between Worktrees

To switch which worktree the installed spellbook runs from, always run `uv run install.py` from the target worktree. Don't just re-point `~/.local/spellbook/source` — the symlink shortcut updates the daemon's code path but misses per-platform MCP registrations (`claude mcp add`, OpenCode, Codex, Forge), so `/mcp` ends up missing `spellbook` or showing a stale tool list. `install.py` is idempotent; run it.

## Architecture Notes

- The MCP server (`spellbook/`) runs as a persistent daemon, not inline with the CLI
- The installer (`installer/`) handles multi-platform installation (Claude Code, OpenCode, Codex, Gemini CLI)
- Skills and commands are markdown files with YAML frontmatter, loaded dynamically by the AI assistant
- Hooks are bash/python scripts installed into the AI assistant's hook system
- The `extensions/` directory contains platform-specific plugins (e.g., OpenCode workflow state)

## Environment Variables

Operator-facing behavioral switches. Not an inventory of every `SPELLBOOK_*`
variable the code reads — path resolution (`SPELLBOOK_DIR`,
`SPELLBOOK_CONFIG_DIR`) and MCP transport settings are covered where they are
used.

| Variable | Effect |
|----------|--------|
| `SPELLBOOK_GIT_PUSH_AUTONOMOUS` | Operator signal that a protected-branch push confirmation may be skipped in high-trust automation. **No code reads it** — protected-branch protection is behavioural, honored by the agent, not enforced by any hook or config. See `rules/50-git-safety.md`. |
| `CLAUDE_CODE_STOP_HOOK_BLOCK_CAP` | Harness variable, not spellbook's, but the installer WRITES it into `settings.json`'s `env` block as `"0"`. Claude Code stops honoring a `Stop` hook's block decision after this many consecutive blocks and ends the turn regardless; `0` disables that cap. Autonomous mode's `Stop` hook blocks by design and bounds itself with its own rolling-window valve (`spellbook/core/autonomous.py`), so the harness cap would only cut enforcement short at an arbitrary count. **A value you set yourself is left alone**, and the installer says so in its output for that run — but autonomous mode then stops being enforced after that many blocks. Written by `installer/components/hooks.py`. |

---

# Spellbook Development Guide

<ROLE>
Spellbook Contributor. Your reputation depends on shipping changes that work across all supported platforms without breaking user installations. Every careless commit risks corrupting thousands of developer environments.
</ROLE>

Development instructions for spellbook codebase. User-facing rule modules: `rules/*.md`.

## Supported Platforms

Claude Code is the **primary** supported platform with full support. The others have basic support; some MCP tools, hooks, and skills are Claude Code-specific but can usually be implemented for other platforms. Contributions to extend coverage are welcome.

| Platform | Support Level | GitHub | Config Location | MCP Transport |
|----------|---------------|--------|-----------------|---------------|
| Claude Code | Primary, full | [anthropics/claude-code](https://github.com/anthropics/claude-code) | `~/.claude/` | HTTP daemon |
| Antigravity | Basic | [google-deepmind/antigravity](https://github.com/google-deepmind/antigravity) | `~/.gemini/antigravity` | HTTP daemon |
| OpenCode | Basic | [anomalyco/opencode](https://github.com/anomalyco/opencode) | `~/.config/opencode/` | HTTP daemon |
| Codex | Basic | [openai/codex](https://github.com/openai/codex) | `~/.codex/` | HTTP daemon |
| Gemini CLI | Basic | [google/gemini-cli](https://github.com/google/gemini-cli) | `~/.gemini/` | HTTP daemon |

## Invariant Principles

1. **Library vs Repo distinction**: Library items (`skills/`, `commands/`) ship to users and require docs. Repo items (`.claude/skills/`) are internal only.
2. **Documentation follows code**: Library changes require CHANGELOG, README, and docs updates. The `check-docs-completeness` pre-commit hook enforces the README and `docs/` halves. **Nothing enforces the CHANGELOG entry** — no hook and no CI job reads it, so a library change ships with a stale CHANGELOG unless you update it yourself.
3. **Test before commit**: `uv run pytest tests/` + `uv run install.py --dry-run` before any commit.

## Glossary

| Term | Location | Ships to Users | Docs Required |
|------|----------|----------------|---------------|
| Library skill | `skills/*/SKILL.md` | Yes | CHANGELOG, README, docs |
| Library command | `commands/*.md` | Yes | CHANGELOG, README, docs |
| Repo skill | `.claude/skills/*/SKILL.md` | No | None |
| Rule module | `rules/*.md` | Yes | CHANGELOG, docs |

## Structure

```
spellbook/
├── .claude/skills/      # Repo skills (internal, NOT shipped)
├── skills/              # Library skills (shipped)
├── commands/            # Library commands (shipped)
├── agents/              # Agent definitions
├── installer/           # Multi-platform installer
│   ├── platforms/       # claude_code, opencode, codex, gemini
│   └── components/      # context_files, symlinks, mcp
├── spellbook/           # Python package (three-layer architecture)
│   ├── core/            # Config, DB, auth, models, compat
│   ├── memory/          # Memory storage and consolidation
│   ├── sessions/        # Session parsing, resume, compaction
│   ├── security/        # Security scanning, canary, trust
│   ├── notifications/   # OS notifications
│   ├── daemon/          # Server daemon management
│   ├── mcp/             # MCP server and tool definitions
│   │   └── tools/       # 13 tool modules (memory, security, etc.)
│   └── cli/             # CLI entry point and command groups
├── scripts/             # Build/maintenance
├── tests/               # Unit, integration
├── docs/                # Generated (skills/commands/agents) + manual
├── lib/                 # Shared JS
└── extensions/          # Platform manifests
```

## Key Files

| File | Purpose |
|------|---------|
| `rules/` | User-facing rule modules (installed per-module) |
| `extensions/gemini/` | Gemini extension (linked via `gemini extensions link`) |
| `install.py` | Installer entry |
| `spellbook/mcp/server.py` | MCP server entry point |
| `skills/dedupe/SKILL.md` | `/dedupe` — semantic instruction deduplication via LLM judgment loop (skill-only, no Python module) |

## Commands

```bash
uv run pytest tests/                              # Fast tests (heavy markers auto-skipped)
uv run pytest tests/unit/test_installer.py        # Specific file
uv run pytest --cov=installer --cov=spellbook tests/  # Coverage
uvx pre-commit install                            # Install hooks
python3 scripts/generate_docs.py                  # Gen docs
uv run install.py --dry-run                       # Test installer
```

## Pre-commit Hooks

Updates TOC in README.md. Checks -- does not write -- the `docs/` mirror of skills/commands/agents/rules.

**Hook failure**: Run the command the hook names, stage the result, retry commit.

## Shell/PowerShell Parity

<CRITICAL>
Any changes to shell scripts (`.sh` files in `hooks/`, `scripts/`, or elsewhere) MUST have corresponding changes to their Python cross-platform equivalents (`.py` wrappers in the same directory). If a shell script is added, modified, or deleted, the Python equivalent must be updated to match. This ensures Windows compatibility.
</CRITICAL>

## Adding Content

**Skills**: Create `skills/<name>/SKILL.md` with `name`/`description` frontmatter. Auto-discovered by MCP.

**Commands**: Create `commands/<name>.md` with `description` frontmatter. Hooks generate docs.

Regenerating the `docs/` mirror is a required, normal part of any change to `skills/`, `commands/`, `agents/`, or `rules/` — not scope creep. After such an edit, run `uv run scripts/generate_docs.py` and commit the regenerated `docs/` pages in the SAME commit as the source. The blocking `generate-docs` pre-commit hook checks freshness, so a commit that omits the regenerated pages fails; the extra generated files are the deterministic product of your source change, never an out-of-scope addition.

## Adding Config Options

<CRITICAL>
Any new user-facing config key MUST satisfy all three points below. Missing any point means a silently-unseen feature, a spammy re-prompt, or a config the user can only set by hand-editing `~/.config/spellbook/spellbook.json`.
</CRITICAL>

A "user-facing config" is anything that governs behavior the user cares about (feature flags, endpoints, modes, thresholds). Internal state and cached values are not user-facing.

### The three-point rule

1. **NEW users** are presented with the option during initial installation.
2. **EXISTING users** re-running install are presented with the option if (and only if) they have never answered it before — i.e., the key is unset in their config.
3. **Users who have already answered** (any explicit value, including `False`, `""`, `0`, `null`) are NOT re-prompted during subsequent installs.

### Required changes per new config key

| Where | What to add |
|-------|-------------|
| `spellbook/core/config.py` | `CONFIG_DEFAULTS` entry (matching key) — or, for a lazily-resolved key family, a `config_default_for()` resolver instead; see "Sanctioned exception" below |
| Installer (BOTH entry points — see below) | Prompt gated by `config_is_explicitly_set(key)` or equivalent `config_get(key) is None` check |
| Relevant wizard | Default surfaced to the user so they see what "don't change" means |

### Divergent install entry points

Spellbook has **two** install entry paths that must be kept in sync:

- **Root** `install.py` (the curl-pipe target, documented entry) — handles fresh installs and upgrades via `python3 install.py`.
- **CLI wrapper** `spellbook/cli/commands/install.py` — invoked by `spellbook install` after spellbook is on PATH.

Any new config prompt MUST be wired into both. A prompt that lives only in the CLI wrapper is invisible to users following the documented curl-pipe install, and vice versa. When touching either file, verify parity with the other.

### Idempotency pattern

```python
from spellbook.core.config import config_get, config_set

# Skip if user has already answered (any explicit value counts as "answered")
if config_get("my_feature_enabled") is not None:
    return

# Prompt, then persist exactly once
answer = input("Enable my-feature? [y/N]: ").strip().lower()
config_set("my_feature_enabled", answer in ("y", "yes"))
```

For keys using dotted names or stored in `profile_store`, use `config_is_explicitly_set(key)` from `spellbook.core.config` — it distinguishes "unset" from "set to default-valued literal".

### Non-tty fallbacks

Interactive prompts must be skipped cleanly when `sys.stdin.isatty()` is False (CI, piped installs). Default behavior in that path must match the "user said no / accept default" branch — NEVER silently write an opt-in flag to True.

### Re-configure flag

The installer accepts `--reconfigure`. When set, idempotency checks are bypassed so users can re-answer. Support this by gating your skip-check on `not getattr(args, "reconfigure", False)`.

## Size Limits and Splitting

<CRITICAL>
Pre-commit hooks enforce size limits to prevent truncation on platforms like OpenCode:
- **Skills**: 1900 lines max, 49KB max
- **Commands**: 1900 lines max, 49KB max

**Do NOT trim content to fit.** Split instead.
</CRITICAL>

### When a Skill Exceeds Limits

1. **Skill becomes orchestrator**: SKILL.md is a thin wrapper defining workflow phases, delegating to commands.
2. **Commands contain the logic**: Each phase or major section becomes a command (e.g., `advanced-code-review-plan.md`).
3. **Skill invokes commands**: Use `/command-name` syntax to delegate.

**Example structure:**

```
skills/advanced-code-review/
  SKILL.md              # ~200 lines - orchestrator only
commands/
  advanced-code-review-plan.md      # Phase 1 logic
  advanced-code-review-context.md   # Phase 2 logic
  advanced-code-review-review.md    # Phase 3 logic
  advanced-code-review-verify.md    # Phase 4 logic
  advanced-code-review-report.md    # Phase 5 logic
```

## Platform Installers

| Platform | File | Output |
|----------|------|--------|
| Claude Code | `installer/platforms/claude_code.py` | CLAUDE.md + MCP + skills/commands |
| Gemini CLI | `installer/platforms/gemini.py` | Native extension via link |
| OpenCode | `installer/platforms/opencode.py` | AGENTS.md + MCP |
| Codex | `installer/platforms/codex.py` | AGENTS.md + MCP |

## Config vs State

Spellbook stores persistent key-value data in two places. Pick the right one:

| File | Module | Purpose |
|------|--------|---------|
| `~/.config/spellbook/spellbook.json` | `spellbook.core.config` | User intent (what the user configured) |
| `~/.local/spellbook/state.json` | `spellbook.core.state` | Runtime state (what the code wrote for itself) |

**Config** keys are user-facing preferences and feature flags: `auto_update`,
`session_mode`, `notify_enabled`, `worker_llm_*`. They are surfaced by the
install wizards. Reading uses `config_get(key)`, writing uses
`config_set(key, value)`.

**State** keys are facts the code discovered or counters the code maintains:
`auto_update_branch` (auto-detected from git), `update_check_failures`
(watcher failure counter). They must never appear in wizards and must never
be presented to the user as a configurable option. Reading uses
`get_state(key)`, writing uses `set_state(key, value)`.

When you add a new persistent key, decide up front:
* Did the user choose this? -> config
* Did the code derive it? -> state

If the distinction is unclear, pick config and document the choice. Moving
later is a migration (see `spellbook.core.state.migrate_config_to_state`).

## Adding Config Options

<CRITICAL>
Every user-facing configuration option MUST follow the three-point rule:

1. **Prompted on fresh install.** If the user has never answered, offer a prompt. Either add the prompt to an existing wizard in `installer/wizards/` (`worker_llm.py`, `defaults.py`) or create a new shared wizard module there.
2. **Prompted on re-install IF the key is still unset.** The idempotency gate uses `spellbook.core.config.config_is_explicitly_set(key)`. If it returns False, ask again. If it returns True, skip.
3. **NOT re-prompted once the user has answered.** Any explicit value counts, including empty strings and False. Declining at the opener still writes a sentinel so the next run does not re-ask.

Wire every wizard into BOTH install entry paths:
- Root `install.py` (the curl-pipe entry point used by new users).
- `spellbook/cli/commands/install.py` (the `spellbook install` CLI command, including the `--reconfigure` branch).

A wizard that lives in only one entry path is a bug. `--reconfigure` must bypass the idempotency gate so users can revisit earlier answers.

Register every new key in `spellbook/core/config.py::CONFIG_DEFAULTS` (runtime default).

**Sanctioned exception — lazily-resolved default families.** A key whose default
cannot be computed without doing real work at import time MUST NOT go in
`CONFIG_DEFAULTS`. `spellbook/core/config.py` is imported by the MCP server and
the hooks, so an import-time computation is paid by every consumer whether or not
it ever reads that key. Register such families through
`config_default_for()` instead, backed by a memoized resolver.

The one family using this today is `rules.module.*`
(`rule_module_config_defaults()`): resolving it means globbing and parsing every
file in `rules/`. `config_default_for()` is the single read path, so callers see
no difference; only the timing moves. A test pins the keys OUT of
`CONFIG_DEFAULTS` so the import-time cost cannot come back by accident.

Tests must cover each new key: fresh-install prompt fires, re-install skip,
`--reconfigure` bypass, non-tty noop, and presence in both install entry paths.
The idempotency-gate helpers are covered in
`tests/test_installer_config_helpers.py`; the wizard behaviours (prompting,
non-tty safety, `--reconfigure`, and the `CONFIG_DEFAULTS` exclusion for the
lazily-resolved family) are covered in `tests/installer/test_rule_modules.py`.
</CRITICAL>

## Testing

Tests marked `docker`, `integration`, `slow`, and `external` are **skipped by default** via `addopts` in `pyproject.toml`. CI overrides this with `--override-ini="addopts="` to run them.

### Sandbox & Security (Tripwire)

This project uses **pytest-tripwire** (imported as `tripwire`) to strictly enforce a testing sandbox. By default, any attempt to spawn a subprocess or access the network will result in an error (`guard = "error"` in `pyproject.toml`).

**How to permit specific actions:**
- **Subprocesses**: Use the `@pytest.mark.allow("subprocess")` marker on your test function.
- **Network**: Use `@pytest.mark.allow("network")`.

Example:
```python
@pytest.mark.allow("subprocess")
def test_cli_invocation():
    # This test is now allowed to use subprocess.run/Popen
    ...
```

**Local development:** just run `uv run pytest tests/` -- heavy tests are excluded automatically.

**To opt in to specific markers locally:**
```bash
# Run integration tests too
uv run pytest tests/ -m "not docker and not slow and not external" --override-ini="addopts="

# Run everything except docker
uv run pytest tests/ -m "not docker" --override-ini="addopts="
```

**Docker tests** only run in CI via `integration-test.yml` in a dedicated container. Never run locally.

### Testing with Tripwire

<CRITICAL>
**Tripwire is the ONLY acceptable mocking framework in this project.** This rule is absolute.

**Forbidden:**
- `unittest.mock` in any form — `patch()`, `patch.object()`, `MagicMock`, `AsyncMock`, `Mock`, `mock_open`, `PropertyMock`, `create_autospec`, etc.
- `pytest-mock` / `mocker` fixture
- `monkeypatch.setattr()`, `monkeypatch.setitem()`, `monkeypatch.delattr()`, `monkeypatch.delitem()` for mocking module attributes, class methods, or functions
- Hand-rolled mock objects or stub classes that exist only to stand in for real dependencies
- `@pytest.fixture` that returns a fake replacement for a real dependency

**Allowed uses of `monkeypatch`** (pytest-builtin, not a mocking framework):
- `monkeypatch.setenv()` / `monkeypatch.delenv()` for environment variables
- `monkeypatch.chdir()` for working directory
- `monkeypatch.syspath_prepend()` for sys.path

That's it. Any other mocking need — function replacement, method stubbing, object patching, HTTP mocking, subprocess mocking, database mocking — MUST use tripwire. No exceptions. If tripwire can't express what you need, that is a signal to refactor the code under test, not to reach for `unittest.mock`.

PR reviewers (including automated ones) that suggest "use tripwire OR monkeypatch" are wrong. The correct phrasing is "use tripwire; monkeypatch is restricted to environment / cwd / sys.path only."
</CRITICAL>

#### Why Tripwire Instead of unittest.mock

Tripwire enforces three guarantees unittest.mock does not:
1. **Every call must be pre-authorized** - unmocked calls raise `UnmockedInteractionError`
2. **Every interaction must be asserted** - unasserted calls raise `UnassertedInteractionsError` at teardown
3. **Every mock must fire** - unused mocks raise `UnusedMocksError`

#### Quick Reference

```python
import tripwire

def test_example():
    # Setup mocks
    config = tripwire.mock("myapp.config:get_setting")
    config.returns("value")

    # Execute in sandbox
    with tripwire:
        result = my_function()

    # Assert interactions (REQUIRED - tripwire enforces this)
    config.assert_call(args=("key",), kwargs={})
```

#### The assertion must be meaningful

<CRITICAL>
Tripwire enforces that you assert; it does not enforce that the assertion says anything.
Assert the REAL values. A wildcard matcher (`AnyThing`, `mock.ANY`, or any equivalent)
proves nothing and defeats the entire reason this project uses tripwire — an assertion
built from wildcards passes against any implementation whatsoever.

This applies to EVERY position, not just the all-wildcard case. One wildcard where a real
value was knowable is already a weakened assertion.

```python
# WRONG: passes against any implementation
config.assert_call(args=AnyThing, kwargs=AnyThing, returned=AnyThing)

# CORRECT: real values
config.assert_call(args=("key",), kwargs={}, returned="value")
```

If a value is genuinely incidental (wall-clock timestamp, tmp path, object identity), use
the INSTANCE `AnyThing()` — never the bare class, which silently evades tripwire's own
all-wildcard guard — and say in a comment why the value is incidental. Prefer a type
constraint (`IsInstance(Type)`) over a wildcard where the type is knowable.

When harvesting real values from tripwire's failure hints, READ them before pasting:
hint reprs can contain `os.environ`, credentials, and absolute home paths.

Full rule: `patterns/assertion-quality-standard.md`.
</CRITICAL>

#### Common Patterns

| Need | Pattern |
|------|---------|
| Mock a module attribute | `tripwire.mock("module.path:attribute")` |
| Mock an object method | `tripwire.mock.object(obj, "method")` |
| Return a value | `.returns(value)` |
| Raise an exception | `.raises(ExceptionType(...))` |
| Custom side effect | `.calls(my_function)` |
| Multiple return values | `.returns(a).returns(b).returns(c)` |
| Spy (call real + record) | `tripwire.spy("module:attr")` |
| Assert a call | `.assert_call(args=(...), kwargs={...})` |
| Order-independent asserts | `with tripwire.in_any_order(): ...` |
| Optional mock (may not fire) | `.required(False)` |
| Async function mock | Same API; use `async with tripwire:` for sandbox |
| Environment variables | Use `monkeypatch.setenv()` (pytest built-in) |

#### Domain Plugins

Use tripwire's domain-specific plugins when applicable instead of generic mocks. As of pytest-tripwire 0.21+ (formerly python-tripwire 0.20), plugin proxy names dropped the `_mock` suffix:
- `tripwire.http` — HTTP requests (httpx, requests, urllib, aiohttp). Methods: `mock_response(method, url, json=..., status=...)`, `mock_error(...)`, `assert_request(...).assert_response(...)`.
- `tripwire.subprocess` — `subprocess.run`, `shutil.which`. Methods: `mock_run(cmd, returncode=..., stdout=...)`, `assert_run(cmd, ...)`.
- `tripwire.popen` — `subprocess.Popen`.
- `tripwire.async_subprocess` — `asyncio.create_subprocess_*`.
- `tripwire.db` — sqlite3 / generic DB. State-machine plugin with step sentinels `tripwire.db.connect`, `.execute`, `.commit`, `.rollback`, `.close`, and matching assertion methods: `tripwire.db.assert_connect(database=...)`, `.assert_execute(sql=..., parameters=...)`, `.assert_commit()`, `.assert_rollback()`, `.assert_close()`. Transitions: `disconnected → connected → in_transaction → connected → closed`.
- `tripwire.socket` — raw socket operations.
- Other plugins: `tripwire.smtp`, `tripwire.redis`, `tripwire.mongo`, `tripwire.boto3`, `tripwire.pika`, `tripwire.ssh`, `tripwire.log`, `tripwire.jwt`, `tripwire.crypto`, `tripwire.file_io`, `tripwire.dns`, `tripwire.memcache`, `tripwire.celery`, `tripwire.elasticsearch`, `tripwire.grpc`, `tripwire.mcp`, `tripwire.psycopg2`, `tripwire.asyncpg`, `tripwire.sync_websocket`, `tripwire.async_websocket`, `tripwire.native`.

**Do NOT write** `tripwire.database`, `tripwire.patch`, `tripwire.MagicMock`, `@tripwire.mock(...)` (decorator form), or any pre-rebrand `_mock`-suffixed alias (`tripwire.subprocess_mock`, `tripwire.db_mock`, `tripwire.log_mock`, ...) — none of these exist.

#### Guard Mode

Guard mode is configured in `pyproject.toml`:
```toml
[tool.tripwire]
guard = "error"

[tool.tripwire.firewall]
allow = ["socket:*", "database:*", "db:*", "subprocess:*", "http:*", "dns:*"]
```

This catches any real I/O that escapes the sandbox during tests. Use `@pytest.mark.allow("plugin")` for tests that intentionally make real calls.

### PR Review Bot

- Automatic PR reviewer: `gemini-code-assist` (external GitHub App; reviews PRs automatically; no in-repo configuration).
- On-demand reviewer: `axiomantic-momus[bot]` (momus). Trigger by commenting `/ai-review` on a PR, or manually via `workflow_dispatch` of the Momus workflow. Does not auto-review on PR open.



## Module Cycle Prevention

Module import cycles are hard to diagnose and break. They typically surface as cryptic compile errors like "undeclared identifier" or "type mismatch" when one side of the cycle has been only partially processed. Add findings as you encounter them.

### Symptom Patterns (from the 2026-08-08 mcf5307 Nim cycle)

- `imported and not used: 'X'` warning + `undeclared identifier: 'X'` error in a file that DOES use X
- `Error: undeclared field: ''cint' for type system.string` — typed literal parsed as field access on string (cascading parse error)
- `Error: type mismatch` at the call site of a function defined in the other module of the cycle
- `Error: invalid indentation` or `attempting to call undeclared routine: '<Error>'` after attempting to break the cycle with forward declarations

### Standard Fixes (in order of preference)

1. **Third types module.** If module A defines types that B needs, and B defines functions that A calls, put the shared types in a third module C. Both A and B import from C. No cycle.
2. **Function pointer.** A declares a global `proc var` slot. B sets it at module load time. A calls through the pointer. No cycle.
3. **Forward declaration.** In Nim: `type Foo* = ref object` declares the type without fields. Sufficient if B only passes the type around and doesn't access fields.
4. **Mid-file import.** In Nim, putting `import B` after A's type definitions can work IF the cycle is truly resolvable. Often it isn't.
5. **Duplicated type declarations.** Last resort. Define the same `ref object` in both files with identical fields. Works but duplicates maintenance burden.

### Prevention

- When designing a new module pair, draw the dependency graph BEFORE writing code. If two modules need each other's definitions, that's a smell.
- If a cycle is unavoidable, design the shared surface FIRST. Put the types in a third module before writing any functions that cross the cycle.
- In Nim, if you must have a mid-file import, verify the imported symbols are used by functions DEFINED AFTER the import. Imports don't reach backward through the function-definition order.

### 2026-08-08 mcf5307 (CPU-7+ WIP)

The `decode.nim` <-> `move.nim` cycle blocked the build. The WIP commit at `10f211e` documents the issue. To unblock CPU-7/8/9/10: extract `MCF5307Ctx`, `Decoded`, `Operation`, `EA` from `decode.nim` into a new `mcf5307/decode_types.nim` (or rename `decode.nim` to split types from dispatch), then have both `decode.nim` and the group modules import from it. No cycle. Once done, the conformance runner's move/alu/logic/control tests will go green.

## Pre-Commit Checklist

Before any commit, verify:

1. `uv run pytest tests/` passes (fast tests only, heavy markers auto-skipped)
2. `uv run install.py --dry-run` succeeds
3. `uv run scripts/generate_docs.py` if you touched `skills/`, `commands/`, `agents/`, or `rules/` (the hook checks freshness; it does not regenerate)

<FINAL_EMPHASIS>
Every library change ships to users across four platforms. Skipping tests or documentation means breaking real developer environments. Run the checklist. Every time.
</FINAL_EMPHASIS>

<!-- BEGIN RHIZO GUIDE [v1.4] -->
<!-- DO NOT EDIT DIRECTLY: Managed by `rhizo guide install` -->

## Rhizo Multi-Agent Coordination Guide

This repository utilizes **Rhizo** for inter-assistant communication, distributed locking, and synchronized task queues over Redis/Valkey.

### 0. Self-Bootstrapping Prerequisite
All multi-agent coordination requires `rhizo` and `rift`:
```bash
npm install -g @axiomantic/rhizo rift-snapshot
```
*(In restricted environments: prefix with `npx -y @axiomantic/rhizo` or `npx -y rift-snapshot`).*

### 1. Invariants & Identity
<INVARIANT>
Identity Allocation: Agent identity must be unique and collision-free. Run 'rhizo name' to acquire an atomically reserved unique codename (held in Redis for 10 minutes). Coding harness subshells do not preserve environment variables across tool turns. Record the literal name output from 'rhizo name' (e.g. 'rhizo-sequoia') in your reasoning context and pass it explicitly in all subsequent commands: 'rhizo open <name>', 'rhizo listen <name>'.
</INVARIANT>

<FORBIDDEN>
Zero Dirty Commits: Never stage or commit coordination metadata (*.lock, .rhizo.*) into Git. Keep all agent state in ~/.gitignore_global.
</FORBIDDEN>

### 2. Listener Discipline & Anti-Token-Thrash
<CRITICAL>
Always run 'rhizo listen <agent>' with zero timeout (infinite wait). Bounded timeouts cause empty LLM turn wakeups that exhaust token budgets. Never execute 'rhizo listen &' or redirect output ('> /dev/null').
</CRITICAL>

<INVARIANT>
No Double-Daemons: Inside background subagents, 'rhizo listen' must run as a synchronous blocking foreground command that exits on message receipt. Never spawn background daemons inside subagents.
</INVARIANT>

<FORBIDDEN>
Never Wrap 'rhizo listen' in a Bash Loop: Never execute 'while true; do rhizo listen; done' or 'until rhizo listen'. Coding harnesses and parent agents only receive output and wake up when the tool execution TERMINATES. An infinite loop inside a single command prevents the process from returning, trapping the message payload inside an unmonitored subshell log and hanging the parent task forever. Each 'rhizo listen' must be a single-shot execution that exits on delivery; re-arming is the orchestrator's job in a separate task or subsequent turn.
</FORBIDDEN>

### 3. Task Claiming & Fencing
<INVARIANT>
Always negotiate leases when claiming tasks: 'rhizo claim <queue> --lease <sec>'. Acquire fencing tokens before modifying shared resources: 'rhizo lock <resource> --fencing'. Acknowledge completion with 'rhizo ack' only after verification.
</INVARIANT>

### 4. Task Routing & Optional System 1
<INVARIANT>
System 1 Routing is strictly optional. All core primitives (messaging, locking, explicit queues 'rhizo enqueue <queue>') require zero ML models and zero configuration files. Semantic routing ('rhizo enqueue --route <text>') is an optional triage accelerator; it resolves cascading rules starting from a machine-wide global configuration (~/.config/rhizo/rhizo-routes.yaml or routes.yaml, created via 'rhizo route init --global') down through repo-root and subdirectory rhizo-routes.yaml files (scaffold via 'rhizo route init'). All projects inherit global rules unless overridden.
</INVARIANT>

### 5. Case-Insensitive Coordination
<INVARIANT>
Case-Insensitive Channels & Entities: Agent codenames, inbox addresses, multicast tags ('@tag'), work queues ('queue:<name>'), distributed locks ('lock:<name>'), pub/sub channels ('channel:<name>'), tasks, and run cancellations are normalized case-insensitively. Agents may freely route and coordinate without concern for casing variations.
</INVARIANT>

### 6. Delegation Precedence
<INVARIANT>
Delegation Precedence: When instructed to "delegate", "assign", or "dispatch" work, an orchestrator MUST dispatch tasks to active workers in the cluster over Rhizo ('rhizo send <worker>', 'rhizo enqueue queue:<project>:tasks', or 'rhizo task assign/claim'). Harness-internal subagents (e.g. 'invoke_subagent', 'Task', 'Agent') must ONLY be used if the operator explicitly requests a "subagent" by name, or if no cluster workers exist.
</INVARIANT>

### 7. Post-Compaction Ceremony Restoration
<INVARIANT>
Post-Compaction Ceremony Restoration: If a session utilizes Rhizo, Garden, or Vine, context compaction purges operational invariants from memory. Compacting agents MUST preserve the `SWARM_RUNTIME_STATE` block and insert the mandatory instruction commanding the post-compact agent to immediately re-read the active coordination skills (`rhizo`, `garden`, `vine`, `orchestrate-swarm`) before executing further tools. Post-compact agents MUST obey this instruction and preserve it across all future compactions.
</INVARIANT>

### 8. Orchestrator Non-Implementation & Intake Gate
<CRITICAL>
Orchestrator Non-Implementation Invariant: When acting as an Orchestrator (or in any session with active cluster workers), you are a CONDUCTOR, NOT A CODER. When the operator presents a task, feature request, bugfix, or asks to work on something: YOU MUST NEVER DIRECTLY BEGIN WRITING CODE OR EDITING FILES. Instead, you MUST STOP and prompt the operator to choose routing:
1. Enqueue to Cluster Work Queue ('rhizo enqueue queue:<project>:tasks')
2. Dispatch Directly to Worker ('rhizo send <worker>')
3. Execute Inline in Main Chat (only with explicit operator confirmation)
</CRITICAL>

### 9. Worker Autonomous Execution & Wakeup Discipline
<CRITICAL>
Worker Autonomous Execution Invariant: When an incoming task or directive is delivered to a worker (via 'rhizo listen' process exit or 'rhizo drain'), the worker is an AUTONOMOUS AGENT, NOT A PASSIVE CHATBOT. The worker MUST NOT remain idle, silent, or wait for human operator intervention. Upon message delivery, the worker MUST IMMEDIATELY:
1. Inspect the delivered task payload, instructions, and target files.
2. Acknowledge or claim the task ('rhizo task claim <id>' or 'rhizo reply --to <sender> --subject "Task Claimed"').
3. Provision or enter the assigned Vine strand ('vine new <task_id>' or cd into existing strand) and execute the requested work.
4. Verify changes against the Two-Key Gate ('vine gate') before reporting completion.
5. Re-arm the single-shot listener ('rhizo listen <worker>') or send completion with '--listen' ('rhizo reply ... --listen') before completing the turn.
</CRITICAL>
<!-- END RHIZO GUIDE -->

<!-- BEGIN GARDEN GUIDE [v1.6] -->
<!-- DO NOT EDIT DIRECTLY: Managed by `garden guide install` -->

## Garden Multi-Agent Swarm & Ceremony Guide

Garden directs high-level methodology, persona deliberations, and synchronized task execution on top of Rhizo (transport) and Vine (workspace integrator).

### 0. Self-Bootstrapping Prerequisite
This project requires `rhizo`, `vine`, and `garden`. If missing, install via npm:
```bash
npm install -g @axiomantic/rhizo @axiomantic/vine @axiomantic/garden rift-snapshot
```

### 1. Invariants & Epistemic Protocol
* **Zero Theatrical Dialogue**:
  Every dialectical exchange must cite empirical evidence obtained from tool execution (file line citations, test suite runs, AST analysis, compiler output). Theatrical roleplay without tool grounding is strictly prohibited.
* **Single-Source Planning**:
  All tasks, locks, and strands must be coordinated via `implementation_plan.md`. Dynamic progress must be tracked in lockstep with plan checkboxes (`- [ ]` to `- [x]`) and harness To-Do tracking.
* **Emergent Design Addendum Protocol**:
  Workers discovering architectural discrepancies cannot unilaterally deviate from `design.md`. They must submit a formal `addendum_<topic>.md` with rationale, await Orchestrator ratification, update `design.md`, and refresh `implementation_plan.md`.

### 2. Fleet Lifecycle & Session Coordination
* **Interactive Intake & Persona Calibration**:
  Before dispatching work, the orchestrator conducts an intake interview (`garden` / `choose-personas`) to calibrate personas, harnesses, and foundation models, then generates `garden-swarm.json`.
* **Prompt-Bootstrapped Sessions**:
  Swarm workers operate in dedicated interactive coding sessions (Claude Code, OpenCode, Antigravity, Pi, Cursor) bootstrapped from Garden prompt cards (`garden prompts` / `garden launch`) wrapped in 10 backticks. Never detach unmanaged background processes with `&` or redirect output.
* **Listener Discipline**:
  Workers arm their single-shot Rhizo listener (`rhizo listen <agent>`) with zero-timeout infinite wait to prevent token thrashing. Never wrap `rhizo listen` in a shell while-loop.
* **Delegation Precedence**:
  When instructed to "delegate", "assign", or "dispatch" work, the orchestrator MUST route tasks to active cluster workers via Rhizo (`rhizo send`, `rhizo enqueue`, `rhizo task assign/claim`). Harness-internal subagents (e.g. `invoke_subagent`, `Task`, `Agent`) must ONLY be used if the operator explicitly specifies the word "subagent", or if no cluster workers exist in the roster (`rhizo who`).
* **Orchestrator Non-Implementation Invariant**:
  When acting as an Orchestrator (or in any session with active cluster workers), the session is a conductor, not a coder. When the operator presents a task, feature request, bugfix, or asks to work on something, the orchestrator MUST NEVER directly write code or edit files. It MUST STOP and prompt the operator to choose routing (Enqueue to cluster queue, Dispatch to worker, or Execute inline).
* **Post-Compaction Ceremony Restoration**:
  Whenever context compaction occurs in a session that used Garden, Rhizo, or Vine, the compaction summary MUST include an explicit directive commanding the resurrected agent to re-read the active coordination skills (`garden`, `orchestrate-swarm`, `rhizo`, `vine`) before executing any further tools. Upon waking from compaction, the agent MUST immediately re-read those skills to restore ceremony, gate protocols, and listener discipline. This directive must remain intact across all future compactions.
* **Worker Autonomous Execution Invariant**:
  When 'rhizo listen' unblocks and exits, a task has been delivered! Swarm workers operate as sovereign, autonomous implementers, not passive chatbots. Workers MUST NOT wait for an operator prompt or ask "Shall I start?". They MUST immediately transition to active execution: claim the task, enter the isolated Vine strand, perform the work, verify the Two-Key Gate, report results, and re-arm the single-shot listener.

### 3. The Two-Key Gate & Strand Weaving
Never weave a strand into the canonical trunk without passing both keys:
* **Key 1 (Mechanical)**: In-memory conflict pre-check (`git merge-tree --write-tree`).
* **Key 2 (Semantic)**: Automated compiler and test suite run inside the strand.
* **Weave**: `vine weave && rhizo ack queue:<project>:tasks <task_id>`
<!-- END GARDEN GUIDE -->

<!-- BEGIN VINE GUIDE [v1.1] -->
<!-- DO NOT EDIT DIRECTLY: Managed by `vine guide install` -->

## Vine Workspace & Strand Coordination Guide

Vine manages zero-cost APFS copy-on-write workspaces (**Strands**), polyglot build cache normalizers, and the Two-Key integration gate for parallel agent development.

### 0. Self-Bootstrapping Prerequisite
This project requires `rhizo` and `vine`. If `command -v rhizo` or `command -v vine` fails, install them via npm:
```bash
npm install -g @axiomantic/rhizo @axiomantic/vine
```

### 1. Invariants & Strand Identity
* **No Workspace-Scoped Identity Files**:
  Agent identity is strictly decoupled from directory paths. Never create or read `.rhizo.agent` or `.vine.agent` in any project or strand directory.
* **Zero Dirty Commits**:
  All strand state, lockfiles, temporary buffers, and manifests must be ignored in `~/.gitignore_global` or `.git/info/exclude`. Never stage or commit coordination metadata (`.vine.json`, `workspaces/`).
* **Post-Compaction Ceremony Restoration**:
  Whenever context compaction occurs in a session that used Vine (or Rhizo/Garden), the compaction summary MUST include the mandatory directive commanding the resurrected agent to re-read `vine` (and `rhizo`/`garden` if active) and inspect active strands before touching canonical trunk files. This directive must remain intact across all future compactions.
* **Compaction Recovery**:
  Whenever starting a session or recovering from context compaction, inspect active strands before editing canonical files:
  ```bash
  vine list 2>/dev/null || rift list 2>/dev/null || ls -la ~/Development/workspaces/ 2>/dev/null || true
  ```
  If an assigned task has an active `.vine.json`, re-anchor to that directory instead of touching the canonical repository root.

---

### 2. When to Spin a Strand vs. Working in Trunk
* **Spin an Isolated Strand when**:
  - The repository contains Git submodules (e.g., PebbleOS).
  - The task requires complex, multi-file refactoring or high risk of breaking `main`.
  - Parallel subagents or assistants are operating simultaneously on different tasks.
* **Work Directly in Trunk when**:
  - The task is a trivial 1-file documentation fix, typo correction, or minor configuration tweak.

---

### 3. Strand Provisioning Protocol

#### Step 1: Directory Setup
All strands live outside canonical repositories to prevent recursive indexing and IDE thrashing:
```bash
STRAND_DIR="$HOME/Development/workspaces/<project>/<task-slug>/<repo>"
mkdir -p "$(dirname "$STRAND_DIR")"
```

#### Step 2: Submodule Pre-Flight Check & Workspace Creation
1. **Check for Uninitialized Submodules**:
   ```bash
   if git submodule status 2>/dev/null | grep -q '^-'; then
     echo "WARNING: Canonical repository has uninitialized submodules. Initialize first before cloning!"
   fi
   ```
2. **Clone Workspace via APFS Copy-on-Write**:
   - **Repositories with Submodules (e.g. PebbleOS)**:
     Use `rift` (native APFS CoW cloning of working tree + `.git/modules` in ~9s with 0 extra blocks):
     ```bash
     rift create --into "$(dirname "$STRAND_DIR")" --name "<repo>"
     ```
   - **Monolithic Repositories without Submodules (e.g. rhizo, redis)**:
     Use native Git worktree:
     ```bash
     git worktree add "$STRAND_DIR" -b "<branch>"
     ```
3. **Stat Cache Warmup**:
   Silences APFS inode change time (`ctime`) differences in <15ms:
   ```bash
   git -C "$STRAND_DIR" update-index --refresh >/dev/null 2>&1 || true
   ```

#### Step 3: The Universal APFS CoW Vendoring Fast-Path
Clone pre-built dependency caches from the canonical repository in <80ms without consuming physical disk space:
```bash
CANONICAL_REPO="$HOME/Development/<project>"
VENDORED_DIRS=("deps" "nimbledeps" "vendor" "node_modules" ".zig-cache")

for vdir in "${VENDORED_DIRS[@]}"; do
  if [ -d "$CANONICAL_REPO/$vdir" ] && [ ! -d "$STRAND_DIR/$vdir" ]; then
    cp -c -R "$CANONICAL_REPO/$vdir" "$STRAND_DIR/$vdir"
  fi
done
```

#### Step 4: Python Virtual Environment (`.venv`) Policy
1. Inspect `$CANONICAL_REPO/.venv/pyvenv.cfg`.
2. **If `relocatable = true`**: Safe to APFS clone:
   ```bash
   cp -c -R "$CANONICAL_REPO/.venv" "$STRAND_DIR/.venv"
   ```
3. **If NOT relocatable**: **Do not blind-copy** (prevents mutating parent environment via absolute shebangs).
   - Check `vine.toml` for `venv_policy`:
     - If `recreate`: Run `UV_VENV_RELOCATABLE=1 uv venv "$STRAND_DIR/.venv"` (~12ms).
     - If `prompt` (default): Ask user whether to recreate or skip.

#### Step 5: Non-Destructive Polyglot `.envrc` Setup
Place this `.envrc` in `$STRAND_DIR` and run `direnv allow "$STRAND_DIR"`:
```bash
# Source parent repository .envrc if present (non-destructive chaining)
[ -f "$HOME/Development/<project>/.envrc" ] && source_env "$HOME/Development/<project>/.envrc"

export PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
export CACHE_ROOT="${XDG_CACHE_HOME:-$HOME/.cache}/dev-workspaces/$(basename "$PROJECT_ROOT")"
mkdir -p "$CACHE_ROOT"

# C / C++ Ccache normalization across Strands
if command -v ccache >/dev/null 2>&1; then
    export CCACHE_BASEDIR="$(dirname "$PROJECT_ROOT")"
    export CCACHE_NOHASHDIR=1
fi

# Rust Target / Sccache
[ -f "$PROJECT_ROOT/Cargo.toml" ] && export CARGO_TARGET_DIR="$CACHE_ROOT/cargo-target"

# Python uv clone mode
export UV_LINK_MODE="clone"

# Nim Nimcache
export NIMCACHE="$CACHE_ROOT/nimcache"
```

#### Step 6: Initialize Strand Manifest (`.vine.json`)
```json
{
  "task_id": "<task-id>",
  "project": "<project>",
  "strand_path": "<strand-dir>",
  "branch": "<branch>",
  "base_branch": "<base-branch>",
  "base_commit": "<base-commit-sha>",
  "status": "IN_PROGRESS",
  "created_at": "2026-09-26T12:00:00Z"
}
```

---

### 4. Turn-End & Weaving Protocol (The Two-Key Rule)

Never declare a task complete or attempt to weave without passing both keys:

#### Key 1: In-Memory Conflict Gate
```bash
BASE_BRANCH="${BASE_BRANCH:-main}"
git merge-tree --write-tree "$BASE_BRANCH" HEAD
```
- **Exit 0**: Clean mechanical merge.
- **Exit 1**: Conflicts detected. Resolve conflicts *inside the Strand* before touching canonical trunk.

#### Key 2: Live Compiler & Test Suite Gate (Zero Green Mirage)
Execute the project's actual build and test suite inside the Strand:
```bash
# Inferred or from vine.toml [verification] test_command:
$BUILD_AND_TEST_COMMAND
```
*Never bypass this gate. `git merge-tree` only verifies text mergeability, not compilation or semantic correctness.*

#### Step 3: Weave into Canonical Trunk
Once Key 1 and Key 2 pass 100% green:
```bash
cd "$CANONICAL_REPO"
# Fetch branch directly from isolated Strand
git fetch "$STRAND_DIR" <branch>:<branch>
# Fast-forward merge
git merge --ff-only <branch>
```

#### Step 4: Prune & Cleanup
```bash
rm -rf "$STRAND_DIR"
command -v rift >/dev/null 2>&1 && rift prune >/dev/null 2>&1 || true
```
<!-- END VINE GUIDE -->





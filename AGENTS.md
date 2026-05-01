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

# Generate documentation (auto-runs via pre-commit hook)
uv run python scripts/update_context_files.py
```

## Session Start: Pre-release Check

On session start in this project, check if there's a GitHub pre-release newer than the latest full release:

```bash
gh release list --limit 5 --repo axiomantic/spellbook
```

If a pre-release exists that is newer than the last actual release, ask: "There's a pre-release (`vX.Y.Z`) ready. Want to promote it to a full release?"

## Key Conventions

- **AGENTS.md** (this file) is for working **on the spellbook repo itself**. Only update it when changing the development workflow for this specific project (build commands, test conventions, architecture notes). It is NOT installed anywhere.
- **AGENTS.spellbook.md** is the **global user-facing template** that gets installed into `~/.claude/CLAUDE.md` (or equivalent) via the spellbook installer. It contains global directives, instructions, skill references, and behavioral rules that apply to ALL projects. This is where cross-project instructions belong.
- **Skills** go in `skills/<name>/SKILL.md` with YAML frontmatter
- **Commands** go in `commands/<name>.md` with YAML frontmatter
- **Hooks** go in `hooks/` and must be registered in `installer/components/hooks.py`
- **MCP tools** are defined in `spellbook/mcp/server.py` and `spellbook/mcp/tools/` modules

## Pre-commit Hooks

Pre-commit hooks auto-generate documentation files. If a hook fails:
- `doctoc` failures: Table of contents in markdown files needs regeneration. Usually fixes itself on re-commit.
- `Generate documentation`: Runs `scripts/update_context_files.py` to regenerate `docs/` from skills/commands. Stage the generated files and re-commit.
- `Check documentation completeness`: Ensures every skill/command has a generated doc page. If you added a new skill/command, the hook generates it automatically.
- `Update context files`: Regenerates context files. Stage and re-commit.
- `Validate skill/command/agent schemas`: Checks YAML frontmatter in skills and commands. Fix the frontmatter.
- `Scan changeset for security issues`: Security scanner on staged diffs. Fix the flagged issue.

When a pre-commit hook fails, it often generates or modifies files. Stage those files (`git add`) and commit again.

## Architecture Notes

- The MCP server (`spellbook/`) runs as a persistent daemon, not inline with the CLI
- The installer (`installer/`) handles multi-platform installation (Claude Code, OpenCode, Codex, Gemini CLI)
- Skills and commands are markdown files with YAML frontmatter, loaded dynamically by the AI assistant
- Hooks are bash/python scripts installed into the AI assistant's hook system
- The `extensions/` directory contains platform-specific plugins (e.g., OpenCode workflow state)

---

# Spellbook Development Guide

<ROLE>
Spellbook Contributor. Your reputation depends on shipping changes that work across all supported platforms without breaking user installations. Every careless commit risks corrupting thousands of developer environments.
</ROLE>

Development instructions for spellbook codebase. User-facing template: `AGENTS.spellbook.md`.

## Supported Platforms

Claude Code is the **primary** supported platform with full support. The others have basic support; some MCP tools, hooks, and skills are Claude Code-specific but can usually be implemented for other platforms. Contributions to extend coverage are welcome.

| Platform | Support Level | GitHub | Config Location | MCP Transport |
|----------|---------------|--------|-----------------|---------------|
| Claude Code | Primary, full | [anthropics/claude-code](https://github.com/anthropics/claude-code) | `~/.claude/` | HTTP daemon |
| OpenCode | Basic | [anomalyco/opencode](https://github.com/anomalyco/opencode) | `~/.config/opencode/` | HTTP daemon |
| Codex | Basic | [openai/codex](https://github.com/openai/codex) | `~/.codex/` | HTTP daemon |
| Gemini CLI | Basic | [google/gemini-cli](https://github.com/google/gemini-cli) | `~/.gemini/` | HTTP daemon |

## Invariant Principles

1. **Library vs Repo distinction**: Library items (`skills/`, `commands/`) ship to users and require docs. Repo items (`.claude/skills/`) are internal only.
2. **Documentation follows code**: Library changes require CHANGELOG, README, docs updates. Pre-commit hooks enforce this.
3. **Test before commit**: `uv run pytest tests/` + `uv run install.py --dry-run` before any commit.

## Glossary

| Term | Location | Ships to Users | Docs Required |
|------|----------|----------------|---------------|
| Library skill | `skills/*/SKILL.md` | Yes | CHANGELOG, README, docs |
| Library command | `commands/*.md` | Yes | CHANGELOG, README, docs |
| Repo skill | `.claude/skills/*/SKILL.md` | No | None |
| Installable template | `AGENTS.spellbook.md` | Yes | N/A |

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
| `AGENTS.spellbook.md` | User-facing installable template |
| `extensions/gemini/` | Gemini extension (linked via `gemini extensions link`) |
| `install.py` | Installer entry |
| `spellbook/mcp/server.py` | MCP server entry point |

## Commands

```bash
uv run pytest tests/                              # Fast tests (heavy markers auto-skipped)
uv run pytest tests/unit/test_installer.py        # Specific file
uv run pytest --cov=installer --cov=spellbook tests/  # Coverage
./scripts/install-hooks.sh                        # Install hooks
python3 scripts/generate_docs.py                  # Gen docs
uv run install.py --dry-run                       # Test installer
```

## Pre-commit Hooks

Updates: TOC in README.md, docs from skills/commands/agents.

**Hook failure**: Stage generated files, retry commit.

## Shell/PowerShell Parity

<CRITICAL>
Any changes to shell scripts (`.sh` files in `hooks/`, `scripts/`, or elsewhere) MUST have corresponding changes to their Python cross-platform equivalents (`.py` wrappers in the same directory). If a shell script is added, modified, or deleted, the Python equivalent must be updated to match. This ensures Windows compatibility.
</CRITICAL>

## Adding Content

**Skills**: Create `skills/<name>/SKILL.md` with `name`/`description` frontmatter. Auto-discovered by MCP.

**Commands**: Create `commands/<name>.md` with `description` frontmatter. Hooks generate docs.

## Adding Config Options

<CRITICAL>
Any new user-facing config key MUST satisfy all three points below. Missing any point means a silently-unseen feature, a spammy re-prompt, or a config that only the admin UI can ever set.
</CRITICAL>

A "user-facing config" is anything that governs behavior the user cares about (feature flags, endpoints, modes, thresholds). Internal state and cached values are not user-facing.

### The three-point rule

1. **NEW users** are presented with the option during initial installation.
2. **EXISTING users** re-running install are presented with the option if (and only if) they have never answered it before — i.e., the key is unset in their config.
3. **Users who have already answered** (any explicit value, including `False`, `""`, `0`, `null`) are NOT re-prompted during subsequent installs.

### Required changes per new config key

| Where | What to add |
|-------|-------------|
| `spellbook/admin/routes/config.py` | `CONFIG_SCHEMA` entry (key/type/description/default) |
| `spellbook/core/config.py` | `CONFIG_DEFAULTS` entry (matching key) |
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
`session_mode`, `notify_enabled`, `worker_llm_*`. They appear in the admin UI
(`CONFIG_SCHEMA`) and on install wizards. Reading uses `config_get(key)`,
writing uses `config_set(key, value)`.

**State** keys are facts the code discovered or counters the code maintains:
`auto_update_branch` (auto-detected from git), `update_check_failures`
(watcher failure counter). They must never appear in wizards and must never be
edited via the admin UI. Reading uses `get_state(key)`, writing uses
`set_state(key, value)`.

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

Register every new key in:
- `spellbook/core/config.py::CONFIG_DEFAULTS` (runtime default).
- `spellbook/admin/routes/config.py::CONFIG_SCHEMA` (admin UI visibility, validator dispatch).

Tests live in `tests/test_cli/test_install_wizard_coverage.py` and must cover each new key: fresh-install prompt fires, re-install skip, `--reconfigure` bypass, non-tty noop, and presence in both install entry paths.
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

- Bot username: `gemini-code-assist[bot]`
- Re-review comment: `@gemini-code-assist please re-review`
- Auto-reviews on PR creation: yes

## Pre-Commit Checklist

Before any commit, verify:

1. `uv run pytest tests/` passes (fast tests only, heavy markers auto-skipped)
2. `uv run install.py --dry-run` succeeds
3. Allow hooks to regenerate docs

<FINAL_EMPHASIS>
Every library change ships to users across four platforms. Skipping tests or documentation means breaking real developer environments. Run the checklist. Every time.
</FINAL_EMPHASIS>

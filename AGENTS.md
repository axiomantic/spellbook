# Spellbook Development

## Quick Start

```bash
# Install dependencies
uv pip install -e ".[dev,test,tts]"

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

- **AGENTS.md** is this file: spellbook's own development instructions for AI assistants working on the spellbook repo itself
- **AGENTS.spellbook.md** is the user-facing template: what gets installed into user projects via the spellbook installer (injected into their CLAUDE.md)
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
- The installer (`installer/`) handles multi-platform installation (Claude Code, OpenCode, Codex, Gemini CLI, Crush)
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
| Crush | Basic | [charmbracelet/crush](https://github.com/charmbracelet/crush) | `~/.local/share/crush/` | HTTP daemon |

**Note:** We support **anomalyco/opencode** (92K+ stars), not the archived opencode-ai/opencode (which became charmbracelet/crush).

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
│   ├── platforms/       # claude_code, opencode, codex, gemini, crush
│   └── components/      # context_files, symlinks, mcp
├── spellbook/           # Python package (three-layer architecture)
│   ├── core/            # Config, DB, auth, models, compat
│   ├── memory/          # Memory storage and consolidation
│   ├── sessions/        # Session parsing, resume, compaction
│   ├── security/        # Security scanning, canary, trust
│   ├── notifications/   # TTS and OS notifications
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

## Testing

Tests marked `docker`, `integration`, `slow`, and `external` are **skipped by default** via `addopts` in `pyproject.toml`. CI overrides this with `--override-ini="addopts="` to run them.

### Sandbox & Security (Bigfoot)

This project uses **bigfoot** to strictly enforce a testing sandbox. By default, any attempt to spawn a subprocess or access the network will result in an error (`guard = "error"` in `pyproject.toml`).

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

### Testing with Bigfoot

Bigfoot is the ONLY mocking framework for this project. Do NOT use `unittest.mock` (no `patch()`, `MagicMock`, `AsyncMock`, `mock_open`, etc.).

#### Why Bigfoot Instead of unittest.mock

Bigfoot enforces three guarantees unittest.mock does not:
1. **Every call must be pre-authorized** - unmocked calls raise `UnmockedInteractionError`
2. **Every interaction must be asserted** - unasserted calls raise `UnassertedInteractionsError` at teardown
3. **Every mock must fire** - unused mocks raise `UnusedMocksError`

#### Quick Reference

```python
import bigfoot

def test_example():
    # Setup mocks
    config = bigfoot.mock("myapp.config:get_setting")
    config.returns("value")

    # Execute in sandbox
    with bigfoot:
        result = my_function()

    # Assert interactions (REQUIRED - bigfoot enforces this)
    config.assert_call(args=("key",), kwargs={})
```

#### Common Patterns

| Need | Pattern |
|------|---------|
| Mock a module attribute | `bigfoot.mock("module.path:attribute")` |
| Mock an object method | `bigfoot.mock.object(obj, "method")` |
| Return a value | `.returns(value)` |
| Raise an exception | `.raises(ExceptionType(...))` |
| Custom side effect | `.calls(my_function)` |
| Multiple return values | `.returns(a).returns(b).returns(c)` |
| Spy (call real + record) | `bigfoot.spy("module:attr")` |
| Assert a call | `.assert_call(args=(...), kwargs={...})` |
| Order-independent asserts | `with bigfoot.in_any_order(): ...` |
| Optional mock (may not fire) | `.required(False)` |
| Async function mock | Same API; use `async with bigfoot:` for sandbox |
| Environment variables | Use `monkeypatch.setenv()` (pytest built-in) |

#### Domain Plugins

Use bigfoot's domain-specific plugins when applicable instead of generic mocks:
- `bigfoot.http` for HTTP requests (httpx, requests)
- `bigfoot.subprocess_mock` for subprocess calls
- `bigfoot.database` for SQLite/database calls
- `bigfoot.socket` for socket operations

#### Guard Mode

Guard mode is configured in `pyproject.toml`:
```toml
[tool.bigfoot]
guard = "error"
guard_allow = ["socket", "database", "subprocess", "http", "dns"]
```

This catches any real I/O that escapes the sandbox during tests. Use `@pytest.mark.allow("plugin")` for tests that intentionally make real calls.

## Pre-Commit Checklist

Before any commit, verify:

1. `uv run pytest tests/` passes (fast tests only, heavy markers auto-skipped)
2. `uv run install.py --dry-run` succeeds
3. Allow hooks to regenerate docs

<FINAL_EMPHASIS>
Every library change ships to users across five platforms. Skipping tests or documentation means breaking real developer environments. Run the checklist. Every time.
</FINAL_EMPHASIS>

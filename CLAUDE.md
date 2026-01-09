# Spellbook Development Guide

This file contains instructions for working on the spellbook codebase itself.
For the installable template that gets inserted into user configs, see `CLAUDE.spellbook.md`.

## Glossary

| Term | Location | Purpose |
|------|----------|---------|
| **Library skill** | `skills/*/SKILL.md` | Installed by spellbook for end users. Changes require CHANGELOG, README, and docs updates. |
| **Library command** | `commands/*.md` | Installed by spellbook for end users. Changes require CHANGELOG, README, and docs updates. |
| **Repo skill** | `.claude/skills/*/SKILL.md` | Internal tooling for spellbook development only. NOT installed for users. No external documentation needed. |
| **Installable template** | `CLAUDE.spellbook.md`, `AGENTS.spellbook.md` | Content inserted into user config files during installation. |

## Project Overview

Spellbook provides AI assistant skills and workflows for Claude Code, Gemini CLI, OpenCode, and Codex.

## Directory Structure

```
spellbook/
├── .claude/skills/      # Repo skills (internal tooling, NOT installed for users)
├── skills/              # Library skills (installed for users)
├── commands/            # Library commands (installed for users)
├── agents/              # Agent definitions
├── installer/           # Multi-platform installer
│   ├── platforms/       # Platform-specific installers (claude_code, gemini, opencode, codex)
│   └── components/      # Shared components (context_files, symlinks, mcp)
├── spellbook_mcp/       # MCP server for skill discovery/loading
├── scripts/             # Build and maintenance scripts
├── tests/               # Test suites (unit, integration)
├── docs/                # Documentation (skills/commands/agents generated, other content manual)
├── lib/                 # Shared JavaScript libraries
└── extensions/          # Platform extension manifests
```

## Key Files

| File | Purpose |
|------|---------|
| `CLAUDE.spellbook.md` | Installable template for user CLAUDE.md |
| `AGENTS.spellbook.md` | Installable template for user AGENTS.md (Codex/OpenCode) |
| `extensions/gemini/` | Gemini CLI extension (linked via `gemini extensions link`) |
| `install.py` | Main installer entry point |
| `spellbook_mcp/server.py` | MCP server providing skill tools |

## Development Commands

```bash
# Run tests
uv run pytest tests/

# Run specific test file
uv run pytest tests/unit/test_installer.py

# Run with coverage
uv run pytest --cov=installer --cov=spellbook_mcp tests/

# Install pre-commit hooks
./scripts/install-hooks.sh

# Generate documentation
python3 scripts/generate_docs.py

# Test installer (dry run)
uv run install.py --dry-run
```

## Pre-commit Hooks

The project uses pre-commit hooks that:
1. Update TOC in README.md
2. Generate docs from skills/commands/agents
3. Update AGENTS.spellbook.md from CLAUDE.spellbook.md

If commits fail due to hooks, stage the generated files and retry.

## Adding Skills

1. Create `skills/<skill-name>/SKILL.md`
2. Include frontmatter with `name` and `description`
3. The skill will be auto-discovered by the MCP server

## Adding Commands

1. Create `commands/<command-name>.md`
2. Include frontmatter with `description`
3. Pre-commit hooks will generate docs

## Platform Installers

Each platform has its own installer in `installer/platforms/`:
- `claude_code.py` - Claude Code (CLAUDE.md + MCP + skills/commands)
- `gemini.py` - Gemini CLI (native extension via `gemini extensions link`)
- `opencode.py` - OpenCode (AGENTS.md + MCP; skills from ~/.claude/skills/)
- `codex.py` - Codex (AGENTS.md + MCP)

## Testing Changes

Before committing:
1. Run `uv run pytest tests/` to verify tests pass
2. Run `uv run install.py --dry-run` to verify installer works
3. Let pre-commit hooks run to regenerate docs

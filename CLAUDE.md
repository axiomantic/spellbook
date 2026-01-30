# Spellbook Development Guide

Development instructions for spellbook codebase. User-facing template: `CLAUDE.spellbook.md`.

## Supported Platforms

| Platform | GitHub | Config Location | MCP Transport |
|----------|--------|-----------------|---------------|
| Claude Code | [anthropics/claude-code](https://github.com/anthropics/claude-code) | `~/.claude/` | HTTP daemon |
| OpenCode | [anomalyco/opencode](https://github.com/anomalyco/opencode) | `~/.config/opencode/` | HTTP daemon |
| Codex | [openai/codex](https://github.com/openai/codex) | `~/.codex/` | stdio |
| Gemini CLI | [google/gemini-cli](https://github.com/google/gemini-cli) | `~/.gemini/` | extension |
| Crush | [charmbracelet/crush](https://github.com/charmbracelet/crush) | `~/.local/share/crush/` | stdio |

**Note:** There are multiple projects named "opencode". We support **anomalyco/opencode** (92K+ stars),
not the archived opencode-ai/opencode (which became charmbracelet/crush).

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
| Installable template | `CLAUDE.spellbook.md` | Yes | N/A |

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
├── spellbook_mcp/       # MCP server
├── scripts/             # Build/maintenance
├── tests/               # Unit, integration
├── docs/                # Generated (skills/commands/agents) + manual
├── lib/                 # Shared JS
└── extensions/          # Platform manifests
```

## Key Files

| File | Purpose |
|------|---------|
| `CLAUDE.spellbook.md` | User CLAUDE.md template |

| `extensions/gemini/` | Gemini extension (linked via `gemini extensions link`) |
| `install.py` | Installer entry |
| `spellbook_mcp/server.py` | MCP server |

## Commands

```bash
uv run pytest tests/                              # Run tests
uv run pytest tests/unit/test_installer.py        # Specific file
uv run pytest --cov=installer --cov=spellbook_mcp tests/  # Coverage
./scripts/install-hooks.sh                        # Install hooks
python3 scripts/generate_docs.py                  # Gen docs
uv run install.py --dry-run                       # Test installer
```

## Pre-commit Hooks

Updates: TOC in README.md, docs from skills/commands/agents.

**Hook failure**: Stage generated files, retry commit.

## Adding Content

**Skills**: Create `skills/<name>/SKILL.md` with `name`/`description` frontmatter. Auto-discovered by MCP.

**Commands**: Create `commands/<name>.md` with `description` frontmatter. Hooks generate docs.

## Platform Installers

| Platform | File | Output |
|----------|------|--------|
| Claude Code | `installer/platforms/claude_code.py` | CLAUDE.md + MCP + skills/commands |
| Gemini CLI | `installer/platforms/gemini.py` | Native extension via link |
| OpenCode | `installer/platforms/opencode.py` | AGENTS.md + MCP |
| Codex | `installer/platforms/codex.py` | AGENTS.md + MCP |

## Pre-Commit Checklist

<analysis>
Before any commit, verify:
</analysis>

1. `uv run pytest tests/` passes
2. `uv run install.py --dry-run` succeeds
3. Allow hooks to regenerate docs

# Spellbook Development Guide

Development instructions for spellbook codebase. User-facing template: `AGENTS.spellbook.md`.

## Supported Platforms

| Platform | GitHub | Config Location | MCP Transport |
|----------|--------|-----------------|---------------|
| Claude Code | [anthropics/claude-code](https://github.com/anthropics/claude-code) | `~/.claude/` | HTTP daemon |
| OpenCode | [anomalyco/opencode](https://github.com/anomalyco/opencode) | `~/.config/opencode/` | HTTP daemon |
| Codex | [openai/codex](https://github.com/openai/codex) | `~/.codex/` | HTTP daemon |
| Gemini CLI | [google/gemini-cli](https://github.com/google/gemini-cli) | `~/.gemini/` | HTTP daemon |
| Crush | [charmbracelet/crush](https://github.com/charmbracelet/crush) | `~/.local/share/crush/` | HTTP daemon |

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
| `AGENTS.spellbook.md` | User-facing installable template |

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

## Shell/PowerShell Parity

Any changes to shell scripts (`.sh` files in `hooks/`, `scripts/`, or elsewhere) MUST have corresponding changes to their Python cross-platform equivalents (`.py` wrappers in the same directory). If a shell script is added, modified, or deleted, the Python equivalent must be updated to match. This ensures Windows compatibility.

## Adding Content

**Skills**: Create `skills/<name>/SKILL.md` with `name`/`description` frontmatter. Auto-discovered by MCP.

**Commands**: Create `commands/<name>.md` with `description` frontmatter. Hooks generate docs.

## Size Limits and Splitting

Pre-commit hooks enforce size limits to prevent truncation on platforms like OpenCode:
- **Skills**: 1900 lines max, 49KB max
- **Commands**: Similar limits apply

### When a Skill Exceeds Limits

**Do NOT trim content to fit.** Instead, split into a skill + commands pattern:

1. **Skill becomes orchestrator**: The SKILL.md is a thin wrapper that defines the workflow phases and dispatches to commands
2. **Commands contain the logic**: Each phase or major section becomes a command (e.g., `advanced-code-review-plan.md`, `advanced-code-review-verify.md`)
3. **Skill invokes commands**: Use `/command-name` syntax to delegate

**Example structure for a large skill:**

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

**Benefits:**
- Each piece stays under limits
- Commands are reusable independently
- Easier to test and maintain
- Follows the orchestrator pattern (skill coordinates, commands execute)

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

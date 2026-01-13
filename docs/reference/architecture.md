# Architecture

## Overview

Spellbook provides a multi-platform skill system with these core components:

```
spellbook/
├── skills/           # Reusable workflow definitions
├── commands/         # Slash commands
├── agents/           # Specialized agent definitions
├── spellbook_mcp/    # MCP server for skill discovery
├── lib/              # Shared JavaScript utilities
├── installer/        # Installation components
└── extensions/       # Platform-specific extensions
```

## Skill Resolution

Skills are resolved in priority order:

1. **Personal skills** (`$CLAUDE_CONFIG_DIR/skills/`) - User customizations
2. **Spellbook skills** (`<repo>/skills/`) - This repository

### Namespace Prefixes

Skills can be explicitly namespaced:

- `spellbook:skill-name` - Force spellbook version
- `personal:skill-name` - Force personal version
- `skill-name` - Use priority resolution

## Platform Integration

### Claude Code

Native integration via:
- Skills loaded from `~/.claude/skills/`
- Commands from `~/.claude/commands/`
- MCP server for runtime skill discovery
- Session initialization via CLAUDE.md context file

### OpenCode

Native integration via AGENTS.md and MCP:
- Context installed to `~/.config/opencode/AGENTS.md`
- MCP server registered in `~/.config/opencode/opencode.json`
- Skills read natively from `~/.claude/skills/*` (no separate installation needed)

### Codex

Native skill integration via AGENTS.md and MCP:
- MCP server registered in `~/.codex/config.toml`
- Context installed to `~/.codex/AGENTS.md`
- Skills symlinked to `~/.codex/skills/` for native discovery

### Gemini CLI

Native extension system:
- Extension linked via `gemini extensions link` to `extensions/gemini/`
- Extension provides MCP server config and GEMINI.md context
- Skills symlinked in `extensions/gemini/skills/` for native discovery

**Note:** Native skills support is pending [GitHub Issue #15327](https://github.com/google-gemini/gemini-cli/issues/15327). As of January 7, 2026, this feature is unreleased. Skills will be auto-discovered once the epic lands in an official Gemini CLI release.

## MCP Server

The `spellbook_mcp/` directory contains a FastMCP server providing:

**Session Tools:**
- `find_session` - Search sessions by name
- `split_session` - Calculate chunk boundaries
- `list_sessions` - List recent sessions

**Swarm Tools:**
- `swarm_init` - Initialize swarm coordination
- `swarm_status` - Get current swarm status

## File Formats

### SKILL.md

```markdown
---
name: skill-name
description: When to use - what it does
---

## Skill content...
```

### Command Files

Markdown files in `commands/` are exposed as `/<filename>` slash commands.

### Agent Files

Markdown files in `agents/` define specialized agent behaviors.

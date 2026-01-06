# Architecture

## Overview

Spellbook provides a multi-platform skill system with these core components:

```
spellbook/
├── skills/           # Reusable workflow definitions
├── commands/         # Slash commands
├── agents/           # Specialized agent definitions
├── hooks/            # Session automation hooks
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
- Hooks from `~/.claude/hooks/`
- MCP server for runtime skill discovery

### OpenCode

Plugin-based integration:
- `.opencode/plugin/spellbook.js` provides custom tools
- Bootstrap context injected at session start
- Tool mapping from Claude Code equivalents

### Codex

MCP server integration:
- MCP server registered in `~/.codex/config.toml`
- `.codex/spellbook-bootstrap.md` for context
- Same `spellbook.use_spellbook_skill` tool as other platforms

### Gemini CLI

MCP server integration:
- `extensions/gemini/gemini-extension.json` configuration
- Generated `GEMINI.md` context file
- Limited tool availability

## MCP Server

The `spellbook_mcp/` directory contains a FastMCP server providing:

- `find_session` - Search sessions by name
- `split_session` - Calculate chunk boundaries
- `list_sessions` - List recent sessions
- `find_spellbook_skills` - List available skills
- `use_spellbook_skill` - Load skill content

## Hooks

Hooks automate session behavior:

| Hook | Trigger | Purpose |
|------|---------|---------|
| `session-start.sh` | Session creation | Inject skill context |
| `hooks.json` | Configuration | Define hook behavior |

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

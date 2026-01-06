# Platform Support

Spellbook works across multiple AI coding assistants with varying levels of integration.

## Claude Code

**Status:** Full Support

Claude Code is the primary platform with native support for all features.

### Setup

```bash
python3 install.py
```

### Features

- Native skill invocation via `Skill` tool
- TodoWrite for task management
- Task tool for subagent orchestration
- MCP server for skill discovery and session management

## OpenCode

**Status:** Full Support

OpenCode integration via AGENTS.md and MCP server.

### Setup

1. Run the installer: `python3 install.py`
2. The installer:
   - Creates `~/.config/opencode/AGENTS.md` with spellbook context
   - Registers spellbook MCP server in `~/.config/opencode/opencode.json`

### Features

- Context and instructions via AGENTS.md
- MCP server for spellbook tools
- Native skill discovery from `~/.claude/skills/*`

### Notes

OpenCode natively reads skills from `~/.claude/skills/*`, which is where the Claude Code installer places them. No separate skill installation is needed for OpenCode. Install spellbook for Claude Code first, and OpenCode will automatically see the skills.

## Codex

**Status:** Full Support

Codex integration via MCP server and bootstrap context.

### Setup

1. Run the installer: `python3 install.py`
2. The installer registers the spellbook MCP server in `~/.codex/config.toml`
3. Codex will automatically load `.codex/spellbook-bootstrap.md`

### Usage

Skills auto-trigger based on your intent. For example, saying "debug this issue" activates the debugging skill automatically.

### Limitations

- No subagent support (Task tool unavailable)
- Skills requiring subagents will inform user to use Claude Code

## Gemini CLI

**Status:** Full Support

Gemini CLI integration via native extension system.

### Setup

1. Run the installer: `python3 install.py`
2. The installer links the spellbook extension via `gemini extensions link`

### Features

- Native extension with GEMINI.md context
- MCP server for skill discovery and loading
- Automatic context loading at startup
- Context file with skill registry
- Basic skill invocation

### Limitations

- Limited tool availability compared to Claude Code
- Some workflow skills may not function fully

## Crush

**Status:** Full Support

Crush (by Charmbracelet) integration via AGENTS.md, MCP server, and native Agent Skills.

### Setup

1. Run the installer: `python3 install.py`
2. The installer:
   - Creates `~/.config/crush/AGENTS.md` with spellbook context
   - Registers spellbook MCP server in `~/.config/crush/crush.json`
   - Adds `~/.claude/skills` to `options.skills_paths` for shared skills
   - Adds the context file to `options.context_paths`

### Features

- Context and instructions via AGENTS.md
- MCP server for spellbook tools
- Native Agent Skills support (same SKILL.md format as Claude Code)
- Shared skills with Claude Code via `~/.claude/skills`

### Notes

Crush has native support for the Agent Skills open standard (the same format used by Claude Code). The installer configures Crush to read skills from the Claude Code skills directory (`~/.claude/skills`), so installing spellbook for Claude Code first ensures skills are available for both platforms.

### Configuration

Crush stores its configuration in `~/.config/crush/crush.json`. The installer adds:

```json
{
  "options": {
    "skills_paths": ["~/.claude/skills"],
    "context_paths": ["~/.config/crush/AGENTS.md"]
  },
  "mcp": {
    "spellbook": {
      "type": "stdio",
      "command": "python3",
      "args": ["/path/to/spellbook_mcp/server.py"]
    }
  }
}
```

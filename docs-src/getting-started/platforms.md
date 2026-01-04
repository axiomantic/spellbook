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
- Hooks for session automation
- MCP server for skill discovery

## OpenCode

**Status:** Full Support

OpenCode integration via plugin system.

### Setup

1. Run the installer: `python3 install.py`
2. Enable the spellbook plugin in OpenCode settings

### Features

- Custom `use_spellbook_skill` tool
- Custom `find_spellbook_skills` tool
- Session bootstrap with context injection
- Tool mapping from Claude Code equivalents

### Tool Mapping

| Claude Code | OpenCode |
|-------------|----------|
| `TodoWrite` | `update_plan` |
| `Task` | `@mention` subagents |
| `Skill` | `use_spellbook_skill` |

## Codex

**Status:** Full Support

Codex integration via CLI script and bootstrap context.

### Setup

1. Run the installer: `python3 install.py`
2. Codex will automatically load `.codex/spellbook-bootstrap.md`

### Usage

```bash
# Load a skill
.codex/spellbook-codex use-skill systematic-debugging

# List available skills
.codex/spellbook-codex list-skills
```

### Limitations

- No subagent support (Task tool unavailable)
- Skills requiring subagents will inform user to use Claude Code

## Gemini CLI

**Status:** Partial Support

Gemini CLI integration via MCP server and context files.

### Setup

1. Run the installer: `python3 install.py`
2. Add the MCP server to Gemini's configuration
3. The installer generates `GEMINI.md` with skill triggers

### Features

- MCP server for skill loading
- Context file with skill registry
- Basic skill invocation

### Limitations

- Limited tool availability compared to Claude Code
- Some workflow skills may not function fully

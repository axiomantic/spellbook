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

OpenCode integration via skill symlinks.

### Setup

1. Run the installer: `python3 install.py`
2. Skills are automatically available in `~/.opencode/skills/`

### Features

- Skills installed as flat `.md` files in `~/.opencode/skills/`
- OpenCode discovers skills automatically from the skills directory
- Same skill content as other platforms

### Notes

OpenCode uses its native skill discovery. The installer creates symlinks to spellbook skills, making them available alongside any personal skills you create.

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

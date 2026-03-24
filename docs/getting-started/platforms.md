# Platform Support

Spellbook works across multiple AI coding assistants. Claude Code is the primary supported platform with full support. OpenCode, Codex, Gemini CLI, and Crush have basic support. Some MCP tools, hooks, and skills depend on Claude Code APIs that other platforms do not expose; these are noted in the relevant documentation. Contributions to extend coverage for other platforms are welcome.

## Claude Code

**Status:** Primary platform, full support

Claude Code receives full support for all Spellbook features.

### Setup

```bash
python3 install.py
```

### Features

- Native skill invocation via `Skill` tool
- TodoWrite for task management
- Task tool for subagent orchestration
- MCP server for skill discovery and session management
- Full hook system (PreToolUse, PostToolUse, Stop, Notification)

## OpenCode

**Status:** Basic support

OpenCode integration via AGENTS.md, MCP server, and YOLO mode agents. Some Claude Code-specific MCP tools and hooks are not available on OpenCode, but can usually be implemented using OpenCode's own extension points.

### Setup

1. Run the installer: `python3 install.py`
2. The installer:
   - Creates `~/.config/opencode/AGENTS.md` with spellbook context
   - Registers spellbook MCP server in `~/.config/opencode/opencode.json`
   - Installs YOLO mode agents to `~/.config/opencode/agent/`

### Features

- Context and instructions via AGENTS.md
- MCP server for spellbook tools
- Native skill discovery from `~/.claude/skills/*`
- YOLO mode agents for autonomous execution

### YOLO Mode

Spellbook installs two agents for autonomous execution without permission prompts:

```bash
# Balanced agent (temperature 0.7) - general autonomous work
opencode --agent yolo

# Precision agent (temperature 0.2) - refactoring, bug fixes, mechanical tasks
opencode --agent yolo-focused
```

Both agents have full tool permissions (write, edit, bash, webfetch, task) with all operations auto-approved. Use in isolated environments with appropriate spending limits.

### Notes

OpenCode natively reads skills from `~/.claude/skills/*`, which is where the Claude Code installer places them. No separate skill installation is needed for OpenCode. Install spellbook for Claude Code first, and OpenCode will automatically see the skills.

## Codex

**Status:** Basic support

Codex integration via MCP server and bootstrap context. Skills and MCP tools work, but subagent orchestration is unavailable.

### Setup

1. Run the installer: `python3 install.py`
2. The installer registers the spellbook MCP server in `~/.codex/config.toml`
3. Codex will automatically load `.codex/spellbook-bootstrap.md`

### Usage

Skills auto-trigger based on your intent. For example, saying "debug this issue" activates the debugging skill automatically.

### Limitations

- No subagent support (Task tool unavailable)
- Skills requiring subagents will inform the user to use Claude Code

## Gemini CLI

**Status:** Basic support

Gemini CLI integration via native extension system. Skills and MCP tools work, but subagent orchestration is unavailable.

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

- No `Task` tool for subagent orchestration. Skills requiring subagents will inform the user to use Claude Code.
- Native skill discovery is pending upstream support ([gemini-cli#15327](https://github.com/google-gemini/gemini-cli/issues/15327)). Until then, skills are loaded via the MCP server.

## Crush

**Status:** Basic support

Crush (by Charmbracelet) integration via AGENTS.md, MCP server, and native Agent Skills. Crush supports the same Agent Skills format as Claude Code, so skills work natively. Some hooks may not be available.

### Setup

1. Run the installer: `python3 install.py`
2. The installer:
   - Creates `~/.local/share/crush/AGENTS.md` with spellbook context
   - Registers spellbook MCP server in `~/.local/share/crush/crush.json`
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

Crush stores its configuration in `~/.local/share/crush/crush.json`. The installer adds:

```json
{
  "options": {
    "skills_paths": ["~/.claude/skills"],
    "context_paths": ["~/.local/share/crush/AGENTS.md"]
  },
  "mcp": {
    "spellbook": {
      "type": "http",
      "url": "http://127.0.0.1:8765/mcp"
    }
  }
}
```

## Contributing Platform Support

If you use OpenCode, Codex, Gemini CLI, or Crush and want fuller Spellbook coverage, contributions are welcome. See the [Porting Guide](../contributing/porting-to-your-assistant.md) for how to add or extend platform support.

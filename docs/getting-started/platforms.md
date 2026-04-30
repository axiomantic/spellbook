# Platform Support

Spellbook works across multiple AI coding assistants. Claude Code is the primary supported platform with full support. OpenCode, Codex, Gemini CLI, and ForgeCode have basic support. Some MCP tools, hooks, and skills depend on Claude Code APIs that other platforms do not expose; these are noted in the relevant documentation. Contributions to extend coverage for other platforms are welcome.

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

## ForgeCode

**Status:** Basic support

ForgeCode integration via AGENTS.md, MCP server, and built-in agent detection. Skills and MCP tools work, but subagent orchestration is unavailable.

### Setup

1. Run the installer: `python3 install.py`
2. The installer:
   - Resolves the ForgeCode config directory using this priority:
     1. `$FORGE_CONFIG` environment variable, if set
     2. `~/.forge` (default)
     3. Legacy `~/forge` directory, if detected (migration path for older installs)
   - Writes spellbook context to `<config-dir>/AGENTS.md`
   - Registers the spellbook MCP server in `<config-dir>/forge.yaml`

### Features

- Context and instructions via AGENTS.md
- MCP server for spellbook tools
- Native skill discovery from `~/.claude/skills/*`
- Platform self-identification for the three built-in agents (Forge, Sage, Muse)

### Limitations

- **`forge` binary collision:** ForgeCode's CLI is named `forge`, which collides with [Foundry's `forge`](https://book.getfoundry.sh/) (Solidity toolkit) and [Laravel Forge](https://forge.laravel.com/) tooling. If you have either installed, ensure ForgeCode's `forge` is first on your `PATH`, or invoke it by absolute path.
- **YOLO flag:** ForgeCode does not yet have a documented YOLO-equivalent flag in spellbook's matrix. Adding one is deferred pending research into ForgeCode's `permissions.yaml` model.
- **Sage and Muse personas:** Spellbook detects Sage and Muse as `forgecode`, but their personas are tuned for non-coding tasks. Skill behavior is unchanged, but persona-driven tone may be unexpected.
- **Custom agents fall through:** Agents defined in `~/.forge/agents/` (custom user agents) are not detected as `forgecode` by spellbook's `session_init`. Only the three built-in agents trigger forgecode-mode behavior. Custom agents will receive generic platform handling.
- No subagent support (Task tool unavailable)

## Provider authentication

Spellbook is provider-agnostic, but third-party harnesses often have constraints worth knowing before you wire up keys.

As of this writing (_Last reviewed: 2026-04_):

- **Claude Code:** First-party Anthropic harness; expects an Anthropic API key or Claude subscription.
- **OpenCode, Codex, Gemini CLI, ForgeCode:** Third-party harnesses that support multiple providers (OpenAI, Anthropic, Google, local models, etc.) via their own configuration. Spellbook does not impose additional auth requirements; refer to each harness's own documentation for provider setup.

When using Anthropic models through a third-party harness, the harness routes API calls using its own credentials and configuration; Spellbook does not proxy or intercept these calls. Rate limits, quotas, and feature support (prompt caching, extended thinking, tool use) depend on the harness's implementation, not on Spellbook.

_Last reviewed: 2026-04_

## Contributing Platform Support

If you use OpenCode, Codex, Gemini CLI, or ForgeCode and want fuller Spellbook coverage, contributions are welcome. See the [Porting Guide](../contributing/porting-to-your-assistant.md) for how to add or extend platform support.

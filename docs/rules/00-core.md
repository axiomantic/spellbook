# Spellbook Core

!!! warning "Mandatory module"
    This module installs on every platform and cannot be declined.

What spellbook is, how paths resolve, what runs at session start, and the shared vocabulary every other rule module assumes.

**Related artifacts:**

- `skills/session-mode-init`
- `skills/session-resume`
- `skills/audio-notifications`
- `skills/managing-artifacts`

## Rule Content

``````````markdown
<CRITICAL>
## What Spellbook Is (And Isn't)

Spellbook is a harness-augmentation layer. *You* (Claude Code, Antigravity, Codex, OpenCode, Gemini CLI, ForgeCode) are the harness: you own the agent loop, tool execution, and core conversational behavior. Spellbook adds a behavioral layer on top: skills, slash commands, hooks, profiles, and a shared MCP server (focus stints, session resume).

Operational consequence:

- The instructions in the spellbook rule modules augment your default behavior; they do not replace it. Where a spellbook rule is more specific than your default, follow the rule. Where the rule is silent, your default behavior stands.
- The MCP server (`spellbook_*` tools) is shared across harnesses on this machine, so stints stored in one harness are visible to another. Treat that shared state as authoritative.
- "Skill" and "command" references in the spellbook rule modules point at spellbook artifacts loaded into your environment, not built-in harness features.

## Spellbook Path Resolution

When interpreting `$SPELLBOOK_DIR` or `$SPELLBOOK_CONFIG_DIR` in skills, commands, and tools, resolve `SPELLBOOK_DIR` in this order and stop at the first step that succeeds:

1. **Environment Variables**: Use `$SPELLBOOK_DIR` or `$SPELLBOOK_CONFIG_DIR` if exported in your runtime environment.
2. **Machine Config File**: Read `~/.config/spellbook/paths.md`, which the installer writes at install time. This is the primary mechanism: it records the checkout location directly, so it works identically on every harness regardless of how the rule modules were delivered.
3. **Symlink Fallback (directory-capable harnesses only)**: If neither the environment variables nor the machine config file yields a path, and this file is a symlink into a spellbook checkout, resolve its symlink target and set `SPELLBOOK_DIR` to the parent of the target's parent directory. Two levels, not one: the target is `<spellbook_dir>/rules/00-core.md`, whose immediate parent is the `rules/` directory, and the checkout root is one level up from that. On a harness that receives the rules as a single generated file there is no symlink to resolve, and this step does not apply.

Independently of those steps: if `SPELLBOOK_CONFIG_DIR` is still unresolved once
`SPELLBOOK_DIR` is known, default it to `~/.local/spellbook`.

## You Are Reading This = Session Start

Execute these steps IN ORDER before responding to the user:

### Step 0: Platform Self-Identification

Identify your platform from your own system prompt or runtime context:

| Platform | Self-identification signal | `platform` value | Assistant Name |
|----------|---------------------------|------------------|----------------|
| Claude Code | You know you are Claude Code | `claude_code` | Claude |
| Antigravity | You know you are Antigravity or system prompt mentions Antigravity | `antigravity` | Antigravity |
| OpenCode | Your system prompt mentions OpenCode or YOLO mode | `opencode` | OpenCode |
| Codex | Your system prompt mentions Codex sandbox | `codex` | Codex |
| Gemini CLI | Your system prompt mentions Gemini CLI | `gemini` | Gemini |
| ForgeCode | Your system prompt opens with 'You are Forge', 'You are Sage', or 'You are Muse' (built-in agents only) | `forgecode` | Forge |

If uncertain, omit the `platform` parameter (backward compatible). Use the assistant name in greetings.

### Step 0.5: OpenCode Agent Inheritance (OpenCode Only)

<CRITICAL>
If platform is `opencode`, track and propagate agent type to all subagents.

**Detection:** Check system prompt:
- "operating in YOLO mode" -> `yolo`
- "YOLO mode with a focus on precision" -> `yolo-focused`
- No YOLO indicators -> `general` (default)

**Store as `CURRENT_AGENT_TYPE`.** When dispatching via Task tool:
- `CURRENT_AGENT_TYPE` is `yolo` or `yolo-focused`: pass that same value as `subagent_type`
- Do NOT use `general` or `explore` when parent is YOLO

**Exception:** Pure exploration (finding files, searching code) may use `explore` even when parent is YOLO.
</CRITICAL>

### Step 1: Session Mode and Resume Initialization

1. Call `spellbook_session_init` MCP tool with `platform` = your platform value from Step 0, and `continuation_message` = user's first message (if available)
2. Handle the response per the Session Mode rules in this module
3. If `resume_available: true`, follow the Session Resume rules in this module
4. Greet with "Welcome to spellbook-enhanced [assistant name]." If `admin_url` is present in the session_init response, append: "Admin: [admin_url]"

### Step 1.5: Profile Activation

If `session_init` returns a `profile` field, read and internalize its behavioral instructions.
The profile shapes your working style, tone, and collaboration patterns for this session.
Profile instructions have a lower priority than explicit user instructions and other core rules in this document.

### Step 2: Project Knowledge Check

1. Check if project has `AGENTS.md` (or your platform's configuration file that references it, e.g. `CLAUDE.md`). If it exists with content, read it silently for context.
2. For larger projects, also check for subdirectory `AGENTS.md` files relevant to the current work area and read those too.
3. If a rule module governing the project-knowledge offer protocol is installed, apply it to decide what to do when the file is missing, thin, or empty. If no such module is installed, read what exists and make no offer.

**Do NOT skip these steps.** They establish session context and persona.
</CRITICAL>

## Session Mode

Load `session-mode-init` skill for mode dispatch table and selection question. Handles fun/tarot/none modes.

## Session Resume

When `resume_available: true`, load `session-resume` skill and execute `resume_boot_prompt` immediately. The skill contains resume field definitions, protocol, continuation detection, and session repairs handling.

## MCP Tools

<RULE>If an MCP tool appears in your available tools list, call it directly. Do not run platform-specific diagnostic commands to verify availability. Your tools list is the source of truth.</RULE>

**MCP configuration location varies by platform:**
- Claude Code: User-scoped in `~/.claude.json`, project-scoped in `.mcp.json`
- OpenCode: Configured in `~/.config/opencode/config.json`
- Codex: Configured in `~/.codex/`
- Gemini CLI: Configured via extension system

## Glossary

| Term | Definition |
|------|------------|
| project-encoded | Path with leading `/` removed, slashes → dashes. `/Users/alice/proj` → `Users-alice-proj` |

Load `managing-artifacts` skill for artifact storage paths and project-encoded conventions.
``````````

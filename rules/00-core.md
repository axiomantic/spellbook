---
id: core
name: Spellbook Core
class: mandatory
description: >
  What spellbook is, how paths resolve, what runs at session start, and the
  shared vocabulary every other rule module assumes.
related:
  - skills/managing-artifacts
renamed_from: []
superseded_by: null
paths: []
---

<CRITICAL>
## What Spellbook Is (And Isn't)

Spellbook is a harness-augmentation layer. *You* (Claude Code, Antigravity, Codex, OpenCode, Gemini CLI, ForgeCode, Prime Agent) are the harness: you own the agent loop, tool execution, and core conversational behavior. Spellbook adds a behavioral layer on top: skills, slash commands, hooks, profiles, and a shared state layer (session resume). On platforms with MCP support (Claude Code, Antigravity, Codex, OpenCode, Gemini CLI), this is provided by an MCP server. On Prime Agent, this is provided by the continual harness (memories, skills, prompt notes).

Operational consequence:

- The instructions in the spellbook rule modules augment your default behavior; they do not replace it. Where a spellbook rule is more specific than your default, follow the rule. Where the rule is silent, your default behavior stands.
- On MCP-capable platforms, the `spellbook_*` tools are shared across harnesses on this machine. Treat shared state as authoritative. On Prime Agent, shared state is managed through the continual harness (memories, skills, prompt notes).
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
| Prime Agent | Your system prompt mentions Prime Agent, RLM, or IPython kernel | `prime_agent` | Prime Agent |

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

1. **On Prime Agent:** Check the continual harness (`rlm.harness.overview()`) for existing session state and memories.
   **On other platforms (Claude Code, Antigravity, Codex, OpenCode, Gemini CLI):** No MCP session tool to call — these platforms just start fresh per session. Skip to Step 2.
2. Greet with "Welcome to spellbook-enhanced [assistant name]."

### Step 2: Project Knowledge Check

1. Check if project has `AGENTS.md` (or your platform's configuration file that references it, e.g. `CLAUDE.md`). If it exists with content, read it silently for context.
2. For larger projects, also check for subdirectory `AGENTS.md` files relevant to the current work area and read those too.
3. If a rule module governing the project-knowledge offer protocol is installed, apply it to decide what to do when the file is missing, thin, or empty. If no such module is installed, read what exists and make no offer.

**Do NOT skip these steps.** They establish session context and persona.
</CRITICAL>

## Glossary

| Term | Definition |
|------|------------|
| project-encoded | Path with leading `/` removed, slashes → dashes. `/Users/alice/proj` → `Users-alice-proj` |

Load `managing-artifacts` skill for artifact storage paths and project-encoded conventions.

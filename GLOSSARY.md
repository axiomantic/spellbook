# Spellbook Glossary

Canonical definitions for spellbook-specific terms. Reference by name instead of re-explaining.

## Core Concepts

| Term | Definition |
|------|------------|
| **Skill** | A deferred-load instruction set with YAML frontmatter. Description always loaded; body loaded only when triggered. |
| **Command** | A slash-invoked action (`/foo`). Loaded on explicit invocation. |
| **Pattern** | A reusable prompt pattern referenced by skills. Lives in `patterns/`. |
| **MCP Tool** | A Model Context Protocol function callable by the LLM. Lives in `spellbook_mcp/`. |
| **Orchestrator** | The main LLM context managing subagents and skill invocation. |
| **Subagent** | A spawned LLM instance handling a delegated task. Returns results to orchestrator. |

## File Locations

| Term | Path |
|------|------|
| **SPELLBOOK_DIR** | Root of spellbook source repository |
| **SPELLBOOK_CONFIG_DIR** | `~/.local/spellbook/` - workspace for docs, plans, logs |
| **User config** | `~/.config/spellbook/spellbook.json` - user preferences |
| **Platform config** | `~/.claude/`, `~/.codex/`, etc. - platform-specific |

## Skill Lifecycle

| Term | Definition |
|------|------------|
| **Trigger** | Condition that causes a skill to load |
| **Deferred load** | Skill body not in context until triggered |
| **Always-loaded** | Content in context from session start (descriptions, CLAUDE.md) |

## Execution Modes

| Term | Definition |
|------|------------|
| **Plan mode** | Research and planning without code changes |
| **YOLO mode** | Execute without confirmation (still respects git safety) |
| **Parallel execution** | Multiple subagents running simultaneously |

## Quality Terms

| Term | Definition |
|------|------------|
| **Green mirage** | Tests that pass but don't verify actual behavior |
| **Instruction engineering** | Principles for writing effective LLM prompts |
| **Token budget** | Context window capacity consideration |

## Platform Terms

| Term | Definition |
|------|------------|
| **Claude Code** | Anthropic's CLI tool |
| **OpenCode** | Open-source Claude Code alternative |
| **Codex** | OpenAI's coding assistant |
| **Gemini CLI** | Google's CLI tool |

# Spellbook Skills Bootstrap for Codex

**EXTREMELY_IMPORTANT:** This file contains critical configuration for the spellbook skills system in Codex.

## What is Spellbook?

Spellbook is a centralized skills repository providing specialized workflows and domain knowledge across multiple AI coding platforms (Claude Code, Codex, OpenCode).

## EXTREMELY_IMPORTANT: Tool Mappings

Codex uses different tool names than Claude Code. Map Claude Code patterns to Codex equivalents:

| Claude Code Tool | Codex Equivalent | Usage |
|-----------------|------------------|-------|
| `TodoWrite` | `update_plan` | Update the conversation plan with task status |
| `Task` | **NOT AVAILABLE** | Tell user subagents are unavailable in Codex |
| `Skill` | `spellbook-codex` command | Use CLI script to load skills |

**EXTREMELY_IMPORTANT:** When a skill requires the Task tool for subagent orchestration, you MUST inform the user that subagent features are not available in Codex and suggest using Claude Code instead.

## Skill Naming Convention

All spellbook skills use kebab-case naming (lowercase with hyphens):
- `systematic-debugging` ✓
- `test-driven-development` ✓
- `SystematicDebugging` ✗
- `test_driven_development` ✗

## Loading Skills in Codex

Use the `spellbook-codex` CLI script to load skills:

```bash
# Load a specific skill
.codex/spellbook-codex use-skill <skill-name>

# List available skills
.codex/spellbook-codex list-skills

# Get help
.codex/spellbook-codex --help
```

The script validates skill names, resolves paths using priority order, and outputs markdown content with frontmatter stripped.

## EXTREMELY_IMPORTANT: Priority Resolution

Skills are resolved in this priority order:

1. **Personal skills** (`~/.codex/skills/`) - highest priority
2. **Spellbook skills** (`~/Development/spellbook/skills/`) - middle priority
3. **Superpowers skills** (built-in) - lowest priority

Personal customizations always override shared skills.

## EXTREMELY_IMPORTANT: Critical Rules

1. **Never modify skill files directly** - skills are version-controlled in the spellbook repository
2. **Always use kebab-case for skill names** - this is required for cross-platform compatibility
3. **Check tool availability** - not all Claude Code tools exist in Codex
4. **Validate skill names** - only alphanumeric, dash, underscore allowed (max 100 chars)
5. **Report missing features** - if a skill requires unavailable tools, inform the user clearly

## Skills Location

Spellbook skills are installed at: `~/Development/spellbook/skills/`

Each skill is a markdown file with:
- Frontmatter metadata (name, description, triggers)
- Workflow instructions
- Tool requirements
- Usage examples

## Integration Status

Codex integration is provided via:
- This bootstrap file (context)
- `spellbook-codex` CLI script (skill loading)
- Symlink at `~/.codex/spellbook` (optional, for easy access)

**EXTREMELY_IMPORTANT:** The `spellbook-codex` script is the ONLY supported way to load skills in Codex. Do not attempt to read skill files directly or implement custom loading logic.

# Spellbook Skills Bootstrap

This file provides context to Claude Code about the spellbook skills system.

## What is Spellbook?

Spellbook is a centralized skills repository that provides specialized workflows and domain knowledge across multiple AI coding platforms (Claude Code, Codex, OpenCode).

## Skill Priority Model

When multiple skills are available with the same name, they are resolved in this priority order:

1. **Personal skills** (`~/.claude/skills/`) - highest priority
2. **Spellbook skills** (`<spellbook-repo>/skills/`) - middle priority
3. **Superpowers skills** (built-in platform skills) - lowest priority

This ensures personal customizations always override shared skills, and shared skills override defaults.

## Namespace Syntax

Skills can be invoked using namespace prefixes:

- `spellbook:skill-name` - explicitly invoke from spellbook repository
- `personal:skill-name` - explicitly invoke from personal skills directory
- `skill-name` - use priority resolution order

The namespace syntax allows bypassing priority resolution when you need a specific version.

## Tool Availability in Claude Code

Claude Code provides these skill-related tools:

- `Skill` - invoke skills from available repositories
- `TodoWrite` - manage task lists within a conversation
- Standard file/git/bash tools for implementation work

## Spellbook Skills Location

Spellbook skills are installed at: `~/Development/spellbook/skills/`

Skills are organized as markdown files with frontmatter metadata defining:
- Skill name and description
- When to invoke the skill
- Workflow instructions
- Required tools and patterns

## Integration Notes

Claude Code can access spellbook skills automatically when they are properly registered in the skills configuration. The Skill tool handles namespace resolution and skill loading transparently.

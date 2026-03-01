# Spellbook for Gemini CLI

This extension provides AI assistant skills and workflows.

## Native Skills Support (Pending Release)

**Status:** Gemini CLI native skills support is pending [GitHub Issue #15327](https://github.com/google-gemini/gemini-cli/issues/15327).

As of January 7, 2026, this feature is unreleased. Once the epic is merged and released:
- Skills in `<extension>/skills/<skill-name>/SKILL.md` will be discovered automatically
- The spellbook extension pre-creates skill symlinks in `extensions/gemini/skills/` for this purpose

Until this lands in an official Gemini CLI release, skills are NOT automatically discovered. You can still use the spellbook MCP server's session and swarm coordination tools.

---

## Spellbook Instructions

@../../AGENTS.spellbook.md

## Gemini-Specific Tool Mapping

When skills reference tools you don't have, substitute Gemini equivalents:

- `Skill` tool → Use native skill loading from extension
- `TodoWrite` → Use Gemini's native task tracking if available
- `Task` tool with subagents → Not available in Gemini
- `Read`, `Write`, `Edit`, `Bash` → Your native tools

## Available Skills

Skills are loaded from this extension and available natively through Gemini CLI.
Refer to the skill descriptions in the main spellbook context for available skills.

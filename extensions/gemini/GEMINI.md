# Spellbook for Gemini CLI

This extension provides AI assistant skills and workflows.

## Spellbook Instructions

@../../CLAUDE.spellbook.md

## Gemini-Specific Tool Mapping

When skills reference tools you don't have, substitute Gemini equivalents:

- `Skill` tool → `spellbook.use_spellbook_skill` MCP tool
- `TodoWrite` → Use Gemini's native task tracking if available
- `Task` tool with subagents → Not available in Gemini
- `Read`, `Write`, `Edit`, `Bash` → Your native tools

## Discovering Skills

List all available skills:
```
spellbook.find_spellbook_skills()
```

## Using Skills

Load and follow a skill's workflow:
```
spellbook.use_spellbook_skill(skill_name="<skill-name>")
```

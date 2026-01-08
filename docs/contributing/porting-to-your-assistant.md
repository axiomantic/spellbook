# Porting Spellbook to Your Coding Assistant

This guide explains how to add Spellbook support to a new coding assistant platform.

## Requirements

Your coding assistant must support **agent skills** (also called "agent prompts" or "custom agents"):

- **Prompt files with trigger descriptions** - Skills are markdown files with descriptions like "Use when implementing features" or "Use when tests are failing"
- **Automatic activation** - The assistant reads the skill description and decides when to apply it based on user intent, not programmatic hooks
- **Context injection** - When a skill activates, its content becomes part of the assistant's instructions

### Examples of Supported Patterns

| Platform | Skill Format | Trigger Mechanism |
|----------|--------------|-------------------|
| Claude Code | `~/.claude/skills/<name>/SKILL.md` | Description in frontmatter |
| OpenCode | Reads from `~/.claude/skills/*` | Same format as Claude Code |
| Codex | `AGENTS.md` with skill definitions | Intent-based matching |
| Gemini CLI | Extension with skill files | Native extension system |
| Crush | `~/.claude/skills/*` via config | Same format as Claude Code |

### What Does NOT Work

- **MCP-only platforms** - MCP provides tools, not agent skills. Spellbook's workflows require skills that shape assistant behavior, not just callable functions.
- **Static system prompts** - Platforms that only support a single fixed prompt cannot use Spellbook's modular skill system.
- **Programmatic-only hooks** - If skills can only trigger on specific events (file save, command run), they cannot respond to user intent.

## Before You Start

1. **Verify skill support** - Check your platform's documentation for "agent skills", "custom agents", "agent prompts", or similar features
2. **Find the skill format** - What file format and location does your platform use?
3. **Understand the trigger mechanism** - How does your platform decide when to apply a skill?

If your platform doesn't support description-based skill activation, Spellbook cannot be meaningfully ported. Consider requesting this feature from your platform's developers.

## Porting Process

### Phase 1: Research

Search your platform's documentation for:

1. **Skill/agent file location** - Where are custom skills stored?
2. **Skill format** - Markdown with frontmatter? JSON? YAML?
3. **Context file location** - Where is the main system prompt/context file?
4. **Detection method** - How can the installer detect if your platform is installed?

Document your findings:
```
Platform: [name]
Skills location: [path]
Skills format: [format]
Context file: [path]
Detection: [method]
```

### Phase 2: Create the Installer

1. Fork `axiomantic/spellbook`
2. Create a feature branch: `feat/add-<platform>-support`
3. Read `installer/platforms/gemini.py` as the reference pattern
4. Create `installer/platforms/<platform>.py` implementing:
   - `detect()` - Check if platform is installed
   - `install()` - Create context file, symlink skills
   - `uninstall()` - Remove spellbook components
   - `get_context_files()` - Return context file paths
   - `get_symlinks()` - Return created symlinks

5. Register in `installer/config.py` and `installer/core.py`

### Phase 3: Test

```bash
# Dry-run first
uv run install.py --dry-run

# Actual installation
uv run install.py

# Verify skills are accessible in your platform
```

### Phase 4: Document

Update:
- `README.md` - Add to Platform Support table
- `docs/getting-started/platforms.md` - Add platform section

### Phase 5: Submit PR

```bash
git add -A
git commit -m "feat: add [Platform] support"
git push -u origin feat/add-<platform>-support
gh pr create --repo axiomantic/spellbook
```

## Questions?

Open an issue at [github.com/axiomantic/spellbook/issues](https://github.com/axiomantic/spellbook/issues) if you need help with the porting process.

# Spellbook

Personal AI assistant skills, commands, and configuration. Works with Claude Code and other AI coding assistants.

## What's Included

- **Skills** - Specialized workflows for common tasks (async patterns, debugging, code review, etc.)
- **Commands** - Slash commands for quick actions
- **CLAUDE.md** - Personal configuration and preferences

## Recommended Setup

For the complete experience, install these in order:

### 1. Heads Up Claude (Statusline)

Adds a statusline showing token usage and conversation stats.

```bash
git clone https://github.com/elijahr/heads-up-claude.git ~/Development/heads-up-claude
cd ~/Development/heads-up-claude
./install.sh
```

### 2. Superpowers (Core Workflows)

The foundation - provides brainstorming, planning, TDD, code review, and execution workflows.

```bash
# Via Claude Code plugin marketplace (recommended)
/plugin marketplace add obra/superpowers-marketplace
/plugin install superpowers@superpowers-marketplace
```

Or for local development:
```bash
git clone https://github.com/obra/superpowers.git ~/Development/superpowers
cd ~/Development/superpowers
# Follow install instructions in README
```

### 3. Spellbook (This Repo)

Your personal skills and configuration.

```bash
git clone https://github.com/elijahr/spellbook.git ~/Development/spellbook
cd ~/Development/spellbook
./install.sh
```

## Manual Installation

If you prefer manual setup:

```bash
# Create symlinks for skills
for skill in ~/Development/spellbook/skills/*/; do
  ln -sf "$skill" ~/.claude/skills/
done

# Create symlinks for commands
for cmd in ~/Development/spellbook/commands/*.md; do
  ln -sf "$cmd" ~/.claude/commands/
done

# Symlink CLAUDE.md
ln -sf ~/Development/spellbook/CLAUDE.md ~/.claude/CLAUDE.md
```

## Directory Structure

```
spellbook/
├── skills/           # Skill directories (each with SKILL.md)
│   ├── async-await-patterns/
│   ├── design-doc-reviewer/
│   ├── factchecker/
│   └── ...
├── commands/         # Slash command files
│   ├── compact.md
│   ├── move-project.md
│   └── ...
├── agents/           # Agent definitions (if any)
├── CLAUDE.md         # Personal configuration
├── install.sh        # Installation script
└── README.md         # This file
```

## Centralized Plans Directory

Design documents and implementation plans are stored in a centralized location:

```
~/.claude/plans/<project-dir-name>/YYYY-MM-DD-<plan-name>.md
```

This keeps planning artifacts outside of project repositories.

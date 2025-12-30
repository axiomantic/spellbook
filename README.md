# Spellbook

Personal AI assistant skills, commands, and configuration for Claude Code and other AI coding assistants.

## What's Included

- **Skills** - Specialized workflows that trigger automatically based on context (async patterns, debugging, code review, feature implementation, etc.)
- **Commands** - Slash commands for quick actions (`/compact`, `/move-project`, etc.)
- **CLAUDE.md** - Personal preferences and behavioral configuration

## Recommended Setup

For the complete experience, install these components in order:

### 1. Claude Code Proxy (Custom Compact Behavior)

A proxy that intercepts Claude Code requests, enabling:
- **Custom compact prompts** - Override the default `/compact` behavior with your own prompt (see `commands/compact.md`)
- **Automatic model upgrades** - Use Opus for compaction to get better context preservation
- **Alternative LLM providers** - Route requests to OpenAI-compatible APIs if desired

```bash
git clone https://github.com/elijahr/claude-code-proxy.git ~/Development/claude-code-proxy
cd ~/Development/claude-code-proxy
./install.sh
```

After installation, restart your shell. The `claude` command will automatically route through the proxy.

### 2. Heads Up Claude (Statusline)

Adds a statusline to Claude Code showing:
- Token usage estimates
- Conversation stats
- Model info

```bash
git clone https://github.com/elijahr/heads-up-claude.git ~/Development/heads-up-claude
cd ~/Development/heads-up-claude
./install.sh
```

### 3. Superpowers (Core Workflows)

The foundation for structured development workflows:
- **Brainstorming** - Collaborative design exploration before coding
- **Planning** - Detailed implementation plans with TDD, YAGNI, DRY
- **Execution** - Subagent-driven development with code review checkpoints
- **Git worktrees** - Isolated workspaces for feature development

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

### 4. Spellbook (This Repo)

Your personal skills and configuration, extending superpowers with:
- Domain-specific skills (Nim PR guide, async patterns, etc.)
- Custom commands
- Personal CLAUDE.md preferences

```bash
git clone https://github.com/elijahr/spellbook.git ~/Development/spellbook
cd ~/Development/spellbook
./install.sh
```

## Skills Included

| Skill | Purpose |
|-------|---------|
| `async-await-patterns` | Enforce proper async/await patterns in JS/TS code |
| `design-doc-reviewer` | Review design documents before implementation planning |
| `factchecker` | Verify claims and statements with evidence |
| `green-mirage-audit` | Audit test suites to ensure tests actually test what they claim |
| `implement-feature` | End-to-end feature implementation orchestrator |
| `implementation-plan-reviewer` | Review implementation plans for completeness |
| `instruction-engineering` | Prompt engineering patterns and techniques |
| `nim-pr-guide` | Guide for contributing PRs to the Nim language |
| `scientific-debugging` | Hypothesis-driven debugging methodology |
| `smart-merge` | Intelligent merge conflict resolution |
| `subagent-prompting` | Patterns for effective subagent prompts |

## Commands Included

| Command | Purpose |
|---------|---------|
| `/compact` | Custom compaction prompt (works with claude-code-proxy) |
| `/address-pr-feedback` | Systematically address PR review comments |
| `/green-mirage-audit` | Quick invocation of test audit skill |
| `/move-project` | Relocate a project with all references updated |

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

This keeps planning artifacts outside of project repositories, avoiding clutter and git noise.

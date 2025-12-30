# Spellbook

[![Tests](https://github.com/elijahr/spellbook/workflows/Test%20Spellbook/badge.svg)](https://github.com/elijahr/spellbook/actions)

Personal AI assistant skills, commands, and configuration for Claude Code and other AI coding assistants.

## What's Included

- **Skills** - Specialized workflows that trigger automatically based on context (async patterns, debugging, code review, feature implementation, etc.)
- **Commands** - Slash commands for quick actions (`/compact`, `/move-project`, etc.)
- **CLAUDE.md** - Personal preferences and behavioral configuration

## Platform Compatibility

Spellbook works across multiple AI coding platforms:

| Platform | Bootstrap Location | Auto-Load | Notes |
|----------|-------------------|-----------|-------|
| **Claude Code** | `~/.claude/` | Yes | Primary platform, full feature support |
| **OpenCode** | `~/.opencode/` | Yes | Compatible via shared structure |
| **Codex** | `.codex/spellbook-bootstrap.md` | Manual | Project-level bootstrap documentation |

### Platform-Specific Setup

**Claude Code / OpenCode**: Skills, commands, and CLAUDE.md are automatically loaded from `~/.claude/` or `~/.opencode/` directories. The installer creates symlinks to keep your configuration in sync.

**Codex**: Uses project-level bootstrap documentation. Copy `.codex/spellbook-bootstrap.md` to your project's `.codex/` directory and invoke the `spellbook-codex` script in your Codex session to load skills and configuration.

## Autonomous Mode

Some skills like `implement-feature` are designed for autonomous operation with minimal interruptions. To enable this mode in Claude Code:

```bash
claude --dangerously-skip-permissions
```

This allows the skill to execute multi-step workflows (git operations, file changes, test runs) without constant approval prompts. Use with caution and review changes before pushing.

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
git clone https://github.com/elijahr/superpowers.git ~/Development/superpowers
cd ~/Development/superpowers
./install.sh
```

**Important:** Spellbook requires [elijahr/superpowers](https://github.com/elijahr/superpowers), not the upstream [obra/superpowers](https://github.com/obra/superpowers). Our fork has critical enhancements, is not namespaced, and is designed to work seamlessly with spellbook. Do not use the marketplace version.

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

| Skill | Purpose | Platform | Auto-Triggers |
|-------|---------|----------|---------------|
| `async-await-patterns` | Enforce proper async/await patterns in JS/TS code | All | Writing async code |
| `design-doc-reviewer` | Review design documents before implementation planning | All | Reviewing design docs |
| `factchecker` | Verify claims and statements with evidence | All | Manual invocation |
| `green-mirage-audit` | Audit test suites to ensure tests actually test what they claim | All | Test review requests |
| `implement-feature` | End-to-end feature implementation orchestrator | All | Feature requests |
| `implementation-plan-reviewer` | Review implementation plans for completeness | All | Plan review |
| `instruction-engineering` | Prompt engineering patterns and techniques | All | Prompt work |
| `nim-pr-guide` | Guide for contributing PRs to the Nim language | All | Nim PR creation |
| `scientific-debugging` | Hypothesis-driven debugging methodology | All | Bug investigation |
| `smart-merge` | Intelligent merge conflict resolution | All | Merge conflicts |
| `subagent-prompting` | Patterns for effective subagent prompts | All | Subagent creation |

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

## Development

### Running Tests

```bash
# Run all tests
npm test

# Run tests in watch mode
npm run test:watch

# Run linter
npm run lint
```

### Test Structure

- `tests/helpers.sh` - Bash testing utilities
- `tests/unit/` - Vitest unit tests for skills
- `tests/integration/` - Integration tests for workflows

## Architecture

### Multi-Platform Bootstrap

Spellbook uses a multi-layer bootstrap approach to work across different AI coding platforms:

1. **Claude Code / OpenCode**: Skills and commands are auto-loaded from `~/.claude/` or `~/.opencode/` via symlinks created by `install.sh`. The `CLAUDE.md` configuration is also symlinked to provide consistent behavior.

2. **Codex**: Project-level bootstrap uses `.codex/spellbook-bootstrap.md` which documents all skills and their trigger conditions. The `spellbook-codex` script can be invoked in Codex sessions to load this documentation.

3. **Version Tracking**: The `.version` file and `RELEASE-NOTES.md` track releases and changes across platforms.

4. **CI/CD**: GitHub Actions run tests and linting on all platforms to ensure compatibility.

### Centralized Plans Directory

Design documents and implementation plans are stored in a centralized location:

```
~/.claude/plans/<project-dir-name>/YYYY-MM-DD-<plan-name>.md
```

This keeps planning artifacts outside of project repositories, avoiding clutter and git noise.

## Acknowledgments

Spellbook is inspired by and requires [elijahr/superpowers](https://github.com/elijahr/superpowers), our fork of the excellent [obra/superpowers](https://github.com/obra/superpowers) by Jesse Vincent.

Superpowers provides foundational workflow patterns (brainstorming, planning, execution, git worktrees) that spellbook extends with domain-specific skills. Our fork includes critical enhancements and is not namespaced, making it the required companion for spellbook.

## License

MIT License - See [LICENSE](LICENSE) for details.

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Spellbook](#spellbook)
  - [Prerequisites](#prerequisites)
  - [Quick Install](#quick-install)
  - [What's Included](#whats-included)
    - [Skills (28 total)](#skills-28-total)
    - [Commands (9 total)](#commands-9-total)
    - [Agents (1 total)](#agents-1-total)
  - [Platform Support](#platform-support)
  - [Companion Tools](#companion-tools)
    - [Heads Up Claude (Recommended)](#heads-up-claude-recommended)
    - [MCP Language Server (Recommended)](#mcp-language-server-recommended)
  - [Development](#development)
    - [Serve Documentation Locally](#serve-documentation-locally)
    - [Run MCP Server Directly](#run-mcp-server-directly)
  - [Documentation](#documentation)
  - [Acknowledgments](#acknowledgments)
  - [License](#license)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# Spellbook

Multi-platform AI assistant skills, commands, and configuration for Claude Code, OpenCode, Codex, and Gemini CLI.

**[Documentation](https://axiomantic.github.io/spellbook/)** | **[Getting Started](https://axiomantic.github.io/spellbook/getting-started/installation/)** | **[Skills Reference](https://axiomantic.github.io/spellbook/skills/)**

## Prerequisites

Install [uv](https://docs.astral.sh/uv/) (fast Python package manager):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Quick Install

One-liner:
```bash
curl -fsSL https://raw.githubusercontent.com/axiomantic/spellbook/main/bootstrap.sh | bash
```

Or manually:
```bash
git clone https://github.com/axiomantic/spellbook.git ~/.local/share/spellbook
cd ~/.local/share/spellbook
uv run install.py
```

**Upgrade:** `cd ~/.local/share/spellbook && git pull && uv run install.py`

**Uninstall:** `uv run ~/.local/share/spellbook/uninstall.py`

## What's Included

### Skills (28 total)

Reusable workflows for structured development:

| Category | Skills | Origin |
|----------|--------|--------|
| **Core Workflow** | brainstorming, writing-plans, executing-plans, test-driven-development, systematic-debugging, using-git-worktrees, finishing-a-development-branch | [superpowers] |
| **Code Quality** | green-mirage-audit, fix-tests, factchecker, find-dead-code, receiving-code-review, requesting-code-review | mixed |
| **Feature Dev** | implement-feature, design-doc-reviewer, implementation-plan-reviewer, devils-advocate, smart-merge | spellbook |
| **Specialized** | async-await-patterns, scientific-debugging, nim-pr-guide | spellbook |
| **Meta** | using-skills, writing-skills, subagent-prompting, instruction-engineering, dispatching-parallel-agents, subagent-driven-development, verification-before-completion | [superpowers] |

### Commands (9 total)

| Command | Description | Origin |
|---------|-------------|--------|
| `/compact` | Custom session compaction | spellbook |
| `/distill-session` | Extract knowledge from sessions | spellbook |
| `/simplify` | Code complexity reduction | spellbook |
| `/address-pr-feedback` | Handle PR review comments | spellbook |
| `/move-project` | Relocate projects safely | spellbook |
| `/green-mirage-audit` | Test suite audit | spellbook |
| `/brainstorm` | Design exploration | [superpowers] |
| `/write-plan` | Create implementation plan | [superpowers] |
| `/execute-plan` | Execute implementation plan | [superpowers] |

### Agents (1 total)

| Agent | Description | Origin |
|-------|-------------|--------|
| code-reviewer | Specialized code review | [superpowers] |

[superpowers]: https://github.com/obra/superpowers

## Platform Support

| Platform | Status | Details |
|----------|--------|---------|
| Claude Code | Full | Native skills + MCP server |
| OpenCode | Full | Plugin + CLI |
| Codex | Full | Bootstrap + CLI |
| Gemini CLI | Partial | MCP server + context file |

## Companion Tools

### Heads Up Claude (Recommended)

Statusline showing token usage and conversation stats.

```bash
git clone https://github.com/elijahr/heads-up-claude.git ~/Development/heads-up-claude
cd ~/Development/heads-up-claude && ./install.sh
```

### MCP Language Server (Recommended)

LSP integration for semantic code navigation.

```bash
git clone https://github.com/axiomantic/mcp-language-server.git ~/Development/mcp-language-server
cd ~/Development/mcp-language-server && go build
```

## Development

### Serve Documentation Locally

```bash
cd ~/.local/share/spellbook
uvx mkdocs serve
```

Then open http://127.0.0.1:8000

### Run MCP Server Directly

```bash
cd ~/.local/share/spellbook/spellbook_mcp
uv run server.py
```

## Documentation

Full documentation available at **[axiomantic.github.io/spellbook](https://axiomantic.github.io/spellbook/)**

- [Installation Guide](https://axiomantic.github.io/spellbook/getting-started/installation/)
- [Platform Support](https://axiomantic.github.io/spellbook/getting-started/platforms/)
- [Skills Reference](https://axiomantic.github.io/spellbook/skills/)
- [Commands Reference](https://axiomantic.github.io/spellbook/commands/)
- [Architecture](https://axiomantic.github.io/spellbook/reference/architecture/)
- [Contributing](https://axiomantic.github.io/spellbook/reference/contributing/)

## Acknowledgments

Spellbook includes skills, commands, agents, and hooks from [obra/superpowers](https://github.com/obra/superpowers) by Jesse Vincent. These foundational workflow patterns (brainstorming, planning, execution, git worktrees, TDD, debugging) form the core of spellbook's development methodology.

See [THIRD-PARTY-NOTICES](THIRD-PARTY-NOTICES) for full attribution and license details.

## License

MIT License - See [LICENSE](LICENSE) for details.

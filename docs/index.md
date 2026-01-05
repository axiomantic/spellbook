# Spellbook

Multi-platform AI assistant skills, commands, and configuration for Claude Code, OpenCode, Codex, and Gemini CLI.

## What is Spellbook?

Spellbook is a comprehensive collection of **skills** (reusable workflows), **commands** (slash commands), and **agents** (specialized reviewers) that enhance AI coding assistants. It provides structured approaches to:

- **Brainstorming** - Collaborative design exploration before coding
- **Planning** - Detailed implementation plans with TDD, YAGNI, DRY principles
- **Execution** - Subagent-driven development with code review checkpoints
- **Debugging** - Scientific and systematic debugging methodologies
- **Testing** - Test-driven development and test quality auditing
- **Code Review** - Structured review processes and feedback handling

## Quick Install

One command installs everything (including prerequisites like uv and Python if needed):

```bash
curl -fsSL https://raw.githubusercontent.com/axiomantic/spellbook/main/bootstrap.sh | bash
```

See [Installation Guide](getting-started/installation.md) for options and manual installation.

## Platform Support

| Platform | Status | Method |
|----------|--------|--------|
| Claude Code | Full | Native skills + MCP server |
| OpenCode | Full | Plugin + CLI |
| Codex | Full | Bootstrap + CLI |
| Gemini CLI | Partial | MCP server + context file |

## Attribution

Spellbook includes skills, commands, agents, and hooks from [obra/superpowers](https://github.com/obra/superpowers) by Jesse Vincent. See [Acknowledgments](acknowledgments.md) for full details.

## License

MIT License - See [LICENSE](https://github.com/axiomantic/spellbook/blob/main/LICENSE) for details.

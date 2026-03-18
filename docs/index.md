<p align="center">
  <img src="assets/logo.svg" alt="Spellbook" width="120" height="120">
</p>

<h1 align="center">Spellbook</h1>

<p align="center">
  Multi-platform AI assistant skills, commands, and configuration for Claude Code, OpenCode, Codex, Gemini CLI, and Crush.
</p>

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

## Key Skills

Five skills worth highlighting:

| Skill | What it does |
|-------|-------------|
| [develop](skills/develop.md) | Full-lifecycle feature orchestrator. Takes an idea through research, requirements discovery, design, planning, TDD implementation, code review, and branch finishing. Classifies complexity and enforces quality gates at every phase. |
| [fractal-thinking](skills/fractal-thinking.md) | Recursive question decomposition. Builds a persistent graph of sub-questions, dispatches parallel workers, detects convergence and contradiction across branches, and synthesizes answers bottom-up. Survives context boundaries. |
| [auditing-green-mirage](skills/auditing-green-mirage.md) | Test integrity auditor. Finds tests that pass but prove nothing: empty assertions, tautological checks, over-mocked reality, tests that cannot fail. |
| [fact-checking](skills/fact-checking.md) | Claim verification engine. Extracts claims from documents or code, dispatches parallel agents to trace each claim to codebase evidence, and produces a graded trust report. |
| [advanced-code-review](skills/advanced-code-review.md) | Multi-phase deep review. Builds a semantic model of the codebase, generates a review plan, analyzes across architectural, security, performance, and correctness dimensions, then verifies its own findings. |

## Attribution

Spellbook includes skills, commands, agents, and hooks from [obra/superpowers](https://github.com/obra/superpowers) by Jesse Vincent. See [Acknowledgments](acknowledgments.md) for full details.

## License

MIT License - See [LICENSE](https://github.com/axiomantic/spellbook/blob/main/LICENSE) for details.

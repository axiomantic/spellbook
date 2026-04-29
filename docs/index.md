<p align="center">
  <img src="assets/logo.svg" alt="Spellbook" width="120" height="120">
</p>

<h1 align="center">Spellbook</h1>

<p align="center">
  A harness-augmentation layer for AI coding assistants. Skills, commands, hooks, and a shared MCP server that runs across Claude Code, OpenCode, Codex, and Gemini CLI.
</p>

## What is Spellbook?

Spellbook is a harness-augmentation layer for AI coding assistants. The *harness* is the runtime that hosts the agent loop and executes tools (Claude Code, Codex, OpenCode, Gemini CLI). Spellbook plugs into whichever harness you are running and adds skills, slash commands, hooks, profiles, and a shared MCP server (memory, focus stints, session resume) on top.

Three things distinguish it from harness-native features and from other skill collections:

- **Harness-agnostic.** The same skills, commands, and memory work across every supported harness on the same project. Switch from Claude Code to OpenCode mid-task and the workflow continues.
- **Shared centralized MCP server.** Memories, focus stints, and session-resume state live in one place, so context stored from a Claude Code session surfaces in an OpenCode session on the same repo. No individual harness ships this.
- **Skills + hooks layer no harness ships natively.** Autonomy enforcement, quality gates, parallel subagent dispatch, and a session resume protocol sit on top of whatever the harness provides.

In practice: **skills** (reusable workflows), **commands** (slash commands), and **agents** (specialized reviewers) covering:

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


<p align="center">
  <img src="./docs/assets/logo-book.svg" alt="Spellbook" width="300">
</p>

<h1 align="center">Spellbook</h1>

<p align="center">
  <em>Principled development on autopilot. Decades of engineering expertise, built in.</em><br>
  For Claude Code, OpenCode, Codex, Gemini CLI, and Crush.
</p>

<p align="center">
  <a href="https://github.com/axiomantic/spellbook/blob/main/LICENSE"><img src="https://img.shields.io/github/license/axiomantic/spellbook?style=flat-square" alt="License"></a>
  <a href="https://github.com/axiomantic/spellbook/stargazers"><img src="https://img.shields.io/github/stars/axiomantic/spellbook?style=flat-square" alt="Stars"></a>
  <a href="https://github.com/axiomantic/spellbook/issues"><img src="https://img.shields.io/github/issues/axiomantic/spellbook?style=flat-square" alt="Issues"></a>
  <a href="https://axiomantic.github.io/spellbook/"><img src="https://img.shields.io/badge/docs-GitHub%20Pages-blue?style=flat-square" alt="Documentation"></a>
</p>

<p align="center">
  <a href="https://github.com/axiomantic/spellbook"><img src="https://img.shields.io/badge/Built%20with-Spellbook-6B21A8?style=for-the-badge&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxNzAuNjY3IiBoZWlnaHQ9IjE3MC42NjciIHZpZXdCb3g9IjAgMCAxMjggMTI4IiBmaWxsPSIjRkZGIiB4bWxuczp2PSJodHRwczovL3ZlY3RhLmlvL25hbm8iPjxwYXRoIGQ9Ik0yMy4xNjggMTIwLjA0YTMuODMgMy44MyAwIDAgMCAxLjM5MSA0LjI4NWMxLjM0NC45NzcgMy4xNjQuOTc3IDQuNTA4IDBMNjQgOTguOTVsMzQuOTMgMjUuMzc1YTMuODEgMy44MSAwIDAgMCAyLjI1NC43MzQgMy44IDMuOCAwIDAgMCAyLjI1NC0uNzM0IDMuODMgMy44MyAwIDAgMCAxLjM5MS00LjI4NWwtMTMuMzQtNDEuMDY2IDM0LjkzLTI1LjM3OWEzLjgzIDMuODMgMCAwIDAgMS4zOTQtNC4yODVjLS41MTItMS41ODItMS45ODQtMi42NDgtMy42NDQtMi42NDhsLTQzLjE4NC4wMDQtMTMuMzQtNDEuMDdDNjcuMTI5IDQuMDE3IDY1LjY2IDIuOTUxIDY0IDIuOTUxcy0zLjEzMyAxLjA2Ni0zLjY0OCAyLjY0NWwtMTMuMzQgNDEuMDY2SDMuODMyYy0xLjY2IDAtMy4xMzMgMS4wNjYtMy42NDQgMi42NDhzLjA0NyAzLjMwNSAxLjM5MSA0LjI4NWwzNC45MyAyNS4zNzl6bTEwLjkzNC04Ljg0NGw4LjkzNC0yNy40OCAxNC40NDkgMTAuNDk2em01OS43OTMgMEw3MC41MTYgOTQuMjA4bDE0LjQ0OS0xMC40OTZ6bTE4LjQ3Ny01Ni44NjdMODguOTkzIDcxLjMxM2wtNS41MTYtMTYuOTg0ek02NC4wMDEgMTkuMTgxbDguOTMgMjcuNDg0SDU1LjA2OHpNNTIuNTc5IDU0LjMyOWgyMi44NGw3LjA1OSAyMS43MjMtMTguNDc3IDEzLjQyNi0xOC40OC0xMy40MjZ6bS0zNi45NTMgMGgyOC44OTVsLTUuNTE2IDE2Ljk4NHoiLz48L3N2Zz4=" alt="Built with Spellbook"></a>
</p>

<p align="center">
  <a href="https://axiomantic.github.io/spellbook/"><strong>Documentation</strong></a> ·
  <a href="https://axiomantic.github.io/spellbook/getting-started/installation/"><strong>Getting Started</strong></a> ·
  <a href="https://axiomantic.github.io/spellbook/skills/"><strong>Skills Reference</strong></a>
</p>

---
## Table of Contents

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Prerequisites](#prerequisites)
- [Quick Install](#quick-install)
- [What's Included](#whats-included)
  - [Skills (26 total)](#skills-26-total)
  - [Commands (15 total)](#commands-15-total)
  - [Agents (1 total)](#agents-1-total)
- [Platform Support](#platform-support)
  - [YOLO Mode](#yolo-mode)
- [Playbooks](#playbooks)
  - [Implementing a Feature](#implementing-a-feature)
  - [Large Feature with Context Exhaustion](#large-feature-with-context-exhaustion)
  - [Test Suite Audit and Remediation](#test-suite-audit-and-remediation)
  - [Parallel Worktree Development](#parallel-worktree-development)
  - [Cross-Assistant Handoff](#cross-assistant-handoff)
- [Recommended Companion Tools](#recommended-companion-tools)
  - [Heads Up Claude](#heads-up-claude)
  - [MCP Language Server](#mcp-language-server)
- [Development](#development)
  - [Serve Documentation Locally](#serve-documentation-locally)
  - [Run MCP Server Directly](#run-mcp-server-directly)
- [Documentation](#documentation)
- [Contributing](#contributing)
- [Acknowledgments](#acknowledgments)
- [Attribution](#attribution)
- [License](#license)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
---

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

### Skills (26 total)

Reusable workflows for structured development:

| Category | Skills | Origin |
|----------|--------|--------|
| **Core Workflow** | [brainstorming], [writing-plans], [executing-plans], [test-driven-development], [debug], [using-git-worktrees], [finishing-a-development-branch] | [superpowers] |
| **Code Quality** | [green-mirage-audit], [fix-tests], [factchecker], [find-dead-code], [receiving-code-review], [requesting-code-review] | mixed |
| **Feature Dev** | [implement-feature], [design-doc-reviewer], [implementation-plan-reviewer], [devils-advocate], [smart-merge] | spellbook |
| **Specialized** | [async-await-patterns], [nim-pr-guide] | spellbook |
| **Meta** | [using-skills], [writing-skills], [subagent-prompting], [instruction-engineering], [dispatching-parallel-agents], [subagent-driven-development] | [superpowers] |

[brainstorming]: https://axiomantic.github.io/spellbook/latest/skills/brainstorming/
[writing-plans]: https://axiomantic.github.io/spellbook/latest/skills/writing-plans/
[executing-plans]: https://axiomantic.github.io/spellbook/latest/skills/executing-plans/
[test-driven-development]: https://axiomantic.github.io/spellbook/latest/skills/test-driven-development/
[debug]: https://axiomantic.github.io/spellbook/latest/skills/debug/
[using-git-worktrees]: https://axiomantic.github.io/spellbook/latest/skills/using-git-worktrees/
[green-mirage-audit]: https://axiomantic.github.io/spellbook/latest/skills/green-mirage-audit/
[fix-tests]: https://axiomantic.github.io/spellbook/latest/skills/fix-tests/
[factchecker]: https://axiomantic.github.io/spellbook/latest/skills/factchecker/
[find-dead-code]: https://axiomantic.github.io/spellbook/latest/skills/find-dead-code/
[receiving-code-review]: https://axiomantic.github.io/spellbook/latest/skills/receiving-code-review/
[requesting-code-review]: https://axiomantic.github.io/spellbook/latest/skills/requesting-code-review/
[implement-feature]: https://axiomantic.github.io/spellbook/latest/skills/implement-feature/
[design-doc-reviewer]: https://axiomantic.github.io/spellbook/latest/skills/design-doc-reviewer/
[implementation-plan-reviewer]: https://axiomantic.github.io/spellbook/latest/skills/implementation-plan-reviewer/
[devils-advocate]: https://axiomantic.github.io/spellbook/latest/skills/devils-advocate/
[smart-merge]: https://axiomantic.github.io/spellbook/latest/skills/smart-merge/
[async-await-patterns]: https://axiomantic.github.io/spellbook/latest/skills/async-await-patterns/
[nim-pr-guide]: https://axiomantic.github.io/spellbook/latest/skills/nim-pr-guide/
[using-skills]: https://axiomantic.github.io/spellbook/latest/skills/using-skills/
[writing-skills]: https://axiomantic.github.io/spellbook/latest/skills/writing-skills/
[subagent-prompting]: https://axiomantic.github.io/spellbook/latest/skills/subagent-prompting/
[instruction-engineering]: https://axiomantic.github.io/spellbook/latest/skills/instruction-engineering/
[dispatching-parallel-agents]: https://axiomantic.github.io/spellbook/latest/skills/dispatching-parallel-agents/
[subagent-driven-development]: https://axiomantic.github.io/spellbook/latest/skills/subagent-driven-development/
[finishing-a-development-branch]: https://axiomantic.github.io/spellbook/latest/skills/finishing-a-development-branch/

### Commands (15 total)

| Command | Description | Origin |
|---------|-------------|--------|
| [/shift-change] | Custom session compaction | spellbook |
| [/distill-session] | Extract knowledge from sessions | spellbook |
| [/simplify] | Code complexity reduction | spellbook |
| [/address-pr-feedback] | Handle PR review comments | spellbook |
| [/move-project] | Relocate projects safely | spellbook |
| [/green-mirage-audit] | Test suite audit | spellbook |
| [/verify] | Verification before completion | [superpowers]* |
| [/systematic-debugging] | Methodical debugging workflow | [superpowers]* |
| [/scientific-debugging] | Hypothesis-driven debugging | spellbook |
| [/brainstorm] | Design exploration | [superpowers] |
| [/write-plan] | Create implementation plan | [superpowers] |
| [/execute-plan] | Execute implementation plan | [superpowers] |
| [/execute-work-packet] | Execute a single work packet with TDD | spellbook |
| [/execute-work-packets-seq] | Execute all packets sequentially | spellbook |
| [/merge-work-packets] | Merge completed packets with QA gates | spellbook |

*\* Converted from skill to command. Originally `verification-before-completion` and `systematic-debugging` skills in superpowers.*

[/shift-change]: https://axiomantic.github.io/spellbook/latest/commands/shift-change/
[/distill-session]: https://axiomantic.github.io/spellbook/latest/commands/distill-session/
[/simplify]: https://axiomantic.github.io/spellbook/latest/commands/simplify/
[/address-pr-feedback]: https://axiomantic.github.io/spellbook/latest/commands/address-pr-feedback/
[/move-project]: https://axiomantic.github.io/spellbook/latest/commands/move-project/
[/green-mirage-audit]: https://axiomantic.github.io/spellbook/latest/commands/green-mirage-audit/
[/verify]: https://axiomantic.github.io/spellbook/latest/commands/verify/
[/systematic-debugging]: https://axiomantic.github.io/spellbook/latest/commands/systematic-debugging/
[/scientific-debugging]: https://axiomantic.github.io/spellbook/latest/commands/scientific-debugging/
[/brainstorm]: https://axiomantic.github.io/spellbook/latest/commands/brainstorm/
[/write-plan]: https://axiomantic.github.io/spellbook/latest/commands/write-plan/
[/execute-plan]: https://axiomantic.github.io/spellbook/latest/commands/execute-plan/
[/execute-work-packet]: https://axiomantic.github.io/spellbook/latest/commands/execute-work-packet/
[/execute-work-packets-seq]: https://axiomantic.github.io/spellbook/latest/commands/execute-work-packets-seq/
[/merge-work-packets]: https://axiomantic.github.io/spellbook/latest/commands/merge-work-packets/

### Agents (1 total)

| Agent | Description | Origin |
|-------|-------------|--------|
| [code-reviewer] | Specialized code review | [superpowers] |

[code-reviewer]: https://axiomantic.github.io/spellbook/latest/agents/code-reviewer/
[superpowers]: https://github.com/obra/superpowers

## Platform Support

| Platform | Status | Details |
|----------|--------|---------|
| Claude Code | Full | Native agent skills |
| OpenCode | Full | Native agent skills |
| Codex | Full | Native agent skills |
| Gemini CLI | Full[^1] | Native agent skills |
| Crush | Full | Native agent skills |

[^1]: Gemini does not yet support agent skills, but it is actively being worked on by the Gemini team. Spellbook skills are already installed to ~/.gemini/extensions/spellbook/skills and should begin working as soon as Gemini releases the feature. You can follow the epic's progress here: https://github.com/google-gemini/gemini-cli/issues/15327

### YOLO Mode

> [!CAUTION]
> **YOLO mode gives your AI assistant full control of your system.**
>
> It can execute arbitrary commands, write and delete files, install packages, and make irreversible changes without asking permission. A misconfigured workflow or hallucinated command can corrupt your project, expose secrets, or worse.
>
> **Cost warning:** YOLO mode sessions can run indefinitely without human checkpoints. This means:
> - Per-token or usage-based pricing can accumulate rapidly
> - Credit limits or usage caps can be exhausted in a single session
> - Long-running tasks may consume significantly more resources than expected
>
> **Only enable YOLO mode when:**
> - Working in an isolated environment (container, VM, disposable branch)
> - You have tested the workflow manually first
> - You have backups and version control
> - You understand what each platform's flag actually permits
> - You have set appropriate spending limits or usage caps
>
> **You are responsible for what it does.** Review platform documentation before enabling.

For fully automated workflows (no permission prompts), each platform has its own flag:

| Platform | Command | What it does |
|----------|---------|--------------|
| Claude Code | `claude --dangerously-skip-permissions` | Skips all permission prompts |
| Gemini CLI | `gemini --yolo` | Enables autonomous execution |
| OpenCode | `opencode --agent yolo`[^2] | Spellbook agent with all tools allowed |
| OpenCode | `opencode --agent yolo-focused`[^2] | Spellbook agent, low temp for precision |
| Codex | `codex --full-auto` | Workspace writes + on-request approval |
| Codex | `codex --yolo` | Bypasses all approvals and sandbox |
| Crush | `crush --yolo` | Bypasses all permission prompts |

[^2]: The `yolo` and `yolo-focused` agents are provided by spellbook, not built into OpenCode. They are [OpenCode agent definitions](https://opencode.ai/docs/agents/) with `permission: "*": "*": allow` for all tools, installed to `~/.config/opencode/agent/` by the spellbook installer.

Without YOLO mode, you'll be prompted to approve each file write, command execution, etc. The workflows still function, but require manual approval at each step.

**OpenCode YOLO agents (spellbook-provided):**
- `yolo` (temperature 0.7): Balanced agent for general autonomous work
- `yolo-focused` (temperature 0.2): Precision agent for refactoring, bug fixes, and mechanical tasks

These agents grant "allow" permission for all tools (write, edit, bash, webfetch, task). They are symlinked from `spellbook/opencode/agent/` to `~/.config/opencode/agent/` during installation.

See platform documentation for details: [Claude Code](https://docs.anthropic.com/en/docs/claude-code), [OpenCode](https://opencode.ai/docs/agents/), [Codex](https://developers.openai.com/codex/cli/reference/), [Gemini CLI](https://github.com/google-gemini/gemini-cli), [Crush](https://github.com/charmbracelet/crush).

## Playbooks

Real-world usage patterns with example transcripts.

### Implementing a Feature

The core workflow: request a feature, answer a few questions, and let the skill handle research, design, and implementation.

```
╭─────────────────────────────────────────────────────────────────────────────╮
│ > Add dark mode toggle to settings                                          │
╰─────────────────────────────────────────────────────────────────────────────╯

⏺ Skill(implement-feature)

  I'll help implement dark mode. First, let me gather preferences.

⏺ AskUserQuestion

  ╭─────────────────────────────────────────────────────────────────────────╮
  │ Execution mode                                                          │
  ├─────────────────────────────────────────────────────────────────────────┤
  │ ○ Fully autonomous (Recommended)                                        │
  │ ○ Interactive                                                           │
  ╰─────────────────────────────────────────────────────────────────────────╯

> Fully autonomous

⏺ Task(Explore)

  ⎿ Found: src/context/ThemeContext.tsx, src/components/Settings.tsx
    React app with styled-components, existing light theme only.

⏺ AskUserQuestion

  ╭─────────────────────────────────────────────────────────────────────────╮
  │ Theme persistence                                                       │
  ├─────────────────────────────────────────────────────────────────────────┤
  │ ○ localStorage (Recommended)                                            │
  │ ○ User account (backend)                                                │
  │ ○ System preference only                                                │
  ╰─────────────────────────────────────────────────────────────────────────╯

> localStorage

⏺ Writing design doc...
  ✓ ~/.local/spellbook/docs/.../plans/dark-mode-design.md

⏺ Writing implementation plan...
  ✓ ~/.local/spellbook/docs/.../plans/dark-mode-impl.md

⏺ Task(Implement ThemeContext updates)
  ⎿ Tests written, implementation complete, code review passed

⏺ Task(Add toggle to Settings)
  ⎿ Tests written, implementation complete, code review passed

⏺ Task(Add CSS variables)
  ⎿ Tests written, implementation complete, code review passed

✓ All tests passing. Dark mode implemented.
  Ready to merge or create PR.
```

### Large Feature with Context Exhaustion

When implementing a complex feature, context can fill up before work completes. The workflow handles this gracefully.

```
╭─────────────────────────────────────────────────────────────────────────────╮
│ > Implement webhook delivery with retry logic and dead letter queue         │
╰─────────────────────────────────────────────────────────────────────────────╯

⏺ Skill(implement-feature)

  I'll help you implement the webhook delivery system. Let me first
  understand the current codebase architecture and gather requirements.

⏺ Task(Explore)

  ⎿ Found: src/events/, src/queue/, src/models/Webhook.ts
    Current event system uses Redis pub/sub. No existing retry logic.

⏺ AskUserQuestion

  ╭─────────────────────────────────────────────────────────────────────────╮
  │ Retry strategy                                                          │
  ├─────────────────────────────────────────────────────────────────────────┤
  │ ○ Exponential backoff (Recommended)                                     │
  │ ○ Fixed interval                                                        │
  │ ○ Linear backoff                                                        │
  ╰─────────────────────────────────────────────────────────────────────────╯

> Exponential backoff

⏺ Writing implementation plan to:
  ~/.local/spellbook/docs/Users-me-myproject/plans/webhook-delivery-impl.md

  ...

⏺ Task(Backend API) [in background]
  ⎿ Implementing retry queue with exponential backoff...

⏺ Task(Worker Service) [in background]
  ⎿ Building delivery worker with circuit breaker...

⏺ Task(Dead Letter Queue) [in background]
  ⎿ Setting up DLQ with monitoring hooks...

  ...

⏺ Task Output(non-blocking) ad8b5e4
  ⎿ Task is still running…

╭─────────────────────────────────────────────────────────────────────────────╮
│ ⚠ Context low · Run /compact to compact & continue                         │
╰─────────────────────────────────────────────────────────────────────────────╯
```

When context runs low, name and distill the session for later:

```
╭─────────────────────────────────────────────────────────────────────────────╮
│ > /rename-session webhook-delivery                                          │
╰─────────────────────────────────────────────────────────────────────────────╯

⏺ Session renamed to: webhook-delivery

╭─────────────────────────────────────────────────────────────────────────────╮
│ > /distill-session webhook-delivery                                         │
╰─────────────────────────────────────────────────────────────────────────────╯

⏺ Skill(distill-session)

  Found session: webhook-delivery
  Processing 847 messages across 3 compact boundaries...

  ⏺ Task(Chunk 1 Summary) [in background]
  ⏺ Task(Chunk 2 Summary) [in background]
  ⏺ Task(Chunk 3 Summary) [in background]

  Synthesizing summaries...

  ✓ Distilled session saved to:
    ~/.local/spellbook/distilled/Users-me-myproject/webhook-delivery-20260106-143022.md

  To continue in a new session:
    1. Start new Claude Code session
    2. Type: "continue work from ~/.local/spellbook/distilled/Users-me-myproject/
              webhook-delivery-20260106-143022.md"
```

Start fresh and resume exactly where you left off:

```
╭─────────────────────────────────────────────────────────────────────────────╮
│ > /clear                                                                    │
╰─────────────────────────────────────────────────────────────────────────────╯

╭─────────────────────────────────────────────────────────────────────────────╮
│ > continue work from ~/.local/spellbook/distilled/Users-me-myproject/       │
│   webhook-delivery-20260106-143022.md                                       │
╰─────────────────────────────────────────────────────────────────────────────╯

⏺ Read(~/.local/spellbook/distilled/.../webhook-delivery-20260106-143022.md)

⏺ SECTION 0: MANDATORY FIRST ACTIONS

  Executing restoration sequence...

⏺ Skill(implement-feature, --resume-from Phase3.Task4)

  Resuming webhook delivery implementation.

  Prior work completed:
  ✓ Design approved (exponential backoff, 5 retries, 1hr max)
  ✓ Database migrations for delivery_attempts table
  ✓ Retry queue infrastructure
  ○ Worker service (in progress - 60% complete)
  ○ Dead letter queue
  ○ Monitoring dashboard

⏺ Read(~/.local/spellbook/docs/.../webhook-delivery-impl.md)

  Continuing from Phase 3, Task 4: Complete worker service...
```

### Test Suite Audit and Remediation

Discover tests that pass but don't actually verify behavior, then fix them.

```
╭─────────────────────────────────────────────────────────────────────────────╮
│ > /green-mirage-audit                                                       │
╰─────────────────────────────────────────────────────────────────────────────╯

⏺ Skill(green-mirage-audit)

  Analyzing test suite: tests/**/*.test.ts
  Found 247 test cases across 34 files.

  ⏺ Task(Analyze auth tests) [in background]
  ⏺ Task(Analyze api tests) [in background]
  ⏺ Task(Analyze util tests) [in background]

  ...

  ✓ Audit complete. Report saved to:
    ~/.local/spellbook/docs/Users-me-myproject/audits/green-mirage-audit-20260106-091522.md

  Summary:
  ┌─────────────────────────────────────────────────────────────────────────┐
  │ SOLID (actually verify behavior)      │ 189 tests (76%)                │
  │ GREEN MIRAGE (false confidence)       │  58 tests (24%)                │
  │                                       │                                │
  │ Critical issues:                      │                                │
  │   • 12 tests mock the thing tested    │                                │
  │   • 8 tests have no meaningful assert │                                │
  │   • 38 tests check implementation     │                                │
  └─────────────────────────────────────────────────────────────────────────┘

╭─────────────────────────────────────────────────────────────────────────────╮
│ > Fix the critical issues from the audit                                    │
╰─────────────────────────────────────────────────────────────────────────────╯

⏺ Skill(fix-tests)

  Loading audit report...
  Found 58 tests requiring remediation.

  Starting with highest-impact fixes (mocked implementations)...

⏺ Read(tests/auth/login.test.ts)

⏺ Edit(tests/auth/login.test.ts)

  - jest.mock('../services/AuthService')  // Mocks the thing we're testing!
  + // Test actual AuthService behavior with test database
```

### Parallel Worktree Development

Split work across isolated branches, merge when complete.

```
╭─────────────────────────────────────────────────────────────────────────────╮
│ > Let's design a new notification system                                    │
╰─────────────────────────────────────────────────────────────────────────────╯

⏺ Skill(brainstorming)

  I'll explore the notification system requirements with you.

  ...design discussion, interface contracts established...

  Design document saved to:
    ~/.local/spellbook/docs/Users-me-myproject/plans/notifications-design.md

╭─────────────────────────────────────────────────────────────────────────────╮
│ > Set up worktrees to implement this in parallel                            │
╰─────────────────────────────────────────────────────────────────────────────╯

⏺ Skill(using-git-worktrees)

  Creating isolated worktrees for parallel development:

  ✓ .worktrees/notif-backend     (branch: feature/notif-backend)
  ✓ .worktrees/notif-frontend    (branch: feature/notif-frontend)
  ✓ .worktrees/notif-tests       (branch: feature/notif-tests)

  Interface contracts copied to each worktree.

╭─────────────────────────────────────────────────────────────────────────────╮
│ > Work on all three tracks                                                  │
╰─────────────────────────────────────────────────────────────────────────────╯

⏺ Task(.worktrees/notif-backend) [in background]
  ⎿ Implementing notification service, queue, templates...

⏺ Task(.worktrees/notif-frontend) [in background]
  ⎿ Building NotificationCenter component, hooks, real-time updates...

⏺ Task(.worktrees/notif-tests) [in background]
  ⎿ Writing integration tests against interface contracts...

  ...

╭─────────────────────────────────────────────────────────────────────────────╮
│ > Merge the worktrees back together                                         │
╰─────────────────────────────────────────────────────────────────────────────╯

⏺ Skill(smart-merge)

  Analyzing 3 worktrees for merge:

  Step 1: Dependency analysis
    notif-tests depends on: notif-backend, notif-frontend
    notif-frontend depends on: notif-backend (types only)
    notif-backend: no dependencies (merge first)

  Step 2: 3-way diff analysis
    No conflicts detected. Interface contracts honored.

  Step 3: Merge sequence
    ✓ Merged notif-backend → main
    ✓ Merged notif-frontend → main
    ✓ Merged notif-tests → main

  Step 4: Validation
    ✓ All tests pass
    ✓ Type check clean
    ✓ Worktrees cleaned up

  Ready to push or create PR.
```

### Cross-Assistant Handoff

Move work between different AI coding assistants without losing context.

```
# In Codex, context is running low on a complex refactor...

╭─────────────────────────────────────────────────────────────────────────────╮
│ > /distill-session                                                          │
╰─────────────────────────────────────────────────────────────────────────────╯

⏺ Session distilled to:
  ~/.local/spellbook/distilled/Users-me-myproject/refactor-auth-20260106-162033.md

# Open Claude Code CLI in terminal...

╭─────────────────────────────────────────────────────────────────────────────╮
│ > continue work from ~/.local/spellbook/distilled/Users-me-myproject/       │
│   refactor-auth-20260106-162033.md                                          │
╰─────────────────────────────────────────────────────────────────────────────╯

⏺ Loading distilled session...

  Context restored:
  • Refactoring auth from session-based to JWT
  • 4 of 7 services migrated
  • Current: PaymentService (blocked on token refresh)
  • Decision: Chose sliding window refresh (not fixed expiry)

  Continuing with PaymentService migration...
```

The distilled file compresses ~50K tokens of conversation into ~3K words of actionable context.

## Recommended Companion Tools

These tools are not necessary but contribute to better development workflows with coding assistants.

### Heads Up Claude

Statusline for Claude Code CLI showing token usage and conversation stats. Helps you track how much context you have left and how much of your subscription quota you have used.

```bash
git clone https://github.com/axiomantic/heads-up-claude.git ~/Development/heads-up-claude
cd ~/Development/heads-up-claude && ./install.sh
```

### MCP Language Server

LSP integration for semantic code navigation, refactoring, and more.

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

## Contributing

**Want Spellbook on your coding assistant?** (Cursor, Cline, Roo, Kilo, Continue, GitHub Copilot, etc.)

Spellbook requires **agent skills** support. Agent skills are prompt files that automatically activate based on trigger descriptions (e.g., "Use when implementing features" or "Use when tests are failing"). This is different from MCP tools or programmatic hooks.

If your assistant supports agent skills with description-based triggers, see the [**Porting Guide**](docs/contributing/porting-to-your-assistant.md) for instructions on adding support. We appreciate contributions!

## Acknowledgments

Spellbook includes many skills, commands, agents, and hooks from [obra/superpowers](https://github.com/obra/superpowers) by Jesse Vincent. These workflow patterns (brainstorming, planning, execution, git worktrees, TDD, debugging) are a core part of spellbook's development methodology.

See [THIRD-PARTY-NOTICES](THIRD-PARTY-NOTICES) for full attribution and license details.

## Attribution

Built something with Spellbook? We'd love to see it! Add this badge to your project:

```markdown
[![Built with Spellbook](https://img.shields.io/badge/Built%20with-Spellbook-6B21A8?style=for-the-badge&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxNzAuNjY3IiBoZWlnaHQ9IjE3MC42NjciIHZpZXdCb3g9IjAgMCAxMjggMTI4IiBmaWxsPSIjRkZGIiB4bWxuczp2PSJodHRwczovL3ZlY3RhLmlvL25hbm8iPjxwYXRoIGQ9Ik0yMy4xNjggMTIwLjA0YTMuODMgMy44MyAwIDAgMCAxLjM5MSA0LjI4NWMxLjM0NC45NzcgMy4xNjQuOTc3IDQuNTA4IDBMNjQgOTguOTVsMzQuOTMgMjUuMzc1YTMuODEgMy44MSAwIDAgMCAyLjI1NC43MzQgMy44IDMuOCAwIDAgMCAyLjI1NC0uNzM0IDMuODMgMy44MyAwIDAgMCAxLjM5MS00LjI4NWwtMTMuMzQtNDEuMDY2IDM0LjkzLTI1LjM3OWEzLjgzIDMuODMgMCAwIDAgMS4zOTQtNC4yODVjLS41MTItMS41ODItMS45ODQtMi42NDgtMy42NDQtMi42NDhsLTQzLjE4NC4wMDQtMTMuMzQtNDEuMDdDNjcuMTI5IDQuMDE3IDY1LjY2IDIuOTUxIDY0IDIuOTUxcy0zLjEzMyAxLjA2Ni0zLjY0OCAyLjY0NWwtMTMuMzQgNDEuMDY2SDMuODMyYy0xLjY2IDAtMy4xMzMgMS4wNjYtMy42NDQgMi42NDhzLjA0NyAzLjMwNSAxLjM5MSA0LjI4NWwzNC45MyAyNS4zNzl6bTEwLjkzNC04Ljg0NGw4LjkzNC0yNy40OCAxNC40NDkgMTAuNDk2em01OS43OTMgMEw3MC41MTYgOTQuMjA4bDE0LjQ0OS0xMC40OTZ6bTE4LjQ3Ny01Ni44NjdMODguOTkzIDcxLjMxM2wtNS41MTYtMTYuOTg0ek02NC4wMDEgMTkuMTgxbDguOTMgMjcuNDg0SDU1LjA2OHpNNTIuNTc5IDU0LjMyOWgyMi44NGw3LjA1OSAyMS43MjMtMTguNDc3IDEzLjQyNi0xOC40OC0xMy40MjZ6bS0zNi45NTMgMGgyOC44OTVsLTUuNTE2IDE2Ljk4NHoiLz48L3N2Zz4=)](https://github.com/axiomantic/spellbook)
```

## License

MIT License - See [LICENSE](LICENSE) for details.

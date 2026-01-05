<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Spellbook](#spellbook)
  - [Prerequisites](#prerequisites)
  - [Quick Install](#quick-install)
  - [What's Included](#whats-included)
    - [Skills (26 total)](#skills-26-total)
    - [Commands (15 total)](#commands-15-total)
    - [Agents (1 total)](#agents-1-total)
  - [Platform Support](#platform-support)
  - [Workflow Recipes](#workflow-recipes)
    - [End-to-End Feature Implementation](#end-to-end-feature-implementation)
    - [Execution Mode: Work Packets for Large Features](#execution-mode-work-packets-for-large-features)
    - [Session Handoff Between Coding Assistants](#session-handoff-between-coding-assistants)
    - [Use Skills in Any MCP-Enabled Assistant](#use-skills-in-any-mcp-enabled-assistant)
    - [Parallel Worktree Development](#parallel-worktree-development)
    - [Prevent Green Mirages (False-Positive Tests)](#prevent-green-mirages-false-positive-tests)
    - [Find and Reuse Past Patterns](#find-and-reuse-past-patterns)
    - [Create Custom Domain Skills](#create-custom-domain-skills)
  - [Recommended Companion Tools](#recommended-companion-tools)
    - [Heads Up Claude](#heads-up-claude)
    - [MCP Language Server](#mcp-language-server)
  - [Development](#development)
    - [Serve Documentation Locally](#serve-documentation-locally)
    - [Run MCP Server Directly](#run-mcp-server-directly)
  - [Documentation](#documentation)
  - [Contributing](#contributing)
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
| [/compact] | Custom session compaction | spellbook |
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

[/compact]: https://axiomantic.github.io/spellbook/latest/commands/compact/
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

### Agents (1 total)

| Agent | Description | Origin |
|-------|-------------|--------|
| [code-reviewer] | Specialized code review | [superpowers] |

[code-reviewer]: https://axiomantic.github.io/spellbook/latest/agents/code-reviewer/
[superpowers]: https://github.com/obra/superpowers

## Platform Support

| Platform | Status | Details |
|----------|--------|---------|
| Claude Code | Full | Native skills + MCP server |
| OpenCode | Full | Skill symlinks |
| Codex | Full | Bootstrap + CLI |
| Gemini CLI | Partial | MCP server + context file |

## Workflow Recipes

### End-to-End Feature Implementation

The `implement-feature` meta-skill orchestrates the complete development workflow from requirements to PR.

```bash
# 1. Just describe what you want to build
"Implement user authentication with MFA support"

# 2. The implement-feature skill triggers automatically and runs:
#    Phase 1: brainstorming (explores requirements, gathers context)
#    Phase 2: design-doc-reviewer (validates architecture)
#    Phase 3: writing-plans (creates detailed implementation plan)
#    Phase 4: implementation-plan-reviewer (verifies plan completeness)
#    Phase 5: test-driven-development (per task, in parallel worktrees)
#    Phase 6: code-reviewer (after each change)
#    Phase 7: finishing-a-development-branch (creates PR)

# 3. Configuration prompts at start:
#    - Autonomous mode? (run without prompting)
#    - Parallel worktrees? (isolated branches for parallel work)
#    - Auto-PR? (create PR when complete)
```

**Why it works:** Design is reviewed BEFORE coding. Tests are written BEFORE implementation. Every phase has a quality gate. No steps skipped or rationalized away.

### Execution Mode: Work Packets for Large Features

For large features that would exhaust context in a single session, `implement-feature` can split work into **work packets** that run in separate sessions.

```bash
# 1. Start feature implementation
"Implement user authentication with MFA support"

# 2. implement-feature analyzes size:
#    - Token estimation: 150,000 tokens (~75% of context window)
#    - Tasks: 24 across 4 tracks
#    - Recommendation: "swarmed" mode

# 3. You choose execution mode:
#    - swarmed: Parallel sessions, one per track (fastest)
#    - sequential: Single session, works through tracks sequentially
#    - delegated: Stay in session, use subagents heavily
#    - direct: Stay in session, minimal delegation (small features)

# 4. For swarmed mode, work packets are generated:
#    ~/.claude/work-packets/user-auth/
#    ├── manifest.json           # Track metadata, dependencies
#    ├── track-1-backend.md      # Boot prompt for backend work
#    ├── track-2-frontend.md     # Boot prompt for frontend work
#    ├── track-3-tests.md        # Boot prompt for test work
#    └── track-4-docs.md         # Boot prompt for docs

# 5. Worker sessions execute packets (parallel terminals):
/execute-work-packet ~/.claude/work-packets/user-auth/track-1-backend.md

# 6. When all tracks complete, merge:
/merge-work-packets ~/.claude/work-packets/user-auth/
```

**Execution Mode Selection:**

| Mode | When to Use | Behavior |
|------|-------------|----------|
| `swarmed` | 25+ tasks OR 80%+ context usage | Parallel sessions, one per track |
| `sequential` | 16-25 tasks OR 65-80% usage | Single session, works through packets |
| `delegated` | 9-15 tasks OR 40-65% usage | Current session, heavy subagent delegation |
| `direct` | ≤8 tasks AND <40% usage | Current session, minimal delegation |

**MCP Tool: `spawn_claude_session`**

Automatically opens terminal windows with worker sessions (macOS/Linux):

```python
# Detected terminal: iTerm2, Warp, Terminal.app, gnome-terminal, etc.
spawn_claude_session(
    prompt="/execute-work-packet ~/.claude/work-packets/user-auth/track-1.md",
    working_directory="/path/to/project"
)
```

**Why it works:** Context overflow is the #1 failure mode for large features. Work packets are self-contained boot prompts. Each worker has fresh context. Smart-merge synthesizes parallel work.

### Session Handoff Between Coding Assistants

Pause work in one assistant, resume in another with full context.

```bash
# In Cursor/Windsurf/any MCP-enabled assistant
# You're 40K tokens deep, need Claude Code's reasoning

# 1. Distill the session (extracts decisions, plans, progress)
/distill-session

# 2. Session saved to ~/.local/spellbook/distilled/<project>/session-YYYYMMDD-HHMMSS.md

# 3. In Claude Code (or any other assistant):
#    Paste the distilled context, then:
Skill('using-skills')  # Resume with full skill awareness
```

**Why it works:** Sessions become portable boot prompts. 50K tokens compress to ~3K words of critical context. MCP tools (`find_session`, `split_session`) handle discovery.

### Use Skills in Any MCP-Enabled Assistant

Run the same structured workflows in Cursor, Windsurf, or Gemini CLI.

```bash
# 1. Spellbook MCP server exposes skills universally
claude mcp add spellbook -- uv run ~/.local/share/spellbook/spellbook_mcp/server.py

# 2. In any MCP-enabled assistant, call skills the same way:
use_spellbook_skill("systematic-debugging")
use_spellbook_skill("green-mirage-audit")
use_spellbook_skill("test-driven-development")

# 3. Skills are just markdown - same behavior everywhere
```

**Why it works:** Skills are platform-agnostic markdown files. The MCP server acts as a universal delivery mechanism across all supported assistants.

### Parallel Worktree Development

Implement complex features across isolated branches, merge intelligently.

```bash
# 1. Plan the feature
Skill('brainstorming')

# 2. Create isolated worktrees
Skill('using-git-worktrees')
# Creates: .worktrees/auth-feature, .worktrees/db-schema, .worktrees/api-endpoints

# 3. Dispatch parallel subagents (each works in their worktree)
Task("Auth module", "Implement authentication in .worktrees/auth-feature", "coder")
Task("DB schema", "Design schema in .worktrees/db-schema", "coder")
Task("API endpoints", "Build API in .worktrees/api-endpoints", "coder")

# 4. When all pass tests, merge with 3-way analysis
Skill('smart-merge')
```

**Why it works:** Interface contracts from the design prevent conflicts. Smart-merge synthesizes parallel changes instead of choosing sides. 2-4x faster than sequential development.

### Prevent Green Mirages (False-Positive Tests)

Audit whether tests actually catch bugs, not just achieve coverage.

```bash
# 1. Tests pass, but do they verify anything?
/green-mirage-audit

# 2. Forensic analysis traces code paths through production code
#    Output: ~/.local/spellbook/docs/<project>/audits/green-mirage-audit-TIMESTAMP.md
#    Shows which tests are SOLID vs GREEN MIRAGE

# 3. Fix identified issues
Skill('fix-tests')  # Takes audit report as input, rewrites weak tests

# 4. Re-audit until all tests are SOLID
```

**Why it works:** Coverage % doesn't guarantee bug detection. Green-mirage-audit checks whether tests would catch real failures.

### Find and Reuse Past Patterns

Query old sessions without searching through files.

```bash
# 1. Use MCP tools to find relevant sessions
find_session(name="async-retry", limit=10)
# Returns: session slugs, timestamps, metadata

# 2. Load specific chunks (respects message boundaries)
split_session(session_path="~/.claude/projects/.../session.jsonl", start_line=0, char_limit=200000)

# 3. Apply the pattern with context
Skill('async-await-patterns')
```

**Why it works:** Sessions become organizational memory. MCP query API replaces manual file searching.

### Create Custom Domain Skills

Encode team-specific workflows as shareable skills.

```bash
# 1. Invoke the skill creation workflow
Skill('writing-skills')

# 2. Define your skill:
#    - Name: graphql-schema-testing
#    - Description: "Use when modifying GraphQL schema"
#    - ROLE, CRITICAL_INSTRUCTION, workflow steps

# 3. Place at ~/.config/opencode/skills/graphql-schema-testing/SKILL.md

# 4. MCP server auto-discovers it
#    Invoke with: Skill('graphql-schema-testing')

# 5. Share via Git - team gets the same workflow
```

**Why it works:** Skills are just markdown. Personal discipline becomes team patterns.

## Recommended Companion Tools

These tools are not necessary but contribute to better development workflows with coding assistants.

### Heads Up Claude

Statusline for Claude Code CLI showing token usage and conversation stats. Helps you track how much context you have left and how much of your subscription quota you have used.

```bash
git clone https://github.com/elijahr/heads-up-claude.git ~/Development/heads-up-claude
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

**Want Spellbook on your coding assistant?** e.g. Cursor, Kline, Roo, Kilo, Continue, GitHub Copilot, etc. If your assistant supports MCP but isn't listed in Platform Support, you can port it yourself:

See the [**Porting Guide**](docs/contributing/porting-to-your-assistant.md) - A self-contained prompt you paste into your coding assistant to have it add Spellbook support for itself and submit a PR back to this repo. We appreciate your contributions!

## Acknowledgments

Spellbook includes many skills, commands, agents, and hooks from [obra/superpowers](https://github.com/obra/superpowers) by Jesse Vincent. These workflow patterns (brainstorming, planning, execution, git worktrees, TDD, debugging) are a core part of spellbook's development methodology.

See [THIRD-PARTY-NOTICES](THIRD-PARTY-NOTICES) for full attribution and license details.

## License

MIT License - See [LICENSE](LICENSE) for details.

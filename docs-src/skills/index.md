# Skills Overview

Skills are reusable workflows that provide structured approaches to common development tasks. They encode best practices and ensure consistent, high-quality work.

## How to Use Skills

### In Claude Code

Skills are invoked automatically when relevant, or explicitly:

```
Use the systematic-debugging skill to investigate this issue
```

### In Other Platforms

See [Platform Support](../getting-started/platforms.md) for platform-specific invocation methods.

## Skill Categories

### Core Workflow Skills

Foundational skills for structured development (from [obra/superpowers](https://github.com/obra/superpowers)):

| Skill | When to Use |
|-------|-------------|
| [brainstorming](brainstorming.md) | Before coding - explore requirements and design |
| [writing-plans](writing-plans.md) | After brainstorming - create implementation plan |
| [executing-plans](executing-plans.md) | Execute a written plan systematically |
| [test-driven-development](test-driven-development.md) | Implementing any feature or fix |
| [debug](debug.md) | **Unified debugging entry point** - routes to appropriate methodology |
| [using-git-worktrees](using-git-worktrees.md) | Isolating feature work from main codebase |

### Code Quality Skills

Skills for maintaining and improving code quality:

| Skill | When to Use |
|-------|-------------|
| [green-mirage-audit](green-mirage-audit.md) | Auditing test suite quality |
| [factchecker](factchecker.md) | Verifying claims and assumptions |
| [find-dead-code](find-dead-code.md) | Identifying unused code |
| [receiving-code-review](receiving-code-review.md) | Processing code review feedback |
| [requesting-code-review](requesting-code-review.md) | Requesting structured code review |

### Feature Development Skills

Skills for building and reviewing features:

| Skill | When to Use |
|-------|-------------|
| [implement-feature](implement-feature.md) | End-to-end feature implementation |
| [design-doc-reviewer](design-doc-reviewer.md) | Reviewing design documents |
| [implementation-plan-reviewer](implementation-plan-reviewer.md) | Reviewing implementation plans |
| [devils-advocate](devils-advocate.md) | Challenging assumptions and decisions |
| [smart-merge](smart-merge.md) | Merging parallel worktrees |

### Specialized Skills

Domain-specific skills:

| Skill | When to Use |
|-------|-------------|
| [async-await-patterns](async-await-patterns.md) | Writing async JavaScript/TypeScript |
| [nim-pr-guide](nim-pr-guide.md) | Contributing to Nim repositories |

### Meta Skills

Skills about skills and subagent orchestration:

| Skill | When to Use |
|-------|-------------|
| [using-skills](using-skills.md) | Understanding how to invoke and use skills |
| [writing-skills](writing-skills.md) | Creating new skills |
| [subagent-prompting](subagent-prompting.md) | Effective subagent instructions |
| [instruction-engineering](instruction-engineering.md) | Optimizing LLM prompts |
| [dispatching-parallel-agents](dispatching-parallel-agents.md) | Parallel subagent orchestration |
| [subagent-driven-development](subagent-driven-development.md) | Delegating to subagents |

## Creating Custom Skills

See [Writing Skills](writing-skills.md) for instructions on creating your own skills.

Personal skills placed in `~/.claude/skills/` take priority over spellbook skills.

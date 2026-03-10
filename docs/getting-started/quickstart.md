# Quick Start

After installation, here's how to start using Spellbook skills.

## Your First Skill

### 1. Check Available Skills

In Claude Code:
```
What skills do I have available?
```

Or use the Skill tool directly to list them.

### 2. Invoke a Skill

When you need a structured workflow, invoke the relevant skill:

```
I need to debug this issue. Use the debugging skill.
```

Or let the AI assistant detect when a skill applies automatically.

## Common Workflows

### Starting a New Feature

Use the `implementing-features` skill. It handles the entire lifecycle: discovery, design, planning, and implementation.

```
I want to add user authentication. Use the implementing-features skill.
```

Or just describe what you want -- the skill is invoked automatically for any code change:

```
Add a REST API for managing projects
```

### Creating an Entire Project

Use the `autonomous-roundtable` skill (Forge) for greenfield projects. It decomposes a project into features and executes them through parallel worktrees with roundtable quality gates.

```
Create a new CLI tool for managing database migrations. Use Forge.
```

### Debugging an Issue

Invoke the `debugging` skill, or just describe the problem:

```
This endpoint returns 500 when the user has no profile. Debug it.
```

The skill triages the issue, selects a methodology (scientific or systematic), and verifies the fix.

### Code Review

**Giving review:**
```
Review this PR using the code-review skill
```

**Addressing feedback:**
```
Address the PR feedback using the code-review skill
```

## Autonomous Mode

For uninterrupted workflows, enable autonomous mode:

```
/allowed-tools Bash(*)
```

This allows skills to execute multi-step workflows (git operations, file changes, test runs) without constant approval prompts.

!!! warning "Use with Caution"
    Review changes before pushing. Autonomous mode executes without confirmation.

## Key Skills to Learn

| Task | Skill |
|------|-------|
| Build or modify features | `implementing-features` |
| Create entire projects | `autonomous-roundtable` (Forge) |
| Debug issues | `debugging` |
| Review code | `code-review` |
| Deep research | `deep-research` |
| Test-first development | `test-driven-development` |
| Feature isolation | `using-git-worktrees` |
| Finish and ship a branch | `finishing-a-development-branch` |

## Tips

1. **Let skills chain:** Many skills invoke other skills as needed
2. **Trust the process:** Skills encode best practices - follow them
3. **Use TodoWrite:** Skills create task lists - check them off as you go
4. **Read skill output:** Skills provide specific instructions - follow them exactly

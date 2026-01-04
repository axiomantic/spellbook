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
I need to debug this issue. Use the systematic-debugging skill.
```

Or let the AI assistant detect when a skill applies automatically.

## Common Workflows

### Starting a New Feature

1. **Brainstorm first:** Use `/brainstorm` or invoke `brainstorming` skill
2. **Create a plan:** Use `/write-plan` or invoke `writing-plans` skill
3. **Execute the plan:** Use `/execute-plan` or invoke `executing-plans` skill

### Debugging an Issue

1. Invoke `systematic-debugging` skill
2. Follow the hypothesis-driven debugging process
3. Document findings and fixes

### Code Review

**Requesting review:**
```
Review my changes using the requesting-code-review skill
```

**Receiving feedback:**
```
Address this PR feedback using the receiving-code-review skill
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
| Design exploration | `brainstorming` |
| Implementation planning | `writing-plans` |
| Bug investigation | `systematic-debugging` |
| Test-first development | `test-driven-development` |
| Feature isolation | `using-git-worktrees` |
| Quality verification | `verification-before-completion` |

## Tips

1. **Let skills chain:** Many skills invoke other skills as needed
2. **Trust the process:** Skills encode best practices - follow them
3. **Use TodoWrite:** Skills create task lists - check them off as you go
4. **Read skill output:** Skills provide specific instructions - follow them exactly

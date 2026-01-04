# Acknowledgments

Spellbook incorporates code from [obra/superpowers](https://github.com/obra/superpowers) by Jesse Vincent, licensed under the MIT License.

## Components from Superpowers

The following components originated from the superpowers project:

### Skills

| Skill | Description |
|-------|-------------|
| [brainstorming](skills/brainstorming.md) | Collaborative design exploration before coding |
| [dispatching-parallel-agents](skills/dispatching-parallel-agents.md) | Orchestrating multiple subagents for parallel work |
| [executing-plans](skills/executing-plans.md) | Systematic plan execution with checkpoints |
| [finishing-a-development-branch](skills/finishing-a-development-branch.md) | Completing and integrating feature work |
| [receiving-code-review](skills/receiving-code-review.md) | Processing and responding to code review feedback |
| [requesting-code-review](skills/requesting-code-review.md) | Structured code review requests |
| [subagent-driven-development](skills/subagent-driven-development.md) | Delegating work to specialized subagents |
| [systematic-debugging](skills/systematic-debugging.md) | Methodical debugging with hypothesis testing |
| [test-driven-development](skills/test-driven-development.md) | Red-green-refactor TDD workflow |
| [using-git-worktrees](skills/using-git-worktrees.md) | Isolated workspaces for feature development |
| [using-skills](skills/using-skills.md) | Meta-skill for invoking other skills (originally "using-superpowers") |
| [verification-before-completion](skills/verification-before-completion.md) | Pre-completion verification checklist |
| [writing-plans](skills/writing-plans.md) | Creating detailed implementation plans |
| [writing-skills](skills/writing-skills.md) | Creating new skills |

### Commands

| Command | Description |
|---------|-------------|
| [/brainstorm](commands/brainstorm.md) | Invoke brainstorming skill |
| [/execute-plan](commands/execute-plan.md) | Execute an implementation plan |
| [/write-plan](commands/write-plan.md) | Create an implementation plan |

### Agents

| Agent | Description |
|-------|-------------|
| [code-reviewer](agents/code-reviewer.md) | Specialized code review agent |

### Hooks

| Hook | Description |
|------|-------------|
| session-start.sh | Session initialization with skill context |
| hooks.json | Hook configuration |

## Original Skills (Spellbook)

The following skills were developed specifically for Spellbook:

| Skill | Description |
|-------|-------------|
| [async-await-patterns](skills/async-await-patterns.md) | JavaScript/TypeScript async/await best practices |
| [design-doc-reviewer](skills/design-doc-reviewer.md) | Design document completeness review |
| [devils-advocate](skills/devils-advocate.md) | Adversarial review of assumptions |
| [factchecker](skills/factchecker.md) | Systematic claim verification |
| [find-dead-code](skills/find-dead-code.md) | Unused code detection |
| [fix-tests](skills/fix-tests.md) | Test remediation and quality improvement |
| [green-mirage-audit](skills/green-mirage-audit.md) | Test suite quality audit |
| [implement-feature](skills/implement-feature.md) | End-to-end feature implementation |
| [implementation-plan-reviewer](skills/implementation-plan-reviewer.md) | Implementation plan review |
| [instruction-engineering](skills/instruction-engineering.md) | LLM prompt optimization |
| [nim-pr-guide](skills/nim-pr-guide.md) | Nim language PR contribution guide |
| [scientific-debugging](skills/scientific-debugging.md) | Formal scientific debugging method |
| [smart-merge](skills/smart-merge.md) | Intelligent worktree merging |
| [subagent-prompting](skills/subagent-prompting.md) | Effective subagent instruction patterns |

## License

See [THIRD-PARTY-NOTICES](https://github.com/axiomantic/spellbook/blob/main/THIRD-PARTY-NOTICES) for the full license text.

---
name: dispatching-parallel-agents
description: Use when facing 2+ independent tasks that can be worked on without shared state or sequential dependencies
---

# Dispatching Parallel Agents

<ROLE>
Parallel Execution Architect. Reputation depends on maximizing throughput while preventing conflicts and merge disasters.
</ROLE>

## Invariant Principles

1. **Independence gate**: Verify no shared state, no sequential dependencies, no file conflicts before dispatch
2. **One agent per domain**: Each agent owns exactly one problem scope; overlap kills parallelism
3. **Self-contained prompts**: Agent receives ALL context needed; no cross-agent dependencies
4. **Constraint boundaries**: Explicit limits prevent scope creep ("do NOT change X")
5. **Merge verification required**: Agent work integrated only after conflict check + full test suite

## Inputs

| Input | Required | Description |
|-------|----------|-------------|
| `tasks` | Yes | List of 2+ tasks to evaluate for parallel dispatch |
| `context.test_failures` | No | Test output showing failures to distribute |
| `context.files_involved` | No | Files each task may touch |

## Outputs

| Output | Type | Description |
|--------|------|-------------|
| `dispatch_decision` | Decision | Parallel vs sequential with rationale |
| `agent_prompts` | Text | Self-contained prompts per agent |
| `merge_report` | Inline | Conflict check + test results summary |

## Dispatch Decision

<analysis>
Before dispatching, answer:
- Are failures in different subsystems/files?
- Can each be understood without the others?
- Would fixing one affect the others?
- Will agents edit same files?
</analysis>

**Dispatch when:** 3+ failures with different root causes, isolated subsystems, no shared state
**Stay sequential when:** Related failures, exploratory debugging, shared resources, unknown scope

## Agent Prompt Template

```markdown
Fix [SPECIFIC SCOPE]:

Failures:
1. [test name] - [expected vs actual]
2. [test name] - [expected vs actual]

Context: [paste error messages, relevant code pointers]

Constraints:
- Do NOT change [specific boundaries]
- Focus only on [scope]

Return: Summary of root cause + changes made
```

## Prompt Quality Gates

| Anti-pattern | Fix |
|--------------|-----|
| "Fix all tests" | Specify exact file/tests |
| No error context | Paste actual errors |
| No constraints | Add "do NOT change X" |
| "Fix it" output | Require cause+changes summary |

## Post-Dispatch Protocol

<reflection>
After agents return:
1. Read each summary - understand what changed
2. Check conflict potential - same files edited?
3. Run full test suite - verify integration
4. Spot check fixes - agents make systematic errors
</reflection>

Only integrate when: summaries reviewed, no file conflicts, tests green

## Anti-Patterns

<FORBIDDEN>
- Dispatching tasks that share mutable state
- Overlapping file ownership between agents
- Vague prompts ("fix the tests", "make it work")
- Skipping conflict check before merge
- Integrating without running full test suite
- Dispatching exploratory work (unknown scope)
</FORBIDDEN>

## Self-Check

Before completing:
- [ ] Independence verified: no shared state, no file overlap
- [ ] Each agent prompt is self-contained with full context
- [ ] Constraints explicitly state what NOT to change
- [ ] All agent summaries reviewed before integration
- [ ] Conflict check performed on returned work
- [ ] Full test suite green after merge

If ANY unchecked: STOP and fix.

## Compressed Example

**Scenario:** 6 failures across 3 files post-refactor

**Domain isolation:**
- agent-tool-abort.test.ts (3): timing issues
- batch-completion-behavior.test.ts (2): event structure
- tool-approval-race-conditions.test.ts (1): async waiting

**Dispatch:** 3 parallel agents, each scoped to one file

**Results:** Independent fixes, zero conflicts, suite green

**Gain:** 3 problems solved in time of 1

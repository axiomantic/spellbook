# executing-plans

Use when you have a written implementation plan to execute

!!! info "Origin"
    This skill originated from [obra/superpowers](https://github.com/obra/superpowers).

## Skill Content

``````````markdown
# Executing Plans

<ROLE>
Implementation Lead executing architect-approved plans. Reputation depends on faithful execution with evidence, not creative reinterpretation.
</ROLE>

## Invariant Principles

1. **Plan Fidelity**: Follow plan steps exactly. Plans encode architect decisions; deviation creates drift.
2. **Evidence Over Claims**: Every task completion requires verification output. Never mark complete without proof.
3. **Blocking Over Guessing**: Uncertainty must halt execution. Wrong guesses compound; asking costs one exchange.
4. **Review Before Proceed**: No task advances past unaddressed review findings. Spec compliance precedes code quality.
5. **Context Completeness**: Subagents receive full task text, never file references. Fresh contexts lack your accumulated knowledge.

---

## Inputs

| Input | Required | Description |
|-------|----------|-------------|
| Plan document | Yes | Implementation plan from `writing-plans` with numbered tasks |
| Mode preference | No | `batch` (default) or `subagent` - how to execute |
| Batch size | No | Tasks per batch in batch mode (default: 3) |

## Outputs

| Output | Type | Description |
|--------|------|-------------|
| Completed implementation | Code | All plan tasks implemented and verified |
| Verification evidence | Inline | Test output, build results per task |
| Task completion log | TodoWrite | Progress tracking with completion status |

---

## Mode Selection

| Mode | Review | Execution | Checkpoints |
|------|--------|-----------|-------------|
| `batch` (default) | Human-in-loop | Sequential inline | Between batches |
| `subagent` | Automated two-stage | Fresh subagent/task | After each task |

**Choose batch when:** architect wants review between batches, tasks tightly coupled, plan needs discussion.

**Choose subagent when:** tasks independent, faster iteration desired, want automated spec+quality review.

---

## Autonomous Mode

Skip: plan concerns (log for later), "ready for feedback" checkpoints, completion confirmations.

Auto-decide: batch size (default 3), implementation details (document choice), applying review fixes.

**Circuit breakers (still pause):**
- Critical plan gaps preventing execution
- 3+ consecutive test failures
- Security-sensitive operations not clearly specified
- Scope/requirements questions (affects what gets built)
- 3+ review cycles on same issue

---

## Batch Mode Process

<analysis>
Before each phase, verify: Do I have everything needed? Any concerns worth raising?
</analysis>

### Phase 1: Load Plan
Read plan. Review critically. If concerns: AskUserQuestion with options (discuss/proceed/update). If clear: TodoWrite and proceed.

### Phase 2: Execute Batch
Default first 3 tasks. Per task: mark in_progress, follow steps exactly, run verifications, mark completed.

### Phase 3: Report
Show implementation + verification output. Say "Ready for feedback."

### Phase 4: Continue
Apply feedback, execute next batch, repeat until complete.

### Phase 5: Complete
Invoke `finishing-a-development-branch` skill.

<reflection>
Did every task show verification output? Did I mark anything complete without evidence? If so, STOP and fix.
</reflection>

---

## Subagent Mode Process

### Phase 1: Extract Tasks
Read plan once. Extract all tasks with full text and context. Create TodoWrite.

### Phase 2: Per-Task Loop
1. Dispatch implementer (`./implementer-prompt.md`)
2. Answer any questions completely
3. Implementer implements, tests, commits, self-reviews
4. Dispatch spec reviewer (`./spec-reviewer-prompt.md`) - loop until compliant
5. Dispatch code reviewer (`./code-quality-reviewer-prompt.md`) - loop until approved
6. Mark complete

### Phase 3: Final Review
Dispatch final code reviewer for entire implementation.

### Phase 4: Complete
Invoke `finishing-a-development-branch` skill.

---

## Anti-Patterns

<FORBIDDEN>
- Skip reviews (spec OR quality)
- Proceed with unfixed issues
- Parallel implementation subagents (conflicts)
- Make subagent read plan file (provide full text)
- Skip scene-setting context
- Start code quality review before spec passes
- Move to next task with open review issues
- Mark task complete without verification evidence
- Deviate from plan steps without explicit approval
- Guess at unclear requirements instead of asking
</FORBIDDEN>

**If subagent asks questions:** Answer completely before proceeding.

**If reviewer finds issues:** Implementer fixes, reviewer re-reviews, loop until approved.

**If subagent fails:** Dispatch fix subagent with specific instructions (avoid context pollution).

---

## Stop Conditions

**STOP immediately when:**
- Blocker mid-task (missing dependency, test fails, unclear instruction)
- Plan has critical gaps
- Verification fails repeatedly

**Ask for clarification rather than guessing.**

---

## Integration

- **writing-plans** - Creates plans this skill executes
- **requesting-code-review** - Review template for subagents
- **finishing-a-development-branch** - Complete development after all tasks
- Subagents should use **test-driven-development**

---

## Self-Check

Before marking execution complete:
- [ ] Every task has verification output shown (tests, build, runtime)
- [ ] No tasks marked complete without evidence
- [ ] All review issues addressed (spec and code quality)
- [ ] Plan followed exactly or deviations explicitly approved
- [ ] `finishing-a-development-branch` invoked

If ANY unchecked: STOP and fix.
``````````

---
name: executing-plans
description: Use when you have a written implementation plan to execute
---

# Executing Plans

Execute implementation plans with configurable execution mode.

**Session mode parameter:**
- `batch` (default): Human-in-loop batch execution with checkpoints for architect review
- `subagent`: Fresh subagent per task with automated two-stage review (spec compliance, then code quality)

| session_mode | Review Type | Task Execution | Checkpoints |
|--------------|-------------|----------------|-------------|
| batch | Human-in-loop | Sequential inline | Between batches |
| subagent | Automated two-stage | Fresh subagent per task | After each task |

**Announce at start:** "I'm using the executing-plans skill to implement this plan."

---

## When to Use Each Mode

**Use `batch` mode when:**
- Working with architect who wants to review between batches
- Tasks are tightly coupled and need human judgment
- Plan needs active discussion and refinement

**Use `subagent` mode when:**
- Tasks are mostly independent
- Want faster iteration without human-in-loop between tasks
- Stay in same session (no context switch)
- Want automated spec compliance + code quality review

---

## Autonomous Mode Behavior

Check your context for autonomous mode indicators:
- "Mode: AUTONOMOUS" or "autonomous mode"
- Explicit instruction to proceed without asking

When autonomous mode is active:

### Skip These Interactions
- Concerns about plan (proceed if minor, log concerns for later)
- "Ready for feedback" checkpoint (continue to next batch/task)
- Waiting for user response after each task (subagent mode)
- Final completion confirmation (proceed to finishing-a-development-branch)

### Make These Decisions Autonomously
- Minor plan concerns: Log and proceed
- Batch size: Use default (3 tasks for batch mode)
- Subagent questions about implementation details: Make reasonable choice and document it
- Review feedback: Apply fixes automatically, re-review without asking

### Circuit Breakers (Still Pause For)
- Critical plan gaps that prevent execution
- Repeated test failures (3+ consecutive)
- Security-sensitive operations not clearly specified
- Subagent questions about SCOPE or REQUIREMENTS (affects what gets built)
- Repeated review failures (3+ cycles on same issue)

When subagent asks a question in autonomous mode, use AskUserQuestion only if the question affects scope:

```javascript
// Scope question - MUST ask user even in autonomous mode
AskUserQuestion({
  questions: [{
    question: "Implementer asks: 'Should this also handle X case?' This affects scope.",
    header: "Scope",
    options: [
      { label: "Yes, include X", description: "Expand scope to handle this case" },
      { label: "No, exclude X (Recommended)", description: "Keep scope minimal per YAGNI" },
      { label: "Defer to future task", description: "Note for later, proceed without" }
    ],
    multiSelect: false
  }]
})
```

---

## The Process - Batch Mode

### Step 1: Load and Review Plan
1. Read plan file
2. Review critically - identify any questions or concerns about the plan
3. If concerns: Use AskUserQuestion to raise them:
   ```javascript
   AskUserQuestion({
     questions: [{
       question: "Found [N] concerns with the plan. How should we proceed?",
       header: "Plan Review",
       options: [
         { label: "Discuss concerns", description: "Review each concern before starting" },
         { label: "Proceed anyway (Recommended if minor)", description: "Start execution, address issues as they arise" },
         { label: "Update plan first", description: "Revise the plan to address concerns" }
       ],
       multiSelect: false
     }]
   })
   ```
4. If no concerns: Create TodoWrite and proceed

### Step 2: Execute Batch
**Default: First 3 tasks**

For each task:
1. Mark as in_progress
2. Follow each step exactly (plan has bite-sized steps)
3. Run verifications as specified
4. Mark as completed

### Step 3: Report
When batch complete:
- Show what was implemented
- Show verification output
- Say: "Ready for feedback."

### Step 4: Continue
Based on feedback:
- Apply changes if needed
- Execute next batch
- Repeat until complete

### Step 5: Complete Development

After all tasks complete and verified:
- Announce: "I'm using the finishing-a-development-branch skill to complete this work."
- **REQUIRED SUB-SKILL:** Use finishing-a-development-branch
- Follow that skill to verify tests, present options, execute choice

---

## The Process - Subagent Mode

Fresh subagent per task + two-stage review (spec then quality) = high quality, fast iteration

### Step 1: Load Plan and Extract Tasks
1. Read plan file once
2. Extract all tasks with full text and context
3. Create TodoWrite with all tasks

### Step 2: Per-Task Execution Loop

For each task:

1. **Dispatch implementer subagent** (use `./implementer-prompt.md`)
2. **Answer questions** if implementer asks any
3. **Implementer implements, tests, commits, self-reviews**
4. **Dispatch spec reviewer subagent** (use `./spec-reviewer-prompt.md`)
   - If issues found: implementer fixes, re-review
   - Loop until spec compliant
5. **Dispatch code quality reviewer subagent** (use `./code-quality-reviewer-prompt.md`)
   - If issues found: implementer fixes, re-review
   - Loop until approved
6. **Mark task complete in TodoWrite**

### Step 3: Final Review
After all tasks:
- Dispatch final code reviewer subagent for entire implementation

### Step 4: Complete Development
- Announce: "I'm using the finishing-a-development-branch skill to complete this work."
- **REQUIRED SUB-SKILL:** Use finishing-a-development-branch

---

## Prompt Templates (Subagent Mode)

These templates are used when dispatching subagents in subagent mode:

- `./implementer-prompt.md` - Dispatch implementer subagent
- `./spec-reviewer-prompt.md` - Dispatch spec compliance reviewer subagent
- `./code-quality-reviewer-prompt.md` - Dispatch code quality reviewer subagent

---

## When to Stop and Ask for Help

**STOP executing immediately when:**
- Hit a blocker mid-batch/task (missing dependency, test fails, instruction unclear)
- Plan has critical gaps preventing starting
- You don't understand an instruction
- Verification fails repeatedly

**Ask for clarification rather than guessing.**

## When to Revisit Earlier Steps

**Return to Review (Step 1) when:**
- Partner updates the plan based on your feedback
- Fundamental approach needs rethinking

**Don't force through blockers** - stop and ask.

---

## Red Flags (Subagent Mode)

**Never:**
- Skip reviews (spec compliance OR code quality)
- Proceed with unfixed issues
- Dispatch multiple implementation subagents in parallel (conflicts)
- Make subagent read plan file (provide full text instead)
- Skip scene-setting context (subagent needs to understand where task fits)
- Ignore subagent questions (answer before letting them proceed)
- Accept "close enough" on spec compliance (spec reviewer found issues = not done)
- Skip review loops (reviewer found issues = implementer fixes = review again)
- Let implementer self-review replace actual review (both are needed)
- **Start code quality review before spec compliance passes** (wrong order)
- Move to next task while either review has open issues

**If subagent asks questions:**
- Answer clearly and completely
- Provide additional context if needed
- Don't rush them into implementation

**If reviewer finds issues:**
- Implementer (same subagent) fixes them
- Reviewer reviews again
- Repeat until approved
- Don't skip the re-review

**If subagent fails task:**
- Dispatch fix subagent with specific instructions
- Don't try to fix manually (context pollution)

---

## Integration

**Required workflow skills:**
- **writing-plans** - Creates the plan this skill executes
- **requesting-code-review** - Code review template for reviewer subagents
- **finishing-a-development-branch** - Complete development after all tasks

**Subagents should use:**
- **test-driven-development** - Subagents follow TDD for each task

## Remember

- Review plan critically first
- Follow plan steps exactly
- Don't skip verifications
- Reference skills when plan says to
- Between batches/tasks: report and wait (unless autonomous)
- Stop when blocked, don't guess

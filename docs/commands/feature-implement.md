# /feature-implement

## Command Content

``````````markdown
# /feature-implement

Phases 3-4 of the implementing-features workflow. Run after `/feature-design` completes.

**Prerequisites:** Phase 2 complete, design document reviewed and approved.

<CRITICAL>
## Prerequisite Verification

Before ANY Phase 3-4 work begins, run this verification:

```bash
# ══════════════════════════════════════════════════════════════
# PREREQUISITE CHECK: feature-implement (Phase 3-4)
# ══════════════════════════════════════════════════════════════

PROJECT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
PROJECT_ENCODED=$(echo "$PROJECT_ROOT" | sed 's|^/||' | tr '/' '-')

echo "=== Phase 3-4 Prerequisites ==="

# CHECK 1: Determine entry path by complexity tier
TIER="[SESSION_PREFERENCES.complexity_tier]"
echo "Complexity tier: $TIER"

if [ "$TIER" = "simple" ]; then
  echo "SIMPLE path: Skipping Phase 3 (no external plan needed)"
  echo "Required: Lightweight research completed (inline)"
  echo "Required: Inline plan confirmed by user (<=5 steps)"
  echo "Navigate directly to the '## Phase 4: Implementation' section header."
  echo "Skip all Phase 3 content. Entering at Phase 4 directly."
else
  # CHECK 2 (STANDARD/COMPLEX): Design document must exist
  echo "Required: Design document exists"
  ls ~/.local/spellbook/docs/$PROJECT_ENCODED/plans/*-design.md 2>/dev/null || echo "FAIL: No design document found"

  # CHECK 3 (STANDARD/COMPLEX): Design review must be complete
  echo "Required: Design review completed"
fi

# CHECK 4 (ALL tiers): No escape hatch conflict
echo "Verify: escape_hatch routing is consistent with current entry point"
```

**If ANY check fails:** STOP. Do not proceed. Return to the appropriate phase.

**Anti-rationalization reminder:** If you are tempted to skip this check because
"the design is simple enough to hold in your head" or "we can plan as we go,"
that is Pattern 3 (Time Pressure) or Pattern 5 (Competence Assertion).
Implementation without a plan produces implementation that must be re-done.
Run the check. 5 seconds of verification prevents 2 hours of rework.
</CRITICAL>

## Invariant Principles

1. **Design precedes implementation** - Never implement without an approved design document and implementation plan
2. **Delegate actual work** - Main context orchestrates; subagents write code, run tests, perform reviews
3. **Quality gates are mandatory** - Code review, fact-checking, and green mirage audit after every task; no exceptions
4. **Behavior preservation in refactoring** - Refactoring mode requires test verification at every transformation; no behavior changes without approval

---

## Phase 3: Implementation Planning

<CRITICAL>
Phase behavior depends on escape hatch:
- **No escape hatch:** Run full Phase 3
- **Impl plan with "review first":** Skip 3.1, start at 3.2
- **Impl plan with "treat as ready":** Skip entire Phase 3
</CRITICAL>

### 3.1 Create Implementation Plan

<RULE>Subagent MUST invoke writing-plans.</RULE>

```
Task (or subagent simulation):
  description: "Create implementation plan"
  prompt: |
    First, invoke the writing-plans skill using the Skill tool.
    Then follow its complete workflow.

    ## Context for the Skill

    Design document: ~/.local/spellbook/docs/<project-encoded>/plans/YYYY-MM-DD-[feature-slug]-design.md
    Parallelization preference: [maximize/conservative/ask]

    Save to: ~/.local/spellbook/docs/<project-encoded>/plans/YYYY-MM-DD-[feature-slug]-impl.md
```

### 3.2 Review Implementation Plan

<RULE>Subagent MUST invoke reviewing-impl-plans.</RULE>

```
Task (or subagent simulation):
  description: "Review implementation plan"
  prompt: |
    First, invoke the reviewing-impl-plans skill using the Skill tool.
    Then follow its complete workflow.

    ## Context for the Skill

    Implementation plan: ~/.local/spellbook/docs/<project-encoded>/plans/YYYY-MM-DD-[feature-slug]-impl.md
    Parent design document: ~/.local/spellbook/docs/<project-encoded>/plans/YYYY-MM-DD-[feature-slug]-design.md

    Return complete findings report with remediation plan.
```

### 3.3 Approval Gate

Same logic as Phase 2.3.

### 3.4 Fix Implementation Plan

Same pattern as Phase 2.4 but for implementation plan.

### 3.4.5 Execution Mode Analysis

<CRITICAL>
Analyze feature size and complexity to determine optimal execution strategy.
</CRITICAL>

**Token Estimation:**

```python
TOKENS_PER_KB = 350
BASE_OVERHEAD = 20000
TOKENS_PER_TASK_OUTPUT = 2000
TOKENS_PER_REVIEW = 800
TOKENS_PER_FACTCHECK = 500
TOKENS_PER_FILE = 400
CONTEXT_WINDOW = 200000

def estimate_session_tokens(design_context_kb, design_doc_kb, impl_plan_kb, num_tasks, num_files):
    design_phase = (design_context_kb + design_doc_kb + impl_plan_kb) * TOKENS_PER_KB
    per_task = TOKENS_PER_TASK_OUTPUT + TOKENS_PER_REVIEW + TOKENS_PER_FACTCHECK
    execution_phase = num_tasks * per_task
    file_context = num_files * TOKENS_PER_FILE
    return BASE_OVERHEAD + design_phase + execution_phase + file_context
```

**Parse implementation plan:**

- `num_tasks`: Count all `- [ ] Task N.M:` lines
- `num_files`: Count all unique files in "Files:" lines
- `num_parallel_tracks`: Count all `## Track N:` headers

**Execution Mode Selection:**

```python
def recommend_execution_mode(estimated_tokens, num_tasks, num_parallel_tracks):
    usage_ratio = estimated_tokens / CONTEXT_WINDOW

    if num_tasks > 25 or usage_ratio > 0.80:
        return "swarmed", "Feature size exceeds safe single-session capacity"

    if usage_ratio > 0.65 or (num_tasks > 15 and num_parallel_tracks >= 3):
        return "swarmed", "Large feature with good parallelization potential"

    if num_tasks > 10 or usage_ratio > 0.40:
        return "delegated", "Moderate size, subagents can handle workload"

    return "direct", "Small feature, direct execution is efficient"
```

**Modes:**

- **swarmed**: Generate work packets, spawn separate sessions, EXIT this session
- **delegated**: Stay in session, delegate heavily to subagents
- **direct**: Stay in session, minimal delegation

**Routing:**

- If `swarmed`: Proceed to 3.5 and 3.6
- If `delegated` or `direct`: Skip to Phase 4

### 3.5 Generate Work Packets (if swarmed)

<CRITICAL>Only runs when execution_mode is "swarmed".</CRITICAL>

**Track Extraction:**

```python
def extract_tracks_from_impl_plan(impl_plan_content):
    tracks = []
    current_track = None

    for line in impl_plan_content.split('\n'):
        if line.startswith('## Track '):
            if current_track:
                tracks.append(current_track)
            parts = line[9:].split(':', 1)
            track_id = int(parts[0].strip())
            track_name = parts[1].strip().lower().replace(' ', '-')
            current_track = {
                "id": track_id,
                "name": track_name,
                "depends_on": [],
                "tasks": [],
                "files": []
            }
        elif current_track and line.strip().startswith('<!-- depends-on:'):
            deps_str = line.strip()[16:-4]
            for dep in deps_str.split(','):
                if dep.strip().startswith('Track '):
                    dep_id = int(dep.strip()[6:])
                    current_track["depends_on"].append(dep_id)
        elif current_track and line.strip().startswith('- [ ] Task '):
            current_track["tasks"].append(line.strip()[6:])
        elif current_track and line.strip().startswith('Files:'):
            files = [f.strip() for f in line.strip()[6:].split(',')]
            current_track["files"].extend(files)

    if current_track:
        tracks.append(current_track)
    return tracks
```

**Create work packet directory:** `~/.claude/work-packets/[feature-slug]/`

**Generate files:**

- `manifest.json`: Track metadata, dependencies, status
- `README.md`: Execution instructions with quality gate checklist
- `track-{id}-{name}.md`: Work packet per track

#### Work Packet Template

<CRITICAL>
Work packets MUST include mandatory quality gates. Packets without gates produce incomplete work that passes tests but fails in production.
</CRITICAL>

Each `track-{id}-{name}.md` MUST follow this template:

```markdown
# Work Packet: [Track Name]

**Feature:** [feature-name]
**Track:** [track-id]
**Dependencies:** [list or "none"]

## Context

[Design context, architectural constraints, interfaces]

## Tasks

[Task list from implementation plan]

## Quality Gates (MANDATORY)

After completing ALL tasks in this packet, you MUST run:

### Gate 1: Implementation Completion Verification

For each task, verify:

- [ ] All acceptance criteria traced to code
- [ ] All expected outputs exist with correct interfaces
- [ ] No dead code paths or unused implementations

### Gate 2: Code Review

Invoke `requesting-code-review` skill:

- Files: [list of files created/modified]
- Review criteria: code quality, error handling, type safety, security

Fix ALL critical and important issues before proceeding.

### Gate 3: Fact-Checking

Invoke `fact-checking` skill:

- Verify all docstrings match actual behavior
- Verify all comments are accurate
- Verify all type hints are correct
- Verify error messages are truthful

Fix ALL false claims before proceeding.

### Gate 4: Test Quality (Green Mirage Audit)

Invoke `audit-green-mirage` skill on test files:

- Verify tests have meaningful assertions (not just "passes")
- Verify tests cover error paths (not just happy path)
- Verify tests don't mock too much

Fix ALL green mirage issues before proceeding.

### Gate 5: Full Test Suite

Run `uv run pytest tests/` (or equivalent).
ALL tests must pass. No exceptions.

## Completion Checklist

Before marking this packet complete:

- [ ] All tasks implemented
- [ ] Gate 1: Implementation completion verified
- [ ] Gate 2: Code review passed (no critical/important issues)
- [ ] Gate 3: Fact-checking passed (no false claims)
- [ ] Gate 4: Green mirage audit passed
- [ ] Gate 5: Full test suite passes
- [ ] Changes committed with descriptive message

If ANY checkbox is unchecked, the packet is NOT complete.
```

#### README.md Template

The work packet `README.md` MUST include:

```markdown
# Work Packets: [Feature Name]

## Execution Protocol

<CRITICAL>
Each packet includes MANDATORY quality gates. Do NOT skip them.
Completing tasks without running gates produces incomplete work.
</CRITICAL>

### For Each Packet:

1. Read the packet's Context section
2. Implement all Tasks using TDD
3. Run ALL Quality Gates (5 gates, in order)
4. Complete the Completion Checklist
5. Commit with descriptive message
6. Update manifest.json status to "complete"

### Quality Gate Summary

| Gate                      | Skill to Invoke        | Pass Criteria                |
| ------------------------- | ---------------------- | ---------------------------- |
| Implementation Completion | (manual verification)  | All criteria traced          |
| Code Review               | requesting-code-review | No critical/important issues |
| Fact-Checking             | fact-checking          | No false claims              |
| Green Mirage Audit        | audit-green-mirage     | No mirage issues             |
| Test Suite                | (run tests)            | All tests pass               |

### After All Packets Complete

Run final integration verification across all packets.
```

### 3.6 Session Handoff (TERMINAL)

<CRITICAL>
After handoff, this session TERMINATES. Orchestrator's job ends here.
Workers take over execution.
</CRITICAL>

If `spawn_claude_session` MCP tool available:

```
Would you like me to:
1. Auto-launch all [count] independent tracks now
2. Provide manual commands for you to run
3. Launch only specific tracks

Please choose: ___
```

Otherwise, provide manual commands:

```bash
# Create worktree
git worktree add [worktree_path] -b [branch_name]

# Start Claude session with work packet
cd [worktree_path]
claude --session-context [work_packet_path]
```

**EXIT this session after handoff.**

---

## ═══════════════════════════════════════════════════════════════════
## STOP AND VERIFY: Phase 3 → Phase 4 Transition
## ═══════════════════════════════════════════════════════════════════

Before proceeding to Phase 4, verify Phase 3 is complete:

```bash
# Verify implementation plan exists
ls ~/.local/spellbook/docs/<project-encoded>/plans/*-impl.md
```

- [ ] Writing-plans subagent DISPATCHED (not done in main context)
- [ ] Implementation plan created and saved
- [ ] Reviewing-impl-plans subagent DISPATCHED
- [ ] Approval gate handled per autonomous_mode
- [ ] All critical/important findings fixed (if any)
- [ ] Execution mode analyzed (swarmed/delegated/direct)
- [ ] If swarmed: Work packets generated, session handoff complete, EXIT

If ANY unchecked: Go back to Phase 3. Do NOT proceed.

---

## Phase 4: Implementation

<CRITICAL>
This phase only executes if execution_mode is "delegated" or "direct".
During Phase 4, delegate actual work to subagents. Main context is for ORCHESTRATION ONLY.
</CRITICAL>

### Phase 4 Delegation Rules

**Main context handles:**

- Task sequencing and dependency management
- Quality gate verification
- User interaction and approvals
- Synthesizing subagent results
- Session state management

**Subagents handle:**

- Writing code (invoke test-driven-development)
- Running tests (Bash subagent)
- Code review (invoke requesting-code-review)
- Fact-checking (invoke fact-checking)
- File exploration and research

<RULE>
If you find yourself using Write, Edit, or Bash tools directly in main context during Phase 4, STOP. Delegate to a subagent instead.
</RULE>

**Why:** Main context accumulates tokens rapidly. Subagents operate in isolated contexts, preserving main context for orchestration.

### 4.1 Setup Worktree(s)

**If worktree == "single":**

```
Task (or subagent simulation):
  description: "Create worktree"
  prompt: |
    First, invoke the using-git-worktrees skill using the Skill tool.
    Create an isolated workspace for this feature.

    ## Context for the Skill

    Feature name: [feature-slug]
    Purpose: Isolated implementation

    Return the worktree path when done.
```

**If worktree == "per_parallel_track":**

<CRITICAL>
Before creating parallel worktrees, setup/skeleton work MUST be completed and committed.
This ensures all worktrees start with shared interfaces.
</CRITICAL>

1. Identify setup/skeleton tasks from impl plan
2. Execute setup tasks in main branch, commit
3. Create worktree per parallel group

**If worktree == "none":**
Work in current directory.

### 4.2 Execute Implementation Plan

**If worktree == "per_parallel_track":**

Execute each parallel track in its own worktree:

```
For each worktree:
  if dependencies not completed: skip (process in next round)

  Task (run_in_background: true):
    description: "Execute tasks in [worktree.path]"
    prompt: |
      First, invoke the executing-plans skill using the Skill tool.
      Execute assigned tasks in this worktree.

      Tasks: [worktree.tasks]
      Working directory: [worktree.path]

      IMPORTANT: Work ONLY in this worktree.

      After each task:
      1. Run code review (invoke requesting-code-review)
      2. Run claim validation (invoke fact-checking)
      3. Commit changes
```

After all parallel tracks complete, proceed to 4.2.5.

**If parallelization == "maximize" (single worktree):**

```
Task:
  description: "Execute parallel implementation"
  prompt: |
    First, invoke the dispatching-parallel-agents skill using the Skill tool.
    Execute the implementation plan with parallel task groups.

    Implementation plan: [path]
    Group tasks by "Parallel Group" field.
```

**If parallelization == "conservative":**

Sequential execution via executing-plans skill.

### 4.2.5 Smart Merge (if per_parallel_track)

<RULE>Subagent MUST invoke merging-worktrees skill.</RULE>

```
Task:
  description: "Smart merge parallel worktrees"
  prompt: |
    First, invoke the merging-worktrees skill using the Skill tool.
    Merge all parallel worktrees.

    ## Context for the Skill

    Base branch: [branch with setup work]
    Worktrees to merge: [list]
    Interface contracts: [impl plan path]

    After successful merge:
    1. Delete all worktrees
    2. Single unified branch with all work
    3. All tests pass
    4. Interface contracts verified
```

### 4.3 Implementation Task Subagent Template

For each individual task:

```
Task:
  description: "Implement Task N: [name]"
  prompt: |
    First, invoke the test-driven-development skill using the Skill tool.
    Implement this task following TDD strictly.

    ## Context for the Skill

    Implementation plan: [path]
    Task number: N
    Working directory: [worktree or current]

    Commit when done.
    Report: files changed, test results, commit hash.
```

### 4.4 Implementation Completion Verification

<CRITICAL>
Runs AFTER each task and BEFORE code review.
Catches incomplete work early.
</CRITICAL>

````
Task:
  description: "Verify Task N completeness"
  prompt: |
    You are an Implementation Completeness Auditor. Verify claimed work
    was actually done - not quality, just existence and completeness.

    ## Task Being Verified

    Task number: N
    Task description: [from plan]

    ## Verification Protocol

    For EACH item, trace through actual code. Do NOT trust file names.

    ### 1. Acceptance Criteria Verification
    For each criterion:
    1. State the criterion
    2. Identify where in code it should be
    3. Trace the execution path
    4. Verdict: COMPLETE | INCOMPLETE | PARTIAL

    ### 2. Expected Outputs Verification
    For each expected output:
    1. State the expected output
    2. Verify it exists
    3. Verify interface/signature
    4. Verdict: EXISTS | MISSING | WRONG_INTERFACE

    ### 3. Interface Contract Verification
    For each interface:
    1. State contract from plan
    2. Find actual implementation
    3. Compare signatures, types, behavior
    4. Verdict: MATCHES | DIFFERS | MISSING

    ### 4. Behavior Verification
    For key behaviors:
    1. State expected behavior
    2. Trace: can this behavior actually occur?
    3. Identify dead code paths
    4. Verdict: FUNCTIONAL | NON_FUNCTIONAL | PARTIAL

    ## Output Format

    ```
    TASK N COMPLETION AUDIT

    Overall: COMPLETE | INCOMPLETE | PARTIAL

    ACCEPTANCE CRITERIA:
    ✓ [criterion 1]: COMPLETE
    ✗ [criterion 2]: INCOMPLETE - [what's missing]

    EXPECTED OUTPUTS:
    ✓ src/foo.ts: EXISTS, interface matches
    ✗ src/bar.ts: MISSING

    INTERFACE CONTRACTS:
    ✓ FooService.doThing(): MATCHES
    ✗ BarService.process(): DIFFERS - missing param

    BEHAVIOR VERIFICATION:
    ✓ User can create widget: FUNCTIONAL
    ✗ Widget validates input: NON_FUNCTIONAL - validation never called

    BLOCKING ISSUES (must fix before proceeding):
    1. [issue]

    TOTAL: [N]/[M] items complete
    ```
````

**Gate Behavior:**

IF BLOCKING ISSUES found:

1. Return to task implementation
2. Fix incomplete items
3. Re-run verification
4. Loop until all COMPLETE

IF all COMPLETE:

- Proceed to 4.5 (Code Review)

### 4.5 Code Review After Each Task

<RULE>Subagent MUST invoke requesting-code-review after EVERY task.</RULE>

```
Task:
  description: "Review Task N implementation"
  prompt: |
    First, invoke the requesting-code-review skill using the Skill tool.
    Review the implementation.

    ## Context for the Skill

    What was implemented: [from implementation report]
    Plan/requirements: Task N from [impl plan path]
    Base SHA: [commit before task]
    Head SHA: [commit after task]

    Return assessment with any issues.
```

If issues found:

- Critical: Fix immediately
- Important: Fix before next task
- Minor: Note for later

### 4.5.1 Claim Validation After Each Task

<RULE>Subagent MUST invoke fact-checking after code review.</RULE>

```
Task:
  description: "Validate claims in Task N"
  prompt: |
    First, invoke the fact-checking skill using the Skill tool.
    Validate claims in the code just written.

    ## Context for the Skill

    Scope: Files created/modified in Task N only
    [List files]

    Focus on: docstrings, comments, test names, type hints, error messages.

    Return findings with any false claims to fix.
```

If false claims found: Fix immediately before next task.

### 4.6 Quality Gates After All Tasks

<CRITICAL>These gates are NOT optional. Run even if all tasks completed successfully.</CRITICAL>

#### 4.6.1 Comprehensive Implementation Audit

<CRITICAL>
Runs AFTER all tasks, BEFORE test suite.
Verifies ENTIRE implementation plan against final codebase.
Catches cross-task integration gaps and items that degraded.
</CRITICAL>

````
Task:
  description: "Comprehensive implementation audit"
  prompt: |
    You are a Senior Implementation Auditor performing final verification.

    ## Inputs

    Implementation plan: [path]
    Design document: [path]

    ## Comprehensive Verification Protocol

    ### Phase 1: Plan Item Sweep

    For EVERY task in plan:
    1. List all acceptance criteria
    2. Trace through CURRENT codebase state
    3. Mark: COMPLETE | INCOMPLETE | DEGRADED

    DEGRADED means: passed per-task verification but no longer works

    ### Phase 2: Cross-Task Integration Verification

    For each integration point between tasks:
    1. Identify: Task A produces X, Task B consumes X
    2. Verify A's output exists with correct shape
    3. Verify B actually imports/calls A's output
    4. Verify connection works (types match, no dead imports)

    Common failures:
    - B imports from A but never calls it
    - Interface changed during B, A's callers not updated
    - Circular dependency introduced
    - Type mismatch producer/consumer

    ### Phase 3: Design Document Traceability

    For each requirement in design doc:
    1. Identify which task(s) should implement it
    2. Verify implementation exists
    3. Verify implementation matches design intent

    ### Phase 4: Feature Completeness

    Answer with evidence:
    1. Can user USE this feature end-to-end?
    2. Any dead ends (UI exists but handler missing)?
    3. Any orphaned pieces (code exists but nothing calls it)?
    4. Does happy path work?

    ## Output Format

    ```
    COMPREHENSIVE IMPLEMENTATION AUDIT

    Overall: COMPLETE | INCOMPLETE | PARTIAL

    ═══════════════════════════════════════
    PLAN ITEM SWEEP
    ═══════════════════════════════════════

    Task 1: [name]
    ✓ Criterion 1.1: COMPLETE
    ✗ Criterion 2.2: DEGRADED - broken by [commit]

    PLAN ITEMS: [N]/[M] complete ([X] degraded)

    ═══════════════════════════════════════
    CROSS-TASK INTEGRATION
    ═══════════════════════════════════════

    Task 1 → Task 2: ✓ Connected
    Task 2 → Task 3: ✗ DISCONNECTED - never calls

    INTEGRATIONS: [N]/[M] connected

    ═══════════════════════════════════════
    DESIGN TRACEABILITY
    ═══════════════════════════════════════

    Requirement: "Rate limiting"
    ◐ PARTIAL - exists but not applied to /login

    REQUIREMENTS: [N]/[M] implemented

    ═══════════════════════════════════════
    FEATURE COMPLETENESS
    ═══════════════════════════════════════

    End-to-end usable: YES | NO | PARTIAL
    Dead ends: [list]
    Orphaned code: [list]
    Happy path: WORKS | BROKEN at [step]

    ═══════════════════════════════════════
    BLOCKING ISSUES
    ═══════════════════════════════════════

    MUST FIX:
    1. [issue with location]
    ```
````

**Gate Behavior:**

IF BLOCKING ISSUES: Fix, re-run audit, loop until clean.
IF clean: Proceed to 4.6.2.

#### 4.6.2 Run Full Test Suite

```bash
pytest  # or npm test, cargo test, etc.
```

If tests fail:

1. Dispatch subagent to invoke systematic-debugging
2. Fix issues
3. Re-run until passing

#### 4.6.3 Green Mirage Audit

<RULE>Subagent MUST invoke audit-green-mirage.</RULE>

```
Task:
  description: "Audit test quality"
  prompt: |
    First, invoke the audit-green-mirage skill using the Skill tool.
    Verify tests actually validate correctness.

    ## Context for the Skill

    Test files: [list of test files]
    Implementation files: [list of impl files]

    Focus on new code added by this feature.
```

If issues found: Fix tests, re-run until clean.

#### 4.6.4 Comprehensive Claim Validation

<RULE>Subagent MUST invoke fact-checking for final comprehensive validation.</RULE>

```
Task:
  description: "Comprehensive claim validation"
  prompt: |
    First, invoke the fact-checking skill using the Skill tool.
    Perform comprehensive claim validation.

    ## Context for the Skill

    Scope: All files created/modified in this feature
    [Complete file list]

    Design document: [path]
    Implementation plan: [path]

    Cross-reference claims against design doc and impl plan.
```

If issues found: Fix, re-run until clean.

#### 4.6.5 Pre-PR Claim Validation

<RULE>Before any PR creation, run final fact-checking pass.</RULE>

```
Task:
  description: "Pre-PR claim validation"
  prompt: |
    First, invoke the fact-checking skill using the Skill tool.
    Perform pre-PR validation.

    ## Context for the Skill

    Scope: Branch changes (all commits since merge-base with main)

    This is the absolute last line of defense.
    Nothing ships with false claims.
```

### 4.7 Finish Implementation

**If post_impl == "offer_options":**

```
Task:
  description: "Finish development branch"
  prompt: |
    First, invoke the finishing-a-development-branch skill using the Skill tool.
    Complete this development work.

    ## Context for the Skill

    Feature: [name]
    Branch: [current branch]
    All tests passing: yes
    All claims validated: yes

    Present options: merge, create PR, cleanup.
```

**If post_impl == "auto_pr":**
Push branch, create PR with gh CLI, return URL.

**If post_impl == "stop":**
Announce complete, summarize, list remaining TODOs.

---

## Refactoring Mode

<RULE>
Activate when: "refactor", "reorganize", "extract", "migrate", "split", "consolidate" appear in request.
Refactoring is NOT greenfield. Behavior preservation is the primary constraint.
</RULE>

### Detection

```typescript
if (request.match(/refactor|reorganize|extract|migrate|split|consolidate/i)) {
  SESSION_PREFERENCES.refactoring_mode = true;
}
```

### Workflow Adjustments

| Phase     | Greenfield               | Refactoring Mode                     |
| --------- | ------------------------ | ------------------------------------ |
| Phase 1   | Understand what to build | Map existing behavior to preserve    |
| Phase 1.5 | Design discovery         | Behavior inventory                   |
| Phase 2   | Design new solution      | Design transformation strategy       |
| Phase 3   | Plan implementation      | Plan incremental migration           |
| Phase 4   | Build and test           | Transform with behavior verification |

### Behavior Preservation Protocol

<CRITICAL>
Every change must pass behavior verification before proceeding.
No "I'll fix the tests later." Tests prove behavior preservation.
</CRITICAL>

**Before any change:**

1. Identify existing behavior (tests, usage patterns, contracts)
2. Document behavior contracts (inputs → outputs)
3. Ensure test coverage for behaviors (add tests if missing)

**During change:**

1. Make smallest possible transformation
2. Run tests after each atomic change
3. Commit working state before next transformation

**After change:**

1. Verify all original behaviors preserved
2. Document any intentional behavior changes (with user approval)

### Refactoring Patterns

| Pattern                   | When                           | Key Constraint                   |
| ------------------------- | ------------------------------ | -------------------------------- |
| **Strangler Fig**         | Replacing system incrementally | Old and new coexist              |
| **Branch by Abstraction** | Changing widely-used component | Introduce abstraction, swap impl |
| **Parallel Change**       | Changing interfaces            | Add new, migrate, remove old     |
| **Feature Toggles**       | Risky changes                  | Disable instantly if problems    |

### Refactoring-Specific Quality Gates

| Gate           | Greenfield              | Refactoring                       |
| -------------- | ----------------------- | --------------------------------- |
| Research       | Understand requirements | Map ALL existing behaviors        |
| Design         | Solution design         | Transformation strategy           |
| Implementation | Feature works           | Behavior preserved + improved     |
| Testing        | New tests pass          | ALL existing tests pass unchanged |

### Refactoring Self-Check

```
[ ] Existing behavior fully inventoried
[ ] Test coverage sufficient before changes
[ ] Each transformation is atomic and verified
[ ] No behavior changes without explicit approval
[ ] Incremental commits at each working state
[ ] Original tests pass (not modified to pass)
```

<FORBIDDEN>
- "Let's just rewrite it" without behavior inventory
- Changing behavior while refactoring structure
- Skipping test verification between transformations
- Big-bang migrations without incremental checkpoints
- Refactoring without existing test coverage (add tests first)
- Combining refactoring with feature changes in same task
</FORBIDDEN>

---

## Skills Invoked

| Phase               | Skill                          | Purpose                                                                    |
| ------------------- | ------------------------------ | -------------------------------------------------------------------------- |
| 1.2                 | analyzing-domains              | **If unfamiliar domain**: Extract ubiquitous language, identify aggregates |
| 1.6                 | devils-advocate                | Challenge Understanding Document                                           |
| 2.1                 | brainstorming                  | Create design doc                                                          |
| 2.1                 | designing-workflows            | **If feature has states/flows**: Design state machine                      |
| 2.2                 | reviewing-design-docs          | Review design doc                                                          |
| 2.4, 3.4            | executing-plans                | Fix findings                                                               |
| 3.1                 | writing-plans                  | Create impl plan                                                           |
| 3.2                 | reviewing-impl-plans           | Review impl plan                                                           |
| 3.5                 | assembling-context             | **If swarmed**: Prepare context packages for work packets                  |
| 4.1                 | using-git-worktrees            | Create workspace(s)                                                        |
| 4.2                 | dispatching-parallel-agents    | Parallel execution                                                         |
| 4.2                 | assembling-context             | Prepare context for parallel subagents                                     |
| 4.2.5               | merging-worktrees              | Merge parallel worktrees                                                   |
| 4.3                 | test-driven-development        | TDD per task                                                               |
| 4.5                 | requesting-code-review         | Review per task                                                            |
| 4.5.1, 4.6.4, 4.6.5 | fact-checking                  | Claim validation                                                           |
| 4.6.2               | systematic-debugging           | Debug test failures                                                        |
| 4.6.3               | audit-green-mirage             | Test quality audit                                                         |
| 4.7                 | finishing-a-development-branch | Complete workflow                                                          |

## Forge Integration (Optional)

When forge tools are available via MCP, they provide token-based workflow enforcement
and roundtable validation. These tools are OPTIONAL but enhance workflow rigor.

| Tool                                | Purpose                                                |
| ----------------------------------- | ------------------------------------------------------ |
| `forge_project_init`                | Initialize feature decomposition with dependency graph |
| `forge_iteration_start`             | Start/resume a feature iteration, get workflow token   |
| `forge_iteration_advance`           | Move to next stage after APPROVE verdict               |
| `forge_iteration_return`            | Return to earlier stage after ITERATE verdict          |
| `forge_roundtable_convene`          | Generate validation prompts with tarot archetypes      |
| `forge_process_roundtable_response` | Parse LLM roundtable output for verdicts               |
| `forge_select_skill`                | Get recommended skill for current stage/context        |

**Token System:** Forge tools use tokens to enforce workflow order. Each stage transition
requires a valid token from the previous operation, preventing stage skipping.

**Roundtable Validation:** The roundtable system uses tarot archetypes (Magician, Priestess,
Hermit, Fool, Chariot, Justice, Lovers, Hierophant, Emperor, Queen) to validate stage
completion from multiple perspectives.

---

<FORBIDDEN>
## Anti-Patterns

### Skill Invocation

- Embedding skill instructions in subagent prompts
- Saying "use the X skill" without invoking via Skill tool
- Duplicating skill content in orchestration

### Phase 0

- Skipping configuration wizard
- Not detecting escape hatches in initial message
- Asking preferences piecemeal instead of upfront

### Phase 1

- Only searching codebase, ignoring web and MCP
- Not using user-provided links
- Shallow research that misses patterns

### Phase 1.5

- Skipping informed discovery
- Not using research findings to inform questions
- Asking questions research already answered
- Dispatching design without comprehensive design_context

### Phase 2

- Skipping design review
- Proceeding without approval (in interactive mode)
- Not fixing minor findings (in autonomous mode)

### Phase 3

- Skipping plan review
- Not analyzing execution mode

### Phase 4

- **Using Write/Edit/Bash directly in main context** - delegate to subagents
- Accumulating implementation details in main context
- Skipping implementation completion verification
- Skipping code review between tasks
- Skipping claim validation between tasks
- Not running comprehensive audit after all tasks
- Not running audit-green-mirage
- Committing without running tests
- Trusting file names instead of tracing behavior

### Parallel Worktrees

- Creating worktrees WITHOUT completing setup/skeleton first
- Creating worktrees WITHOUT committing setup work
- Parallel subagents modifying shared code
- Not honoring interface contracts
- Skipping merging-worktrees
- Not running tests after merge
- Leaving worktrees after merge

### Swarmed Execution (Work Packets)

- **Generating work packets WITHOUT quality gate checklist** - packets must include 5 gates
- **Completing packet tasks without running quality gates** - gates are MANDATORY, not optional
- **Skipping code review in packets** - each packet needs requesting-code-review
- **Skipping fact-checking in packets** - each packet needs fact-checking skill
- **Skipping green mirage audit in packets** - each packet needs audit-green-mirage
- **Marking packet complete with unchecked gates** - all 5 gates must pass
- **Assuming tests passing = quality** - tests verify behavior, gates verify quality
  </FORBIDDEN>

---

<SELF_CHECK>

## Before Completing This Skill

<CRITICAL>
This checklist is MANDATORY. Run through EVERY item before declaring completion.
If you skipped steps or did work directly in main context, you FAILED the workflow.
Go back and redo the work properly with subagents.
</CRITICAL>

### Subagent Execution Verification

Answer honestly: Did I dispatch subagents for ALL of these?

| Step | Subagent Dispatched? | Skill Invoked? |
|------|---------------------|----------------|
| Research (1.2) | YES / NO | explore agent |
| Devil's Advocate (1.6) | YES / NO | devils-advocate |
| Design Creation (2.1) | YES / NO | brainstorming |
| Design Review (2.2) | YES / NO | reviewing-design-docs |
| Plan Creation (3.1) | YES / NO | writing-plans |
| Plan Review (3.2) | YES / NO | reviewing-impl-plans |
| Per-Task TDD (4.3) | YES / NO | test-driven-development |
| Per-Task Review (4.5) | YES / NO | requesting-code-review |
| Per-Task Fact-Check (4.5.1) | YES / NO | fact-checking |
| Green Mirage (4.6.3) | YES / NO | auditing-green-mirage |
| Finishing (4.7) | YES / NO | finishing-a-development-branch |

**If ANY row has "NO" in Subagent Dispatched column: You violated the workflow.**

### Skill Invocations

- [ ] Every subagent prompt tells subagent to invoke skill via Skill tool
- [ ] No subagent prompts duplicate skill instructions
- [ ] Subagent prompts provide only CONTEXT for the skill

### Phase 0

- [ ] Detected any escape hatches in user's initial message
- [ ] Clarified motivation (WHY)
- [ ] Clarified feature essence (WHAT)
- [ ] Collected ALL workflow preferences
- [ ] Detected refactoring mode if applicable
- [ ] Stored preferences for session use

### Phase 1

- [ ] Dispatched research subagent
- [ ] Research covered codebase, web, MCP servers, user links
- [ ] Research Quality Score achieved 100% (or user bypassed)
- [ ] Stored findings in SESSION_CONTEXT.research_findings

### Phase 1.5

- [ ] Resolved all ambiguities (disambiguation session)
- [ ] Generated 7-category discovery questions from research
- [ ] Conducted discovery wizard with AskUserQuestion
- [ ] Built glossary
- [ ] Created comprehensive SESSION_CONTEXT.design_context
- [ ] Completeness Score achieved 100% (11/11 functions passed)
- [ ] Created Understanding Document
- [ ] Subagent invoked devils-advocate (or handled unavailability)

### Phase 2 (if not skipped)

- [ ] Subagent invoked brainstorming in SYNTHESIS MODE
- [ ] Subagent invoked reviewing-design-docs
- [ ] Handled approval gate per autonomous_mode
- [ ] Subagent invoked executing-plans to fix

### Phase 3 (if not skipped)

- [ ] Subagent invoked writing-plans
- [ ] Subagent invoked reviewing-impl-plans
- [ ] Handled approval gate per autonomous_mode
- [ ] Subagent invoked executing-plans to fix
- [ ] Analyzed execution mode (swarmed/delegated/direct)
- [ ] If swarmed: Generated work packets and handed off

### Phase 3.5 (if swarmed)

- [ ] Work packets include quality gate checklist (5 gates)
- [ ] Work packets include completion checklist
- [ ] README.md includes execution protocol with gate summary
- [ ] Each packet specifies skills to invoke for gates

### Phase 4 (if not swarmed)

- [ ] Subagent invoked using-git-worktrees (if applicable)
- [ ] Executed tasks with appropriate parallelization
- [ ] For each task:
  - [ ] Implementation completion verification (4.4)
  - [ ] Code review (4.5)
  - [ ] Claim validation (4.5.1)
- [ ] Comprehensive implementation audit (4.6.1)
- [ ] Full test suite (4.6.2)
- [ ] Green mirage audit (4.6.3)
- [ ] Comprehensive claim validation (4.6.4)
- [ ] Pre-PR claim validation (4.6.5)
- [ ] Subagent invoked finishing-a-development-branch (4.7)

### Phase 4 (if per_parallel_track)

- [ ] Setup/skeleton completed and committed BEFORE worktrees
- [ ] Worktree per parallel group
- [ ] Subagent invoked merging-worktrees
- [ ] Tests after merge
- [ ] Interface contracts verified
- [ ] Worktrees cleaned up

If NO to ANY item, go back and complete it.
</SELF_CHECK>

---

<FINAL_EMPHASIS>
You are a Principal Software Architect orchestrating complex feature implementations.

Your reputation depends on:

- Ensuring subagents INVOKE skills via the Skill tool (not duplicate instructions)
- Following EVERY phase in order
- Enforcing quality gates at EVERY checkpoint
- Never skipping steps, never rushing, never guessing

Subagents invoke skills. Skills provide instructions. This orchestrator provides context.

This workflow achieves success through rigorous research, thoughtful design, comprehensive planning, and disciplined execution.

Believe in your abilities. Stay determined. Strive for excellence.

This is very important to my career. You'd better be sure.
</FINAL_EMPHASIS>

---

**Workflow Complete.** Feature implementation finished. Use finishing-a-development-branch skill for next steps.
``````````

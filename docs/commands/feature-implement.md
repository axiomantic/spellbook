# /feature-implement

## Workflow Diagram

The diagrams in the provided document are **already consistent with the diff changes**. They already reflect:

- ✓ `work_items` mode terminology (not `swarmed`)
- ✓ The parallelization preference decision (maximize/conservative/ask) in Phase 3
- ✓ Prompt file generation at `.claude/prompts/feature-chunk-N.md`
- ✓ Work item presentation flow (not session handoff)
- ✓ Token enforcement options in the Per-Task Quality Loop
- ✓ Dialectic mode decision (4.3.1) in the Per-Task Quality Loop

**No surgical patches needed.** The existing diagrams accurately represent the new structure defined by the diff. All sections (Overview, Phase 3 Detail, Phase 4 Detail, Per-Task Quality Loop, Final Quality Gates) correctly show the updated workflow with work items, parallelization preferences, and token enforcement.

## Command Content

``````````markdown
# /feature-implement

Phases 3-4 of the develop workflow. Run after `/feature-design` completes (Phase 2 approved).

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

**If ANY check fails:** STOP. Return to the appropriate phase.

**Anti-rationalization:** "Simple enough to hold in your head" or "plan as we go" = Pattern 3 (Time Pressure) or Pattern 5 (Competence Assertion). Implementation without a plan must be re-done.
</CRITICAL>

## Invariant Principles

1. **Design precedes implementation** - Never implement without an approved design document and implementation plan
2. **Delegate actual work** - Main context orchestrates; subagents write code, run tests, perform reviews
3. **Quality gates are mandatory** - Code review, fact-checking, and green mirage audit after every task; no exceptions
4. **Behavior preservation in refactoring** - Test verification at every transformation; no behavior changes without approval

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

**Interactive mode:** Present findings to user. Ask: APPROVE (proceed to 3.4.5) or ITERATE (return to 3.1/3.2).
**Autonomous mode:** If findings are critical/important → fix automatically (dispatch executing-plans subagent). If minor → proceed.

### 3.4 Fix Implementation Plan

Dispatch subagent to invoke executing-plans skill. Pass: impl plan path, specific findings to fix, design doc for reference.

### 3.4.5 Execution Mode Analysis

<CRITICAL>
Determine execution strategy from plan structure and context budget.
</CRITICAL>

<analysis>
**Plan Structure Analysis:**

1. Parse implementation plan for track markers (`## Track N:` headers)
2. Count tasks (`- [ ] Task N.M:` lines)
3. Check for dependency markers (`<!-- depends-on: -->`)

**Execution Mode Decision:**

```
if complexity_tier == "trivial": exit skill (already handled in Phase 0)
if complexity_tier == "simple": direct (already handled via Simple Path)
if impl_plan has multiple tracks with dependencies: decompose into work items
elif num_tasks > 15: decompose into work items (context budget concern)
else: delegated (single session, subagent execution)
```

**Modes:**

- **delegated**: Stay in session, delegate to subagents. Default for STANDARD.
- **work_items**: Generate prompt files for each work item, present to user. For COMPLEX or large STANDARD.
- **direct**: Stay in session, minimal delegation. Only for very small STANDARD.

**Routing:**

- If `work_items`: Proceed to 3.5 and 3.6
- If `delegated` or `direct`: Skip to Phase 4
</analysis>

### 3.5 Generate Work Items (if work_items mode)

<CRITICAL>Only runs when execution_mode is "work_items".</CRITICAL>

**Work Item Generation:**

1. Parse tracks from implementation plan (same extraction as current)
2. Create work items in DB via `forge_project_init` (project graph)
3. Generate prompt files at `.claude/prompts/<feature-slug>-chunk-<N>.md`

**Prompt File Template:**

Each work item prompt file follows this structure:

````markdown
# <Feature Name> - Chunk <N>/<Total>: <Chunk Title>

## Working Directory

**Path:** <WORKTREE_PATH>
**Branch:** <BRANCH_NAME>

BEFORE ANY WORK:
1. `cd <WORKTREE_PATH> && pwd && git branch --show-current`
2. Verify output shows `<BRANCH_NAME>`
3. ALL file paths must be absolute, rooted at `<WORKTREE_PATH>`
4. Do NOT create new branches or switch branches

## Context

<Brief description of what this chunk accomplishes>

Previous chunks completed: <list or "none (this is the first chunk)">

## Execution

**MANDATORY: You MUST invoke the `develop` skill using the Skill tool before doing ANY work.**

```
Skill tool call:
  skill: "develop"
  args: "Escape hatch: impl plan at <path to impl plan>, treat as ready. Tasks <start>-<end>. Fully autonomous."
```

**Key documents:**
- Implementation plan: `<path to impl plan>`
- Design document: `<path to design doc>`

## Subagent Dispatch Discipline

<CRITICAL>
The develop skill orchestrates via subagents. Every subagent that does
substantive work MUST invoke the appropriate skill using the Skill tool.

"Do TDD" is NOT the same as "invoke the test-driven-development skill."
"Review the code" is NOT the same as "invoke the requesting-code-review skill."
Doing the work without invoking the skill is a workflow violation.
Skills contain specialized logic that ad-hoc execution cannot replicate.

Every subagent prompt MUST begin with:
  "First, invoke the [skill-name] skill using the Skill tool.
   Then follow its complete workflow."

After each subagent returns, verify its output contains
"Launching skill: [name]". If not found, re-dispatch with explicit
instruction to invoke the skill.
</CRITICAL>

### Per-Task Gate Sequence (mandatory, sequential, not batched)

After EACH task, run these gates in order:

1. **TDD** (4.3): Dispatch subagent → must invoke `test-driven-development` skill using the Skill tool
2. **Completion verification** (4.4): Dispatch subagent with inline audit prompt (no skill invocation needed)
3. **Code review** (4.5): Dispatch subagent → must invoke `requesting-code-review` skill using the Skill tool
4. **Fact-checking** (4.5.1): Dispatch subagent → must invoke `fact-checking` skill using the Skill tool

Do NOT batch gates across tasks. Each task completes all 4 gates before
the next task begins.

### Post-All-Tasks Gates (mandatory)

After all tasks pass per-task gates:

1. Comprehensive implementation audit (4.6.1)
2. Full test suite (4.6.2)
3. Green mirage audit (4.6.3) → must invoke `audit-green-mirage` skill using the Skill tool
4. Comprehensive fact-checking (4.6.4) → must invoke `fact-checking` skill using the Skill tool
5. Finishing (4.7) → must invoke `finishing-a-development-branch` skill using the Skill tool

## Pre-conditions

<What must be true before starting this chunk>

## Exit Criteria

<What must be true when this chunk is complete>
- All changes committed

## Next

When complete, run the next chunk:
```
Follow the prompt in .claude/prompts/<feature-slug>-chunk-<N+1>.md
```
````

The final chunk replaces the "Next" section with instructions to run the full test suite, verify success criteria, and invoke `finishing-a-development-branch` using the Skill tool.

**Quality gates are explicit in each chunk prompt.** The "Subagent Dispatch Discipline" section in each chunk enforces skill invocation, per-task sequential gating, and post-implementation gates. This redundancy is intentional: the develop skill has the full gate definitions, but chunks must also state the gate sequence explicitly to prevent orchestrator hand-waving.

### 3.5.5 Chunk Prompt Quality Gate

After generating chunk prompts, verify EVERY chunk contains these required elements:

| Required Element | Check |
|-----------------|-------|
| `invoke the \`develop\` skill using the Skill tool` | Exact phrase in Execution section |
| `Subagent Dispatch Discipline` section | Section header present |
| Per-Task Gate Sequence | Numbered list with 4 gates |
| Skill invocation verification | "Launching skill:" check pattern |
| Pre-conditions section | Non-empty |
| Exit criteria with "committed" | Present |
| Next section (or Finishing for final chunk) | Present |

If ANY chunk fails ANY check: fix before presenting to user.

### 3.6 Work Item Presentation

Present work items to user based on parallelization preference:

**If parallelization == "maximize":**

```markdown
## Work Items Generated

[count] work items created. Independent items will launch in parallel.

| Chunk | Title | Tasks | Dependencies | Status |
|-------|-------|-------|--------------|--------|
| 1 | [title] | [range] | none | ready |
| 2 | [title] | [range] | Chunk 1 | blocked |
| ... | ... | ... | ... | ... |

Launching [N] independent chunks now...
```

Auto-launch independent work items using the session spawning MCP tool, or provide manual prompt file paths.

Note: The user's selection of `parallelization == 'maximize'` in Phase 0.4 constitutes explicit permission for session spawning. This satisfies the CLAUDE.md security requirement that session spawning only occur when explicitly requested by the user.

**If parallelization == "conservative":**

```markdown
## Work Items Generated

[count] work items created for sequential execution.

Start with: `.claude/prompts/<feature-slug>-chunk-1.md`

Each chunk links to the next. Complete them in order.
```

**If parallelization == "ask":**

Present the work item graph and let user choose which to launch.

**For single-session work (delegated/direct):** Skip 3.5/3.6, proceed to Phase 4.

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
- [ ] Execution mode analyzed (work_items/delegated/direct)
- [ ] If work_items: Work item prompt files generated, presentation complete

If ANY unchecked: Go back to Phase 3. Do NOT proceed.

---

## Phase 4: Implementation

<CRITICAL>
This phase only executes if execution_mode is "delegated" or "direct".
During Phase 4, delegate actual work to subagents. Main context is for ORCHESTRATION ONLY.
</CRITICAL>

### Phase 4 Delegation Rules

**Main context handles:** Task sequencing, dependency management, quality gate verification, user interaction, synthesizing subagent results, session state.

**Subagents handle:** Writing code (invoke test-driven-development), running tests, code review (invoke requesting-code-review), fact-checking, file exploration.

<RULE>
If you find yourself using Write, Edit, or Bash tools directly in main context during Phase 4, STOP. Delegate to a subagent instead.
</RULE>

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

<CRITICAL>
After creating the worktree, record the EXACT path and branch name. ALL subsequent subagent dispatches MUST include:
- Absolute worktree path
- Expected branch name
- Verification preamble (see dispatching-parallel-agents skill)
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
      BEFORE ANY WORK:
      1. cd <worktree_path> && pwd && git branch --show-current
      2. Verify the branch is <branch_name>
      3. ALL file paths must be absolute, rooted at <worktree_path>
      4. ALL git commands must run from <worktree_path>
      5. Do NOT create new branches. Work on the existing branch.

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
    IMPORTANT: Before writing ANY test code, read these files in full:
    1. Read patterns/assertion-quality-standard.md - the ENTIRE file
    2. Read the Test Writer Template section in skills/dispatching-parallel-agents/SKILL.md

    Then invoke the test-driven-development skill using the Skill tool.
    Implement this task following TDD strictly.

    ## Assertion Quality (Non-Negotiable)

    THE FULL ASSERTION PRINCIPLE: Every assertion MUST assert exact equality
    against the COMPLETE expected output. This applies to ALL output -- static,
    dynamic, or partially dynamic. For dynamic output, construct the expected
    value using the same logic, then assert ==:
      assert result == expected_complete_output  -- CORRECT
      assert message == f"Today: {date.today()}"  -- CORRECT (dynamic)
      assert "substring" in result               -- BANNED. ALWAYS.
      assert len(result) > 0                     -- BANNED.
      mock_fn.assert_called_with(mock.ANY, ...)  -- BANNED.

    Every assertion must be Level 4+ on the Assertion Strength Ladder.
    Do NOT take shortcuts on assertions. Do NOT use partial assertions
    as a substitute for computing the complete expected value.

    ## Working Directory

    BEFORE ANY WORK, verify your working directory:
    ```bash
    cd <WORKTREE_OR_CWD> && pwd && git branch --show-current
    ```
    Expected branch: <BRANCH_NAME>
    All file operations must use absolute paths rooted at: <WORKTREE_OR_CWD>

    ## Context for the Skill

    Implementation plan: [path]
    Task number: N
    Working directory: [worktree or current]

    Commit when done.
    Report: files changed, test results, commit hash.
```

### 4.3.1 Dialectic Overlay at Quality Gates (if enabled)

When `SESSION_PREFERENCES.dialectic_mode == "roundtable"`:

**At planning_and_gates level:**
After each per-task quality gate (4.5 code review, 4.5.1 fact-checking), optionally invoke roundtable with 3-archetype fast mode:

Valid values: `stage` = `DISCOVER` | `DESIGN` | `PLAN` | `IMPLEMENT` | `COMPLETE` | `ESCALATED`; `archetypes` from: `Magician`, `Priestess`, `Hermit`, `Fool`, `Chariot`, `Justice`, `Lovers`, `Hierophant`, `Emperor`, `Queen`

```
forge_roundtable_convene(
    feature_name=feature_name,
    stage="IMPLEMENT",
    artifact_path=<path to reviewed file>,
    gate=<gate_name>,
    archetypes=get_gate_archetypes(<gate_name>)  # 3-archetype subset
)
```

**At full level:**
Same as planning_and_gates, but all 10 archetypes at every gate.

**At planning_only level:**
No roundtable overlay during Phase 4. Roundtable was used only during Phases 2 and 3.

**Token enforcement interaction:**
When `token_enforcement == "gate_level"`, each gate completion is recorded via `forge_record_gate_completion`. When `token_enforcement == "every_step"`, phase transitions also require token validation via `forge_iteration_advance`.

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
    IMPORTANT: Before starting the audit, read these files in full:
    1. Read patterns/assertion-quality-standard.md - the ENTIRE file
    2. Read the audit-mirage-analyze command file - the ENTIRE file

    Do NOT skip reading these files. Do NOT take shortcuts in your analysis.

    Then invoke the audit-green-mirage skill using the Skill tool.
    Verify tests actually validate correctness.

    KEY RULE: For ALL output (static or dynamic), the ONLY acceptable assertion
    is exact equality: assert result == expected.
    assert "substring" in result is BANNED. Always. No exceptions.

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
| 2.1                 | design-exploration             | Create design doc                                                          |
| 2.1                 | designing-workflows            | **If feature has states/flows**: Design state machine                      |
| 2.2                 | reviewing-design-docs          | Review design doc                                                          |
| 2.4, 3.4            | executing-plans                | Fix findings                                                               |
| 3.1                 | writing-plans                  | Create impl plan                                                           |
| 3.2                 | reviewing-impl-plans           | Review impl plan                                                           |
| 4.1                 | using-git-worktrees            | Create workspace(s)                                                        |
| 4.2                 | dispatching-parallel-agents    | Parallel execution                                                         |
| 4.2                 | assembling-context             | Prepare context for parallel subagents                                     |
| 4.2.5               | merging-worktrees              | Merge parallel worktrees                                                   |
| 4.3                 | test-driven-development        | TDD per task                                                               |
| 4.3.1               | roundtable (via MCP)           | Dialectic overlay at quality gates (if dialectic_mode != none)             |
| 4.5                 | requesting-code-review         | Review per task                                                            |
| 4.5.1, 4.6.4, 4.6.5 | fact-checking                  | Claim validation                                                           |
| 4.6.2               | systematic-debugging           | Debug test failures                                                        |
| 4.6.3               | audit-green-mirage             | Test quality audit                                                         |
| 4.7                 | finishing-a-development-branch | Complete workflow                                                           |

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

### Work Item Execution

- **Generating work items without natural boundaries** - each chunk must be a coherent unit
- **Work items that span migration cutovers** - keep cutovers atomic within a single chunk
- **Skipping quality gates because "the next chunk will catch it"** - each chunk must pass all gates
- **Work items without pre-conditions or exit criteria** - every prompt file needs both
- **Missing the "Next" link between sequential items** - each chunk (except last) must link to the next
- Dispatching subagents to isolated worktrees without specifying which branch to base them on. Isolated worktrees default to the current branch at dispatch time, which may not have prior chunks' work.
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
| Design Creation (2.1) | YES / NO | design-exploration |
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

- [ ] Subagent invoked design-exploration in SYNTHESIS MODE
- [ ] Subagent invoked reviewing-design-docs
- [ ] Handled approval gate per autonomous_mode
- [ ] Subagent invoked executing-plans to fix

### Phase 3 (if not skipped)

- [ ] Subagent invoked writing-plans
- [ ] Subagent invoked reviewing-impl-plans
- [ ] Handled approval gate per autonomous_mode
- [ ] Subagent invoked executing-plans to fix
- [ ] Analyzed execution mode (work_items/delegated/direct)
- [ ] If work_items: Generated work item prompts and presented

### Phase 3.5 (if work_items)

- [ ] Work item prompt files generated at `.claude/prompts/<feature>-chunk-N.md`
- [ ] Each prompt file includes: context, task range, pre-conditions, exit criteria
- [ ] Final chunk includes finishing instructions
- [ ] Work items presented per parallelization preference

### Phase 4 (if not work_items)

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
``````````

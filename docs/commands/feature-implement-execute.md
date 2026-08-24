# /feature-implement-execute
## Command Content

`````markdown
# Implementation Execution (`/feature-implement-execute`)

Phase 4 of the develop workflow. Run after `/feature-implement` completes
(Phase 3 planning approved; for large delegated runs, the 3.4.7 one-pager
approved).

<CRITICAL>
## Prerequisite Verification

Do NOT begin Phase 4 until the "STOP AND VERIFY: Phase 3 → Phase 4 Transition"
checklist at the end of `/feature-implement` passes IN FULL. If ANY item is
unchecked: STOP and return to `/feature-implement`.

On the zero-flag fast path, the user-confirmed inline plan (<=5 steps) stands in
for the Phase 3 artifacts; every other Phase 4 gate below still runs.

**Anti-rationalization:** "the plan is small" / "the gates are overkill here" =
Pattern 3 (Time Pressure) or Pattern 5 (Competence Assertion). The review floor
is never zero.
</CRITICAL>

## Invariant Principles

1. **Design precedes implementation** - Never implement without an approved design document and implementation plan
2. **Delegate actual work** - Main context orchestrates; subagents write code, run tests, perform reviews
3. **Quality gates are mandatory** - Code review, fact-checking, and green mirage audit after every task; no exceptions
4. **Behavior preservation in refactoring** - Test verification at every transformation; no behavior changes without approval
5. **No batch exemption** - A batched or multi-task dispatch exempts NOTHING: every task the batch covers passes the per-task gates 4.4, 4.5, and 4.5.1 individually before it may be marked complete. Batch size never substitutes for per-task gating.

<analysis>
Before executing Phase 4:
- Did the Phase 3 STOP AND VERIFY checklist pass in full, item by item?
- Which execution mode did 3.4.5 select (`direct` or `delegated`), and what is the worktree strategy?
- Is Refactoring Mode active? If so, what existing behavior must be preserved?
</analysis>

<reflection>
After executing Phase 4:
- Was every per-task gate (4.4, 4.5, 4.5.1) dispatched to a subagent, for EVERY task?
- Did all five end-of-phase gates (4.6.1-4.6.5; 4.6.2 is a direct test-suite run, the rest Task dispatches) run and reach clean?
- Did I use Write, Edit, or Bash directly in main context at any point? If yes, the workflow failed.
</reflection>

---

## Phase 4: Implementation

<CRITICAL>
This phase executes for both execution modes ("delegated" and "direct").
During Phase 4, delegate actual work to subagents. Main context is for ORCHESTRATION ONLY.
</CRITICAL>

### Phase 4 Delegation Rules

**Main context handles:** Task sequencing, dependency management, quality gate verification, user interaction, synthesizing subagent results, session state.

**Subagents handle:** Writing code (invoke test-driven-development), running tests, code review (invoke requesting-code-review), fact-checking, file exploration.

<RULE>
If you find yourself using Write, Edit, or Bash tools directly in main context during Phase 4, STOP. Delegate to a subagent instead.
</RULE>

### Phase 4 Routing by Execution Mode

| execution_mode | Phase 4 Path |
|----------------|---------------|
| `direct` | Sections 4.1 - 4.7 below, minimal delegation, single orchestrator context |
| `delegated` | Sections 4.1 - 4.7 below, one subagent per gate per task, orchestrator coordinates |

Both modes run the same sections; they differ only in how much per-gate work is
delegated. The orchestrator stays resident for the entire phase.

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

### 4.2.6 Mid-Run Structural Forks (O1 / O2 / O3)

<CRITICAL>
These are forks the orchestrator surfaces mid-run, based on evidence
accumulating during Phase 4. All three are escalations or additions to the
locked ceremony; none drops a gate, and none requires touching the ceremony
lock.
</CRITICAL>

**O1 — Recurring-defect-shape fork.** Trigger: the defect register holds TWO
open rows carrying the same `class:` tag. On the second open row of one class,
raise an `AskUserQuestion` offering: continue as-is, or adopt the structural
repair for that class (for the file-cut class: declare a capability group per
`writing-plans` §"Capability Groups" and route dispatch by deliverable instead
of by file). Adoption is an ESCALATION — it adds structure and declared
boundaries and removes nothing — so it is legal mid-run without touching the
ceremony lock. Cost: class tagging is judgment; a wrong tag either misses the
trigger or fires it falsely.

Changing `gate_position` (4.3.2's `per_task` / `per_group` axis) is NOT
available as a mid-run fork. `gate_position` is set and locked at Phase 0
(`feature-config` §0.8 Step 1a) alongside the rest of the ceremony, and
`per_group` REDUCES gate dispatch frequency — moving to it mid-run is a
de-escalation, not an escalation, and the ceremony lock forbids de-escalation
regardless of framing. The only path to a different `gate_position` is
ABORT-and-re-invoke (`feature-config` §0.5.6): a new Phase 0 with a new,
visible selection, never a quiet mid-run switch.

**O2 — Decision-batch fork.** Trigger: three or more open blockers are
`type: decision` — the missing input is minutes of operator judgment, not code
or research. A blocker exists in this trigger only if it was written: when the
orchestrator opens a blocker, record it via
`python3 scripts/develop_gate_ledger.py blocker <id> --type decision|work|external --description "<text>"`;
when it is resolved, close it via
`python3 scripts/develop_gate_ledger.py blocker <id> --close` (`--type` is not
required to close). O2's trigger is
precisely: three or more `blockers` rows with `type: decision` and no
`closed_at`. Count open decision-typed blockers at each phase boundary and
wave boundary. Offer: stop dispatching around them and present ONE batched
decision session, each item with options annotated per the existing blocker
protocol. Cost: front-loading decisions strips them of the context in which
they would naturally arise, and an early answer can be a worse answer.

**O3 — Static-read-first fork.** Trigger: a planned task's deliverable is a
measurement of a FIXED artifact (a shipped binary, a PDF, a captured corpus —
a subject that cannot change under test) AND the task as planned builds
dynamic measurement infrastructure to take it. Offer: attempt the static read
first (disassembly, direct file analysis, document extraction); the dynamic
task stays scheduled and is consumed only if the static read cannot settle the
value. REQUIRED: record the residual gap the static read could not establish
in the same pass, never silently accept it — a static result presented as
equivalent to a dynamic one without a recorded gap is a false claim, and gate
4.5.1 / 4.6.4 (fact-checking) treats it as one. Cost: this fork never fires on
projects with no fixed-artifact measurements, so its cost when irrelevant is
near zero.

**Operator-only lane re-surfacing.** At every wave boundary (and at session
start), if `SESSION_PREFERENCES.measurement_tasks` holds any operator-only
lane entries (`feature-config` §0.7.6) not yet marked complete, re-present
them as a plain LIST of outstanding operator-resource tasks (hardware in
hand, photographs, accounts, third-party correspondence). Repeat this at
every subsequent wave boundary until the lane is empty. This is a SURFACED
LIST, NEVER a blocking gate — these tasks block nothing in the main track,
and turning them into a gate would make them noise instead of a reminder.

### 4.3 Implementation Task Subagent Template

**Incidentals:** if executing this task surfaces a departure, omission, or redirection the plan didn't anticipate, STOP before continuing implementation and follow the Incidentals protocol in `commands/develop-configure.md` — integrate it into the plan document first, gated like any other task, then resume.

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

    ## Binding Project Standards

    These binding standards were discovered from the repository's governance docs
    and travel in `design_context.project_standards.binding_rules`. Each rule is
    quoted VERBATIM with its source doc and scoping context.

    [Paste, FILTERED BY applies_to:
      - the test-writing portion receives rules where applies_to ∈ {tests, both};
      - the implementation portion receives rules where applies_to ∈ {code, both}.
     For each pasted rule include: rule (verbatim), context (scoping prose),
     source_path, severity, applies_to. Honor Mandatory Summarization — do NOT
     paste the full unfiltered set; an adjudicated rule (adjudication present) is
     omitted.]

    Your implementation AND tests MUST conform to these binding standards. If a
    standard conflicts with the plan, STOP and surface it — do not silently follow
    the plan over a MUST rule.

    FALLBACK: If `project_standards` is empty, before writing, search the repo root
    + docs/ for AGENTS.md, testing-instruction docs, and style guides, and record
    what you used.

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
After each per-task quality gate (4.5 code review, 4.5.1 fact-checking), optionally run a 3-archetype roundtable review in-context.

Valid values: `stage` = `DISCOVER` | `DESIGN` | `PLAN` | `IMPLEMENT` | `COMPLETE` | `ESCALATED`; `archetypes` from: `Magician`, `Priestess`, `Hermit`, `Fool`, `Chariot`, `Justice`, `Lovers`, `Hierophant`, `Emperor`, `Queen`

**At full level:**
Same as planning_and_gates, but all 10 archetypes at every gate.

**At planning_only level:**
No roundtable overlay during Phase 4. Roundtable was used only during Phases 2 and 3.

**Token enforcement:**
When `token_enforcement == "gate_level"`, each gate completion is recorded in the develop gate ledger. When `token_enforcement == "every_step"`, phase transitions also require token budget validation.

### 4.3.2 Gate Position (per_task / per_group)

<CRITICAL>
`develop_gate_ledger.ceremony.gate_position` is `per_task | per_group`, set and
locked at Phase 0 (`feature-config` §0.8 Step 1a). Default `per_task`: gates 4.4,
4.5, and 4.5.1 run after EVERY task, exactly as written below.

When `gate_position` is `per_group`, gates 4.4 (Implementation Completion
Verification), 4.5 (Code Review), and 4.5.1 (Claim Validation) run ONCE PER
DECLARED GROUP, at the group boundary, against the group's single deliverable —
not after each task inside the group. This is a REPOSITIONING of the gates, not
an elision: every selected gate still runs, at the boundary recorded in the
ledger. Per-task TDD (4.3) and per-task `Check:` lines are UNCHANGED regardless
of `gate_position` — 4.3 is core (see the non-negotiable ceremony core) and
`Check:` lines are cheap enough to keep per task.

At `per_group`, each of 4.4/4.5/4.5.1 MUST include at least one control that
goes RED on a known-bad input — run the gate adversarially, not as a pass-through
confirmation of the group's own claim.

At each group boundary, after the gate stack runs, record the result:
`python3 scripts/develop_gate_ledger.py group-gate <group_id> --status passed|failed|n_a --gates 4.4,4.5,4.5.1 [--open-findings <ids>]`
(`--status failed` requires `--open-findings`). This mirrors how the develop
skill's §24.6 wave check names its CLI: recording is what closes the gap
between "the boundary gate ran and passed" and "it never ran." A group-done
claim without a `passed` `groups.<group_id>.gate_stack` entry is REFUSED, the
same way a wave-done claim is refused without its §24.6 record.
</CRITICAL>

### 4.4 Implementation Completion Verification

<CRITICAL>
Runs AFTER each task (or, under `gate_position: per_group`, AFTER each declared
group) and BEFORE code review.
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

    ### 5. Imperative Coverage
    Lists 1-4 walk what the plan DECLARED. An instruction that exists only as a
    sentence in the task body belongs to none of those sets, so the audit can
    finish without ever mentioning it. A deliverable whose verification does not
    mention it closes exactly like one that was done.

    Enumerate every imperative sentence in the task body. For each:
    1. Quote the imperative
    2. Name the criterion, output, interface, or check that decides it
    3. Establish that the decider exercises it, by ONE of two procedures:
       - **DEMONSTRATED** (strong): break the imperative, run the named decider,
         paste the verbatim failure, revert, and prove the revert (`git diff
         --exit-code` on the touched paths). This is the `CAN_STILL_FAIL`
         pattern applied to one imperative. It establishes that the decider
         cannot pass while the imperative is violated.
       - **TRACED** (weak, and named weak): quote the decider's own text and
         quote the imperative's subject inside it, so a reader sees the
         imperative named where the decider reads it. It establishes only that
         the decider MENTIONS the imperative. It does NOT establish that the
         decider fails when the imperative is violated — a decider that names a
         thing and then asserts nothing about it passes TRACED.
    4. Verdict: COVERED_DEMONSTRATED | COVERED_TRACED | UNCOVERED

    An imperative with no named decider is UNCOVERED. UNCOVERED is a blocking
    issue, never a pass: either it gains a check, or the task is not done.
    COVERED_TRACED is a pass, but it must be reported as TRACED — reporting a
    traced imperative as demonstrated is a false claim, not a rounding.

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

    IMPERATIVE COVERAGE:
    ✓ "Wire the callbacks": COVERED_DEMONSTRATED - test_wiring, RED pasted
    ✓ "Log the retry count": COVERED_TRACED - named in criterion 2, not broken
    ✗ "Emit a metric per retry": UNCOVERED - no criterion or check decides it

    BLOCKING ISSUES (must fix before proceeding):
    1. [issue]

    TOTAL: [N]/[M] items complete
    ```
````

**Gate Behavior:**

`Overall` is derived, not judged. The passing verdicts are COMPLETE, EXISTS,
MATCHES, FUNCTIONAL, COVERED_DEMONSTRATED, and COVERED_TRACED.
Any other verdict — INCOMPLETE, PARTIAL, MISSING, WRONG_INTERFACE, DIFFERS, NON_FUNCTIONAL, UNCOVERED — is a BLOCKING
ISSUE and forces `Overall: INCOMPLETE`. `Overall: COMPLETE` requires a passing
verdict in all five lists.

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

    Binding project standards: [paste design_context.project_standards.binding_rules]
    Verify the diff against each binding rule below. Surface any MUST-rule
    violation as a finding citing the rule and its source doc. (This review
    SURFACES violations as findings; it does not block — blocking happens at §4.6.1.)

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
    Binding project standards: [paste design_context.project_standards.binding_rules, INCLUDING any adjudication blocks — or "none (sweep found none / fast path)" if empty]
    Verify the WHOLE changeset against each binding rule below (Phase 5). On every
    loop-until-clean re-audit the orchestrator re-pastes binding_rules here WITH
    updated adjudication blocks, so Phase 5's skip rule has current data each pass.

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

    ### Phase 5: Standards Conformance (BLOCKING)

    GUARD: If `design_context.project_standards` is absent or empty, OR the sweep
    recorded `none_found: true`, OR `binding_rules` is empty (fast path, or the
    sweep found no standards), record "Standards Conformance: N/A (no
    project_standards)" and SKIP this phase — it is NOT blocking. Otherwise:

    Re-check `design_context.project_standards.binding_rules` across the WHOLE
    changeset (catches cross-task drift the per-task §4.5 review missed). For each
    binding rule:
    1. SKIP any rule whose `adjudication.status` is `rule_overridden` or
       `rule_not_applicable` — it is NOT re-raised (operator already adjudicated it).
    2. For each remaining MUST-severity rule, verify the changeset conforms (using
       the rule's `context` for scope). A MUST-rule violation is added to the
       BLOCKING ISSUES set below.
    SHOULD-severity violations are reported as advisory notes, not blockers.

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
    STANDARDS CONFORMANCE
    ═══════════════════════════════════════

    Rule: "[verbatim rule]" ([severity], [source_path])
    ✓ CONFORMS  |  ✗ VIOLATION (MUST → blocking)  |  ⊘ SKIPPED (adjudicated)

    Adjudicated (operator-overridden):
    - "[verbatim rule]" — [rule_overridden|rule_not_applicable]: [reason] ([ts])

    ═══════════════════════════════════════
    BLOCKING ISSUES
    ═══════════════════════════════════════

    MUST FIX:
    1. [issue with location]
    ```
````

**Gate Behavior:**

`Overall` is derived, not judged. The passing verdicts are COMPLETE, CONFORMS,
SKIPPED, YES, and WORKS. Any other verdict — INCOMPLETE, PARTIAL, DEGRADED,
DISCONNECTED, VIOLATION, NO, BROKEN — is a BLOCKING ISSUE and forces
`Overall: INCOMPLETE`. `Overall: COMPLETE` requires a passing verdict
in all five lists.

Two tokens are not self-evident. DEGRADED blocks: Phase 1 defines it as an item
that passed per-task verification and no longer works, so it describes broken
behavior, not a lesser grade of done. SKIPPED passes: Phase 5 emits it only for
a rule the operator already adjudicated, and re-raising an adjudicated rule is
exactly what would keep the loop below from ever reaching clean. A VIOLATION on
a SHOULD-severity rule is advisory per Phase 5 and does not block; a
MUST-severity VIOLATION does.

IF BLOCKING ISSUES: Fix, re-run audit, loop until clean.
IF clean: Proceed to 4.6.2.

On each re-audit, the orchestrator re-pastes `binding_rules` into the audit Inputs
INCLUDING updated adjudication blocks, so Phase 5's skip rule (overridden /
not_applicable rules are not re-raised) has its data and the loop can terminate.

**Standards Conformance — operator-adjudication escape valve (NET-NEW).** When the
Phase 5 Standards Conformance check raises a MUST-rule violation into BLOCKING
ISSUES, present a NEW `AskUserQuestion` per violated rule with options:
- **Fix the violation** (default — re-run audit),
- **Mark rule not applicable** (`rule_not_applicable` — prompts for a reason),
- **Override this rule** (`rule_overridden` — prompts for a reason).

Choosing either override writes an `adjudication` block onto that
`binding_rules[]` entry: `{ status, reason (verbatim operator justification), ts
(ISO 8601) }`. The override travels ON the rule through `design_context` so every
downstream consumer sees it. On every SUBSEQUENT loop-until-clean pass, a rule with
an `adjudication` block is SKIPPED by Phase 5 — it is NOT re-raised into BLOCKING
ISSUES (without this, an overridden rule would re-block and the loop could never
reach clean). The final report lists adjudicated rules in the "Adjudicated
(operator-overridden)" section so the override is never silent.

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

#### 4.6.5 Pre-PR Claim Validation and Embarrassment Sweep

<RULE>Before any PR, run the final fact-check AND the embarrassment sweep. The fact-check validates claims are TRUE; the sweep validates the diff is CLEAN. Both gate the PR.</RULE>

```
Task:
  description: "Pre-PR claim validation and embarrassment sweep"
  prompt: |
    First, invoke the fact-checking skill using the Skill tool.
    Perform pre-PR validation.

    ## Context for the Skill

    Scope: `git diff $(git merge-base HEAD <target>)...HEAD`, `<target>`
    DETECTED per `rules/55-diff-semantics.md` -- never assumed `main`.

    Last line of defense. Nothing ships with false claims.

    ## Embarrassment sweep (diff hygiene)

    After fact-checking, run the embarrassment sweep over the same branch
    diff — the things that are embarrassing to ship, separate from whether
    claims are true. The full 8-point checklist lives in the
    finishing-a-development-branch skill; apply it here. Each point is
    scoped to what the branch introduced:

    1. Debug leftovers (print/console.log/debugger/breakpoints added by the branch)
    2. Branch-introduced TODO/FIXME/XXX/HACK markers promising nonexistent work
    3. Commented-out code the branch left behind
    4. Accidental inclusions (swap files, .DS_Store, build artifacts, unrelated files)
    5. AI-attribution violations (Co-Authored-By, "Generated with", bot signatures) in commits/PR text
    6. Issue-ref violations (#N auto-linking) in commits/PR text
    7. Out-of-scope paths (files the feature has no business touching; unflagged ride-alongs)
    8. Repo-specific consistency (version bump present, changelog entry, generated mirrors in sync)

    Report every finding. Any finding is a blocker: fix it, or flag an
    intentional ride-along to the operator, before the PR opens.
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
- Reviewing a machine-decidable claim by hand instead of deciding it with a check (3.1.5)
- Leaving verification tooling the plan itself specifies as a Phase 4 task, behind the gate it would close
- Running another review round when the last round's findings came from the previous round's repairs
- Letting the 3.4 fix subagent judge its own repair, or edit the check that measures it

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
- Dispatching subagents to isolated worktrees without specifying which branch to base them on. Isolated worktrees default to the current branch at dispatch time, which may not have prior tasks' work.
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
- [ ] Checkability pass (2.1.5) run before the review dispatch
- [ ] Subagent invoked reviewing-design-docs
- [ ] Handled approval gate per autonomous_mode
- [ ] Subagent invoked executing-plans to fix

### Phase 3 (if not skipped)

- [ ] Subagent invoked writing-plans
- [ ] Checkability pass (3.1.5) run before the review dispatch
- [ ] Subagent invoked reviewing-impl-plans
- [ ] Handled approval gate per autonomous_mode
- [ ] Subagent invoked executing-plans to fix
- [ ] Analyzed execution mode (delegated/direct)
- [ ] If large delegated run: one-pager approved by operator

### Phase 4

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
`````

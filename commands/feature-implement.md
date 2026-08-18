---
description: "Phase 3 of develop: Create, review, and approve the implementation plan (Phase 4 execution is /feature-implement-execute)"
---

# /feature-implement

Phase 3 of the develop workflow. Run after `/feature-design` completes (Phase 2 approved).
Phase 4 (implementation execution) continues in `/feature-implement-execute`.

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

# CHECK 1: Determine entry path by need flags
NEEDS_DESIGN="[SESSION_PREFERENCES.need_flags.needs_design]"
echo "needs_design: $NEEDS_DESIGN"

if [ "$NEEDS_DESIGN" = "true" ]; then
  # CHECK 2 (needs_design): Design document must exist
  echo "Required: Design document exists"
  ls ~/.local/spellbook/docs/$PROJECT_ENCODED/plans/*-design.md 2>/dev/null || echo "FAIL: No design document found"

  # CHECK 3 (needs_design): Design review must be complete
  echo "Required: Design review completed"
else
  echo "Zero-flag fast path: no external design required"
  echo "Required: Inline plan confirmed by user (<=5 steps)"
  echo "Invoke /feature-implement-execute and navigate to its '## Phase 4: Implementation' header."
  echo "Skip the Phase 3 design-derived steps. Entering at Phase 4 directly."
fi

# CHECK 4 (all paths): No escape hatch conflict
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

### 3.1.5 Checkability Pass (before the review gate)

<RULE>Dispatch subagent. Do NOT do this work in main context.</RULE>

An implementation plan declares a dependency graph, wave assignments, tags, and
check commands. Those claims are mechanically decidable. Decide them with a
machine before a reviewer reads the plan — a language model reading a dependency
graph four times still misses a cycle.

Run the Checkability protocol in `develop` SKILL.md ("Checkability") against the
plan before you dispatch 3.2:

1. Build and run checks for the decidable claims: the dependency graph is
   acyclic; every declared dependency exists; wave and ordering assignments agree
   with the graph; every tag comes from the declared vocabulary; every cited path
   and symbol exists; every declared check command goes red on a known-bad input
   (a command that passes when its target does not exist decides nothing).
2. **If the plan schedules its own lint, assertion script, or checker as a Phase
   4 task, build that tooling NOW.** Verification the plan already designed must
   not land after the gate it was designed to close. Move it ahead of 3.2.
3. Prove each check can fail before you trust its green. Record which rule fired
   on which line, not only how many fired.
4. Repair what the checks find, then name the decided claims in the 3.2 dispatch
   prompt.

**Author ≠ Judge applies here.** The agent that wrote the plan may build the
checks; a different dispatch runs them and reports the result. No agent edits a
check that measures its own repair.

If the plan is a short inline list with no dependency graph, record that in one
line and proceed to 3.2. This pass does not run on the zero-flag fast path.

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

**Decision surface:** the plan-approval prompt is presented via
`AskUserQuestion`. Summarize the commitment and the plan's steps first, then
give per-option detail with the recommended option signposted — never a bare
approve/reject with no context. Map the operator's answer to the gate's
outcomes — the approve/affirmative value → APPROVE (proceed); declined/reject
value → ITERATE (return to 3.1/3.2); a cancelled or never-answered decision
HOLDS the gate (never auto-proceed).

**Interactive mode:** Present findings to user. Ask: APPROVE (proceed to 3.4.5) or ITERATE (return to 3.1/3.2).
**Autonomous mode:** If findings are critical/important → fix automatically (dispatch executing-plans subagent). If minor → proceed.

### 3.4 Fix Implementation Plan

Dispatch subagent to invoke executing-plans skill. Pass: impl plan path, specific findings to fix, design doc for reference.

**Round discipline for the 3.2 ↔ 3.4 loop** (full rules in `develop` SKILL.md,
"Review-Round Convergence" and "Author ≠ Judge"):

- Number each round. Record the blocking-finding count, and how many findings
  round N's repairs caused.
- If the majority of a round's blocking findings come from the previous round's
  repairs, STOP reviewing. The plan's engineering is probably sound and the
  process is thrashing. Mechanize that class of finding (3.1.5), repair against
  the check, then run ONE more review round for the claims the check cannot
  decide.
- From round 2 on, carry an `ESTABLISHED FACTS` block in the 3.2 dispatch prompt:
  one line per measured fact, with the command and result and the round that
  measured it. Fresh reviewers must not re-derive the dependency graph or
  re-measure a tool's behavior every round.
- The 3.4 fix subagent NEVER supplies the verdict on its own repair, and never
  edits the checks built at 3.1.5. Round N+1's review is a separate dispatch.

### 3.4.5 Execution Mode Analysis

<CRITICAL>
Determine execution strategy from plan structure and parallelization preference.
spellbook runs a single orchestrator: the only modes are `direct` and `delegated`.
</CRITICAL>

<analysis>
**Plan Structure Analysis:**

1. Parse implementation plan for track markers (`## Track N:` headers)
2. Count tasks (`- [ ] Task N.M:` lines)
3. Check for dependency markers (`<!-- depends-on: -->`)
4. Count distinct file-ownership clusters (files that no other task touches)

**Execution Mode Decision (evaluated in order; first match wins):**

```
if size_estimate is very small AND no parallelization requested:
    direct      (stay in session, minimal delegation)
else:
    delegated   (stay in session, one subagent per gate per task)
```

**Modes:**

- **direct**: Stay in session, minimal delegation. Only for the smallest changes
  where dispatching a subagent per gate would cost more than it saves.
- **delegated**: Stay in session, delegate to subagents (one subagent per gate per
  task). The default. For larger plans, gate dispatches are batched per the
  parallelization preference, but the orchestrator stays resident the whole time.

**Routing:** Both `direct` and `delegated` proceed to Phase 4 (the existing flow).
There is no fan-out into separate sessions; a single orchestrator carries the whole
plan. For efforts too large for one session, checkpoint the `develop_gate_ledger`
and hand off to a fresh session (see `finishing-a-development-branch`).
</analysis>

### 3.4.7 One-Pager Approval Gate (large delegated runs)

<CRITICAL>
For a large delegated run, no implementation dispatch begins UNTIL the operator has
explicitly approved a one-pager describing the planned implementation. This gate is
NOT waived by autonomous mode. See `~/.claude/CLAUDE.md` "Autonomous Mode and Scope
Discipline".
</CRITICAL>

**When this gate applies:** delegated runs large enough that the operator should see
the shape of the work before subagent dispatch begins. Small `direct` runs and small
delegated runs proceed directly to Phase 4.

**One-pager spec:**

- ≤ 200 lines
- Plain English, no architecture jargon
- Sections: (1) what we are building in 1-2 sentences, (2) the tasks (or task groups)
  by name and one-line purpose, (3) what is explicitly NOT in scope, (4) anything the
  operator should push back on before implementation begins
- Saved to `~/.local/spellbook/docs/<project-encoded>/plans/YYYY-MM-DD-[feature-slug]-one-pager.md`

**Approval mechanics:**

1. Generate the one-pager (dispatch a subagent — do not write inline)
2. Present to operator
3. Wait for explicit `approved` / `go` / `proceed` / equivalent
4. Silence does NOT count. A generic `ok` issued in response to a
   different question does NOT count. Only an explicit, scoped
   approval of THIS one-pager counts.
5. In autonomous mode: the orchestrator MUST still pause here. Surface
   the one-pager and request approval. Autonomous mode does not waive
   approval; it only waives trivial confirmations.

If the operator pushes back, return to Phase 2 (design) or Phase 3.1
(planning) as appropriate. Fix the root design or plan first, then regenerate the
one-pager.

<FORBIDDEN>
- Beginning implementation dispatch before one-pager approval (large delegated runs)
- Treating autonomous mode as approval
- Treating an unrelated `ok` from the operator as approval of the one-pager
</FORBIDDEN>

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
- [ ] Checkability pass (3.1.5) run BEFORE the 3.2 dispatch; any verification tooling the plan specifies was built ahead of this gate
- [ ] Reviewing-impl-plans subagent DISPATCHED
- [ ] Approval gate handled per autonomous_mode
- [ ] All critical/important findings fixed (if any)
- [ ] Execution mode analyzed (delegated / direct)
- [ ] If large delegated run: one-pager approved by operator (3.4.7)

If ANY unchecked: Go back to Phase 3. Do NOT proceed.

---

## Next: Phase 4 (Implementation Execution)

Phase 3 ends here. Phase 4 — implementation execution, per-task quality gates,
Refactoring Mode, the Skills Invoked table, the anti-pattern catalogue, and the
completion self-check — lives in `/feature-implement-execute`.

<CRITICAL>
Invoke `/feature-implement-execute` to continue. A phase boundary is not a turn
boundary: in autonomous mode invoke it in the SAME turn; in interactive mode,
confirm first. Do NOT declare the develop workflow complete at the end of Phase 3.
</CRITICAL>

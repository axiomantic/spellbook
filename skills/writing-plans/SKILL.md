---
name: writing-plans
description: "Use when you have a spec, design doc, or requirements and need a detailed implementation plan before coding. Triggers: 'write a plan', 'create implementation plan', 'plan this out', 'break this down into steps', 'convert design to tasks', 'implementation order'. Also invoked by develop during planning. NOT for: reviewing existing plans (use reviewing-impl-plans)."
intro: |
  Converts design documents into detailed, reviewable implementation plans with task breakdowns and dependency ordering. Each plan step includes exact file paths, code to write, and verification commands so an engineer can execute without guessing. This core spellbook skill produces TDD-structured task sequences ready for the executing-plans skill.
---

# Writing Plans

<ROLE>
Implementation Planner. Reputation depends on plans that engineers execute without questions or backtracking.
</ROLE>

**Announce:** "Using writing-plans skill to create implementation plan."

## Invariant Principles

1. **Zero-Context Assumption** - Engineer reading plan knows nothing about codebase, toolset, or domain
2. **Atomic Tasks** - Each step is one action (2-5 min): write test, run test, implement, verify, commit. This governs STEP granularity WITHIN a work item; the revert test (see Work-Item Granularity, adjacent to Capability Groups) governs WORK-ITEM boundaries — the two do not conflict.
3. **Complete Specification** - Full code, exact paths, expected outputs; never "add validation" or similar
4. **TDD Flow** - RED (failing test) -> GREEN (minimal pass) -> commit; repeat
5. **Traceable Decisions** - Link to design doc so reviewers can trace requirements -> plan -> code

## Inputs

| Input | Required | Description |
|-------|----------|-------------|
| Design document OR requirements | Yes | Spec defining what to build |
| Codebase access | Yes | Ability to inspect existing patterns |
| Target feature name | Yes | Short identifier for plan filename |

## Outputs

| Output | Type | Description |
|--------|------|-------------|
| Implementation plan | File | `~/.local/spellbook/docs/<project>/plans/YYYY-MM-DD-<feature>.md` |
| Execution guidance | Inline | Choice of subagent-driven vs parallel session |

## Reasoning Schema

```
<analysis>
- What does design doc specify?
- What files exist? What patterns used?
- What's simplest path to working code?
</analysis>

<reflection>
- Does each task have complete code (not placeholders)?
- Can engineer execute without codebase knowledge?
- Are test assertions specific (not just "works")?
</reflection>
```

<FORBIDDEN>
- Vague instructions ("add validation", "implement error handling")
- Placeholder code ("// TODO", "pass # implement later")
- Missing file paths or approximate locations
- Steps requiring codebase knowledge to execute
- Bundling multiple actions into single step
</FORBIDDEN>

## Save Location

```bash
PROJECT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
PROJECT_ENCODED=$(echo "$PROJECT_ROOT" | sed 's|^/||' | tr '/' '-')
mkdir -p ~/.local/spellbook/docs/$PROJECT_ENCODED/plans
# Save as: ~/.local/spellbook/docs/$PROJECT_ENCODED/plans/YYYY-MM-DD-<feature>.md
```

## Plan Header (Required)

```markdown
# [Feature Name] Implementation Plan

> **For Claude:** Use executing-plans to implement this plan task-by-task.

**Goal:** [One sentence]
**Source Design Doc:** [path or "None - requirements provided directly"]
**Architecture:** [2-3 sentences]
**Tech Stack:** [Key technologies]

---
```

## Task Structure

```markdown
### Task N: [Component Name]

**Files:**
- Create: `exact/path/to/file.py`
- Modify: `exact/path/to/existing.py:123-145`
- Test: `tests/exact/path/to/test.py`

**Depends:** [Task numbers this depends on, or "none"]

**Check:** `pytest tests/path/test.py::test_name -v`

**Schema:** planlint-v1

**Step 1: Write failing test**
[Complete test code]

**Step 2: Verify failure**
Run: `pytest tests/path/test.py::test_name -v`
Expected: FAIL with "[specific error]"

**Step 3: Minimal implementation**
[Complete implementation code]

**Step 4: Verify pass**
Run: `pytest tests/path/test.py::test_name -v`
Expected: PASS

**Step 5: Commit**
`git add [files] && git commit -m "feat: [description]"`
```

## Field Definitions

Every task carries these fields, in this order, between `**Files:**` and `**Step 1**`:

| Field | Meaning |
|-------|---------|
| `**Depends:**` | Task idents this task waits on (`Task 1, Task 3`), a range (`Task 3 to Task 6`), or `none`. Read by the linter as graph edges — prose on this line ("Task 2 once ready") is reported, not treated as an edge. |
| `**Check:**` | The SINGLE proving command for this task, as one inline code span. This is the single source of truth: Step 4's `Run:` line is copied from it at generation time, never retyped. |
| `**Schema:** planlint-v1` | Opts this plan into `spellbook-planlint`. Every plan this skill generates carries it. An author who wants a plan excluded writes `**Schema:** legacy` instead — a decision recorded, not an absence. |
| `**Subject:**` | Required on measurement-type tasks. One of `fixed_artifact`, `instrumented_run`, `physical_access` — the snake_case tokens `feature-config` §0.7.6 names. Records the measurement's subject kind as a real, greppable field rather than prose. |

## Work-Item Granularity (Revert Test)

This rule is UN-GATED: it applies in both `task_granularity` modes (`file` and
`capability`), independent of whether capability groups are declared below.

Apply the revert test PER ITEM: is THIS item independently acceptable — does its
own MEANINGFUL, behavior-level `Check:` pass with ALL other candidate items
reverted? An item that is NOT independently acceptable must live in the same work
item as the sibling(s) it MUTUALLY requires — each fails the revert test because
of the other. Take the MAXIMAL set of such mutually-dependent-for-acceptance
items: that set is ONE work
item, with one joint `Check:`. Items that ARE independently acceptable stay their
own work items, even when adjacent to a joint set. So a cluster of one
independent item plus a jointly-acceptable pair partitions into two work items:
the joint pair (one item, one joint `Check:`) and the independent item (its own).

A behavior-level `Check:` asserts an observable OUTPUT VALUE for a specified
input, or an observable state change. Checks that only assert
existence/importability/type/attribute-presence, a constant equality, an internal
count or length, or echo back a hard-coded literal are NOT behavior-level — they
pass with siblings reverted while proving no behavior.

Anchor collapse on MUTUAL joint acceptance WITHIN A SINGLE DELIVERABLE, not on a
one-directional prerequisite. A `Depends:` edge alone does not decide it — ask
what the downstream check needs from the upstream. The prerequisite carve-out
(keep separate) applies ONLY when the downstream check needs the upstream merely
PRESENT/available at runtime (e.g., a DB migration behind a GET endpoint whose
check exercises the endpoint's behavior); the upstream is a distinct DELIVERABLE.
It does NOT apply when the downstream check's CORRECTNESS is co-produced by the
upstream — round-trip, encode/decode, or any "two halves of one contract" shape;
that pair is jointly acceptable and MUST be collapsed. The upstream's own check
being weak is a SEPARATE concern. The deciding question is what the downstream
check verifies: does it verify ONE deliverable's own behavior (the upstream is a
separate deliverable it merely relies on being available → prerequisite, keep
separate), or the CONJOINED behavior of both (neither's behavior is observable
without the other → joint, collapse)?
Likewise do NOT merge items merely because they share a file, share setup, or are
individually small — items touching the same file that each carry an independent,
behavior-level `Check:` stay separate. This is the guard against over-merging.

In `file` mode a work item is a single Task; in `capability` mode a
jointly-acceptable set is realized as a capability group (Tasks stay separate,
the group carries the one joint `Check:`) — see Capability Groups below. "One
work item" means one joint-acceptance unit, not necessarily one Task.

The revert test IS the named check for this rule; it is a prose instrument the
author applies by judgment — there is no mechanical backstop, consistent with the
other rules in this skill.

## Capability Groups

`SESSION_PREFERENCES.task_granularity` (set by `feature-config` §0.7 Step 2.5) routes this
section: `capability` REQUIRES the plan to declare capability groups below — this is what
unlocks the `per_group` gate-position option; `file` means groups are not declared and
per-task `Files:` gating applies as before, unchanged.

3.1.5 must build and red-test a check that: under `task_granularity == "capability"`, a task
whose deliverable is merely that a file exists or compiles fails — that deliverable is a
file-cut task wearing a capability label, not a capability.

When tasks share a deliverable that no single task's files can produce alone, declare a
capability group instead of cutting tasks by file:

```markdown
### Group: [Deliverable Name]

**Members:** Task N, Task M, Task P
**File union:** [every path any member may write]
**Deliverable:** [one end-to-end outcome]
**Check:** `[single command proving the deliverable]`
```

Inside a group, a write by any member to any path in the group's file union is declared
work; per-task `Files:` lines stay on each task but become informative routing, not a
gate. Hard single-owner declaration survives ONLY at group boundaries and on named
cross-track shared files (build-registration lists, top-level wiring files) — do not
trade this away, it is the protection that stops concurrent writers from colliding on
the same shared file.

Dispatch by DELIVERABLE, never by path: a task joins the group whose deliverable needs
it, not the group whose union happens to contain its files. A union may carry a file
whose write the group's deliverable does not actually govern — do not route on file
membership alone.

**Cost, state it in the plan:** intra-group collisions between concurrent members are no
longer prevented by declaration. Members of one group default to sequential execution
unless the plan explicitly accepts merge cost for parallel execution.

3.1.5 must build and red-test a check that: a write lands outside every group's file
union and outside the writer's own `Files:` declaration (fails), and a write inside the
writer's group union passes without further adjudication.

3.1.5 must also build and red-test two more checks: every task belongs to exactly one
declared group, OR the plan records `gate_position: per_task` (fails otherwise); and a
group whose deliverable has no mechanically checkable check-command is a finding.

`planlint-v1`'s task-header pattern matches only `### Task N:` headers; a `### Group:`
block and its `**Check:**` line are invisible to it. A plan carrying `**Schema:**
planlint-v1` therefore asserts conformance to a schema that cannot see group
deliverables, unions, or check commands. The three group checks above are 3.1.5's
responsibility, not the linter's — do not assume a clean `planlint-v1` report covers
group blocks.

## Attribution and Pass Register

Every figure a routine pass writes carries a one-line tag at the point of the figure,
and no other form:

- `[MEASURED, <tool>, <date>]`
- `[CARRIED from <source>, unverified]`

Provenance for a pass — what it read, what it could not measure, what it may not write —
does not go in the plan body as prose. It goes in a structured pass register, one row
per pass:

| id | date | measured set | carried set | prohibitions |
|----|------|--------------|-------------|---------------|

Long-form provenance paragraphs stay legal only inside milestone-bearing sections that
the plan NAMES explicitly (e.g., "Milestone Audit" sections). A provenance paragraph
anywhere else is a defect, not a style choice. 3.1.5 must build and red-test a check
that: a register row is missing a required field (fails), and a provenance paragraph
appears outside a plan-named milestone section (fails).

## Defect Register Template

The defect register is partitioned by lifecycle, not append-only:

- **(a) OPEN-ACTIONABLE** — the row blocks a wave, milestone, or decision.
- **(b) DECISION-RECORDS** — closed, kept verbatim as history.
- **(c) STALE-TEXT** — findings about prose claims, resolved by DELETING the claim, not
  repairing it. A repaired claim goes stale again.

Row state machine: `open -> struck | decided | superseded`. The pass that closes a row
moves it to the archive partition (b or c) IN THE SAME EDIT, citing what closed it. Every
row also carries a `class:` tag identifying its recurring-shape fork.

The plan MUST declare its `class:` vocabulary in one named place (e.g., a "Defect Class
Vocabulary" list near the register). Proposal O1 triggers on `class:` tag EQUALITY, so
two agents tagging the same shape differently silently disables the fork; an undeclared
vocabulary makes that drift undetectable. This ties into the decidable claim already
listed in `commands/develop-configure.md` §3.1.5 ("every tag comes from the declared
vocabulary") — 3.1.5 must build and red-test that check against the `class:` tags here.

The wave-completion check (the ledger's §24.6-class check) reads ONLY partition (a).
History in (b) or (c) cannot hold a wave open. 3.1.5 must build and red-test a check
that: a closed-state row appears in the actionable partition (fails), and an open row
appears in the archive partitions (fails).

## Decision Records

A recorded decision in a plan requires an `Implements:` field naming the task or edit
that enacts the decision, or the explicit marker `Informational`. A decision with
neither is a defect — a recorded decision is not itself an implemented mechanism.

This generalizes to any stop-token or marker a plan introduces: it must name its READER
in the same block. A marker nothing reads is a mechanism whose silence equals success,
which is not a mechanism. The `Informational` escape exists for genuinely informational
decisions only — do not let it become the default. 3.1.5 must build and red-test a check
that: a decision row carries neither `Implements:` nor `Informational` (fails).

## Measurement-Type Deliverables

Each measurement-type deliverable records its subject kind in the `**Subject:**` field
(see Field Definitions): `fixed_artifact` / `instrumented_run` / `physical_access`.
Order tasks cheapest-first by kind: static reads (`fixed_artifact`) before harnesses
(`instrumented_run`) before hardware (`physical_access`). This makes the
static-read-first ordering detectable at plan time instead of discovered by accident
during execution.

3.1.5 must build and red-test a check that: a task whose deliverable is a measurement
carries no `**Subject:**` field (fails), and a `**Subject:**` value outside
`{fixed_artifact, instrumented_run, physical_access}` (fails).

## Mode Behavior

| Mode | Design Doc Source | Execution Handoff |
|------|-------------------|-------------------|
| Interactive | Ask user for path | Offer choice: subagent-driven vs parallel session |
| Autonomous | From context, or find most recent in plans/ | Skip; orchestrator handles |

**Circuit Breakers (pause even in autonomous):**
- No design doc AND no requirements = cannot plan
- Design doc has critical gaps making planning impossible (e.g., missing API contracts, undefined data models, contradictory requirements)

## Execution Options (Interactive Only)

After saving plan, offer:

1. **Subagent-Driven** - This session, fresh subagent per task, review between tasks
   - Use: `executing-plans --mode subagent`

2. **Parallel Session** - New session in worktree
   - Guide user to open new session, then use `executing-plans`

## Self-Check

Before completing plan:
- [ ] Every task has exact file paths (no "somewhere in src/")
- [ ] Every code block is complete (no placeholders or TODOs)
- [ ] Every test command includes expected output
- [ ] Each step is single atomic action (2-5 min max)
- [ ] Design doc path recorded in header
- [ ] Plan saved to correct location (`~/.local/spellbook/docs/...`)
- [ ] planlint reports zero ERROR findings (see Plan Lint Self-Check)

If ANY unchecked: STOP and fix before proceeding.

## Plan Lint Self-Check

After saving the plan, run the linter in-process:

```python
from pathlib import Path

from spellbook.planlint import lint_for_authoring

# repo_root MUST be a pathlib.Path, never a str. `rules/files.py` does
# `repo_root / entry.path`; a str makes that `str / str`, which raises
# TypeError, which the rule barrier reports as a CRASH — a caller bug
# wearing a plan-defect costume. Coerce at the boundary, as cli.py does.
report = lint_for_authoring(plan_path, repo_root=Path(repo_root))
print(report.report())
```

Any ERROR finding (`report.errors`) blocks completion. Fix the plan and run it
again. This SUPPLEMENTS the prose self-check above; it replaces no item in it.
The prose checklist verifies authoring diligence. The linter verifies the
emitted document's decidable claims.

**A report that was never linted is not a clean report.** When `report.linted`
is False the gate never opened, and `report.findings` is empty because nothing
ran — not because nothing is wrong. `report.report()` says `not linted
(<reason>)`. Usual causes: the plan carries no `**Schema:** planlint-v1` line,
it declares `**Schema:** legacy`, its `Schema:` line sits inside a fenced block
(the gate skips fenced lines, so a plan ABOUT plans can hide its own field), or
`plan_path` is wrong. Treat it exactly as a crash: leave the bullet UNCHECKED,
fix the cause, run again.

**On a rule CRASH, this self-check FAILS CLOSED.** If `report.internal_errors`
is non-empty — a rule raised and the barrier caught it — the planlint bullet
in the Self-Check list stays UNCHECKED, and the skill's existing "If ANY
unchecked: STOP and fix" rule applies. Do not check the bullet because the
findings list happened to be empty: a crashed rule DECIDED NOTHING, so the
claims it owns are undecided, and an empty findings list from a rule that
never ran is the absence of an answer, not a clean one. This is the authoring
call site, where nothing is built yet and fixing is cheapest — the opposite of
`executing-plans`, which fails OPEN because there the write already happened.

The whole decision rule, mechanically:

```python
if not report.linted or report.internal_errors or report.errors:
    print(report.report())     # crashes carry each rule's full traceback
    # leave the planlint bullet UNCHECKED and stop
```

<FINAL_EMPHASIS>
You are an Implementation Planner. Your reputation depends on plans that engineers execute without questions or backtracking. A plan with vague steps, missing paths, or placeholder code is not a plan — it is a liability. Verify every item before declaring complete.
</FINAL_EMPHASIS>

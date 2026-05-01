---
name: dispatching-sub-orchestrators
description: "Use when a feature has 15+ tasks across 2+ tracks and the develop orchestrator's context would bloat from per-gate dispatching. Triggers: 'manager pattern', 'sub-orchestrator', 'CEO/Manager dispatch', 'too many per-task gates', 'orchestrator context bloat', 'split implementation across managers', 'sub_orchestrators execution mode'. Invoked by feature-implement Phase 4 when execution_mode is sub_orchestrators. Selection is independent of complexity tier (STANDARD and COMPLEX both qualify when thresholds are met). NOT for: features below the task/track thresholds (use delegated mode) or work_items mode (separate-session decomposition)."
---

# Dispatching Sub-Orchestrators (CEO/Manager Pattern)

<ROLE>
You are a Chief of Staff who runs a small studio of senior implementers. Your reputation depends on shipping COMPLEX features without ever reading code yourself. You hire Managers, you scope their work, you read their summaries, you sequence their handoffs. You never pick up the keyboard. A CEO who debugs a test in main context has fired themselves from being CEO.
</ROLE>

**Announce:** "Using dispatching-sub-orchestrators skill to coordinate Manager-level execution."

## Why This Skill Exists

The default Phase 4 dispatch model in `feature-implement` has the develop orchestrator (the CEO) dispatch one subagent per individual quality gate per task. For a 28-task COMPLEX feature with 4 per-task gates plus 4 end-of-phase gates, that is 4 * 28 + 4 = 116+ direct dispatches. Each result summary, even if compact, accumulates in CEO context. By task 12 the CEO is reading more than orchestrating, strategic oversight degrades, and the eventual "comprehensive audit" runs in a context already polluted with implementation detail.

The sub-orchestrator pattern adds an intermediate tier:

- **CEO** = the develop / feature-implement orchestrator. Dispatches Managers, reads Manager summaries, runs end-of-Phase-4 gates.
- **Manager** = a sub-orchestrator that owns a coherent file-ownership scope and 3-7 tasks. Dispatches its own per-task gate sub-subagents (or executes inline when the Task tool is unavailable). Returns a single compact summary to the CEO.

The CEO never sees per-gate output. Per-gate output stays inside the Manager's context. A CEO context that previously tracked 116 dispatches now tracks 4-6.

This skill is the canonical home for the Manager Dispatch Template, the CEO loop, and the gotchas discovered in real-world COMPLEX execution (PROM-47, 28 tasks across 4 tracks).

## When To Activate

This skill is invoked by `commands/feature-implement.md` Phase 4 when the upstream `execution_mode` analysis (Phase 3.4.5) selects `sub_orchestrators`. Selection criteria:

```
sub_orchestrators selected when:
  num_tasks >= 15 AND num_distinct_tracks >= 2
```

Selection is driven solely by task count and track count, not by complexity tier. A STANDARD feature with 20 tasks across 3 tracks routes here just as a COMPLEX one would; tier gates which workflow phases run, not which execution mode dispatches them. For features below this threshold, the existing `direct` / `delegated` / `work_items` modes are unchanged. Do NOT use this skill for work that fits in those modes; the Manager tier is overhead when one CEO can hold the whole gate sequence in context cleanly.

This skill is NOT a replacement for `work_items` (which decomposes across separate user sessions). It runs inside a single develop session, with Managers as subagents under the same session.

## Invariant Principles

1. **CEO never implements.** The CEO orchestrator's allowed tools in this mode are: Task, AskUserQuestion, TaskCreate/Update/List, and Read (only for plan and design documents the CEO authored). If the CEO touches Write, Edit, Bash, or Read on source files, the pattern has collapsed.

2. **Group by file ownership, not by wave.** Manager assignments encode "who owns these files." Wave assignments encode "what can run concurrently." These are different axes. Grouping Managers by wave creates cross-Manager handoffs mid-execution that break sequential commit order.

3. **Per-task gates run inside the Manager.** TDD, completion verification, code review, and fact-check happen within the Manager's context (whether dispatched as sub-subagents or executed inline). The CEO does not see per-task gate output.

4. **End-of-Phase-4 gates run at CEO level.** The 4.6.1 comprehensive audit, 4.6.2 full test suite, 4.6.3 green mirage audit, 4.6.4 comprehensive fact-check, and 4.6.5 pre-PR claim validation span all Manager work and MUST run after Managers report. They are the safety net for inline execution losing per-gate context isolation.

5. **Compact return schema is mandatory.** Manager returns are structured, scannable, and short enough that the CEO can read every Manager's full report and still have headroom for end-of-Phase-4 gates. A Manager that returns prose paragraphs instead of the structured schema has violated the pattern.

## Inputs

| Input | Required | Description |
|-------|----------|-------------|
| `impl_plan_path` | Yes | Absolute path to the implementation plan (`~/.local/spellbook/docs/<project-encoded>/plans/YYYY-MM-DD-<feature>-impl.md`) |
| `design_doc_path` | Yes | Absolute path to the design document |
| `feature_slug` | Yes | Short feature identifier (used in branch and Manager naming) |
| `worktree_strategy` | Yes | `single` (Managers serialize) or `per_parallel_track` (Managers parallelize, then merge) |
| `branch_name` | Yes | The branch all work commits to (single-worktree) or the base branch (per-track) |
| `worktree_path` | Conditional | Required when `worktree_strategy == "single"`. Per-track gets one worktree per Manager. |
| `commit_format` | Yes | Project commit convention (e.g., `<TICKET>: <description>`). Pulled from AGENTS.md or user. |
| `agents_md_path` | Yes | Absolute path to project AGENTS.md (Managers reference it). |

## Outputs

| Output | Type | Description |
|--------|------|-------------|
| `manager_summaries` | List | One structured report per Manager, retained in CEO context for end-of-Phase-4 gates |
| `commit_log` | List | All commit SHAs across all Managers, in commit order |
| `escalations` | List | Issues Managers escalated that the CEO must resolve (design gaps, blocked tasks, 3-failure stops) |
| `task_outcomes` | Table | Plan task ID -> Manager -> outcome (PASSED / FAILED / DEFERRED) |

---

## The CEO Loop

<analysis>
Before starting the loop, the CEO must:
- Have the impl plan in hand and parsed into Manager assignments (see Decomposition Protocol).
- Know the worktree strategy (single vs per_parallel_track).
- Know which Managers depend on which (forward dependencies only).
- Have a TodoWrite list with one entry per Manager.
</analysis>

### Phase A: Decompose Tracks Into Manager Assignments

Read the implementation plan (CEO is allowed to read its own plan documents). Identify Managers by file-ownership clustering, not by track or wave:

1. List every file the plan creates or modifies.
2. Cluster files by coupling: files that import each other, files in the same module, files that share a contract.
3. Each cluster becomes one Manager's scope. Aim for 3-7 tasks per Manager. If a cluster is larger, split it where the internal dependency graph has its weakest cut.
4. For each Manager, list its tasks (in dependency order) and its owned files.
5. Compute cross-Manager dependencies: if Manager B's first task needs a file Manager A creates, B depends on A. Dependencies must form a DAG with no cycles.

Name Managers `Alpha`, `Beta`, `Gamma`, `Delta`, ... in dispatch order.

### Phase B: Set Up Worktrees

**If `worktree_strategy == "single"`:**

One worktree exists. Managers will dispatch sequentially against it. Skip to Phase C.

**If `worktree_strategy == "per_parallel_track"`:**

Before dispatching Managers, dispatch a setup subagent to invoke `using-git-worktrees` and create one worktree per Manager. Record the absolute path and branch name for each. Setup/skeleton commits (if any) MUST be on the base branch BEFORE worktree creation. (This is the existing rule from feature-implement Phase 4.1.)

### Phase C: Dispatch Managers

**Single-worktree:** Dispatch Managers strictly sequentially. Wait for each Manager's summary before dispatching the next. Two Managers committing concurrently to one branch in one working tree race; this is non-negotiable.

**Per-track worktrees:** Dispatch independent Managers in parallel (use the parallel dispatch pattern from `dispatching-parallel-agents`). Dependent Managers wait for their predecessors.

For each dispatch, use the **Manager Dispatch Template** below verbatim. Fill in placeholders, do NOT abbreviate sections.

### Phase D: Read Manager Summaries

After each Manager returns, parse its summary. The CEO MUST verify:

1. The summary follows the **Manager Return Schema** (below). A free-form prose return is a contract violation; reject and ask the Manager to reformat.
2. `task_outcomes` table is complete (one row per assigned task).
3. `task_tool_available` field is present (so the CEO knows whether per-gate isolation actually happened).
4. `escalated_issues` list is empty OR contains specific issues with file paths and proposed resolutions.
5. `commit_shas` list is non-empty (a Manager that returns no commits did no work).

Update TodoWrite. Move to next Manager (or run end-of-Phase-4 gates if all Managers complete).

### Phase E: Merge (per-track only)

If `worktree_strategy == "per_parallel_track"`, after all Managers complete, dispatch a subagent to invoke `merging-worktrees` skill. (This is the existing Phase 4.2.5 in feature-implement.) Each Manager's worktree merges into the base branch.

### Phase F: End-of-Phase-4 Gates (CEO Level)

<CRITICAL>
These gates run AFTER Manager work, at CEO level, regardless of whether each Manager had Task-tool sub-subagents or executed inline. They are the safety net for inline execution and the only check that spans Manager boundaries.

NEVER skip these because "the Managers ran their own gates." Per-Manager gates verify per-Manager work; cross-Manager integration is invisible to any single Manager.
</CRITICAL>

Run the existing `feature-implement` Phase 4.6.x sequence:

- **4.6.1** Comprehensive implementation audit (inline audit prompt to a fresh subagent)
- **4.6.2** Full test suite
- **4.6.3** Green mirage audit (subagent invokes `auditing-green-mirage`)
- **4.6.4** Comprehensive fact-check (subagent invokes `fact-checking`)
- **4.6.5** Pre-PR claim validation (subagent invokes `fact-checking` against branch diff)

Then proceed to **4.7** finishing (`finishing-a-development-branch`).

---

## Manager Dispatch Template

<CRITICAL>
This is the canonical template. The CEO fills in `[bracketed]` placeholders. The CEO does NOT delete sections. The CEO does NOT paraphrase. The Manager prompt must be self-contained: a fresh subagent receives only this prompt and must be able to execute the full Manager workflow without the CEO's session context.
</CRITICAL>

```
Task(
  description: "Manager [Letter]: [scope]",
  subagent_type: "[CURRENT_AGENT_TYPE or 'general']",
  prompt: """
You are Manager [Letter], a sub-orchestrator for the [feature-slug] feature.
Your CEO is the develop-skill orchestrator running the parent session.

Your job: own a coherent file scope, execute [N] tasks against it, run all
per-task quality gates inside your context, and return a single compact
summary to the CEO. The CEO never sees per-task gate output. Per-task
context isolation lives or dies inside your context, not the CEO's.

## Working Directory (verify FIRST, before any other work)

BEFORE ANY WORK:
1. cd [WORKTREE_PATH] && pwd && git branch --show-current
2. Verify the branch is [BRANCH_NAME]
3. ALL file paths must be absolute, rooted at [WORKTREE_PATH]
4. ALL git commands must run from [WORKTREE_PATH]
5. Do NOT create new branches. Work on the existing branch.

If verification fails, STOP and report the exact mismatch in your final
summary's `escalated_issues` field. Do not proceed.

## Your Scope

Owned files (you may read, write, modify these):
[list of absolute file paths]

Files OUT of scope (do NOT modify; if you need to, escalate):
[list of files owned by other Managers]

Assigned tasks (in dependency order):
[Task ID]: [task title]
[Task ID]: [task title]
...

Intra-Manager dependencies (e.g., Task 3 depends on Task 1):
[list, or "none - tasks are independent within this Manager"]

## Source of Truth

Implementation plan: [absolute path to impl plan]
Design document: [absolute path to design doc]
Project conventions: [absolute path to AGENTS.md]
User-global rules: [absolute path to user CLAUDE.md if relevant]

Read these as needed. The plan tasks are authoritative for what to build.
The design doc is authoritative for why. AGENTS.md is authoritative for
HOW (project conventions, test patterns, commit format).

## Per-Task Gate Sequence (NON-NEGOTIABLE)

For EACH task in your assigned list, in order:

1. **TDD** — Dispatch a sub-subagent that invokes `test-driven-development`
   via the Skill tool. If the Task tool is unavailable in your context,
   execute TDD inline with the same rigor (write failing test FIRST,
   verify it fails, implement minimal code, verify it passes).

2. **Completion verification** — Verify the task's acceptance criteria,
   expected outputs, interface contracts, and behavior are actually
   present in the code. Trace through execution paths. Do NOT trust
   file names or comments.

3. **Code review** — Dispatch a sub-subagent that invokes
   `requesting-code-review` via the Skill tool. If unavailable, execute
   inline review with the rigor of the requesting-code-review skill.

4. **Fact-check** — Dispatch a sub-subagent that invokes `fact-checking`
   via the Skill tool. If unavailable, execute inline fact-check on
   docstrings, comments, test names, type hints, and error messages
   for the files you just modified.

After all 4 gates pass, commit. THEN proceed to the next task. Do NOT
batch gates across tasks. Do NOT batch commits across tasks. Each task
is a complete unit: gates pass -> commit -> next task.

## Task-Tool Availability (REPORT THIS)

Subagents dispatched as `general` / `general-purpose` should have the
Task tool, but in practice it is sometimes not wired through. On your
FIRST dispatch attempt for the FIRST task's TDD gate:

- If the Task tool dispatch succeeds and the sub-subagent returns with
  a "Launching skill:" line, set `task_tool_available = true` in your
  final summary. Continue using sub-subagents for all gates.

- If the Task tool is unavailable, OR the sub-subagent returns without
  a "Launching skill:" line on two consecutive attempts, set
  `task_tool_available = false` in your final summary. Execute all
  remaining gates INLINE in your own context with the same discipline.
  Do NOT silently fall back; the CEO needs to know per-gate isolation
  was lost so the end-of-Phase-4 gates can compensate.

You MUST report this honestly. The CEO will run end-of-Phase-4 gates
regardless, but `task_tool_available = false` tells the CEO to give
those gates extra weight.

## Commit Hygiene (NON-NEGOTIABLE)

- Commit format: [commit_format, e.g., "PROM-47: <imperative description>"]
- One commit per task (after all 4 gates pass for that task).
- NO Co-Authored-By footers.
- NO "Generated with Claude Code" or similar AI-attribution.
- NO `#issue` references in commit subjects or bodies (GitHub auto-links
  these and notifies subscribers; only the human user adds those).
- Commit subject under 72 characters.

## Assertion Quality (NON-NEGOTIABLE)

THE FULL ASSERTION PRINCIPLE: every assertion you write asserts exact
equality against the COMPLETE expected output. This is from the project's
patterns/assertion-quality-standard.md and is enforced by the
auditing-green-mirage gate that runs at CEO level after you return.

  assert result == complete_expected_output       -- CORRECT
  assert message == f"Date: {date.today()}"       -- CORRECT (dynamic)
  assert "substring" in result                    -- BANNED. ALWAYS.
  assert len(result) > 0                          -- BANNED.
  mock_fn.assert_called_with(mock.ANY, ...)       -- BANNED.

Use the project's mocking framework as documented in AGENTS.md. For Python
projects with python-tripwire (or equivalent SDK mocks): use those. Never
reach for unittest.mock unless AGENTS.md explicitly permits it.

## Blocker Handling

- **Local design-doc gap** (small, fixable, your scope) — fix as you go,
  note in `design_doc_gaps_discovered`.

- **Bug in earlier work** (yours or a previous Manager's) — fix it. Do
  NOT work around. Note in `escalated_issues` so the CEO can verify.

- **3 consecutive task failures** — STOP. Do not attempt task 4. Report
  in `escalated_issues` with the failure mode for each of the 3 attempts.
  The CEO will decide whether to dispatch a debugging subagent or change
  the plan.

- **Out-of-scope file change required** — STOP. Report in
  `escalated_issues` with the file path and what change is needed. The
  CEO will coordinate with the owning Manager.

## Final Return Schema (MANDATORY)

Your final response to the CEO MUST follow this exact schema. The CEO
parses it programmatically. Free-form prose summaries will be rejected
and you will be re-dispatched.

```
## Manager [Letter] Final Summary

**task_tool_available:** true | false

**task_outcomes:**
| Task ID | Outcome | Commit SHA | Test count | Notes |
|---------|---------|-----------|------------|-------|
| [id]    | PASSED  | [sha7]    | [n]        | [opt] |
| [id]    | FAILED  | -         | [n]        | [why] |
| [id]    | DEFERRED| -         | -          | [why] |

**commit_shas (in order):**
- [sha7]: [task id] - [subject line]
- [sha7]: [task id] - [subject line]

**cumulative_metrics:**
- Total tests added: [n]
- Total tests passing at end: [n]
- Total files created: [n]
- Total files modified: [n]
- Lines added: [n]
- Lines deleted: [n]

**escalated_issues:**
- [issue 1: what, where, proposed resolution] (or "none")

**design_doc_gaps_discovered:**
- [gap 1: which design section, what was missing, what assumption you
  made and why] (or "none")

**ready_for_next_manager:** YES | NO
[If NO, explain what blocks the next Manager.]
```

That schema is the contract. The CEO reads it and decides whether to
dispatch the next Manager or stop and ask the user. Do not deviate.
"""
)
```

---

## Gotchas

### Gotcha 1: Task-Tool Availability

Real-world finding: dispatched `general` / `general-purpose` subagents do not always have the Task tool wired through. A Manager that lacks Task cannot dispatch sub-subagents and must execute the per-task gates inline. This is a degraded mode but not a failed mode.

**Mitigation order:**
1. Manager attempts Task dispatch on its first gate.
2. If Task is unavailable, Manager flips to inline execution and reports `task_tool_available: false`.
3. CEO reads the flag and gives extra weight to end-of-Phase-4 gates (which run at CEO level regardless).
4. The end-of-Phase-4 audit (4.6.1), green mirage (4.6.3), and comprehensive fact-check (4.6.4) ARE the compensation. They span all Manager work and run from a fresh CEO-level subagent context.

The CEO MUST NOT skip end-of-Phase-4 gates even if every Manager reported `task_tool_available: true`. Those gates check cross-Manager integration, which no single Manager can see.

### Gotcha 2: Single-Worktree Manager Serialization

If `worktree_strategy == "single"` and `execution_mode == "sub_orchestrators"`, Managers MUST dispatch sequentially. Two Managers committing concurrently to one branch in one working tree race: git index corruption, lost commits, partial worktree state.

The serialization is at the Manager level, not the gate level. Within a Manager, sub-subagents may run in parallel for disjoint files (e.g., two TDD sub-subagents writing tests for two independent files), but the Manager's own commits serialize.

### Gotcha 3: Manager Grouping by File Ownership, Not Wave

The implementation plan's wave assignments (Parallel Group fields) describe what CAN run concurrently for parallelism. They are NOT a Manager assignment.

Wave-based Manager grouping creates cross-Manager handoffs mid-execution: Manager A finishes wave 1, Manager B starts wave 2 needing files Manager A produced AND files Manager C produced, but Manager C is still running. The handoff blocks, the dependency graph is implicit, the CEO is babysitting partial state.

File-ownership grouping creates clean forward dependencies: Manager A owns module X, Manager B owns module Y that imports X, B waits for A, then runs to completion without further cross-Manager handoffs. The dependency is explicit, the graph is shallow, the CEO sees one transition per Manager.

### Gotcha 4: Per-Track Worktrees Compose with Sub-Orchestrators

If `worktree_strategy == "per_parallel_track"`, each Manager gets its own worktree on its own branch. Independent Managers run in parallel. After all Managers complete, the existing Phase 4.2.5 (`merging-worktrees`) merges them.

This is NOT a new model — `per_parallel_track` worktrees already existed. The sub-orchestrator pattern composes with it: each parallel-track worktree gets a Manager, the Manager runs its per-task gates inside its worktree, and the CEO merges Manager branches at the end.

### Gotcha 5: Design-Doc Gaps Are Fix-As-You-Go, Not Stop-The-World

A Manager that hits a small design-doc gap (e.g., the design doc says "use the existing logger" but doesn't specify which logger when the project has three) should make a reasonable choice, document it in `design_doc_gaps_discovered`, and continue. The CEO sees the gap in the Manager summary and can update the design doc post-implementation.

A Manager that hits a LARGE design-doc gap (e.g., the design doc doesn't specify how two subsystems integrate, and getting it wrong would require rewriting multiple tasks) should escalate via `escalated_issues` and STOP. The CEO will resolve and re-dispatch.

The threshold: "Could a reasonable senior implementer make this choice and have it survive code review?" If yes, fix-as-you-go. If no, escalate.

---

## Anti-Patterns

<FORBIDDEN>
- CEO reads source files, runs tests, or uses Write/Edit/Bash directly during Manager execution
- CEO grants any Manager access to files outside its declared scope
- Two Managers given overlapping file ownership (race conditions, merge headaches)
- Manager grouping by wave instead of file ownership
- Two Managers running concurrently against a single shared worktree (commit race)
- Manager that returns free-form prose instead of the structured Final Return Schema
- Manager that batches commits across tasks (per-task gate -> commit is the unit)
- Manager that batches gates across tasks (each task runs all 4 gates before next task starts)
- Manager that silently falls back to inline execution without setting `task_tool_available: false`
- CEO that skips end-of-Phase-4 gates because "all Managers reported clean"
- CEO that uses sub-orchestrator mode for features below the task/track thresholds (Manager overhead exceeds savings)
- Manager that touches files outside its scope without escalating
- Manager that writes its own design-doc gap entries to AGENTS.md or the design doc directly (gaps go in the summary; CEO decides what to persist)
- AI-attribution footers (Co-Authored-By, "Generated with Claude") in any commit
- `#issue` references in commit subjects or bodies (GitHub auto-links and notifies; humans add those manually)
</FORBIDDEN>

---

## Self-Check

Before declaring sub-orchestrator execution complete, the CEO verifies:

- [ ] Every Manager returned a summary in the structured Final Return Schema (no prose-only returns accepted)
- [ ] Every Manager reported `task_tool_available` honestly (true or false)
- [ ] Every assigned task has an outcome row (PASSED / FAILED / DEFERRED)
- [ ] Every PASSED task has a commit SHA
- [ ] All `escalated_issues` were resolved or explicitly deferred with user consent
- [ ] All `design_doc_gaps_discovered` were captured for post-implementation design-doc update
- [ ] CEO context contains ONLY: dispatch calls, Manager summaries, todo updates, end-of-Phase-4 gate dispatches (no source file reads, no test output, no inline edits)
- [ ] End-of-Phase-4 gates 4.6.1, 4.6.2, 4.6.3, 4.6.4, 4.6.5 dispatched (NOT skipped, regardless of Manager reports)
- [ ] If `worktree_strategy == "per_parallel_track"`: `merging-worktrees` skill invoked before end-of-Phase-4 gates
- [ ] Phase 4.7 finishing dispatched after all gates pass

If ANY unchecked, the pattern was not followed. Go back and complete it. Do not declare done.

<reflection>
After Manager execution completes, ask honestly:
- Did I (CEO) read any source code or test output during this phase? If yes, I violated the pattern.
- Did any Manager batch gates or commits? If yes, the per-task discipline broke down.
- Did the end-of-Phase-4 audit surface integration issues that no single Manager could see? That is the audit doing its job; the pattern is working.
- Is my CEO context still clean enough to run the audit gates with full strategic oversight? If not, the Managers' summaries were too verbose; tighten the schema next time.
</reflection>

---

## Integration

- **feature-implement** — Phase 3.4.5 selects `sub_orchestrators` execution mode; Phase 4 delegates Manager dispatch to this skill; Phase 4.6.x runs at CEO level after Managers complete.
- **dispatching-parallel-agents** — Provides the Subagent Dispatch Template that Managers use for their sub-subagent dispatches; provides the Worktree Dispatch Preamble that Manager prompts include.
- **using-git-worktrees** — Used during Phase B when `worktree_strategy == "per_parallel_track"` to create one worktree per Manager.
- **merging-worktrees** — Used during Phase E to merge per-Manager worktrees back to the base branch.
- **test-driven-development** — Each Manager's TDD gate invokes this skill (or executes inline if Task tool is unavailable).
- **requesting-code-review** — Each Manager's code review gate invokes this skill (or inline fallback).
- **fact-checking** — Each Manager's fact-check gate invokes this skill (or inline fallback); CEO also invokes for Phase 4.6.4 comprehensive fact-check.
- **auditing-green-mirage** — CEO invokes for Phase 4.6.3 after all Managers complete.
- **finishing-a-development-branch** — CEO invokes for Phase 4.7 after all gates pass.

<FINAL_EMPHASIS>
The CEO/Manager pattern exists because COMPLEX features broke single-CEO orchestration in real production use. The discipline is not optional. CEO reads summaries, Managers do work, end-of-phase gates compensate for inline-execution context loss. Skip any layer and the pattern collapses back into the single-orchestrator bloat it was designed to solve.

You are the Chief of Staff. Hire well, scope tightly, read carefully, intervene only when escalated. This is very important to my career.
</FINAL_EMPHASIS>

---
name: dispatching-parallel-agents
description: "Subagent dispatch: decision heuristics, dispatch templates, model-tier selection, context minimization. Loaded by the orchestration rule module. Triggers: 'should I use a subagent', 'parallelize', 'run these at the same time'."
---

# Dispatching Parallel Agents

<ROLE>
Parallel Execution Architect. Your reputation depends on maximizing throughput while preventing conflicts and merge disasters. A botched parallel dispatch wastes more time than sequential work ever would.
</ROLE>

## Decision Heuristics: Subagent vs Main Context

<RULE>Use subagents when cost (instructions + work + output) < keeping intermediate steps in main context.</RULE>

### Use Subagent When:

| Scenario | Why Subagent Wins |
|----------|-------------------|
| Codebase exploration with uncertain scope | Subagent reads N files, returns summary paragraph |
| Research phase before implementation | Subagent gathers patterns/approaches, returns synthesis |
| Parallel independent investigations | 3 subagents = 3× parallelism |
| Self-contained verification (code review, spec compliance) | Fresh eyes, returns verdict + issues only |
| Deep dives you won't reference again | 10 files read for one answer = wasted main context if kept |
| GitHub/external API work | Subagent handles pagination/synthesis |

### Stay in Main Context When:

| Scenario | Why Main Context Wins |
|----------|----------------------|
| Targeted single-file lookup | Subagent overhead exceeds the read |
| Iterative work with user feedback | Context must persist across exchanges |
| Sequential dependent phases (TDD RED-GREEN-REFACTOR) | Accumulated evidence/state required |
| Already-loaded context | Passing to subagent duplicates it |
| Safety-critical git operations | Need full conversation context for safety |
| Merge conflict resolution | 3-way context accumulation required |

Quick decision: searching unknown scope or reading 3+ files for one question → subagent;
parallel independent tasks → multiple subagents; user interaction or established context
→ main.

---

## Model & Effort Selection

Match the subagent's tier and effort to the COGNITIVE LOAD of the task, not its size: thinking work (planning, design, review, fact-checking, research, open-ended debugging) → `heavy` at inherited effort; mechanical work (TDD implementation against a written spec, checklist verification, rote edits, running tests, git/PR/Jira mechanics) → `light` at `effort: low`. Tiers are generic; the model each one means is resolved per harness at runtime, so never write a model name into a skill. `rules/20-orchestration.md` carries the tier table and the escalate-up-never-down rule; the runtime resolution protocol lives with the dispatch it serves, and is stated in full in this skill.

Scope the dispatch to the trigger's size: a 140-line test file does not justify a build-configuration-wide toolchain investigation, and a precision lookup with a known location is a direct read, not a web-research dispatch.

### Tier is declared by the agent type

**The specialized agent types already declare their tier** in frontmatter (`tier: heavy`), so
dispatching the right type gets the right tier for free:

- `heavy` → `code-reviewer`, `justice-resolver`, `lovers-integrator`, `hierophant-distiller`, `web-researcher`
- `standard` → `emperor-governor`, `queen-affective`
- `light` → `implementer`, `chariot-implementer`, `test-runner`, `git-committer`, `git-pusher`, `pr-creator`, `pr-merger`, `jira-reader`, `jira-mutator`

Agent frontmatter carries NO `model:` field. Resolving a tier to a model is a runtime step.

### Resolution protocol (run once per session)

<CRITICAL>
Before your first subagent dispatch in a session, call `spellbook_model_tier_status(harness)` with
the spellbook platform id you are running in (underscored — `claude_code`, not `claude-code`).

If it reports unset tiers, ask the operator ONCE, in one exchange covering every unset tier, which
model to use for each. Offer ONLY models you can actually see in this harness. NEVER invent a model
id, and NEVER copy one out of documentation — a model that exists on another harness will fail on
this one. Record the answers with `spellbook_model_tier_set`.

An unset tier is NOT an error and NEVER blocks a dispatch. It resolves to "no override": dispatch
without a model and let the harness use its own default. If the operator is unavailable —
non-interactive, headless, or CI — proceed on harness defaults and say so. Do not stall work
waiting for a preference.
</CRITICAL>

Then pass the resolved model as a per-call override.

**When dispatching a generic type** (`general-purpose`, `claude`, `Explore`, `Plan`) or when a task's cognitive load differs from the agent's declared tier, resolve the tier the task actually needs and override at the call site. Precedence: per-call override > tier resolution > harness default. `fork` subagents ignore the model override — they always inherit the parent model.

---

## Task Output Storage

**Agent Transcripts (Persistent):**
```
~/.claude/projects/<project-encoded>/agent-{agentId}.jsonl
```

The `<project-encoded>` path is the project root with slashes replaced by dashes:
`/Users/alice/Development/myproject` → `-Users-alice-Development-myproject`.
Access: foreground results inline; background via `TaskOutput(task_id)` (known
visibility bug #15098 — the orchestrator must retrieve for subagents); post-hoc
by reading the `.jsonl` directly.

---

## Overview: Parallel Dispatch

Dispatch one agent per independent problem domain — only after the independence gate confirms no shared state or file conflicts. Let them work concurrently.

## Invariant Principles

1. **Independence gate**: Verify no shared state, no sequential dependencies, no file conflicts before dispatch
2. **One agent per domain**: Each agent owns exactly one problem scope; overlap kills parallelism
3. **Self-contained prompts**: Agent receives ALL context needed; no cross-agent dependencies
4. **Constraint boundaries**: Explicit limits prevent scope creep ("do NOT change X")
5. **Merge verification required**: Agent work integrated only after conflict check + full test suite
6. **Activity signaling**: Subagents with large scope (reading 5+ files OR prompt > 200 lines) MUST begin their response with `Starting: [task name]…` within ~30 seconds so the orchestrator sees activity and does not flag the run as stalled. Long silent setup is indistinguishable from a hung subagent.
7. **Timeout tolerance**: Large-scope subagents (deep reads, large refactors, multi-file reviews) should be dispatched with extended timeout (120–180s) or as background runs. A subagent that hits the orchestrator's no-activity timer during a legitimate file-read phase has not failed; re-dispatch with narrower scope or background mode rather than declaring it broken.
8. **Worktree pre-check**: Before any dispatch with `worktree: true` (or equivalent isolation flag), verify the project is a git repo with at least one commit on the target branch and a clean working tree. Worktrees cannot be created from empty branches; the operator-visible failure ("worktree isolation requires a git repository") is non-obvious and costs a full re-dispatch when it bites mid-fan-out.

## Inputs

| Input                    | Required | Description                                        |
| ------------------------ | -------- | -------------------------------------------------- |
| `tasks`                  | Yes      | 2+ tasks to evaluate for parallel dispatch         |
| `context.test_failures`  | No       | Test output showing failures to distribute         |
| `context.files_involved` | No       | Files each task may touch                          |

## Outputs

| Output              | Type     | Description                           |
|--------------------|----------|---------------------------------------|
| `dispatch_decision` | Decision | Parallel vs sequential with rationale |
| `agent_prompts`     | Text     | Self-contained prompts per agent      |
| `merge_report`      | Inline   | Conflict check + test results summary |

## When to Use

Decision path: multiple failures? → are they independent? If no (related), one agent
investigates all. If yes → can they work in parallel? Shared state means sequential
agents; no shared state means parallel dispatch, one agent per problem domain.

<CRITICAL>
Independence verification is the gate. Answer ALL of these BEFORE dispatching:
</CRITICAL>

<analysis>
Are failures in different subsystems/files? Can each be understood without the others?
Would fixing one affect the others? Will agents edit the same files?
</analysis>

**Use when:** 3+ test files failing with different root causes; multiple subsystems broken independently; each problem understandable without context from others; no shared state between investigations.

**Don't use when:** failures are related; need full system state; agents would interfere (same files, shared resources); exploratory debugging.

---

## The Pattern

### 1. Identify Independent Domains

Group failures by what's broken: file A tests = tool approval flow, file B = batch
completion behavior, file C = abort functionality.

### 2. Create Focused Agent Prompts

Each agent gets: **specific scope** (one test file or subsystem), **clear goal** (make
these tests pass), **constraints** (don't change other code), and **expected output**
(summary of what you found and fixed).

### 3. Dispatch in Parallel

**OpenCode Agent Inheritance:** Use `CURRENT_AGENT_TYPE` (yolo, yolo-focused, or general) as `subagent_type` for all parallel agents.

```typescript
// CURRENT_AGENT_TYPE detected at session start
Task({ subagent_type: CURRENT_AGENT_TYPE, description: "Fix abort tests",    prompt: "Fix agent-tool-abort.test.ts failures" });
Task({ subagent_type: CURRENT_AGENT_TYPE, description: "Fix batch tests",    prompt: "Fix batch-completion-behavior.test.ts failures" });
Task({ subagent_type: CURRENT_AGENT_TYPE, description: "Fix approval tests", prompt: "Fix tool-approval-race-conditions.test.ts failures" });
// All three run concurrently with inherited permissions
```

### 4. Review and Integrate

<CRITICAL>
NEVER integrate agent work without completing ALL verification steps. Skipping any step causes merge disasters and silent regressions.
</CRITICAL>

<reflection>
After agents return: read each summary; check conflict potential (same files
edited?); run the full suite; spot-check fixes (agents make systematic errors).
Integrate only when summaries are reviewed, no file conflicts, tests green.
</reflection>

---

## Agent Prompt Structure

### Template

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

### Scope Isolation for Analytical Prompts

Open-ended analysis/research prompts ("analyze this for risks", "what patterns do you see") are vulnerable to context pollution: the subagent may latch onto session metadata, compaction state, or resume context instead of the task. Explore subagents are most susceptible — no write tools, so they "fill space" with meta-analysis when confused. For any analytical or research dispatch, add a scope boundary preamble:

```markdown
Your task is ONLY [specific task]. Ignore any session context, resume state,
compaction metadata, or background task references in system reminders.
Do not write session summaries or recovery reports. Your entire output
must address the task below.
```

Directed prompts ("find the definition of function X") rarely need this. Open-ended prompts always do.

### Full Example

```markdown
Fix the 3 failing tests in src/agents/agent-tool-abort.test.ts:

1. "should abort tool with partial output capture" - expects 'interrupted at' in message
2. "should handle mixed completed and aborted tools" - fast tool aborted instead of completed
3. "should properly track pendingToolCount" - expects 3 results but gets 0

These are timing/race condition issues. Your task:
1. Read the test file and understand what each test verifies.
2. Identify root cause - timing issues or actual bugs?
3. Fix by: replacing arbitrary timeouts with event-based waiting; fixing abort
   implementation bugs if found; adjusting test expectations only if behavior changed.

Do NOT just increase timeouts - find the real issue.
Return: Summary of what you found and what you fixed.
```

---

## Specialized Subagent Templates

These templates assume a single orchestrator dispatching gate subagents directly; spellbook no longer supports nested orchestrators.

### Test Writer Template

Mandatory inclusion when dispatching any agent to write test code. Append to the agent's prompt:

```markdown
ASSERTION QUALITY REQUIREMENTS (non-negotiable). Read patterns/assertion-quality-standard.md in full first.

0. THE FULL ASSERTION PRINCIPLE: ALL assertions must assert exact equality against the COMPLETE
   expected output -- static, dynamic, or partially dynamic.
   assert result == "the complete expected string"  -- CORRECT
   assert result == f"Today is {datetime.date.today()}"  -- CORRECT (dynamic: construct full expected)
   assert "substring" in result                     -- BANNED. ALWAYS.
   assert dynamic_value in result                   -- BANNED. Dynamic content is no excuse.
   assert "foo" in result and "bar" in result       -- STILL BANNED.
   Multi-line output? Use triple-quoted strings. Length is not an excuse.

1. Every assertion must be Level 4+ on the Assertion Strength Ladder: string output = exact match
   (L5) or parsed structural (L4); object = full equality or all-field assertions; collection =
   full equality or content verification. BANNED: bare substring checks, length/existence checks
   (assert len(x) > 0), multiple substring checks, tautologies (assert result ==
   func(same_input)), mock.ANY in call assertions (construct expected argument).

2. IRON LAW: before writing any assertion ask: "If the value was garbage, would this catch it?"
   If NO: stop and write a stronger assertion.

3. BROKEN IMPLEMENTATION: for each test function, state which specific production code mutation
   would cause the test to fail. If you cannot name one, the test is worthless.

4. STRUCTURAL CONTAINMENT: when asserting string content, verify WHERE it appears, not just THAT
   it appears -- a field must be verified inside its struct block (index range or parsing).

5. NO PARTIAL-TO-PARTIAL UPGRADES: replacing assert len(x) > 0 with assert "keyword" in result is
   NOT a fix. Both are BANNED. A real fix reaches Level 4+.

6. MOCK CALL ASSERTIONS: assert EVERY call made to a mock, with ALL args, and verify call count.
   Never use mock.ANY -- construct expected args dynamically if they are dynamic. Asserting only
   some calls hides behavior gaps.
```

### Test Adversary Template

For review passes on test code. Dispatch a subagent with this persona to break every assertion:

```markdown
ROLE: Test Adversary. Your job is to BREAK tests, not validate them.

Read patterns/assertion-quality-standard.md in full; heed The Full Assertion Principle.

IMMEDIATE REJECTION CRITERIA (check FIRST):
- Any assert "X" in result on ANY output: REJECTED (Level 2)
- Any assert len(x) > 0 or assert x is not None: REJECTED (Level 1)
- Any fix that replaced one BANNED pattern with another: REJECTED (Pattern 10)
- Any tautological assertion (assert result == func(same_input)): REJECTED

For each assertion:
1. Read it plus the production code it exercises.
2. If the function is deterministic, ONLY Level 5 (exact equality) is acceptable.
3. Classify it on the Assertion Strength Ladder.
4. Construct a SPECIFIC, PLAUSIBLE broken implementation that still passes --
   "plausible" = real-bug-shaped (off-by-one, wrong variable, missing field,
   swapped args, dropped output), not adversarial (return the exact expected string).
5. Verdict:

   SURVIVED: [the broken implementation that passes]
   LADDER: Level [N] - [name]; DETERMINISTIC: [Yes/No]
   FIX: [what the assertion should be instead]

   -- or --

   KILLED: [why no plausible broken implementation survives]
   LADDER: Level [N] - [name]; DETERMINISTIC: [Yes/No]

Summary: total reviewed / KILLED (levels) / SURVIVED (fixes) / BANNED L1-2 / Pattern 10.
```

### Branch-Scoped Review Template

When dispatching a subagent to review a branch's changes (a local branch diff, not a GitHub PR), the subagent MUST receive the actual diff, not just file paths — a file path points to the entire file, so the subagent cannot distinguish branch changes from pre-existing code and will flag pre-existing gaps as regressions.

Compute the diff first (`cd <path> && git diff origin/master...HEAD`; for large diffs, `--stat` plus per-file sections, or a changed-function allow-list via `git diff ...HEAD | grep -E '^\+.*def |^\+.*class |^@@' | head -50`), then include:

```markdown
## Branch Review Context (MANDATORY)

- Branch: <branch-name>
- Working directory: <absolute-path>
- Merge base: origin/master

SCOPE CONSTRAINT: Only analyze code that appears in the diff below. Functions in
changed files that were NOT modified by this branch are OUT OF SCOPE. Do not flag
pre-existing issues as branch regressions.

VERIFICATION PREAMBLE: Before any other work, run:
  cd <working-directory> && pwd && git branch --show-current
Verify you are in the correct directory on the correct branch. If not, stop and report the mismatch.

## Diff

<paste diff output here>
```

### PR Review Subagent Template

REQUIRED when dispatching any subagent to review a PR (target is a PR number or URL, not a local branch).

**Step 1 — Resolve review mode before dispatch:**

```bash
PR_HEAD_SHA=$(gh pr view <PR_NUMBER> --json headRefOid --jq '.headRefOid')
PR_BRANCH=$(gh pr view <PR_NUMBER> --json headRefName --jq '.headRefName')
WORKTREE_PATH=$(git worktree list --porcelain | grep -A2 "branch refs/heads/$PR_BRANCH" | grep "worktree" | awk '{print $2}')
```

| Condition | Review Mode | Agent Working Directory |
|-----------|-------------|------------------------|
| Worktree exists for PR branch | `LOCAL_FILES` | `$WORKTREE_PATH` |
| No worktree, local HEAD = PR HEAD SHA | `LOCAL_FILES` | Current repo root |
| No worktree, local HEAD ≠ PR HEAD SHA | `DIFF_ONLY` | N/A — use diff only |

**Step 2 — Inject into subagent prompt:**

```markdown
## PR Review Context (MANDATORY — read before touching any file)

- PR: #<NUMBER>; PR HEAD SHA: <SHA>
- Review mode: LOCAL_FILES | DIFF_ONLY
- Working directory: <WORKTREE_PATH or "use diff only">
- Changed files: <LIST>

REVIEW MODE INSTRUCTIONS:
- LOCAL_FILES: Safe to read files in <working_directory>. DO NOT read files outside this directory.
- DIFF_ONLY: DO NOT read any local files in the changed file set. The diff is the ONLY
  authoritative source. Any "not present" finding based on a local file read is WRONG.
```

<FORBIDDEN>
- Dispatching a PR review subagent without injecting PR HEAD SHA and review mode
- Dispatching in LOCAL_FILES mode without specifying the exact working directory
- Dispatching in DIFF_ONLY mode while pointing the agent at the local filesystem
</FORBIDDEN>

---

## Common Mistakes

| Anti-pattern        | Problem                     | Fix                                        |
| ------------------- | --------------------------- | ------------------------------------------ |
| "Fix all the tests" | Agent gets lost             | Specify exact file/tests                   |
| No error context    | Agent guesses wrong         | Paste actual error messages and test names |
| No constraints      | Agent refactors everything  | Add "do NOT change X"                      |
| "Fix it" output     | You don't know what changed | Require cause+changes summary              |

---

## Anti-Patterns

<FORBIDDEN>
- Dispatching tasks that share mutable state
- Overlapping file ownership between agents
- Vague prompts ("fix the tests", "make it work")
- Skipping conflict check before merge
- Integrating without running full test suite
- Dispatching exploratory work (unknown scope)
- Parallel dispatch when failures might be related
- Dispatching a branch review subagent with file paths instead of diffs (subagent cannot distinguish branch changes from pre-existing code)
- Dispatching a worktree subagent without the verification preamble, without specifying which branch to base worktrees on (subagent may operate in the wrong directory)
- Using `isolation: "worktree"` for tasks that depend on prior uncommitted work (isolated worktrees branch from current HEAD, missing uncommitted changes)
- Dispatching open-ended analytical prompts to Explore subagents without a scope isolation preamble (agent will latch onto session metadata instead of performing the task)
- Dispatching without the Subagent Efficiency Contract block in the prompt
- Carrying raw tool output >2,000 chars forward instead of a reduction
</FORBIDDEN>

---

## Real Example

6 failures across 3 files post-refactor. **Domain isolation:** agent-tool-abort.test.ts (3, timing), batch-completion-behavior.test.ts (2, event structure bug), tool-approval-race-conditions.test.ts (1, async waiting). **Dispatch:** 3 parallel agents, one per file. **Results:** timeouts → event-based waiting; threadId moved to correct place; wait added for async completion. **Integration:** zero conflicts, full suite green. **Gain:** N parallel problems resolved in time of the slowest (best case N×).

---

## Context Minimization Protocol

<CRITICAL>
When orchestrating multi-step workflows (especially via skills like develop, executing-plans, etc.), you are an ORCHESTRATOR, not an IMPLEMENTER.

Your job is to COORDINATE subagents, not to DO the work yourself.
Every line of code you read or write in main context is WASTED TOKENS.
</CRITICAL>

FORBIDDEN in main context — reading source files, writing/editing code, running
tests, analyzing errors, searching the codebase. Each bloats main context with
work a subagent does and returns summarized (explore for reads/searches, TDD for
edits, debugging for errors).

ALLOWED: dispatching subagents, reading result summaries, updating the todo list,
phase transitions and gate checks, user communication, reading/writing plan
documents.

### Self-Check Before Any Action

Before EVERY action: about to read a source file, edit code, run a command, or analyze
output? → STOP. Dispatch subagent instead.

---

## Subagent Dispatch Template

> **Before invoking this template:** perform the Pre-Dispatch Ritual (Phase Declaration) per the `develop` skill — announce the phase, the work scope, and the exit criteria.

<CRITICAL>
When dispatching subagents that should invoke skills, use this EXACT pattern. No variations.

**OpenCode Agent Inheritance:** If `CURRENT_AGENT_TYPE` is `yolo` or `yolo-focused`, use that as `subagent_type` instead of `general`. This ensures subagents inherit autonomous permissions.
</CRITICAL>

```
Task(
  description: "[3-5 word summary]",
  subagent_type: "[CURRENT_AGENT_TYPE or 'general']",
  prompt: """
First, invoke the [SKILL-NAME] skill using the Skill tool.
Then follow its complete workflow.

If the Skill tool is unavailable in your context, or the named skill does
not appear in your skills catalog after your first tool call, STOP and
report the exact missing capability verbatim. Do NOT inline-execute the
skill's behavior. Do NOT paraphrase the skill from memory. Do NOT proceed
with the work. Silent fallback is a contract violation; the orchestrator
will reject any result that does not contain a "Launching skill:" line.

## Context for the Skill

[ONLY provide context - file paths, requirements, constraints]
[DO NOT provide implementation instructions]
[DO NOT duplicate what the skill already knows]
"""
)
```

### Subagent Efficiency Contract (include in EVERY dispatch prompt)

This block is the dispatch-time form of **Mandatory Summarization**: a tool that returns structured
or verbose data (Figma, DevTools, build logs) is wrapped in a summarization step before anything
reaches the orchestrator. Append it verbatim to every subagent prompt:

```
TOOL OUTPUT DISCIPLINE:
- After any tool call whose output exceeds ~2,000 characters, immediately
  reduce it to the facts the task needs before your next step. Do not carry
  raw logs, full file dumps, or listings forward turn over turn.
- Build/test/lint output: reduce to pass/fail counts plus the names and
  messages of failures. Never re-paste a passing log.
- Never load base64 or image data into context unless the task is to
  analyze that exact image.

CALL BATCHING:
- Read a file ONCE, in full (or one bounded range), not in repeated
  offset windows.
- Combine related searches into one grep with alternation
  (grep -E 'a|b|c'), not one call per identifier.
- Treat configure/build/test as ONE step with one summarized result
  unless a gate requires them separated.
- Report repetitive results (e.g., mutation variants M1..M23) as one
  table in one message, not one message each.
```

**Agent Type Selection:**
| Parent Agent | Subagent Type | Notes |
|--------------|---------------|-------|
| `yolo` | `yolo` | Inherit autonomous permissions |
| `yolo-focused` | `yolo-focused` | Inherit focused autonomous permissions |
| `general` or unknown | `general` | Default behavior |
| Any (exploration only) | `explore` | Read-only exploration tasks |

## Dispatch Protocol

Four conventions that cut tokens without costing comprehension. The first three remove
duplication and fix an order; none compress text. The fourth compresses content density
— never format identity. Across all four: do NOT invent a shorthand, an abbreviation
scheme, or a stenographic encoding, and do NOT alter the canonical return vocabulary or
envelope. The waste this protocol targets was never wording. It was repeated content.

### Prompt layout is fixed and cache-aligned

Order every dispatch prompt with the INVARIANT BLOCKS FIRST and the volatile
task detail LAST:

1. Efficiency Contract (verbatim, byte-identical every dispatch)
2. Return envelope schema (verbatim)
3. Constraints the dispatcher states for this dispatch (e.g. explicit FORBIDDEN
   actions, scope boundaries) — not a canonical per-agent-type block, since none
   exists to copy. If the dispatched agent type has its own defined guardrails
   (e.g. an agent-type file under `~/.claude/agents/*.md` with an Invariant
   Principles or Guardrails section), quote the relevant lines here.
4. `TASK` — what to do, this dispatch only
5. `SCOPE` — files, directories, boundaries
6. `INPUTS` — pointers to material (see below)
7. `FORBIDDEN` — actions out of bounds for this dispatch
8. `BUDGET` — token or time ceiling, or "none"

Blocks 1-3 are prefix-cacheable only while they stay byte-identical. Paraphrasing
them per dispatch defeats the cache and costs real money for zero benefit. COPY
them; do not rewrite them.

### Pass pointers, not payloads

Content longer than ~30 lines goes in a file and the dispatch carries
`path:line-range`. A subagent that needs it reads it once. Inlining a file into
a prompt and then having the subagent read that same file is the duplication
this rule exists to stop.

- Material shared by N dispatches: write it ONCE to the scratchpad, pass that
  one path to all N.
- Reports name `path:line` for every claim a reader might want to verify.
- Exception: a short excerpt that IS the subject of the task — quote it inline.

### Return envelope

This is **Subagent Strict Schema** at dispatch time. Every dispatch declares the shape it wants
back; every subagent returns that shape and nothing else. Conversational leak in place of the
declared schema is forbidden. Default when a skill defines no shape of its own:

```json
{
  "status": "COMPLETE | OPEN | BLOCKED",
  "reason": "required when status is OPEN or BLOCKED, else empty",
  "findings": [{"id": "", "severity": "", "path": "", "line": 0, "claim": ""}],
  "artifacts": ["paths written or modified"],
  "unverified": ["claims this agent could not confirm"]
}
```

A conversational report in place of the declared shape is a FAILED dispatch even
when the work behind it is right. `unverified` is not optional politeness — an
empty `unverified` on a task involving measurement is itself a claim.

### Canonical result vocabulary

Use these exact tokens. They are names with one meaning each, not abbreviations
to decode. A private synonym per skill is how "done" came to mean four different
things on one project.

| Domain | Values |
|---|---|
| Task state | `COMPLETE`, `OPEN`, `BLOCKED` |
| Artifact conformance | `CONFORMS`, `SALVAGEABLE`, `REWRITE`, `UNCLAIMED` |
| Finding provenance | `NEW`, `INDUCED`, `CARRIED` |
| Verification outcome | `VERIFIED`, `UNVERIFIED`, `REFUTED`, `INCONCLUSIVE` |
| Gate result | `PASSED`, `FAILED`, `N_A` |
| Convergence | `CONVERGING`, `OSCILLATING` |
| Figure confidence | `MEASURED`, `DERIVED`, `CARRIED`, `ESTIMATED` |

Gate results are written to the §24.6 ledger in lowercase (`passed` / `failed` / `n_a`) —
that is the only form `scripts/develop_gate_ledger.py`'s `wave-discipline` and `group-gate`
CLI accept. The uppercase form above is for prose and reports; do not pass it to the CLI.

`CARRIED` is the value `rules/20-orchestration.md` already requires: a figure you did
not measure yourself in this session, passed along unverified. It is distinct from
`DERIVED` (computed from values that were measured) and from `ESTIMATED` (no
measurement behind it at all). Projects whose existing documents use `INFERRED` may
keep that word — it is an accepted synonym for `DERIVED` and does not need churning.

**Observed: seven carried figures in one session; the subagents' own measurements
refuted all seven** — a lint baseline reported as "one finding" measured 156; a count
attributed to a code comment that did not exist; a flag rule relayed without the `-R`
prefix the original measurement required. In a codebase where a written measurement is
trusted by default, a carried figure written as if measured gets copied into a source
comment no reader can tell apart from a real measurement. Mark it `CARRIED`.

**Extending the vocabulary.** A domain this table does not cover is expected. That does
NOT license a private synonym for a value that IS here. When work needs a value the
table lacks: add it project-locally (`AGENTS.md`, one-line definition) so work is not
blocked, surface it to the operator as a SUGGESTION (spellbook is the PREFERRED home),
and let the operator decide. Never edit this table without that decision, and never sit
on a value you have used twice without proposing it — a value that has appeared in two
projects is overdue for this table.


### Content density: compress redundancy, never information

The first three conventions cut repeated content; this one cuts wasted wording — in
dispatches and returned prose alike, where it matters more: outputs cost several times
the input rate and are not prefix-cached. These rules govern DENSITY. They do not
license a private shorthand, an encoding, or any change to the canonical envelope and
vocabulary above.

1. **No social framing, either direction.** No greetings, no acknowledgment, no
   transition sentences, no summary-of-the-summary at the end.
2. **Common vocabulary only; never binary encodings.** A common English word
   tokenizes cheaply; rare strings and typos shatter into sub-word tokens.
   Base64/hex/binary are catastrophically expensive — never use them to
   "compress" anything.
3. **Delimiters for data, grammar for instructions.** Fielded data (paths,
   counts, verdicts) goes in tables or single-token-delimited fields.
   Load-bearing instructions keep normal syntax: negation scope, conditionals,
   and precedence die first under compression, and one misread costs a full
   re-dispatch — dwarfing everything these rules save.
4. **Shared jargon over spelled-out mechanics** — only jargon the corpus or the
   receiving agent already shares; never coin private abbreviations. Calibrate
   density to the receiving tier: what a heavy-tier agent parses reliably
   misfires more on a light tier.
5. **Bound the scope, not just the words.** The largest hidden sink is unbounded
   work, not filler: "research X" can burn 100k where "answer Y from file Z,
   lines 1-50" burns 5k. State stop conditions, read ranges, and negative space
   ("do not run the full suite", "no preamble").
6. **Returns before dispatches.** The highest-value compression target is what
   comes BACK: declare the return shape (above), require fixed-column tables for
   measurements per `rules/45`, forbid restating the task or narrating method
   unless a finding depends on it.

## Dispatch Mechanics and Examples

### Skill Availability by Agent Type

The Skill tool is included for most subagent types but not all. Verify before dispatching skill-dependent work:

| Subagent Type | Has Skill tool | Notes |
|---|---|---|
| `general-purpose` (or `general`) | yes | Full toolset; default for develop dispatches |
| `Explore` (or `explore`) | yes | Read-only exploration; cannot edit files |
| `Plan` | yes | Read-only planning; cannot edit files |
| `yolo`, `yolo-focused` (OpenCode) | yes | Inherit autonomous permissions |
| `claude-code-guide` | no | Restricted to Bash, Read, WebFetch, WebSearch |
| `statusline-setup` | no | Restricted to Read, Edit |

Dispatching a skill-using prompt to an agent type without the Skill tool is a contract bug. The dispatch will produce no "Launching skill:" line and the orchestrator must reject the result.

Every dispatch pays a fixed skill-catalog injection cost (~30K characters) regardless of whether the subagent uses any skill. When several small sequential tasks would each need a dispatch, prefer one subagent with the combined sequential scope — provided the tasks are not separate rows of a develop dispatch table (that combination is forbidden by 40-develop-discipline). This cost is harness-level and cannot be reduced from a prompt or a rule file — consolidating dispatches is the only lever available here, so do not spend effort trying to suppress the injection itself.

**Lazy-injection caveat:** The skills catalog system-reminder is injected into a subagent's context AFTER its first tool call, not at session start. A subagent that introspects its tools or system reminders before acting may falsely conclude that no skills are available. The dispatch template's "First, invoke the [SKILL-NAME] skill" instruction forces the first tool call to BE the skill invocation, sidestepping this footgun. Do not weaken that instruction.

### Worktree Dispatch

<CRITICAL>
When dispatching ANY subagent to work in a worktree or alternate directory, the prompt MUST begin with this verification preamble. No exceptions.
</CRITICAL>

```markdown
BEFORE ANY WORK:
1. cd <WORKTREE_PATH> && pwd && git branch --show-current
2. Verify the branch is <EXPECTED_BRANCH>
3. ALL file paths must be absolute, rooted at <WORKTREE_PATH>
4. ALL git commands must run from <WORKTREE_PATH>
5. Do NOT create new branches. Do NOT read files from <MAIN_REPO_PATH> -- that is a DIFFERENT branch.
```

**Why this matters:** without explicit path and branch verification, agents silently read files and run git from the main repo (a different branch), producing confidently wrong results and duplicate infrastructure branched from main.

**When using `isolation: "worktree"`:** the worktree branches from the CURRENT branch at dispatch time. If prior work items' commits aren't on the current branch yet, the isolated worktree won't have them. For sequential dependencies, commit and stay on the same branch rather than using isolated worktrees.

### WRONG vs RIGHT Examples

**WRONG - Doing work in main context:** read the config file, then edit line 45, then keep going.

**RIGHT - Delegating to subagent:** `Task(description: "Implement config field", prompt: "Invoke test-driven-development skill. Context: Add 'extends' field to provider config in packages/opencode/src/config/config.ts")`, then wait for the result.

**WRONG - Instructions in subagent prompt:** `"Use TDD skill. First write a test that checks the extends field exists. Then implement by adding a z.string().optional() field after line 865..."`

**RIGHT - Context only in subagent prompt:** `"Invoke test-driven-development skill. Context: Add 'extends' field to Config.Provider schema. Location: packages/opencode/src/config/config.ts around line 865."`

### Subagent Prompt Length Verification

Before dispatching ANY subagent: count prompt lines, estimate tokens as `lines * 7`;
if > 200 lines with no valid justification, compress before dispatch. Most prompts
should be < 150 lines — they provide CONTEXT and invoke skills.

---

## Dispatch Survival Protocols

Five mechanisms against one failure class: **dispatches that die mid-work.**
**Observed:** five died in two days (2026-08-20→22) — billing/API errors or context
exhaustion; three while composing final reports, one leaving half-written tree state
a later pass nearly trusted as a baseline.

### Artifact-first reporting

**When:** runs over ~30 min, reads over 1000 lines, or structured findings. Write
findings INCREMENTALLY to a named artifact path (`scratchpad/<task-name>/report.md`)
as each major unit completes — not only into the final message, which becomes status +
pointer + unwritten deltas. Add the path to the return envelope's required `artifacts`
field rather than inventing a second channel: this is the write-side counterpart of
"pass pointers, not payloads" — the orchestrator passes paths in; the agent writes
paths out.

**Observed:** transcript-only work products die with the session; on-disk ones survive.

### Compact-verdict budgets

**When:** plan reviews, audits, fact-checks, any multi-question analysis. Specify UP
FRONT in the brief: per-question verdict lines using the canonical tokens (`VERIFIED` /
`UNVERIFIED` / `CARRIED` — never mint compound variants), one line each with its single
strongest evidence; a return cap (~800 words); a command budget for final delivery.

**Observed:** long prose reports are precisely the ones that never arrive — three of the
five deaths happened while composing them.

### Heartbeat lines

**When:** multi-phase builds and TDD cycles. ONE line at each phase boundary ("RED
observed", "GREEN", "mutation N restored") — distinguishes still-working from dead
without polling; gives a resume exact salvage points, not "somewhere mid-task".

### Truncation-recovery protocol (orchestrator side)

<CRITICAL>
Verify tree state FIRST (`git status --porcelain` + targeted greps for expected
artifacts) before ANY re-dispatch. Never trust report shape — report shape is what failed.
</CRITICAL>

Then classify the death: billing/auth error → pause ALL dispatches until resolved;
context exhaustion → resume the SAME agent over fresh dispatch (retains derived
context); crash → tree-verify then fresh dispatch. A resumed agent gets a
stop-investigating instruction, a hard remaining-command budget, and a compact output
shape. Salvage rule: partial work already in files is KEPT if it verifies; never
re-dispatch blind over uncommitted tree changes. This governs agents that DIED; the
Timeout Tolerance invariant governs agents still RUNNING — neither replaces the other.

### Two-phase deep reads

**When:** source documents over 5000 lines. Phase A extracts ONLY the needed sections,
compressed, to an on-disk digest; Phase B works from the digest instead of re-reading.
Costs one round-trip; buys survival of the working phase, which cannot die of
exhaustion from the read itself.

<FORBIDDEN>
- Dispatching a long task (>~30 min, >1000-line reads) without an incremental artifact path
- Re-dispatching after a suspicious/truncated/absent report before verifying tree state
- Fresh-dispatching after context exhaustion when a same-agent resume is available
</FORBIDDEN>

## Self-Check

Before completing:

- [ ] Independence verified: no shared state, no file overlap
- [ ] Each agent prompt is self-contained with full context
- [ ] Constraints explicitly state what NOT to change
- [ ] All agent summaries reviewed before integration
- [ ] Conflict check performed on returned work
- [ ] Full test suite green after merge
- [ ] Survival mandates applied where triggered: artifact path (long dispatches), verdict budgets (deep investigations), heartbeats (multi-phase builds)

<CRITICAL>
If ANY unchecked: STOP and fix. Parallel dispatch without independence verification causes merge disasters. The independence gate is non-negotiable; verify before dispatch, verify before integration.
</CRITICAL>

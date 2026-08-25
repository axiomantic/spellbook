---
name: develop
description: |
  Use when building, creating, modifying, or planning any code change. Triggers: "implement X", "build Y", "add feature Z", "create X", "change how X works", "modify Y", "update the Z", "refactor X", "rework Y", "restructure Z", "make X do Y", "let's plan how to", "plan the implementation", "how should we implement", "how would you build", "what's the best way to implement", "I want to...", "We need...", "Would be great to...", "Can we add...", "Let's add...", "Let's build...", "Let's make...", "start a new project". Also for: new projects, repos, templates, greenfield development, refactoring, migrations, multi-file modifications, any code change requiring planning. PREFER THIS OVER plan mode or ad-hoc implementation for ANY substantive code change. NOT for: bug fixes (use debugging), pure research (use deep-research), questions about existing code without intent to change it, or test-only fixes (use fixing-tests).
intro: |
  Full-lifecycle feature implementation orchestrator that coordinates research, discovery, design, planning, and execution through specialized subagents with quality gates at every phase. Handles everything from greenfield projects to multi-file refactors. Invoke with `/develop` or describe what you want to build, and this core spellbook skill manages the entire workflow from requirements through verified delivery.
---

<ROLE>
You are the gatekeeper of the develop workflow. Your one job is to make the cost of thoroughness VISIBLE before it is paid, let the operator choose deliberately, and then get out of the way. You do not implement. You do not plan. You ask, you dispatch, you hold the contract.
</ROLE>

<BEHAVIORAL_MODE>
ENTRY GATE: ask which path, then load that path. Never read source files, write code, or run tests from this file. Everything the orchestrator needs after the choice lives in `$SPELLBOOK_DIR/commands/develop-configure.md`.
</BEHAVIORAL_MODE>

## Invariant Principles

1. **Ask before spending.** The ceremony cost is disclosed and chosen BEFORE any phase runs, never assumed from the phrasing that triggered this skill.
2. **The choice is the operator's.** develop may recommend; the operator's answer is the source of truth.
3. **Chosen ceremony LOCKS.** From the moment a ceremony path is chosen, escalation stays legal and de-escalation never becomes legal. The two honest answers to "this is taking too long" are FINISH or ABORT-and-re-invoke.
4. **No path is zero review except the one that exits.** Both ceremony paths carry a review floor. Only "skip develop entirely" leaves the operator unguarded, and it says so out loud.
5. **develop stays resident on both ceremony paths.** There is no auto-exit; the skill remains active to enforce the floor it sold.

## Reasoning Schema

<analysis>Before asking: state what the request appears to touch, and which path you would recommend and why.</analysis>
<reflection>After the answer: confirm the chosen path is recorded, the ceremony is locked, and the correct body was loaded.</reflection>

---

## The Gate

<CRITICAL>
On invocation, ask the operator via AskUserQuestion which path to take. Ask FIRST — before reading files, before exploring, before planning. Do not load `commands/develop-configure.md` until the answer is in.

Offer exactly these THREE options (the harness adds its own "Other"). Present each option's cost honestly; the descriptions below are the point of this gate, not decoration.
</CRITICAL>

**Question:** How much ceremony should this change get?

### Option 1 — Full ceremony (most correct, slowest)

> Full ceremony: every gate in the develop review floor runs, plus the depth gates the request's need-flags call for. Each phase is its own set of subagent dispatches, so this is MANY dispatches and the slowest path by a wide margin. Once chosen, the ceremony LOCKS: no phrasing during the run reopens it, and the only ways out are FINISH or ABORT-and-re-invoke. Escalating to more ceremony is always allowed; dropping a gate never is.

### Option 2 — Fast path (lighter, still gated)

> Fast path: a reduced gate set, but NEVER zero review. Research and the plan happen inline, in this conversation, instead of running as full phases with their own dispatches — you confirm the plan before anything is executed. Fewer and faster gates, and a gate that cannot apply is RECORDED as not-applicable rather than silently dropped. The ceremony LOCKS identically: no phrasing reopens it, FINISH or ABORT are the only ways out, and escalation is allowed where de-escalation is not. Work that outgrows the fast path is re-flagged and continues at the gated phase rather than being squeezed through.

### Option 3 — Skip develop entirely (least cost, no gates)

> Skip develop: this skill exits immediately and you do the work directly. Nothing is dispatched, no phases run, and no ledger is written. NO review of any kind comes from this skill — nothing here will notice a regression, a test that passes without verifying behavior, or an untested edit. Choose this when you already know exactly what to change and accept that the verification is entirely yours.

**Want the specifics before deciding?** The authoritative gate roster — which gates
form the floor for each path, and which depth gates each need-flag adds — is the
*Tiered Review Floor* tables in `$SPELLBOOK_DIR/commands/develop-configure.md`.
Read them from there; this gate deliberately does not restate them, so they
cannot drift apart.

**Recommend** Option 1 when the request touches behavior across more than a handful of files, needs a design decision, or introduces infrastructure. **Recommend** Option 2 for a bounded, well-understood edit. Never recommend Option 3; offer it, and let the operator take it.

---

## Autonomous Mode

<CRITICAL>
Autonomous / YOLO mode scopes CONFIRMATIONS, not SCOPE. Choosing a ceremony is a scope decision, so the gate STILL ASKS in autonomous mode. Standing autonomous permission is not an answer.

The one exception is an operator who cannot be reached — a non-interactive, headless, or CI session where AskUserQuestion reaches no human. There, and only there, default to **Full ceremony** and say so in the transcript. NEVER silently pick the cheap path, and never treat "this looks small" as unavailability.

**Autonomy is the SECOND, orthogonal question.** Ceremony is how much verification runs; autonomy is who decides and when the run may end. Ask it AFTER a ceremony path is chosen, on BOTH ceremony paths, never on skip; hand it to the `autonomous-mode` skill, which owns it and its limits. Autonomy scopes CONFIRMATIONS only: it skips no gate, phase, or dispatch, and never reopens the locked ceremony. A blocker still reaches the operator through AskUserQuestion.
</CRITICAL>

---

## After the Answer

| Answer | What you do |
|--------|-------------|
| Full ceremony | Load `$SPELLBOOK_DIR/commands/develop-configure.md` and run the full phase sequence. develop STAYS RESIDENT. |
| Fast path | Load `$SPELLBOOK_DIR/commands/develop-configure.md` and follow its zero-flag routing. develop STAYS RESIDENT. |
| Skip entirely | EXIT this skill. Say plainly which gates the operator is giving up. Do not dispatch, do not write a ledger. |
| Other (harness-provided) | Treat the operator's own words as the answer; if they describe a ceremony, map it to one of the three and confirm. |

On BOTH ceremony paths, ask the autonomy question next, before the first
dispatch. Hand it to the `autonomous-mode` skill, which owns the question,
writes the record, and states the limits. It is a separate question with a
separate answer: ceremony is how much verification runs, autonomy is who
decides and when the run may end. On skip, it is not asked.

<CRITICAL>
**Resident-orchestrator contract.** On both ceremony paths develop does NOT auto-exit. It remains the active orchestrator, dispatches every phase through subagents, and enforces the review floor it just sold. Only "skip entirely" exits.

**The lock attaches at the ANSWER.** Record it in `develop_gate_ledger.ceremony` with `locked_at`. Every phase after this point executes EXACTLY ONE row of the develop dispatch table and must be preceded by a Phase Declaration citing the ledger line it satisfies. The full treatment — forbidden rationalizations, ABORT-and-re-invoke, wave discipline (§24.6), stop semantics, and the incidentals protocol — is in `$SPELLBOOK_DIR/commands/develop-configure.md`.

**After a compaction mid-develop, RE-READ `$SPELLBOOK_DIR/commands/develop-configure.md`** before the next dispatch. A compacted context has lost the ceremony lock and the gate semantics, and a run that continues without them elides gates while reporting success.
</CRITICAL>

## Inputs

- The operator's request (what to build or change).
- Any existing `develop_gate_ledger` for this project — a live ledger means a run is already in progress; resume it rather than re-asking, unless the operator is deliberately re-invoking to change ceremony.

## Outputs

- A chosen path, recorded and locked.
- On either ceremony path, the loaded orchestrator body and a running phase sequence.
- On skip, an exited skill and an explicit statement of the gates forgone.
- On either ceremony path, the autonomy question asked and answered through the `autonomous-mode` skill — with a record written and read back, or an explicit statement that autonomous mode was not enabled.

<FORBIDDEN>
- Loading `commands/develop-configure.md` before the operator has answered.
- Inferring the answer from the phrasing of the request, the size of the change, or standing autonomous mode.
- Defaulting to the fast path or to skip when the operator cannot be reached.
- De-escalating the ceremony after the answer, under any phrasing.
- Exiting the skill on a ceremony path.
- Dispatching a phase on a ceremony path before the autonomy question has been asked, or answering it yourself from standing autonomous phrasing.
</FORBIDDEN>

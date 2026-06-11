# /feature-discover

## Workflow Diagram

---

## Diagram 1: Phase 1.5 Overview

End-to-end flow from prerequisite check through all sub-phases to Phase 2 handoff. Decision diamonds (red) are quality gates; the devil's advocate dispatch (blue) is the only subagent in the top-level flow. See cross-reference table for detail diagrams.

```mermaid
flowchart TD
    START(["Phase 1.5 Entry"])
    PRECHECK{"needs_research=true\nPhase 1 complete?"}
    STOP1(["STOP: Return to Phase 1"])

    DISAMB["§1.5.0 Disambiguation\nSession — ARH"]
    GEN["§1.5.1 Generate\n7-Category Questions"]
    WIZARD["§1.5.2 Discovery Wizard\n7 categories × ARH"]
    DRIFT1{"§1.5.2.5\nScope Drift?"}
    REFLAG1["Re-flag need-flags\n& Continue"]
    STANDARDS["§1.5.2.6 Project-\nStandards Cross-Check"]
    GLOSSARY["§1.5.3 Build Glossary\n& Persistence Option"]
    SYNTH["§1.5.4 Synthesize\ndesign_context"]
    GATE_C{"§1.5.5 Completeness\n13/13 or bypass?"}
    REWORK["Return to\ndiscovery / research"]
    UNDOC["§1.5.6 Create\nUnderstanding Document"]
    APPROVE{"User approves\nUnderstanding Doc?"}
    REVISE["Revise / Return\nto Discovery"]
    DA_CHECK{"devils-advocate\nskill available?"}
    DA_FALLBACK["Fallback:\nInstall / Skip / Manual\n(see Diagram 5)"]
    DA_SUB["§1.6.2 Dispatch\nDevils Advocate\nSubagent"]
    DISPOSITIONS["Per-finding Dispositions\naddress / note_only / out_of_scope"]
    META["Meta-action A/B/C/D"]
    DRIFT2{"Post-1.6\nScope Drift?"}
    REFLAG2["Re-flag\n& Continue"]
    PHASE2(["Phase 2: /feature-design"])

    START --> PRECHECK
    PRECHECK -- "No" --> STOP1
    PRECHECK -- "Yes" --> DISAMB
    DISAMB --> GEN --> WIZARD --> DRIFT1
    DRIFT1 -- "Yes" --> REFLAG1 --> STANDARDS
    DRIFT1 -- "No" --> STANDARDS
    STANDARDS --> GLOSSARY --> SYNTH --> GATE_C
    GATE_C -- "Pass" --> UNDOC
    GATE_C -- "Fail" --> REWORK --> WIZARD
    UNDOC --> APPROVE
    APPROVE -- "A: Approve" --> DA_CHECK
    APPROVE -- "B/C: Revise" --> REVISE --> UNDOC
    DA_CHECK -- "Yes" --> DA_SUB
    DA_CHECK -- "No" --> DA_FALLBACK --> DA_SUB
    DA_SUB --> DISPOSITIONS --> META --> DRIFT2
    DRIFT2 -- "Yes" --> REFLAG2 --> PHASE2
    DRIFT2 -- "No" --> PHASE2

    classDef terminal fill:#51cf66,stroke:#3a9e50,color:#000
    classDef stop fill:#ff6b6b,stroke:#cc4444,color:#000
    classDef gate fill:#ff6b6b,stroke:#cc4444,color:#000
    classDef subagent fill:#4a9eff,stroke:#2275cc,color:#000

    class START,PHASE2 terminal
    class STOP1 stop
    class PRECHECK,DRIFT1,GATE_C,APPROVE,DA_CHECK,DRIFT2 gate
    class DA_SUB subagent

    subgraph LEGEND ["Legend"]
        direction LR
        LT(["Success terminal"])
        LS(["Stop terminal"])
        LG{"Decision / Gate"}
        LA["Subagent Dispatch"]
        LP["Process Step"]
    end
    class LT terminal
    class LS stop
    class LG gate
    class LA subagent
```

---

## Diagram 2: Adaptive Response Handler (ARH) Pattern

Applies to all discovery questions in §1.5.0 (disambiguation) and §1.5.2 (discovery wizard). Classifies 7 response types and routes to appropriate action. RESEARCH_REQUEST and UNKNOWN trigger subagent dispatch; CLARIFICATION loops the same question; DIRECT_ANSWER, SKIP, and SCOPE_EXPANSION advance the wizard. The fractal-thinking path is conditional on §1.5.0 disambiguation only.

```mermaid
flowchart TD
    QUESTION["Present Question to User"]
    RECV["Receive User Response"]
    CLASSIFY{"Classify\nResponse Type"}

    DA_ACT["DIRECT_ANSWER\nMatches option or clear selection:\nAccept answer, update context"]
    RR_ACT["RESEARCH_REQUEST\nresearch this / look into / find out:\nDispatch Research Subagent"]
    UNK_ACT["UNKNOWN\nI do not know / not sure / unclear:\nDispatch Research Subagent"]
    CLAR_ACT["CLARIFICATION\nwhat do you mean / can you explain:\nRephrase + add context + examples"]
    SKIP_ACT["SKIP\nskip / not relevant / does not apply:\nMark out-of-scope, add to exclusions"]
    ABORT_ACT(["USER_ABORT\nstop / cancel / exit:\nSave state, exit with resume instructions"])
    EXP_ACT["SCOPE_EXPANSION\ninclude X / we should also:\nDefer to end of category\nThen run Scope Drift Check"]

    FRACTAL["§1.5.0 disambiguation only:\nIf HIGH-impact ambiguity,\nInvoke fractal-thinking pulse\nOn failure: LOG warning + continue"]
    REGEN["Regenerate question\nwith new research context"]
    NEXT_Q(["Advance to\nnext question / category"])

    QUESTION --> RECV --> CLASSIFY
    CLASSIFY -- "DIRECT_ANSWER" --> DA_ACT --> NEXT_Q
    CLASSIFY -- "RESEARCH_REQUEST" --> RR_ACT --> FRACTAL --> REGEN --> QUESTION
    CLASSIFY -- "UNKNOWN" --> UNK_ACT --> FRACTAL
    CLASSIFY -- "CLARIFICATION" --> CLAR_ACT --> QUESTION
    CLASSIFY -- "SKIP" --> SKIP_ACT --> NEXT_Q
    CLASSIFY -- "USER_ABORT" --> ABORT_ACT
    CLASSIFY -- "SCOPE_EXPANSION" --> EXP_ACT --> NEXT_Q

    classDef terminal fill:#51cf66,stroke:#3a9e50,color:#000
    classDef stop fill:#ff6b6b,stroke:#cc4444,color:#000
    classDef gate fill:#ff6b6b,stroke:#cc4444,color:#000
    classDef subagent fill:#4a9eff,stroke:#2275cc,color:#000
    classDef note fill:#3a3820,stroke:#888840,color:#d8d8b0

    class NEXT_Q terminal
    class ABORT_ACT stop
    class CLASSIFY gate
    class RR_ACT,UNK_ACT subagent
    class FRACTAL note

    subgraph LEGEND ["Legend"]
        direction LR
        LT(["Advance / Success"])
        LS(["Stop / Abort"])
        LG{"Decision / Gate"}
        LA["Subagent Dispatch"]
        LP["Process Step"]
        LN["Note / Conditional"]
    end
    class LT terminal
    class LS stop
    class LG gate
    class LA subagent
    class LN note
```

---

## Diagram 3: Scope Drift Check

Runs at §1.5.2.5 (post-discovery) and post-§1.6 (post-devil's-advocate). Calls `detect_missing_flags()` — returns any newly-implied `needs_design` / `needs_infrastructure` flags not yet set in Phase 0. Response is always re-flag-and-continue, never stop.

```mermaid
flowchart TD
    ENTRY["Discovery answers accumulated\nor: DA review complete"]
    RUN["Run detect_missing_flags()"]
    EMPTY{"Returns\nempty set?"}
    NO_DRIFT(["No drift — continue unchanged"])
    SIGNALS["Identify each\nnewly-implied signal"]
    INFRA{"Signal implies\nneeds_infrastructure?"}
    SET_INFRA["Set needs_infrastructure = true\nauto-implies needs_design = true"]
    SET_DESIGN["Set needs_design = true"]
    NOTIFY["Notify user:\nScope Drift Detected — re-flagging\nList each signal and implied flag"]
    UPDATE["Update Understanding Document:\nExpanded scope + newly-set flags"]
    CONTINUE(["Continue — new flags route\nDesign and Infrastructure\nphases and gates"])

    ENTRY --> RUN --> EMPTY
    EMPTY -- "Yes" --> NO_DRIFT
    EMPTY -- "No" --> SIGNALS --> INFRA
    INFRA -- "Yes" --> SET_INFRA --> NOTIFY
    INFRA -- "No (design only)" --> SET_DESIGN --> NOTIFY
    NOTIFY --> UPDATE --> CONTINUE

    classDef terminal fill:#51cf66,stroke:#3a9e50,color:#000
    classDef gate fill:#ff6b6b,stroke:#cc4444,color:#000

    class NO_DRIFT,CONTINUE terminal
    class EMPTY,INFRA gate

    subgraph LEGEND ["Legend"]
        direction LR
        LT(["Success / Continue"])
        LG{"Decision / Gate"}
        LP["Process Step"]
    end
    class LT terminal
    class LG gate
```

---

## Diagram 4: Completeness Gate (13 Validation Functions)

§1.5.5 — all 13 functions must pass (score = 100%) to proceed. Below 100% the user chooses: rework, return to research, or explicit bypass accepting the risk. A dashed loop re-enters the gate after rework.

```mermaid
flowchart TD
    ENTRY["§1.5.5 Completeness Gate"]
    FUNCTIONS["Run 13 Validation Functions\n\nFN1   research_quality_validated\n         score=100 OR override=true\nFN2   ambiguities_resolved\n         all ambiguities have results\nFN3   architecture_chosen\n         chosen_approach + rationale non-null\nFN4   scope_defined\n         in_scope AND out_of_scope non-empty\nFN5   mvp_stated\n         definition.length > 10\nFN6   integration_verified\n         all points validated=true\nFN7   failure_modes_identified\n         edge_cases OR failure_scenarios non-empty\nFN8   success_criteria_measurable\n         metrics all have non-null thresholds\nFN9   glossary_complete\n         terms >= unique terms in answers\n         OR user_said_no_glossary_needed\nFN10  assumptions_validated\n         all assumptions have confidence value\nFN11  no_tbd_items\n         no TBD/unknown strings in design_context\nFN12  flags_consistent_with_scope\n         detect_missing_flags() returns empty\nFN13  standards_discovered\n         searched=true AND source recorded\n         OR none_found with globs recorded"]
    CALC["Score = (passed_count / 13) x 100%"]
    THRESHOLD{"Score = 100%?"}
    FAIL_OPTS["Show each unchecked item\nOptions:\nA  Return to discovery wizard\nB  Return to research phase\nC  Bypass gate — accept risk"]
    BYPASS{"User selects\nC (bypass)?"}
    REWORK["Return to\nDiscovery / Research"]
    PROCEED(["§1.5.6 Create\nUnderstanding Document"])

    ENTRY --> FUNCTIONS --> CALC --> THRESHOLD
    THRESHOLD -- "Yes" --> PROCEED
    THRESHOLD -- "No" --> FAIL_OPTS --> BYPASS
    BYPASS -- "Yes (C)" --> PROCEED
    BYPASS -- "No (A or B)" --> REWORK
    REWORK -.->|"re-enter gate" | ENTRY

    classDef terminal fill:#51cf66,stroke:#3a9e50,color:#000
    classDef gate fill:#ff6b6b,stroke:#cc4444,color:#000

    class PROCEED terminal
    class THRESHOLD,BYPASS gate

    subgraph LEGEND ["Legend"]
        direction LR
        LT(["Success / Proceed"])
        LG{"Decision / Gate"}
        LP["Process Step"]
    end
    class LT terminal
    class LG gate
```

---

## Diagram 5: Devil's Advocate Flow (§1.6)

Availability check with 3-way fallback, subagent dispatch, per-finding disposition loop (default = `note_only`), meta-action choice, then post-1.6 scope drift recheck. In autonomous mode, scope-expanding findings must NOT be triaged as `address` without operator confirmation.

```mermaid
flowchart TD
    AVAIL{"Check available\nskills list for\ndevils-advocate"}

    NOT_AVAIL["WARNING:\ndevils-advocate not found"]
    OPT_A["A: Install skill\nuv run install.py\nthen restart session"]
    OPT_B["B: Skip review\nskip_devils_advocate = true\nLog warning"]
    OPT_C["C: Manual review\nPresent doc to user\nCollect critique\nAdd to devils_advocate_critique"]
    EXIT_INST(["Exit: run install.py\nthen restart"])
    SKIP_TO(["Proceed to\nPost-1.6 Scope Drift Check\nno dispositions loop"])

    DISPATCH["§1.6.2 Dispatch\nDevils Advocate Subagent\ninvokes devils-advocate skill"]
    CRITIQUE["Receive Critique\nFindings List"]

    FINDING["Present one finding:\ntitle / category\nfinding text / recommendation"]
    DISP_Q{"Assign disposition\nper finding\n(autonomous: explicit triage required\nno default address for scope-expansions)"}
    ADDR["address:\nReturn to discovery\nfor this specific gap\nnot the default"]
    NOTE["note_only:\nDocument as\nknown limitation\nDEFAULT"]
    OOS["out_of_scope:\nRevise scope\nfor this finding"]
    RECORD["Record disposition\nin dispositions map"]
    MORE{"More\nfindings?"}

    META_Q["Present meta-action:\nA  Return to discovery for address items\nB  Add note_only items to Known Limitations\nC  Revise scope for out_of_scope items\nD  Proceed to Phase 2"]
    DRIFT_CHECK(["Post-1.6\nScope Drift Check\n(Diagram 3)"])

    AVAIL -- "Available" --> DISPATCH
    AVAIL -- "Not available" --> NOT_AVAIL
    NOT_AVAIL --> OPT_A
    NOT_AVAIL --> OPT_B
    NOT_AVAIL --> OPT_C
    OPT_A --> EXIT_INST
    OPT_B --> SKIP_TO
    OPT_C --> DISPATCH

    DISPATCH --> CRITIQUE --> FINDING --> DISP_Q
    DISP_Q --> ADDR --> RECORD
    DISP_Q --> NOTE --> RECORD
    DISP_Q --> OOS --> RECORD
    RECORD --> MORE
    MORE -- "Yes" --> FINDING
    MORE -- "No" --> META_Q --> DRIFT_CHECK

    classDef terminal fill:#51cf66,stroke:#3a9e50,color:#000
    classDef stop fill:#ff6b6b,stroke:#cc4444,color:#000
    classDef gate fill:#ff6b6b,stroke:#cc4444,color:#000
    classDef subagent fill:#4a9eff,stroke:#2275cc,color:#000

    class DRIFT_CHECK,SKIP_TO terminal
    class EXIT_INST stop
    class AVAIL,DISP_Q,MORE gate
    class DISPATCH subagent

    subgraph LEGEND ["Legend"]
        direction LR
        LT(["Success / Continue"])
        LS(["Stop / Exit"])
        LG{"Decision / Gate"}
        LA["Subagent Dispatch"]
        LP["Process Step"]
    end
    class LT terminal
    class LS stop
    class LG gate
    class LA subagent
```

---

## Cross-Reference Table

| Diagram | Title | Overview node(s) |
|---------|-------|-----------------|
| Diagram 1 | Phase 1.5 Overview | — |
| Diagram 2 | ARH Pattern | `DISAMB` (§1.5.0), `WIZARD` (§1.5.2), `EXP_ACT` → Scope Drift |
| Diagram 3 | Scope Drift Check | `DRIFT1` (§1.5.2.5), `DRIFT2` (Post-1.6); also ARH `EXP_ACT` |
| Diagram 4 | Completeness Gate | `GATE_C` (§1.5.5) |
| Diagram 5 | Devil's Advocate Flow | `DA_CHECK`, `DA_FALLBACK`, `DA_SUB`, `DISPOSITIONS`, `META` |

## Command Content

``````````markdown
# Feature Discovery (Phase 1.5)

<ROLE>
Discovery Facilitator for feature implementation. Your reputation depends on understanding documents built on evidence, not assumptions. Design phases constructed on incomplete discovery produce wrong software. Get it right here.
</ROLE>

<CRITICAL>
## Prerequisite Verification

Before ANY Phase 1.5 work begins, verify:

```
# VERIFICATION TEMPLATE — not executable; substitute actual session values

Required: needs_research is true
  Current: [SESSION_PREFERENCES.need_flags.needs_research]
  → If not needs_research: STOP. This phase does not run.
     (needs_research gates BOTH Research (Phase 1) and Discovery (Phase 1.5);
      a single inclusive-OR flag — unfamiliar code OR fuzzy requirements.)

Required: Phase 1 research complete
  Verify: SESSION_CONTEXT.research_findings populated
  Verify: Research Quality Score = 100% (or user-bypassed)

Required: Research was done by subagent (not in main context)
```

**If ANY check fails:** STOP. Return to Phase 1.

**Anti-rationalization:** "Research was thorough enough" and "we already understand the codebase" are known bypass rationalizations (Pattern 4: Similarity Shortcut, Pattern 2: Expertise Override). Run the check. Trust the process.
</CRITICAL>

## Invariant Principles

1. **Research informs questions** — Questions derive from research findings; never ask what research already answered
2. **100% completeness required** — Proceed to design only when all 13 validation functions pass; no exceptions without explicit bypass
3. **Adaptive response handling** — User responses trigger appropriate actions; never force exact answers
4. **Understanding document is the gate** — Devil's advocate reviews the understanding document; approval unlocks design

<CRITICAL>
Use research findings to generate informed questions. Apply ARH pattern to all discovery questions. All discovery must achieve 100% completeness before proceeding to design.
</CRITICAL>

### Adaptive Response Handler (ARH) Pattern

| Response Type    | Detection Pattern                              | Action                                                          |
| ---------------- | ---------------------------------------------- | --------------------------------------------------------------- |
| DIRECT_ANSWER    | Matches option (A, B, C, D) or clear selection | Accept answer, update context, continue                         |
| RESEARCH_REQUEST | "research this", "look into", "find out"       | Dispatch research subagent, regenerate question with findings   |
| UNKNOWN          | "I don't know", "not sure", "unclear"          | Dispatch subagent to research, rephrase with additional context |
| CLARIFICATION    | "what do you mean", "can you explain", "?"     | Rephrase question with more context, examples, re-ask           |
| SKIP             | "skip", "not relevant", "doesn't apply"        | Mark as out-of-scope, add to explicit_exclusions, continue      |
| USER_ABORT       | "stop", "cancel", "exit"                       | Save current state, exit cleanly with resume instructions       |
| SCOPE_EXPANSION | "include X in scope", "let's also", "and while we're at it", "we should also", user adds new workstream | Defer to end of current category, then run Scope Drift Check |

Apply to ALL discovery questions in Phase 1.5.

### Scope Drift Check

<CRITICAL>
This mechanic detects when discovery answers reveal new design or infrastructure
needs that were not flagged in Phase 0. The response is **re-flag-and-continue**:
set the corresponding need-flag and keep going. There is no scope "upgrade" and no
work-item decomposition — the need-flags drive which phases and gates run.
Referenced from: Phase 1.5.2.5, Post-1.6, and inline via ARH during wizard.
</CRITICAL>

**Drift Signals:**

| Signal | Detection | Flag it implies |
|--------|-----------|-----------------|
| Design decision surfaced | Answer reveals a real architectural choice (new structure, a choice between approaches, a contract other code depends on) not in the original framing | `needs_design` |
| New workstream implied | Answer implies a parallel track of work whose shape is non-obvious | `needs_design` |
| New dependency / infra / schema | Answers reveal a new third-party dependency, new infra/service, or a data-schema/migration change | `needs_infrastructure` (which implies `needs_design`) |
| Structural change escalation | Answers reveal new modules/schemas needed | `needs_design` (or `needs_infrastructure` if it is a schema/migration) |

**Evaluation:**

```typescript
// Returns the set of need-flags that discovery implies but that were not
// already set in Phase 0. An empty set means no drift — proceed unchanged.
function detect_missing_flags(): string[] {
  const flags = SESSION_PREFERENCES.need_flags;
  const signals = detect_drift_signals(discovery_answers);
  const missing: string[] = [];

  for (const s of signals) {
    if (s.implies === "needs_infrastructure" && !flags.needs_infrastructure) {
      missing.push("needs_infrastructure"); // implies needs_design below
    }
    if (
      (s.implies === "needs_design" || s.implies === "needs_infrastructure") &&
      !flags.needs_design
    ) {
      missing.push("needs_design");
    }
  }

  return Array.from(new Set(missing));
}
```

**When drift detected (re-flag-and-continue):**

1. Do NOT stop the workflow or "upgrade" scope. Briefly note the new need to the user:
   ```
   Scope Drift Detected — re-flagging

   Discovery surfaced needs not flagged in Phase 0:
   - [signal 1 description] → setting needs_design
   - [signal 2 description] → setting needs_infrastructure (implies needs_design)

   These flags turn on the corresponding phases/gates (Design, and for
   infrastructure the heavier planning emphasis). Continuing discovery.
   ```
2. Set the implied flags in `SESSION_PREFERENCES.need_flags`:
   - `needs_design = true` for a design/structural/workstream signal.
   - `needs_infrastructure = true` for a new dependency/infra/schema signal;
     this AUTO-IMPLIES `needs_design = true` (do not leave infra set without design).
3. Update the understanding document to reflect the expanded scope and the
   newly-set flags.
4. Continue the discovery wizard. The newly-set flags route the later phases
   (Design in Phase 2, heavier planning emphasis in Phase 3) — no work-item
   decomposition, no separate project initialization.

### 1.5.0 Disambiguation Session

**PURPOSE:** Resolve all ambiguities BEFORE generating discovery questions

For each ambiguity from Phase 1.3, present:

```markdown
AMBIGUITY: [description from Phase 1.3]

CONTEXT FROM RESEARCH:
[Relevant research findings with evidence]

IMPACT ON DESIGN:
[Why this matters / what breaks if we guess wrong]

PLEASE CLARIFY:
A) [Specific interpretation 1]
B) [Specific interpretation 2]
C) [Specific interpretation 3]
D) Something else (please describe)

Your choice: ___
```

**PROCESSING (ARH Pattern):**

| Response Type    | Pattern            | Action                                           |
| ---------------- | ------------------ | ------------------------------------------------ |
| DIRECT_ANSWER    | A, B, C, D         | Update disambiguation_results, continue          |
| RESEARCH_REQUEST | "research this"    | Dispatch subagent, regenerate ALL questions      |
| UNKNOWN          | "I don't know"     | Dispatch subagent, rephrase with findings        |
| CLARIFICATION    | "what do you mean" | Rephrase with more context, re-ask               |
| SKIP             | "skip"             | Mark as out-of-scope, add to explicit_exclusions |
| USER_ABORT       | "stop"             | Save state, exit cleanly                         |

**Fractal exploration (conditional):** When the user responds UNKNOWN or RESEARCH_REQUEST on a HIGH-impact ambiguity, invoke fractal-thinking with intensity `pulse` and seed: "What are the full implications of [Interpretation A] vs [Interpretation B]?". Use synthesis for richer disambiguation context showing convergent vs divergent implications.

**Fractal failure fallback:** If fractal-thinking invocation fails, LOG warning and continue disambiguation with available context.

**Example Flow:**

```
Question: "Research found JWT (8 files) and OAuth (5 files). Which should we use?"
User: "What's the difference? I don't know which is better."

ARH Processing:
→ Detect: UNKNOWN type
→ Action: Dispatch research subagent
  "Compare JWT vs OAuth in our codebase. Return pros/cons."
→ Subagent returns comparison
→ Regenerate question with new context:
  "Research shows:
   - JWT: Stateless, used in API endpoints, mobile-friendly
   - OAuth: Third-party integration, complex setup

   For mobile API auth, which fits better?
   A) JWT (stateless, mobile-friendly)
   B) OAuth (third-party logins)
   C) Something else"
→ User: "A - JWT makes sense"
→ Update disambiguation_results
```

### 1.5.1 Generate Deep Discovery Questions

**INPUT:** Research findings + Disambiguation results
**OUTPUT:** 7-category question set

**GENERATION RULES:**

1. Make questions specific using research findings (not generic)
2. Reference concrete codebase patterns discovered in Phase 1
3. Include at least one assumption check per category
4. Generate 3-5 questions per category

**7 CATEGORIES:**

**1. Architecture & Approach**

- How should [feature] integrate with [discovered pattern]?
- Should we follow [pattern A from file X] or [pattern B from file Y]?
- ASSUMPTION CHECK: Does [discovered constraint] apply here?

**2. Scope & Boundaries**

- Research shows [N] similar features. Should this match their scope?
- Explicit exclusions: What should this NOT do?
- MVP definition: What's the minimum for success?
- ASSUMPTION CHECK: Are we building for [discovered use case]?

**3. Integration & Constraints**

- Research found [integration points]. Which are relevant?
- Interface verification: Should we match [discovered interface]?
- ASSUMPTION CHECK: Must this work with [discovered dependency]?

**4. Failure Modes & Edge Cases**

- Research shows [N] edge cases in similar code. Which apply?
- What happens if [dependency] fails?
- How should we handle [boundary condition]?

**5. Success Criteria & Observability**

- Measurable thresholds: What numbers define success?
- How will we know this works in production?
- What metrics should we track?

**6. Vocabulary & Definitions**

- Research uses terms [X, Y, Z]. What do they mean here?
- Are [term A] and [term B] synonyms?
- Build glossary as terms emerge

**7. Assumption Audit**

- I assume [X] based on [research finding]. Correct?
- Explicit validation of ALL research-based assumptions

**Example Questions (Architecture):**

```
Feature: "Add JWT authentication for mobile API"

After research found JWT in 8 files and OAuth in 5 files,
and user clarified JWT is preferred:

1. Research shows JWT implementation in src/api/auth.ts using jose library.
   Should we follow this pattern or use a different JWT library?
   A) Use jose (consistent with existing code)
   B) Use jsonwebtoken (more popular)
   C) Different library (specify)

2. Existing JWT implementations store tokens in Redis (src/cache/tokens.ts).
   Should we use the same storage approach?
   A) Yes - use existing Redis token cache
   B) No - use database storage
   C) No - use stateless approach (no storage)
```

### 1.5.2 Conduct Discovery Wizard (with ARH)

Present questions one category at a time (7 iterations):

```markdown
## Discovery Wizard (Research-Informed)

Based on research findings and disambiguation, I have questions in 7 categories.

### Category 1/7: Architecture & Approach
[Present 3-5 questions]
[Wait for responses, process with ARH]

### Category 2/7: Scope & Boundaries
[Continue...]
```

Progress tracking: "[Category N/7]: X/Y questions answered"

### 1.5.2.5 Post-Discovery Scope Drift Check

<CRITICAL>
After completing the discovery wizard, run the Scope Drift Check with all accumulated answers.
This catches scope expansion that occurred gradually across multiple questions.
</CRITICAL>

Run `detect_missing_flags()`. If it returns a non-empty set, follow the "When drift detected (re-flag-and-continue)" protocol from the Scope Drift Check section above: set the implied need-flags, update the understanding document, and continue.

### 1.5.2.6 Project-Standards Cross-Check (operator)

Surface the discovered governance docs (`design_context.project_standards`) to the
operator. The cross-check has two modes, keyed on `none_found`:

- **Sources found** → **light** reinforcement (AskUserQuestion):
  "I found these standards docs: [list with kind + summary]. Anything I'm missing
  or that doesn't apply?"
- **`none_found: true`** → **REQUIRED** cross-check (not light): the operator MUST
  be asked to name any governance/doctrine doc the heuristic layers missed. Both
  the conventional glob net and the content classifier can miss (doctrine buried in
  an unconventional dir, or declarative prose under-weighted); the operator is the
  true generalizer when both layers come up empty. Record any operator-named doc
  back into `project_standards.sources` / `binding_rules`.

### 1.5.3 Build Glossary

**Process:**

1. Extract domain terms from discovery answers during wizard
2. Build glossary as terms emerge (not in batch at end)
3. After wizard completes, show full glossary
4. Ask user ONCE about persistence

```
I've built a glossary with [N] terms:
[Show glossary preview]

Would you like to:
A) Keep it in this session only
B) Persist to project CLAUDE.md (all team members benefit)
```

**IF B SELECTED — Glossary Persistence Protocol:**

**Location:** Append to end of project CLAUDE.md file

**Format:**

```markdown
---

## Feature Glossary: [Feature Name]

**Generated:** [ISO 8601 timestamp]
**Feature:** [feature_essence from design_context]

### Terms

**[term 1]**
- **Definition:** [definition]
- **Source:** [user | research | codebase]
- **Context:** [feature-specific | project-wide]
- **Aliases:** [alias1, alias2, ...]

**[term 2]**
[...]

---
```

**Write Operation:**

1. Read current CLAUDE.md content
2. Append formatted glossary
3. Write back to CLAUDE.md
4. Verify write succeeded

**ERROR HANDLING:**

- If write fails (permission denied, read-only): Fallback to `~/.local/spellbook/docs/<project-encoded>/glossary-[feature-slug].md`
- Show location: "Glossary saved to: [path]"
- Suggest: "Manually append to CLAUDE.md when ready"

**COLLISION HANDLING:**

- Check for existing "## Feature Glossary: [Feature Name]" section
- If same feature glossary exists: Skip, warn "Glossary for this feature already exists in CLAUDE.md"
- If different feature glossary exists: Append as new section (multiple feature glossaries allowed)

### 1.5.4 Synthesize design_context

Build complete `DesignContext` object from all prior phases.

**Structure reference:** DesignContext fields are defined in the `develop` skill. If the skill is unavailable, request the user provide the expected field structure before proceeding.

**Validation:**

- No null values (except explicitly optional fields)
- No "TBD" or "unknown" strings
- All arrays with content or explicit "N/A"

### 1.5.5 Completeness Checklist (13 Validation Functions)

```typescript
// FUNCTION 1: Research quality validated
function research_quality_validated(): boolean {
  return quality_scores.research_quality === 100 || override_flag === true;
}

// FUNCTION 2: Ambiguities resolved
function ambiguities_resolved(): boolean {
  return categorized_ambiguities.every((amb) =>
    disambiguation_results.hasOwnProperty(amb.description),
  );
}

// FUNCTION 3: Architecture chosen
function architecture_chosen(): boolean {
  return (
    discovery_answers.architecture.chosen_approach !== null &&
    discovery_answers.architecture.rationale !== null
  );
}

// FUNCTION 4: Scope defined
function scope_defined(): boolean {
  return (
    discovery_answers.scope.in_scope.length > 0 &&
    discovery_answers.scope.out_of_scope.length > 0
  );
}

// FUNCTION 5: MVP stated
function mvp_stated(): boolean {
  return mvp_definition !== null && mvp_definition.length > 10;
}

// FUNCTION 6: Integration verified
function integration_verified(): boolean {
  const points = discovery_answers.integration.integration_points;
  return points.length > 0 && points.every((p) => p.validated === true);
}

// FUNCTION 7: Failure modes identified
function failure_modes_identified(): boolean {
  return (
    discovery_answers.failure_modes.edge_cases.length > 0 ||
    discovery_answers.failure_modes.failure_scenarios.length > 0
  );
}

// FUNCTION 8: Success criteria measurable
function success_criteria_measurable(): boolean {
  const metrics = discovery_answers.success_criteria.metrics;
  return metrics.length > 0 && metrics.every((m) => m.threshold !== null);
}

// FUNCTION 9: Glossary complete
function glossary_complete(): boolean {
  const uniqueTermsInAnswers = extractUniqueTerms(discovery_answers);
  return (
    Object.keys(glossary).length >= uniqueTermsInAnswers.length ||
    user_said_no_glossary_needed === true
  );
}

// FUNCTION 10: Assumptions validated
function assumptions_validated(): boolean {
  const validated = discovery_answers.assumptions.validated;
  return validated.length > 0 && validated.every((a) => a.confidence !== null);
}

// FUNCTION 11: No TBD items
function no_tbd_items(): boolean {
  const contextJSON = JSON.stringify(design_context);
  const forbiddenTerms = [/\bTBD\b/i, /\bto be determined\b/i, /\bunknown\b/i];
  const filtered = contextJSON.replace(/"confidence":\s*"[^"]*"/g, "");
  return !forbiddenTerms.some((regex) => regex.test(filtered));
}

// FUNCTION 12: Need-flags consistent with discovered scope
function flags_consistent_with_scope(): boolean {
  // No newly-implied flags = the set is consistent with what discovery found.
  // If discovery surfaced a design/infra need, it must already be reflected in
  // SESSION_PREFERENCES.need_flags (re-flag-and-continue sets it immediately).
  return detect_missing_flags().length === 0;
}

// FUNCTION 13: Project standards discovered
function standards_discovered(): boolean {
  // Passes when the sweep RAN AND (recorded >=1 source OR none_found:true WITH
  // search_globs_used populated). Does NOT require any binding rule to exist —
  // a repo may legitimately have no doctrine — only that the search demonstrably
  // happened and its result is recorded.
  const ps = design_context?.project_standards;
  if (!ps || ps.searched !== true) return false;
  const hasSource = Array.isArray(ps.sources) && ps.sources.length > 0;
  const auditableEmpty =
    ps.none_found === true &&
    Array.isArray(ps.search_globs_used) &&
    ps.search_globs_used.length > 0;
  return hasSource || auditableEmpty;
}
```

**SCORE CALCULATION:**

```typescript
const checked_count = Object.values(validation_results).filter(
  (v) => v === true,
).length;
const completeness_score = (checked_count / 13) * 100;
```

**DISPLAY FORMAT:**

```
Completeness Checklist:

[✓/✗] All research questions answered with HIGH confidence
[✓/✗] All ambiguities disambiguated
[✓/✗] Architecture approach explicitly chosen and validated
[✓/✗] Scope boundaries defined with explicit exclusions
[✓/✗] MVP definition stated
[✓/✗] Integration points verified against codebase
[✓/✗] Failure modes and edge cases identified
[✓/✗] Success criteria defined with measurable thresholds
[✓/✗] Glossary complete for all domain terms
[✓/✗] All assumptions validated with user
[✓/✗] No "we'll figure it out later" items remain
[✓/✗] Need-flags consistent with discovered scope (any new design/infra need re-flagged)
[✓/✗] Project standards discovered (sweep ran; ≥1 source recorded OR none_found with globs recorded)

Completeness Score: [X]% ([N]/13 items complete)
```

**GATE BEHAVIOR:**

IF completeness_score < 100:

```
Completeness Score: [X]% - Below threshold

OPTIONS:
A) Return to discovery wizard for missing items
B) Return to research for new questions
C) Proceed anyway (bypass gate, accept risk)

Your choice: ___
```

IF completeness_score == 100: Proceed to Phase 1.5.6

### 1.5.6 Create Understanding Document

**FILE PATH:** `~/.local/spellbook/docs/<project-encoded>/understanding/understanding-[feature-slug]-[timestamp].md`

**Generate Understanding Document:**

```markdown
# Understanding Document: [Feature Name]

## Feature Essence
[1-2 sentence summary]

## Research Summary
- Patterns discovered: [...]
- Integration points: [...]
- Constraints identified: [...]

## Architectural Approach
[Chosen approach with rationale]
Alternatives considered: [...]

## Scope Definition

IN SCOPE:
- [...]

EXPLICITLY OUT OF SCOPE:
- [...]

MVP DEFINITION:
[Minimum viable implementation]

## Integration Plan
- Integrates with: [...]
- Follows patterns: [...]
- Interfaces: [...]

## Failure Modes & Edge Cases
- [...]

## Success Criteria
- Metric 1: [threshold]
- Metric 2: [threshold]

## Glossary
[Full glossary from Phase 1.5.3]

## Validated Assumptions
- [assumption]: [validation]

## Project Standards (Discovered Governance Docs)
- Searched: [yes/no]
- Globs used: [...]
- Candidates considered: [N]
- Sources found: [path — kind — one-line summary, per doc]
- Binding rules: [verbatim rule — severity (MUST/SHOULD) — applies_to (code/tests/both) — source_path, per rule]
- None found: [true/false] (if true, REQUIRED operator cross-check was run)
- Truncated candidates: [paths classified on headings + first-N-lines only]

## Completeness Score
Research Quality: [X]%
Discovery Completeness: [X]%
Overall Confidence: [X]%
```

Present to user:

```
I've synthesized research and discovery into the Understanding Document above.

Please review and:
A) Approve (proceed to Devil's Advocate review)
B) Request changes (specify what to revise)
C) Return to discovery (need more information)

Your choice: ___
```

**BLOCK design phase until user approves (A).**

### 1.6 Devil's Advocate Review

<CRITICAL>
The devils-advocate skill is a REQUIRED dependency. Check availability before attempting invocation.
</CRITICAL>

#### 1.6.1 Check Devil's Advocate Availability

**Verify skill exists in available skills list.**

**IF SKILL NOT AVAILABLE:**

```
WARNING: devils-advocate skill not found in available skills.

The Devil's Advocate review is REQUIRED for quality assurance.

OPTIONS:
A) Install skill first (recommended)
   Run 'uv run install.py' from spellbook directory, then restart session

B) Skip review for this session (not recommended)
   Proceed without adversarial review - higher risk of missed issues

C) Manual review
   I'll present the Understanding Document for YOUR critique instead

Your choice: ___
```

**Handle user choice:**

- **A (Install):** Exit with instructions: "Run 'uv run install.py' from spellbook directory, then restart this session"
- **B (Skip):** Set `skip_devils_advocate = true`, log warning, proceed to Phase 2
- **C (Manual):** Present Understanding Document, collect user's critique, add to `devils_advocate_critique` field, proceed

#### 1.6.2 Invoke Devil's Advocate Skill

<RULE>Subagent MUST invoke devils-advocate skill using the Skill tool.</RULE>

```
Task:
  description: "Devil's Advocate Review"
  prompt: |
    First, invoke the devils-advocate skill using the Skill tool.
    Then follow its complete workflow.

    ## Context for the Skill

    Understanding Document:
    [Insert full Understanding Document from Phase 1.5.6]
```

Present critique to user, then run **per-finding disposition** before
any meta-action choice. For each finding in the critique:

1. Present the finding (title, category, finding text, recommendation)
2. Ask via AskUserQuestion: disposition = `address`, `note_only`, or
   `out_of_scope`?
3. Record disposition in `SESSION_CONTEXT.devils_advocate_dispositions`

**Default disposition is `note_only`.** `address` is never the default.

In autonomous mode, the operator is not present, so the orchestrator
MUST make an explicit triage decision per finding using the same three
values. Triaging silently as `address` is forbidden. A finding that
expands scope (introduces capabilities, infrastructure, or external
integrations not in the operator's initial request) MUST be triaged
`note_only` or `out_of_scope`, never `address`, without operator
confirmation. See `~/.claude/CLAUDE.md` "Autonomous Mode and Scope
Discipline".

After dispositions are assigned, present the meta-action choice:

```markdown
## Devil's Advocate Critique

[Full critique output from skill, with dispositions filled in]

---

Please review and choose next steps:
A) Address only `address`-disposition findings (return to discovery
   for those specific gaps)
B) Document `note_only` findings as known limitations (add to
   Understanding Document)
C) Revise scope per `out_of_scope` findings
D) Proceed to design (only `address` findings will shape Phase 2)

Your choice: ___
```

### Post-1.6 Scope Drift Recheck

After devil's advocate review, re-run the Scope Drift Check. The devil's advocate may have surfaced scope expansions not visible during initial discovery.

Run `detect_missing_flags()`. If it returns a non-empty set, follow the "When drift detected (re-flag-and-continue)" protocol: set the implied need-flags, update the understanding document, and continue.

<FORBIDDEN>
- Asking questions that Phase 1 research already answered
- Proceeding to design with completeness_score < 100% without explicit user bypass
- Blocking on glossary persistence when user chose session-only (A)
- Running devil's advocate review in main context instead of dispatching subagent
- Treating DesignContext structure as defined here — always reference develop skill for field definitions
- Continuing Phase 1.5 if prerequisite check fails
</FORBIDDEN>

---

## Phase 1.5 Complete

```bash
# Verify understanding document exists
ls ~/.local/spellbook/docs/<project-encoded>/understanding/
```

Before proceeding to Phase 2, verify:

- [ ] All ambiguities resolved (disambiguation session complete)
- [ ] 7-category discovery questions generated and answered
- [ ] Glossary built
- [ ] design_context synthesized (no null values, no TBD)
- [ ] Completeness Score = 100% (13/13 validation functions)
- [ ] Understanding Document created and saved
- [ ] Devil's advocate subagent DISPATCHED (not done in main context)
- [ ] User approved Understanding Document

If ANY unchecked: Complete Phase 1.5. Do NOT proceed.

**Next:** Run `/feature-design` to begin Phase 2.

<FINAL_EMPHASIS>
Discovery quality determines design quality. An understanding document built on assumptions is not an understanding document — it is a blueprint for the wrong system. Every unanswered question here becomes a rework cycle later. Do not proceed to design until discovery is complete.
</FINAL_EMPHASIS>
``````````

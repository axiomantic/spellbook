# /feature-research

## Workflow Diagram

```mermaid
flowchart TD
    START(["/feature-research invoked"]):::terminal

    PRE["Prerequisite Verification\n(bash check block)"]:::process

    C1{"needs_research\n== true?"}:::decision
    C2{"Phase 0\ncomplete?"}:::decision
    C3{"impl_plan\nescape hatch\nactive?"}:::decision

    STOP_NEEDS(["STOP: needs_research is false\nReturn to Phase 0"]):::fail
    STOP_P0(["STOP: Phase 0 incomplete\nReturn to Phase 0"]):::fail
    STOP_ESCAPE(["STOP: Escape hatch active\nSkip to Phase 3+"]):::fail

    S11["1.1 Research Strategy Planning\nAnalyze feature request\nGenerate codebase questions\nIdentify knowledge gaps"]:::process

    DISPATCH["1.2 Subagent Dispatch\nResearch Agent – Codebase Patterns"]:::subagent

    SF{"Subagent\nsucceeded?"}:::decision
    RETRY["Retry once\n(same instructions)"]:::process
    SF2{"Second attempt\nsucceeded?"}:::decision
    UNKNOWN["Mark all findings UNKNOWN\nNote failure reason\nReturn to user (do not block)"]:::process

    S13["1.3 Ambiguity Extraction\nExtract MEDIUM/LOW/UNKNOWN items\nExtract flagged ambiguities\nCategorize: Technical/Scope/Integration/Terminology\nPrioritize by impact"]:::process

    S14["1.4 Research Quality Score\nCoverage Score\nAmbiguity Resolution Score\nEvidence Quality Score\nUnknown Detection Score\nOverall = min of all four"]:::process

    QG{"Score\n= 100%?"}:::gate

    OPT{"User\nchoice"}:::decision
    OPT_A["A: Continue anyway\n(bypass, accept risk)"]:::process
    OPT_B["B: Iterate: add questions\nre-dispatch subagent"]:::process
    OPT_C["C: Reduce scope\nremove low-confidence items"]:::process

    CHECKLIST["Phase 1 Completion Checklist\n✓ Subagent dispatched\n✓ Score 100% (or bypassed)\n✓ Ambiguities categorized\n✓ Findings stored in\n  SESSION_CONTEXT.research_findings"]:::process

    DONE(["Phase 1 Complete\nProceed to /feature-discover"]):::terminal

    START --> PRE
    PRE --> C1
    C1 -->|"false"| STOP_NEEDS
    C1 -->|"true"| C2
    C2 -->|"incomplete"| STOP_P0
    C2 -->|"complete"| C3
    C3 -->|"active"| STOP_ESCAPE
    C3 -->|"not active"| S11

    S11 --> DISPATCH
    DISPATCH --> SF
    SF -->|"yes"| S13
    SF -->|"no"| RETRY
    RETRY --> SF2
    SF2 -->|"yes"| S13
    SF2 -->|"no"| UNKNOWN
    UNKNOWN --> S13

    S13 --> S14
    S14 --> QG
    QG -->|"100%"| CHECKLIST
    QG -->|"< 100%"| OPT
    OPT --> OPT_A
    OPT --> OPT_B
    OPT --> OPT_C
    OPT_A --> CHECKLIST
    OPT_B --> S11
    OPT_C --> S14

    CHECKLIST --> DONE

    subgraph LEGEND["Legend"]
        L1["Process"]:::process
        L2["Subagent Dispatch"]:::subagent
        L3["Quality Gate"]:::gate
        L4(["Terminal"]):::terminal
        L5{"Decision"}:::decision
        L6(["Failure / Stop"]):::fail
    end

    classDef process fill:#2d2d2d,stroke:#888,color:#e8e8ea
    classDef subagent fill:#1a3a5c,stroke:#4a9eff,color:#4a9eff
    classDef gate fill:#3a1a1a,stroke:#ff6b6b,color:#ff6b6b
    classDef terminal fill:#1a3a1a,stroke:#51cf66,color:#51cf66
    classDef decision fill:#2d2d2d,stroke:#aaa,color:#e8e8ea
    classDef fail fill:#3a1a1a,stroke:#ff6b6b,color:#ff6b6b
```

**Overview:** `/feature-research` is Phase 1 of the develop skill. It runs only when `needs_research` is true, dispatches a codebase-exploration subagent, extracts and categorizes ambiguities from the findings, computes a four-component quality score, and requires 100% (or explicit user bypass) before handing off to `/feature-discover`.

**Quality Gate components** (all must be 100%; overall = minimum):
| Component | Formula |
|---|---|
| Coverage | HIGH-confidence answers ÷ total questions |
| Ambiguity Resolution | Categorized ambiguities ÷ total ambiguities |
| Evidence Quality | Findings with file refs ÷ answerable findings |
| Unknown Detection | Flagged unknowns ÷ LOW/UNKNOWN findings |

## Command Content

``````````markdown
# Feature Research (Phase 1)

<ROLE>
Research Strategist. Your reputation depends on surfacing unknowns BEFORE design begins. A research phase that misses a critical ambiguity poisons every downstream decision. This is very important to my career.
</ROLE>

<CRITICAL>
## Prerequisite Verification

Before ANY Phase 1 work begins, run this verification:

```bash
# ══════════════════════════════════════════════════════════════
# PREREQUISITE CHECK: feature-research (Phase 1)
# ══════════════════════════════════════════════════════════════

echo "=== Phase 1 Prerequisites ==="

# CHECK 1: This phase runs only when the needs_research flag is set.
# needs_research = "the work touches code/systems we don't yet understand,
# OR the requirements themselves are still fuzzy." It is the single operator
# flag (chosen in Phase 0) that switches on BOTH Research (Phase 1) and
# Discovery (Phase 1.5). See SESSION_PREFERENCES.need_flags.
echo "Required: need_flags.needs_research == true"
echo "Current needs_research: [SESSION_PREFERENCES.need_flags.needs_research]"
# If needs_research is false, this phase does not run — develop skips
# Research and Discovery and proceeds with the phases its other flags select.

# CHECK 2: Phase 0 must be complete
echo "Required: Phase 0 checklist 100% complete"
echo "Verify: motivation, feature_essence, preferences all populated"

# CHECK 3: No escape hatch skipping to Phase 3+
echo "Required: No impl plan escape hatch active"
echo "Verify: SESSION_PREFERENCES.escape_hatch.type != 'impl_plan'"
```

**If ANY check fails:** STOP. Do not proceed. Return to the appropriate phase.

**Anti-rationalization:** Tempted to skip because "you already know `needs_research` is set" or "Phase 0 was obviously complete"? That is Pattern 2 (Expertise Override). Run the check. It takes 5 seconds.
</CRITICAL>

## Invariant Principles

1. **Research before design** — Understand the codebase and surface unknowns before any design work begins
2. **100% quality score required** — All research questions need HIGH confidence answers; bypass requires explicit user consent
3. **Evidence with confidence levels** — Every finding includes evidence and confidence rating; UNKNOWN is a valid answer
4. **Ambiguity extraction** — Low-confidence and unknown items become explicit ambiguities for disambiguation

<CRITICAL>
Systematically explore codebase and surface unknowns BEFORE design work. All research findings must achieve 100% quality score to proceed.
</CRITICAL>

### 1.1 Research Strategy Planning

**INPUT:** User feature request + motivation
**OUTPUT:** Research strategy with specific questions

1. Analyze feature request for technical domains
2. Generate codebase questions:
   - Which files/modules handle similar features?
   - What patterns exist for this type of work?
   - What integration points are relevant?
   - What edge cases have been handled before?
3. Identify knowledge gaps explicitly

**Example Questions:**

```
Feature: "Add JWT authentication for mobile API"

Generated Questions:
1. Where is authentication currently handled in the codebase?
2. Are there existing JWT implementations we can reference?
3. What mobile API endpoints exist that will need auth?
4. How are other features securing API access?
5. What session management patterns exist?
```

### 1.2 Execute Research (Subagent)

**SUBAGENT DISPATCH:** YES
**REASON:** Exploration with uncertain scope. Subagent reads N files, returns synthesis.

```
Task:
  description: "Research Agent - Codebase Patterns"
  prompt: |
    You are a research agent. Answer these specific questions about the codebase.
    For each question:

    1. Search systematically using search tools (grep, glob, search_file_content)
    2. Read relevant files
    3. Extract patterns, conventions, precedents
    4. FLAG any ambiguities or conflicting patterns
    5. EXPLICITLY state 'UNKNOWN' if evidence is insufficient

    CRITICAL: Mark confidence level for each answer:
    - HIGH: Direct evidence found (specific file references)
    - MEDIUM: Inferred from related code
    - LOW: Educated guess based on conventions
    - UNKNOWN: No evidence found

    QUESTIONS TO ANSWER:
    [Insert questions from 1.1]

    RETURN FORMAT (strict JSON):
    {
      "findings": [
        {
          "question": "...",
          "answer": "...",
          "confidence": "HIGH|MEDIUM|LOW|UNKNOWN",
          "evidence": ["file:line", ...],
          "ambiguities": ["..."]
        }
      ],
      "patterns_discovered": [
        {
          "name": "...",
          "files": ["..."],
          "description": "..."
        }
      ],
      "unknowns": ["..."]
    }
```

**ERROR HANDLING:**

- Subagent fails: retry once with same instructions
- Second failure: return all findings marked UNKNOWN; note "Research failed after 2 attempts: [error]"; do NOT block — user chooses to proceed or retry
- **TIMEOUT:** 120 seconds per subagent

### 1.3 Ambiguity Extraction

**INPUT:** Research findings from subagent
**OUTPUT:** Categorized ambiguities

1. Extract all MEDIUM/LOW/UNKNOWN confidence items
2. Extract all flagged ambiguities
3. Categorize by type:
   - **Technical:** How it works (e.g., "Two auth patterns found — which to use?")
   - **Scope:** What to include (e.g., "Unclear if feature includes password reset")
   - **Integration:** How it connects (e.g., "Multiple integration points — which is primary?")
   - **Terminology:** What terms mean (e.g., "'Session' used inconsistently")
4. Prioritize by impact on design: HIGH/MEDIUM/LOW

**Example Output:**

```
TECHNICAL (HIGH impact):
- Ambiguity: Two authentication patterns found (JWT in 8 files, OAuth in 5 files)
  Source: Research finding #3 (MEDIUM confidence)
  Impact: Determines entire auth architecture

SCOPE (MEDIUM impact):
- Ambiguity: Similar features handle password reset; unclear if in scope
  Source: Research finding #7 (LOW confidence)
  Impact: Affects feature completeness
```

### 1.4 Research Quality Score

**SCORING FORMULAS:**

```typescript
// 1. COVERAGE SCORE
function coverageScore(findings: Finding[], questions: string[]): number {
  const highCount = findings.filter(f => f.confidence === "HIGH").length;
  if (questions.length === 0) return 100;
  return (highCount / questions.length) * 100;
}

// 2. AMBIGUITY RESOLUTION SCORE
function ambiguityResolutionScore(ambiguities: Ambiguity[]): number {
  if (ambiguities.length === 0) return 100;
  const categorized = ambiguities.filter(a => a.category && a.impact);
  return (categorized.length / ambiguities.length) * 100;
}

// 3. EVIDENCE QUALITY SCORE
function evidenceQualityScore(findings: Finding[]): number {
  const answerable = findings.filter(f => f.confidence !== "UNKNOWN");
  if (answerable.length === 0) return 0;
  const withEvidence = answerable.filter(f => f.evidence.length > 0);
  return (withEvidence.length / answerable.length) * 100;
}

// 4. UNKNOWN DETECTION SCORE
function unknownDetectionScore(findings: Finding[], flaggedUnknowns: string[]): number {
  const lowOrUnknown = findings.filter(
    f => f.confidence === "UNKNOWN" || f.confidence === "LOW",
  );
  if (lowOrUnknown.length === 0) return 100;
  return (flaggedUnknowns.length / lowOrUnknown.length) * 100;
}

// OVERALL SCORE: Weakest link determines quality — ALL must be 100%
function overallScore(...scores: number[]): number {
  return Math.min(...scores);
}
```

**DISPLAY FORMAT:**

```
Research Quality Score: [X]%

Breakdown:
✓/✗ Coverage: [X]% ([N]/[M] questions with HIGH confidence)
✓/✗ Ambiguity Resolution: [X]% ([N]/[M] ambiguities categorized)
✓/✗ Evidence Quality: [X]% ([N]/[M] findings have file references)
✓/✗ Unknown Detection: [X]% ([N]/[M] unknowns explicitly flagged)

Overall: [X]% (minimum of all criteria)
```

**GATE BEHAVIOR:**

IF SCORE < 100%:

```
Research Quality Score: [X]% - Below threshold

OPTIONS:
A) Continue anyway (bypass gate, accept risk)
B) Iterate: Add more research questions and re-dispatch
C) Skip ambiguous areas (reduce scope, remove low-confidence items)

Your choice: ___
```

IF SCORE = 100%:

- Display: "✓ Research Quality Score: 100% - All criteria met"
- Proceed to Phase 1.5

<FORBIDDEN>
- Doing research work in main context instead of dispatching a subagent
- Proceeding when any prerequisite check fails
- Running this phase when `needs_research` is false (the flag, not a phase, gates this work)
- Proceeding past the quality gate without a 100% score or explicit user bypass
- Blocking progress after two subagent failures (return UNKNOWN findings; do not halt)
</FORBIDDEN>

---

## Phase 1 Complete

Before proceeding to Phase 1.5, verify:

- [ ] Research subagent was DISPATCHED (not done in main context)
- [ ] Research Quality Score = 100% (or user bypassed with consent)
- [ ] All ambiguities extracted and categorized
- [ ] Findings stored in SESSION_CONTEXT.research_findings

If ANY unchecked: Complete Phase 1. Do NOT proceed.

**Next:** Run `/feature-discover` to begin Phase 1.5.

<FINAL_EMPHASIS>
Research is the foundation every downstream decision rests on. A gap here propagates through design, implementation, and review. Surface unknowns now — not during code review. Your reputation depends on delivering a research phase where nothing critical was missed.
</FINAL_EMPHASIS>
``````````

# /feature-research

## Workflow Diagram

I will generate a Mermaid diagram to visualize the `feature-research` command by following these steps:

1. **Analyze `commands/feature-research.md`**: I'll read the markdown file to understand the process, its steps, decision points, and any referenced commands or skills. This will help determine the overall structure and complexity, and confirm that Mermaid is the appropriate diagramming tool.
2. **Extract Content**: I will systematically go through the markdown file, identifying all key actions, decisions, inputs, outputs, and any conditional logic. I will look for calls to other agents, skills, or commands, and note success/failure conditions.
3. **Generate Diagram**: Based on the extracted information, I will construct a Mermaid diagram. I'll use standard flow chart elements:
    * Rectangles for processes/steps.
    * Diamonds for decision points.
    * Stadium shapes for start/end points.
    * Blue for subagent dispatches (`#4a9eff`).
    * Red for quality gates/critical checks (`#ff6b6b`).
    * Green for successful terminal conditions (`#51cf66`).
    I will also include a legend within the diagram.
4. **Verify Diagram**: I will check the Mermaid code for syntax errors and ensure that the diagram accurately reflects the `feature-research` command as described in the markdown file, covering all branches and outcomes.
```mermaid
graph TD
    %% Node Definitions
    start((Start))
    stop((Stop))
    prereq_check{Prerequisite Verification}
    prereq_fail_stop[Stop: Prerequisite Failed]:::red_stop
    strategy_plan[1.1 Research Strategy Planning]
    dispatch_subagent[1.2 Execute Research (Subagent)]:::blue_subagent
    subagent_retry_check{Subagent First Failure?}
    subagent_fail_2nd_stop[Subagent Failed Twice: Return UNKNOWN Findings]
    extract_ambiguities[1.3 Ambiguity Extraction]
    calc_quality_score[1.4 Research Quality Score Calculation]
    quality_gate{Research Quality Score >= 100%?}
    user_choice[User Chooses Action]
    phase1_complete_check{Phase 1 Complete Verification}
    phase1_fail_stop[Stop: Phase 1 Incomplete]:::red_stop
    proceed_to_1_5[/Proceed to Phase 1.5 (feature-discover)/]:::green_success

    %% Graph Connections
    start --> prereq_check
    prereq_check -- Any Check Fails --> prereq_fail_stop
    prereq_check -- All Checks Pass --> strategy_plan
    strategy_plan --> dispatch_subagent
    dispatch_subagent -- 1st Failure --> subagent_retry_check
    subagent_retry_check -- Yes --> dispatch_subagent
    subagent_retry_check -- No (2nd Failure) --> subagent_fail_2nd_stop
    subagent_fail_2nd_stop --> extract_ambiguities
    dispatch_subagent -- Success --> extract_ambiguities
    extract_ambiguities --> calc_quality_score
    calc_quality_score --> quality_gate
    quality_gate -- No (<100%) --> user_choice
    user_choice -- Continue Anyway / Iterate / Skip --> phase1_complete_check
    quality_gate -- Yes (100%) --> phase1_complete_check
    phase1_complete_check -- Any Unchecked --> phase1_fail_stop
    phase1_complete_check -- All Checked --> proceed_to_1_5

    proceed_to_1_5 --> stop
    prereq_fail_stop --> stop
    phase1_fail_stop --> stop


    %% Styling
    classDef red_stop fill:#ff6b6b,stroke:#333,stroke-width:2px,color:#fff;
    classDef green_success fill:#51cf66,stroke:#333,stroke-width:2px,color:#fff;
    classDef blue_subagent fill:#4a9eff,stroke:#333,stroke-width:2px,color:#fff;

    %% Legend
    subgraph Legend
        direction LR
        A[Process] --> B{Decision}
        C[Stop/Failure]:::red_stop
        D[Subagent Dispatch]:::blue_subagent
        E[Success]:::green_success
    end
```

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

# CHECK 1: Complexity tier must be STANDARD or COMPLEX
echo "Required: complexity_tier in (standard, complex)"
echo "Current tier: [SESSION_PREFERENCES.complexity_tier]"
# TRIVIAL exits the skill; SIMPLE uses lightweight inline research — neither runs this phase.

# CHECK 2: Phase 0 must be complete
echo "Required: Phase 0 checklist 100% complete"
echo "Verify: motivation, feature_essence, preferences all populated"

# CHECK 3: No escape hatch skipping to Phase 3+
echo "Required: No impl plan escape hatch active"
echo "Verify: SESSION_PREFERENCES.escape_hatch.type != 'impl_plan'"
```

**If ANY check fails:** STOP. Do not proceed. Return to the appropriate phase.

**Anti-rationalization:** Tempted to skip because "you already know the tier" or "Phase 0 was obviously complete"? That is Pattern 2 (Expertise Override). Run the check. It takes 5 seconds.
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
- Running this phase when complexity_tier is TRIVIAL or SIMPLE
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

# /feature-research

## Command Content

``````````markdown
# Feature Research (Phase 1)

## Invariant Principles

1. **Research before design** - Understand the codebase and surface unknowns before any design work begins
2. **100% quality score required** - All research questions need HIGH confidence answers; bypass requires explicit user consent
3. **Evidence with confidence levels** - Every finding includes evidence and confidence rating; UNKNOWN is a valid answer
4. **Ambiguity extraction** - Low-confidence and unknown items become explicit ambiguities for disambiguation

<CRITICAL>
Systematically explore codebase and surface unknowns BEFORE design work.
All research findings must achieve 100% quality score to proceed.
</CRITICAL>

### 1.1 Research Strategy Planning

**INPUT:** User feature request + motivation
**OUTPUT:** Research strategy with specific questions

**Process:**

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
Task (or subagent simulation):
  description: "Research Agent - Codebase Patterns"
  prompt: |
    You are a research agent. Your job is to answer these specific questions about
    the codebase. For each question:

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
    [Insert questions from Phase 1.1]

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

- If subagent fails: Retry once with same instructions
- If second failure: Return findings with all items marked UNKNOWN
- Note: "Research failed after 2 attempts: [error]"
- Do NOT block progress - user chooses to proceed or retry

**TIMEOUT:** 120 seconds per subagent

### 1.3 Ambiguity Extraction

**INPUT:** Research findings from subagent
**OUTPUT:** Categorized ambiguities

**Process:**

1. Extract all MEDIUM/LOW/UNKNOWN confidence items
2. Extract all flagged ambiguities
3. Categorize by type:
   - **Technical:** How it works (e.g., "Two auth patterns found - which to use?")
   - **Scope:** What to include (e.g., "Unclear if feature includes password reset")
   - **Integration:** How it connects (e.g., "Multiple integration points - which is primary?")
   - **Terminology:** What terms mean (e.g., "'Session' used inconsistently")
4. Prioritize by impact on design (HIGH/MEDIUM/LOW)

**Example Output:**

```
Categorized Ambiguities:

TECHNICAL (HIGH impact):
- Ambiguity: Two authentication patterns found (JWT in 8 files, OAuth in 5 files)
  Source: Research finding #3 (MEDIUM confidence)
  Impact: Determines entire auth architecture

SCOPE (MEDIUM impact):
- Ambiguity: Similar features handle password reset, unclear if in scope
  Source: Research finding #7 (LOW confidence)
  Impact: Affects feature completeness
```

### 1.4 Research Quality Score

**SCORING FORMULAS:**

```typescript
// 1. COVERAGE SCORE
function coverageScore(findings: Finding[], questions: string[]): number {
  const highCount = findings.filter((f) => f.confidence === "HIGH").length;
  if (questions.length === 0) return 100;
  return (highCount / questions.length) * 100;
}

// 2. AMBIGUITY RESOLUTION SCORE
function ambiguityResolutionScore(ambiguities: Ambiguity[]): number {
  if (ambiguities.length === 0) return 100;
  const categorized = ambiguities.filter((a) => a.category && a.impact);
  return (categorized.length / ambiguities.length) * 100;
}

// 3. EVIDENCE QUALITY SCORE
function evidenceQualityScore(findings: Finding[]): number {
  const answerable = findings.filter((f) => f.confidence !== "UNKNOWN");
  if (answerable.length === 0) return 0;
  const withEvidence = answerable.filter((f) => f.evidence.length > 0);
  return (withEvidence.length / answerable.length) * 100;
}

// 4. UNKNOWN DETECTION SCORE
function unknownDetectionScore(
  findings: Finding[],
  flaggedUnknowns: string[],
): number {
  const lowOrUnknown = findings.filter(
    (f) => f.confidence === "UNKNOWN" || f.confidence === "LOW",
  );
  if (lowOrUnknown.length === 0) return 100;
  return (flaggedUnknowns.length / lowOrUnknown.length) * 100;
}

// OVERALL SCORE: Weakest link determines quality
function overallScore(...scores: number[]): number {
  return Math.min(...scores); // All must be 100%
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

---

## Phase 1 Complete

Before proceeding to Phase 1.5, verify:

- [ ] Research subagent was DISPATCHED (not done in main context)
- [ ] Research Quality Score = 100% (or user bypassed with consent)
- [ ] All ambiguities extracted and categorized
- [ ] Findings stored in SESSION_CONTEXT.research_findings

If ANY unchecked: Complete Phase 1. Do NOT proceed.

**Next:** Run `/feature-discover` to begin Phase 1.5.
``````````

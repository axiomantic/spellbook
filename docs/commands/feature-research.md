# /feature-research
## Command Content

````markdown
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
2. **The gate is an exit status, not a score** — `check_research_quality.py` blocks on the artifact; confidence ratings are self-assessed and labelled as such; bypass requires explicit user consent
3. **Evidence with confidence levels** — Every finding includes evidence and confidence rating; UNKNOWN is a valid answer
4. **Ambiguity extraction** — Low-confidence and unknown items become explicit ambiguities for disambiguation

<CRITICAL>
Systematically explore codebase and surface unknowns BEFORE design work. Research findings must pass the mechanical Phase 1 gate (§1.4) to proceed.
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

    A MISSING TOOL IS NOT A CONSTRAINT TO DESIGN AROUND. If a tool you need is
    absent, install it, or propose the installation to the operator — see
    `rules/60-autonomy.md`. Either way, record it in `tooling` below. Research
    built on an unrecorded missing tool rests on a premise nobody can re-check.

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
      "unknowns": ["..."],
      "tooling": {
        "checked": true,
        "none_missing": false,
        "missing": [
          {
            "tool": "hg",
            "resolution": "installed | installation_proposed | operator_declined | alternative_found",
            "detail": "what was run, proposed, or declined",
            "alternative": "named replacement — REQUIRED for alternative_found"
          }
        ]
      }
    }

    When no tool was missing, that is `"none_missing": true` with `"missing": []`.
```

**ERROR HANDLING:**

- Subagent fails: retry once with same instructions
- Second failure: return all findings marked UNKNOWN; note "Research failed after 2 attempts: [error]"; do NOT block — user chooses to proceed or retry
- **TIMEOUT:** 120 seconds per subagent

**ARTIFACT (write the returned JSON to disk).** The §1.4 gate reads a file, so
the orchestrator persists the subagent's return object verbatim before moving on:

**FILE PATH:** `~/.local/spellbook/docs/<project-encoded>/research/research-[feature-slug]-[timestamp].json`

Keep `SESSION_CONTEXT.research_findings` as the in-memory carrier; the file is
what the gate can read and what a later reviewer can re-check.

### 1.2.5 Project Development-Guidance Discovery (Subagent)

**SUBAGENT DISPATCH:** YES
**REASON:** Generic governance-doc discovery. The sweep nets candidate docs by
convention, then classifies them by content. Returns a structured object, not raw
doc dumps.

This is the **primary sweep** on the research path. It runs the generic two-layer
discovery mechanism and produces `project_standards`. The feature-design §2.0.1
fallback observes `project_standards` already populated on this path and does NOT
re-sweep.

```
Task:
  description: "Discover project development-guidance / governance docs"
  prompt: |
    You are a research agent discovering a repository's binding development and
    testing standards. Discovery is GENERIC — work by convention + content
    classification, NEVER by hardcoded filenames.

    LAYER 1 — Conventional-pattern glob net (root + docs/ tree, skip vendored deps
    node_modules/.venv/venv/vendor/.git/build/dist). Net for governance-doc
    conventions, e.g.:
      - Agent/assistant config: AGENTS.md, CLAUDE.md, GEMINI.md, .cursorrules,
        .github/copilot-instructions.md
      - Contribution/standards: CONTRIBUTING*, DEVELOPERS*, CODING_STANDARDS*,
        CODESTYLE*, STYLE*, ARCHITECTURE*
      - Docs trees: docs/** (esp. AI dirs like docs/ai/**),
        docs/**/*{testing,contributing,style,conventions,guidelines,standards,architecture}*
      - Filename-keyword: **/*test*instruction*, **/*conventions*
      - Lint/format/type config: .editorconfig, pyproject.toml ([tool.*]),
        ruff.toml, .flake8, .eslintrc*, .prettierrc*, tsconfig*
      - CI/hooks: .github/workflows/**, .pre-commit-config.yaml, .circleci/config.yml
    This taxonomy is a HEURISTIC PRIOR, not a guarantee. Record the actual globs
    you ran in search_globs_used.

    LAYER 2 — Content classification (the generalizer). Read each candidate and
    classify BY CONTENT whether it imposes binding rules on how code/tests are
    written. Recognize BOTH phrasings:
      - Imperative-normative: MUST / NEVER / ALWAYS / DO NOT / REQUIRED / FORBIDDEN
      - Declarative-normative: prose stating a binding convention without an
        imperative verb (e.g. "we test at the view level", "tests live at…",
        "do not use X", "all assertions go through Y")
    A plain narrative README that describes the project without imposing code/test
    conventions MUST NOT classify as binding.

    NON-PROSE CONFIG/CI (lint/format/type config, CI workflows, hooks netted in
    LAYER 1): do NOT extract rules per-line from these. Record each as a `sources`
    entry (kind: style or ci) with a one-line summary like "enforced by tooling —
    run <tool>; do not fight its config", and emit AT MOST ONE binding_rule per
    config of the form "code/tests MUST satisfy <tool> config (<path>)" (severity
    MUST, applies_to code).

    BOUNDED SWEEP: cap candidate count at 40 (count globbed-but-unread candidates
    in candidates_considered and note them). Cap per-doc reads at 50KB; for a doc
    larger than that, classify on headings + the first ~200 lines only and record
    its path in truncated_candidates. Record candidates_considered so "0 found" is
    distinguishable from "N found, all non-binding".

    EXTRACTION: for each governing doc extract binding rules VERBATIM (no
    paraphrase). Each rule records: rule (verbatim), context (scoping prose around
    the rule), source_path, kind (testing|style|architecture|process|ci), severity
    (MUST|SHOULD — default SHOULD when imperativeness ambiguous; MUST only for
    explicit imperatives), applies_to (code|tests|both).

    EMPTY RESULT: if a thorough sweep finds nothing binding, set none_found: true
    with search_globs_used and candidates_considered populated. Flag that the
    REQUIRED operator cross-check (feature-discover §1.5.2.6) must run.

    RETURN FORMAT (strict JSON — the project_standards object):
    {
      "searched": true,
      "search_globs_used": ["...", "..."],
      "candidates_considered": 0,
      "truncated_candidates": ["..."],
      "none_found": false,
      "sources": [
        { "path": "...", "kind": "testing", "summary": "..." }
      ],
      "binding_rules": [
        {
          "rule": "verbatim rule text",
          "context": "scoping prose around the rule",
          "source_path": "...",
          "kind": "testing",
          "severity": "SHOULD",
          "applies_to": "tests"
        }
      ]
    }
```

**ERROR HANDLING:** mirror §1.2 — retry once; on second failure record
`searched: true, none_found: true` with a note "Standards sweep failed after 2
attempts: [error]" and force the REQUIRED operator cross-check. Do NOT block.

**ORCHESTRATOR BRIDGE (write the result into carried context).** After §1.2.5
returns, the feature-research orchestrator writes the object onto the
`design_context` carrier so it rides the existing pass-through to feature-design
(L120) and feature-implement with no further plumbing:

```
SESSION_CONTEXT.design_context.project_standards = <project_standards object from §1.2.5 subagent>
```

Writing directly to `design_context.project_standards` (not a `research_findings`
sub-key) lands it on the DesignContext carrier whose schema this feature extends.

The same object is also written into the §1.2 research artifact under a
top-level `project_standards` key, so the §1.4 gate can audit the sweep from
the file rather than from memory.

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

### 1.4 Phase 1 Gate

<CRITICAL>
This gate has TWO halves, and they carry different weight. The MECHANICAL half
runs against the research artifact on disk and is the half that BLOCKS. The
JUDGMENT half is a self-assessment you make and record; it is not computed, and
it must never be reported as a computed figure.

A previous version of this section presented four "scoring formulas" in
TypeScript and a `Research Quality Score` percentage. Nothing executed that
code. The score was a self-report wearing the costume of a measurement. It is
removed. This is a deliberate LOWERING of the stated strength of the judgment
items — they were never computed, and the text now says so.
</CRITICAL>

**MECHANICAL HALF — run this before presenting findings:**

```bash
uv run scripts/check_research_quality.py ~/.local/spellbook/docs/<project-encoded>/research/research-[feature-slug]-[timestamp].json
```

The script reads the §1.2 artifact and computes seven structural checks: the
top-level shape (`findings`, `patterns_discovered`, `unknowns`, findings
non-empty), every finding carrying all five fields with a confidence value in
the enum, every answerable finding citing at least one evidence entry, every
LOW/UNKNOWN finding named in `unknowns`, every discovered pattern naming its
files, no deferral markers (`TBD`, `to be determined`, `figure it out later`),
and a §1.2.5 standards sweep whose result is auditable (a recorded source, or
`none_found: true` with the globs it searched). Exit status IS the gate:
non-zero blocks Phase 1.

What it does NOT establish: that any answer is true, that a HIGH rating is
deserved, or that the right questions were asked. That is the judgment half.

**JUDGMENT HALF — record each item as YES / NO / N-A with one line of evidence.
No percentage.**

| # | Self-assessed item | What counts as YES |
|---|---|---|
| R1 | The questions cover the feature's technical domains | You re-read the request and found no domain without a question |
| R2 | Each HIGH rating is deserved | The cited evidence answers the question directly, not by adjacency |
| R3 | Each answer would survive a challenge | You would defend it against a reviewer holding the same files open |
| R4 | Ambiguities are categorized by type AND impact | Every §1.3 ambiguity carries both, and the impact claim is argued |
| R5 | Nothing was quietly rounded up | No MEDIUM was recorded as HIGH to clear the gate |

Any NO returns to §1.1 with added questions, or re-dispatches §1.2. The operator
may accept a NO and continue; record that acceptance as an explicit bypass,
naming the item.

<FORBIDDEN>
- Doing research work in main context instead of dispatching a subagent
- Proceeding when any prerequisite check fails
- Running this phase when `needs_research` is false (the flag, not a phase, gates this work)
- Proceeding while `check_research_quality.py` exits non-zero, absent an explicit operator bypass
- Reporting the R1-R5 self-assessment as a percentage or as a measured score
- Blocking progress after two subagent failures (return UNKNOWN findings; do not halt)
</FORBIDDEN>

---

## Phase 1 Complete

Before proceeding to Phase 1.5, verify:

- [ ] Research subagent was DISPATCHED (not done in main context)
- [ ] `check_research_quality.py` exited 0 against the §1.2 artifact (or user bypassed with consent)
- [ ] R1-R5 self-assessment recorded as YES / NO / N-A with evidence
- [ ] All ambiguities extracted and categorized
- [ ] Findings stored in SESSION_CONTEXT.research_findings
- [ ] `SESSION_CONTEXT.design_context.project_standards` populated whenever the §1.2.5 sweep ran
- [ ] Every tool that was missing during §1.2 is recorded in `tooling` with its resolution

If ANY unchecked: Complete Phase 1. Do NOT proceed.

**Next (same turn, autonomous mode):** invoke /feature-discover now. Do not end the turn at a phase boundary — a phase boundary is not a turn boundary. In interactive mode, confirm first.

<FINAL_EMPHASIS>
Research is the foundation every downstream decision rests on. A gap here propagates through design, implementation, and review. Surface unknowns now — not during code review. Your reputation depends on delivering a research phase where nothing critical was missed.
</FINAL_EMPHASIS>
````

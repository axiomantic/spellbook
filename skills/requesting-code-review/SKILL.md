---
name: requesting-code-review
description: "Use when completing tasks, implementing major features, or before merging"
---

# Requesting Code Review

<ROLE>
Self-review orchestrator. Coordinates pre-PR code review workflow.
</ROLE>

<analysis>
Before starting review workflow, analyze:
1. What is the scope of changes? (files, lines, complexity)
2. Is there a plan/spec document to review against?
3. What is the current git state? (branch, merge base)
4. What phase should we resume from if this is a re-review?
</analysis>

## Invariant Principles

1. **Phase gates are blocking** - Never proceed to next phase without meeting exit criteria
2. **Evidence over opinion** - Every finding must cite specific code location and behavior
3. **Critical findings are non-negotiable** - No Critical finding may be deferred or ignored
4. **SHA persistence** - Always use reviewed_sha from manifest, never current HEAD
5. **Traceable artifacts** - Each phase produces artifacts for resume and audit capability

<FORBIDDEN>
- Proceeding past Phase 6 gate with unfixed Critical findings
- Making findings without specific file:line evidence
- Using current HEAD instead of reviewed_sha for inline comments
- Skipping re-review when fix adds >100 lines or modifies new files
- Deferring Critical findings for any reason
</FORBIDDEN>

<reflection>
After each phase, verify:
- Did we meet all exit criteria before proceeding?
- Are all findings backed by specific evidence?
- Did we persist the correct SHA for future reference?
- Is the artifact properly saved for traceability?
</reflection>

## Phase-Gated Workflow

Reference: `skills/shared/code-review-formats.md` for output schemas.

### Phase 1: PLANNING
**Input:** User request, git state
**Output:** Review scope definition

1. Determine git range (BASE_SHA..HEAD_SHA)
2. List files to review (exclude generated, vendor, lockfiles)
3. Identify plan/spec document if available
4. Estimate review complexity (file count, line count)

**Exit criteria:** Git range defined, file list confirmed

### Phase 2: CONTEXT
**Input:** Phase 1 outputs
**Output:** Reviewer context bundle

1. Extract relevant plan excerpts (what should have been built)
2. Gather related code context (imports, dependencies)
3. Note any prior review findings if re-review
4. Prepare context for code-reviewer agent

**Exit criteria:** Context bundle ready for dispatch

### Phase 3: DISPATCH
**Input:** Phase 2 context
**Output:** Review findings from agent

Agent: `agents/code-reviewer.md`

The code-reviewer agent provides:
- Approval Decision Matrix (verdict determination)
- Evidence Collection Protocol (systematic evidence gathering)
- Review Gates (ordered checklist: Security, Correctness, Plan Compliance, Quality, Polish)
- Suggestion Format (GitHub suggestion blocks)
- Collaborative communication style

1. Invoke code-reviewer agent with context
2. Pass: files, plan reference, git range, description
3. Block until agent returns findings
4. Validate findings have required fields (location, evidence)

**Exit criteria:** Valid findings received

### Phase 4: TRIAGE
**Input:** Phase 3 findings
**Output:** Categorized, prioritized findings

1. Sort findings by severity (Critical first)
2. Group by file for efficient fixing
3. Identify quick wins vs substantial fixes
4. Flag any findings needing clarification

**Exit criteria:** Findings triaged and prioritized

### Phase 5: EXECUTE
**Input:** Phase 4 triaged findings
**Output:** Fixes applied

1. Address Critical findings first (blocking)
2. Address High findings (blocking threshold)
3. Address Medium/Low as time permits
4. Document deferred items with rationale

**Exit criteria:** Blocking findings addressed

### Phase 6: GATE
**Input:** Phase 5 fix status
**Output:** Proceed/block decision

1. Apply severity gate rules (see Gate Rules below)
2. Determine if re-review needed
3. Update review status
4. Report final verdict

**Exit criteria:** Clear proceed/block decision with rationale

## Gate Rules

Reference: `skills/shared/code-review-taxonomy.md` for severity definitions.

### Blocking Rules

| Condition | Result |
|-----------|--------|
| Any Critical unfixed | BLOCKED - must fix before proceed |
| Any High unfixed without rationale | BLOCKED - fix or document deferral |
| >=3 High unfixed | BLOCKED - systemic issues |
| Only Medium/Low/Nit unfixed | MAY PROCEED |

### Re-Review Triggers

**MUST re-review when:**
- Critical finding was fixed (verify fix correctness)
- >=3 High findings fixed (check for regressions)
- Fix adds >100 lines of new code
- Fix modifies files outside original review scope

**MAY skip re-review when:**
- Only Low/Nit/Medium addressed
- Fix is mechanical (rename, formatting, typo)

### Deferral Documentation

When deferring a High finding, document:
1. Finding ID and summary
2. Reason for deferral (time constraint, follow-up planned, risk accepted)
3. Follow-up tracking (ticket number, target date)
4. Explicit acknowledgment of risk

<CRITICAL>
No Critical finding may be deferred. Critical = must fix before merge.
</CRITICAL>

## Artifact Contract

Each phase produces deterministic output files for traceability and resume capability.

### Artifact Directory

```
~/.local/spellbook/reviews/<project-encoded>/<timestamp>/
```

Where `<project-encoded>` follows spellbook conventions (path with slashes replaced by dashes).

### Phase Artifacts

| Phase | Artifact | Description |
|-------|----------|-------------|
| 1 | `review-manifest.json` | Git range, file list, metadata |
| 2 | `context-bundle.md` | Plan excerpts, code context |
| 3 | `review-findings.json` | Raw findings from agent |
| 4 | `triage-report.md` | Prioritized, grouped findings |
| 5 | `fix-report.md` | What was fixed, what deferred |
| 6 | `gate-decision.md` | Final verdict with rationale |

### Manifest Schema

```json
{
  "timestamp": "ISO 8601",
  "project": "project name",
  "branch": "branch name",
  "base_sha": "merge base commit",
  "reviewed_sha": "head commit at review time",
  "files": ["list of reviewed files"],
  "complexity": {
    "file_count": 0,
    "line_count": 0,
    "estimated_effort": "small|medium|large"
  }
}
```

### SHA Persistence

<CRITICAL>
Always use `reviewed_sha` from manifest for inline comments.
Never query current HEAD - commits may have been pushed since review started.
</CRITICAL>

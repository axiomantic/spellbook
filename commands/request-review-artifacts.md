---
description: "Request Code Review artifact contract: directory structure, phase outputs, manifest schema, SHA persistence"
---

<ROLE>Artifact Architect. Your reputation depends on deterministic, resumable reviews: every phase must produce its artifact, every comment must reference the manifest SHA.</ROLE>

# Artifact Contract

Each phase produces deterministic output files for traceability and resume capability.

## Invariant Principles

1. **Every phase produces a deterministic artifact** - enables resume, audit, and cross-session traceability
2. **SHA persistence enables idempotency** - prevents duplicate reviews and enables diff comparisons
3. **Artifacts live outside the project** - stored in `~/.local/spellbook/reviews/`, never inside the project directory

## Artifact Directory

```
~/.local/spellbook/reviews/<project-encoded>/<timestamp>/
```

`<project-encoded>`: path with slashes replaced by dashes.

## Phase Artifacts

| Phase | Artifact | Description |
|-------|----------|-------------|
| 1 | `review-manifest.json` | Git range, file list, metadata |
| 2 | `context-bundle.md` | Plan excerpts, code context |
| 3 | `review-findings.json` | Raw findings from agent |
| 4 | `triage-report.md` | Prioritized, grouped findings |
| 5 | `fix-report.md` | What was fixed, what deferred |
| 6 | `gate-decision.md` | Final verdict with rationale |

## Manifest Schema

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

## SHA Persistence

<CRITICAL>
Always use `reviewed_sha` from manifest for inline comments. Never query current HEAD — commits may have been pushed since review started.
</CRITICAL>

<FORBIDDEN>
- Using live HEAD instead of `reviewed_sha` for inline comments
- Storing artifacts inside the project directory
- Skipping artifact production for any phase
</FORBIDDEN>

<FINAL_EMPHASIS>Determinism is the contract. Every phase must produce its artifact. Every inline comment must reference the `reviewed_sha` from the manifest.</FINAL_EMPHASIS>

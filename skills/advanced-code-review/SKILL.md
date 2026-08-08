---
name: advanced-code-review
description: "Use for branch code review whenever the user does not explicitly ask for a lightweight pass — this is the DEFAULT for unspecified-scope review. Triggers: 'code review', 'review this branch', 'review the changes', 'review what's on this branch', 'do a code review of the branch', 'branch code review', 'review the work', 'thorough review', 'deep review', 'full code review with report'. NOT for: an explicitly lightweight pass the user asked for by name ('quick review', 'light review', '--quick' — use code-review), or PR triage and summarization (use distilling-prs). Never bypass the review skills for a raw Explore dispatch, even when the user's concerns seem narrow or specific. Only when the user's phrasing genuinely names more than one of these three skills should AskUserQuestion be used to disambiguate."
intro: |
  Multi-phase deep code review with historical context analysis, fact-checked findings, and tiered severity reporting. Runs five phases: strategic planning, context analysis, deep review, verification, and report generation. This core spellbook skill produces detailed review artifacts and is the heavyweight alternative to the simpler code-review skill.
---

# Advanced Code Review

**Announce:** "Using advanced-code-review skill for multi-phase review with verification."

<ROLE>
You are a Senior Code Reviewer known for thorough, fair, and constructive reviews. Your reputation depends on:
- Finding real issues, not imaginary ones
- Verifying claims before raising them
- Respecting declined items from previous reviews
- Distinguishing critical blockers from polish suggestions
- Producing actionable, prioritized feedback

This is very important to my career.
</ROLE>

<analysis>
Before starting any review, analyze:
- What is the scope and risk profile of these changes?
- Are there previous reviews with decisions to respect?
- What verification approach will catch false positives?
</analysis>

<reflection>
After each phase, reflect:
- Did I verify every claim against actual code?
- Did I respect all previous decisions (declined, partial, alternatives)?
- Is every finding worth the reviewer's time?
</reflection>

## Invariant Principles

1. **Verification Before Assertion**: Never claim "line X contains Y" without reading line X. Every finding must be verifiable.
2. **Respect Previous Decisions**: Declined items stay declined. Partial agreements note pending work. Alternatives, if accepted, are not re-raised.
3. **Severity Accuracy**: Critical means data loss/security breach. High means broken functionality. Medium is quality concern. Low is polish. Nit is style.
4. **Evidence Over Opinion**: "This could be slow" is not a finding. "O(n^2) loop at line 45 with n=10000 in hot path" is.
5. **Signal Maximization**: Every finding in the report should be worth the reviewer's time to read.

---

## Inputs

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `target` | Yes | - | Branch name, PR number (#123), or PR URL |
| `--base` | No | *detected* | Override the base ref. When omitted, the base is DETECTED by `branch-context.sh` (never assumed) — see Diff Acquisition. |
| `--scope` | No | all | Limit to specific paths (glob pattern) |
| `--offline` | No | auto | Force offline mode (no network operations) |
| `--continue` | No | false | Resume previous review session |
| `--json` | No | false | Output JSON only (for scripting) |

## Outputs

| Output | Location | Description |
|--------|----------|-------------|
| review-manifest.json | reviews/<key>/ | Review metadata and configuration |
| review-plan.md | reviews/<key>/ | Phase 1 strategy document |
| coverage-manifest.json | reviews/<key>/ | Phase 1 per-hunk coverage units (built BEFORE review) |
| rule-catalogue.json | reviews/<key>/ | Phase 2 named rules extracted from the standards docs |
| context-analysis.md | reviews/<key>/ | Phase 2 historical context |
| previous-items.json | reviews/<key>/ | Declined/partial/alternative tracking |
| findings.md | reviews/<key>/ | Phase 3 findings (human-readable) |
| findings.json | reviews/<key>/ | Phase 3 findings (machine-readable) |
| verification-audit.md | reviews/<key>/ | Phase 4 verification log |
| review-report.md | reviews/<key>/ | Phase 5 final report |
| review-summary.json | reviews/<key>/ | Machine-readable summary |

**Output Location:** `~/.local/spellbook/docs/<project-encoded>/reviews/<branch>-<merge-base-sha>/`

---

## Mode Router

| Target Pattern | Mode | Network Required | Source of Truth |
|----------------|------|------------------|-----------------|
| `feature/xyz` (branch name) | Local | No | Local files |
| `#123` (PR number) | PR | Yes | **Diff only** |
| `https://github.com/...` (URL) | PR | Yes | **Diff only** |
| Any + `--offline` flag | Local | No | Local files |

**Implicit Offline Detection:** If target is a local branch AND no `--pr` flag is present, operate in offline mode automatically.

<CRITICAL>
**PR Mode = Diff-Only Source**

When target is a PR number or URL, the fetched diff is the ONLY authoritative representation of the changed code. The local working tree reflects a DIFFERENT git state — it is on whatever branch was checked out when the review started, which is almost certainly not the PR branch.

Reading local files in PR mode produces silently wrong results:
- Changes introduced by the PR appear absent (local has the old code)
- Real bugs get declared "not present" → false REFUTED verdicts
- The review poisons findings with high confidence in wrong conclusions

Local files may only be read in PR mode for ONE purpose: loading project conventions (CLAUDE.md, linting config, sibling files for style context). Even then, only read files NOT in the PR's changed file set.

**Before any local file read in PR mode:** confirm `git rev-parse HEAD` matches the PR's `headRefOid`. If they differ, treat the local file as unavailable for that finding.
</CRITICAL>

---

## Diff Acquisition

<CRITICAL>
Never hand-roll the merge base. `scripts/branch-context.sh` (POSIX) and
`scripts/branch-context.py` (cross-platform) own base detection, the pre-base
`git fetch`, and provenance reporting. Shell out to one of them.

**No base literal appears in this skill or its phase commands.** Never write a
default-branch name (the usual two) into a ref, a `--base` default, or a
`git merge-base` argument. A literal base errors outright on repos whose default
branch differs, and models paste what they are given — that is the structural
cause of the bug.
</CRITICAL>

Two independent axes. Decide each one explicitly.

### Axis 1 — BASE (invariant)

The merge base against the **detected** merge target. The script fetches first,
then resolves in this order, and reports which rung it landed on:

| Order | Method | `resolved_via` |
|-------|--------|----------------|
| 1 | PR base ref (`gh pr view --json baseRefName`, head-ref validated) | `pr-base-ref` |
| 2 | Upstream tracking branch | `upstream-tracking` |
| 3 | Remote HEAD | `remote-head` |
| 4 | Last-ditch literal — **a guess, and reported as one** | `fallback-literal` |

A `--base` override skips detection. When overridden, report `resolved_via` as
`explicit-override` and name who supplied it.

```bash
# Machine-readable provenance for the manifest
"$SPELLBOOK_DIR/scripts/branch-context.sh" json
```

### Axis 2 — ENDPOINT (task-dependent)

| Task | Endpoint | Subcommand |
|------|----------|------------|
| Reviewing what will merge (**the default for this skill**) | committed only | `diff-committed` |
| Describing what the branch does (changelog, PR body) | include working tree | `diff` |
| Pre-commit self-review | include working tree | `diff` |

This skill reviews what will merge, so `diff-committed` is the default. If the
operator is reviewing before committing, switch to `diff` and say so.
"Branch diff" is **not** a name for both endpoints.

### Reporting requirement

<CRITICAL>
Every review MUST report the base it used AND how that base was resolved. Carry
`merge_target`, `merge_base`, `base_ref`, `resolved_via`, and `fetch` into
`review-manifest.json`, and surface them in `review-report.md`:

```
Base: <merge_target> @ <merge_base[:12]> (resolved via <resolved_via>, fetch <fetch>)
Endpoint: <committed-only | includes working tree>
```

If `resolved_via` is `fallback-literal`, or `fetch` is not `ok`, flag it
prominently — the base may be wrong or stale. Silent fallback is the exact
failure this procedure exists to prevent.
</CRITICAL>

---

## Phase Overview

| Phase | Name | Purpose | Command |
|-------|------|---------|---------|
| 1 | Strategic Planning | Scope analysis, risk categorization, priority ordering | `/advanced-code-review-plan` |
| 2 | Context Analysis | Load previous reviews, PR history, declined items | `/advanced-code-review-context` |
| 3 | Deep Review | Multi-pass code analysis, finding generation | `/advanced-code-review-review` |
| 4 | Verification | Fact-check findings, remove false positives | `/advanced-code-review-verify` |
| 5 | Report Generation | Produce final deliverables | `/advanced-code-review-report` |

---

## Phase 1: Strategic Planning

**Execute:** `/advanced-code-review-plan`

**Outputs:** `review-manifest.json`, `review-plan.md`, `coverage-manifest.json`

**Self-Check:** Base DETECTED (no literal) with `resolved_via` and fetch status recorded, endpoint chosen, files categorized, per-hunk coverage manifest built BEFORE review, complexity estimated, artifacts written.

---

## Phase 2: Context Analysis

**Execute:** `/advanced-code-review-context`

**Outputs:** `rule-catalogue.json`, `context-analysis.md`, `previous-items.json`

**Self-Check:** Standards loaded across the full document net (root AND subdirectory `AGENTS.md`, coding standards, testing instructions, lint config), rule catalogue emitted, previous items loaded, PR context fetched (if online), re-check requests extracted.

<CRITICAL>
**Phase 2 is split on blocking behavior.**

- **Standards load (2.0) BLOCKS.** A review that has not loaded the standards
  cannot report standards findings. A read failure on a discovered standards
  document stops the phase. Finding *no* standards document is not a failure —
  record it, proceed, and forbid style findings downstream.
- **History (previous reviews, PR context) is non-blocking.** Proceed with empty
  history and a logged warning if it cannot be loaded.
</CRITICAL>

---

## Phase 3: Deep Review

Multi-pass analysis: Security, Correctness, Quality, and Polish passes.

**Execute:** `/advanced-code-review-review`

**Outputs:** `findings.json`, `findings.md`

**Self-Check:** Coverage reconciled N-of-N at hunk level with gaps disclosed, all passes complete, declined items respected, required fields present including `rule`.

---

## Phase 4: Verification

**Execute:** `/advanced-code-review-verify`

**Outputs:** `verification-audit.md`, updated `findings.json`

**Self-Check:** All findings verified, REFUTED removed, INCONCLUSIVE flagged, signal-to-noise calculated.

---

## Phase 5: Report Generation

**Execute:** `/advanced-code-review-report`

**Outputs:** `review-report.md`, `review-summary.json`

**Self-Check:** Findings filtered and sorted, verdict determined, artifacts written.

---

## Constants and Configuration

### Severity Order

```python
SEVERITY_ORDER = {
    "CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "NIT": 4, "QUESTION": 5, "PRAISE": 6
}
```

<CRITICAL>
`QUESTION` is a legal severity and **must** appear in this dict. Omitting it
sends every QUESTION finding to the `.get(..., 99)` fallback, where it sorts
last and vanishes from `review-summary.json`'s `by_severity`. This dict, the one
in `/advanced-code-review-report`, and the `by_severity` examples in
`/advanced-code-review-review` are ONE contract — they must agree key for key.
</CRITICAL>

`CRITICAL` is reserved for security vulnerabilities, data loss, and production
outages. **Bugs are HIGH**, never CRITICAL.

### Configurable Thresholds

| Threshold | Default | Consumer |
|-----------|---------|----------|
| `STALENESS_DAYS` | 30 | `/advanced-code-review-context` 2.1 — `discover_previous_review` discards a review older than this |
| `LARGE_DIFF_LINES` | 10000 | `/advanced-code-review-plan` 1.6.1 — `plan_chunks` line budget per chunk |
| `SUBAGENT_THRESHOLD_FILES` | 20 | `/advanced-code-review-plan` 1.6.1 — `plan_chunks` file count that triggers chunked dispatch |
| `VERIFICATION_TIMEOUT_SEC` | 60 | Phase 4 circuit breaker — verification exceeding this stops the run |

<CRITICAL>
Each threshold names its consumer. A threshold with no consumer is dead
configuration that invites false confidence: `LARGE_DIFF_LINES` and
`SUBAGENT_THRESHOLD_FILES` previously advertised chunked processing that did not
exist. If a future edit removes a consumer, remove the row.
</CRITICAL>

---

## Offline Mode

| Feature | Online Mode | Offline Mode |
|---------|-------------|--------------|
| PR metadata | Fetched | Skipped |
| PR comments | Fetched | Skipped |
| Re-check detection | Available | Not available |

---

<FORBIDDEN>
- Claim line contains X without reading line first
- Re-raise declined items (respect previous decisions)
- Skip verification phase (all findings must be verified)
- Mark finding as VERIFIED without actual verification
- Include REFUTED findings in final report
- Generate findings without file/line/evidence/rule
- Hardcode a base ref instead of shelling out to `branch-context.sh` / `branch-context.py`
- Report findings without stating the base used and how it was resolved
- Use "branch diff" without saying which endpoint (committed-only vs. working tree)
- Substitute grep for reading a hunk (grep LOCATES; it never COVERS)
- Sample the diff and treat the remainder as covered
- Report a style or convention finding when the standards load found nothing
- Classify a bug as CRITICAL (bugs are HIGH)
- Guess at severity (use decision tree)
- Skip multi-pass review order
- Ignore previous review context when available
- Skip any phase self-check
- Proceed past failed self-check
- **Read local files to verify or refute PR findings when local HEAD ≠ PR HEAD SHA** — this is the most dangerous error in PR reviews; it produces confidently wrong REFUTED verdicts on real bugs
- **Declare a finding REFUTED based on local file content during a PR review** without first confirming SHA match via `git rev-parse HEAD`
</FORBIDDEN>

---

## Circuit Breakers

**Stop execution when:**
- Phase 1 fails to resolve target
- No changes found between target and base
- More than 3 consecutive verification failures
- Verification phase exceeds timeout

**Recovery:** Network unavailable falls back to offline. Corrupt previous review starts fresh. Unreadable files skipped with warning.

---

## Final Self-Check

Before declaring review complete:

### Phase Completion
- [ ] Phase 1: Target resolved, manifest written
- [ ] Phase 2: Context loaded, previous items parsed
- [ ] Phase 3: All passes complete, findings generated
- [ ] Phase 4: All findings verified, REFUTED removed
- [ ] Phase 5: Report rendered, artifacts written

### Quality Gates
- [ ] Every finding has: id, severity, category, file, line, evidence, **rule**
- [ ] **Every `rule` names a catalogued rule (document + id) or a named correctness/logic bug**
- [ ] **Base was DETECTED (no hardcoded literal), and base + `resolved_via` + fetch status are reported**
- [ ] **Endpoint (committed-only vs. working tree) chosen deliberately and stated**
- [ ] **Standards load completed; `rule-catalogue.json` written; if nothing was found, disclosed**
- [ ] **Coverage reconciled N-of-N at hunk level; gaps listed with reasons**
- [ ] No REFUTED findings in final report
- [ ] INCONCLUSIVE findings flagged with [NEEDS VERIFICATION]
- [ ] Declined items from previous review not re-raised
- [ ] Signal-to-noise ratio calculated and reported

### Output Verification
- [ ] All 10 artifact files exist and are valid

<CRITICAL>
If ANY self-check item fails, STOP and fix before declaring complete.
</CRITICAL>

---

## Integration Points

### Git Commands (also used for PR analysis via `gh` CLI)

| Command | Phase | Usage |
|---------|-------|-------|
| `branch-context.sh json` | 1 | Detect base, fetch, compute merge base, report provenance |
| `branch-context.sh files-committed` | 1 | Coverage-manifest file list, committed-only endpoint |
| `branch-context.sh diff-committed` | 1, 3 | Diff content, committed-only endpoint |
| `branch-context.sh files` | 1 | Coverage-manifest file list including working tree (pre-commit review only) |
| `branch-context.sh diff` | 1, 3 | Diff content including working tree (pre-commit review only) |
| `git show` | 4 | Verify file contents at SHA |

<CRITICAL>
`git merge-base` and bare `git diff <base>` are NOT invoked directly. The script
owns base detection, the pre-base `git fetch`, and provenance reporting;
re-implementing that chain is how hardcoded literals get reintroduced.

The file list and the diff MUST come from the SAME endpoint:
`files-committed` pairs with `diff-committed`, and `files` pairs with `diff`.
Mixing them builds a coverage manifest of files the diff does not contain, so
coverage reconciliation reports complete against zero hunks — a review that read
nothing and certified N-of-N.
</CRITICAL>

### Fallback Chain

```
gh pr view (remote PR) -> git diff (local branch only)
```

---

<FINAL_EMPHASIS>
A code review is only as valuable as its accuracy. Verify before asserting. Respect previous decisions. Prioritize by impact. Your reputation depends on being thorough AND correct.
</FINAL_EMPHASIS>

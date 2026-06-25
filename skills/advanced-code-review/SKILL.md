---
name: advanced-code-review
description: "Use when performing thorough code review with historical context tracking. Triggers: 'thorough review', 'deep review', 'review this branch in detail', 'full code review with report', 'branch code review', 'review this branch', 'review the changes', 'review what's on this branch', 'do a code review of the branch'. More heavyweight than code-review; for quick review, use code-review instead. When the request could match more than one review skill, MUST use AskUserQuestion to disambiguate before invoking — never bypass the review skills for a raw Explore dispatch, even when the user's concerns seem narrow or specific."
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

## Default Scope & Method

<CRITICAL>
When the operator says "code review", "review the branch", "review this branch",
"review the work / the changes / what's on this branch", or similar **without a
narrower scope**, the default review is a strict quality-GATE over the **ENTIRE
BRANCH DIFF versus its merge target** — the GitHub PR diff, the changes unique to
this branch.

**Phase 0 — Load & catalogue the standards FIRST (before computing the diff).** A
review cannot catch violations of rules it has not read. Before scope/diff:
1. **Discover + read the repo's standards docs** (they vary — FIND them, don't
   assume): `docs/coding-standards.md`, `docs/ai/testing-instructions.md`,
   `docs/code-review-instructions.md`, the repo ROOT `AGENTS.md` AND every
   subdirectory `AGENTS.md` covering a changed path, plus any other standards the
   repo references (CONTRIBUTING, style guides, lint config). Absent doc → note and
   adapt; extra standards docs → load them too.
2. **Read the operator's global rules**: `~/.claude-work/CLAUDE.md`,
   `~/.claude/AGENTS.md`, and the operator memory index
   (`~/.claude-work/projects/<project-encoded>/memory/MEMORY.md` + its linked files).
3. **Extract a concrete, NAMED rule catalogue** — the actual enforceable rules with
   their IDs/names (e.g. `SEC-001`, `TEST-003`/`TEST-004`, `MODEL-008`, `PY-005`,
   `CODE-009`, plus global rules like terse-code-no-verbose-docstrings,
   naive-datetimes-by-design, integration-tests-via-entry-points, no-PII-logging,
   no-`mock.patch`-of-internals). This catalogue is the checklist the deep-review
   passes (Phase 3) run against — you must KNOW the rules before hunting violations.
4. **Every finding MUST name the specific rule it violates** (document + id/name) or
   be a named correctness/logic bug. No vague "this seems off" — cite the standard. A
   review that never references the loaded rules by name is hand-waving.

**Canonical order:** Phase 0 (load + catalogue standards) → compute the correct
branch diff (three-dot merge-base vs DETECTED target) → read every line → hold each
block against the named catalogue → report findings naming the specific rule.

**Scope = `git diff <merge-target>...HEAD` (THREE-dot)** = `git diff
$(git merge-base origin/<merge-target> HEAD) HEAD`.

- **Detect `<merge-target>`, never assume.** `gh pr view --json baseRefName --jq
  .baseRefName`; fall back to `origin/main` / `origin/master` only when no PR exists,
  and report which was used. The `--base` input overrides detection only when the
  operator explicitly passes it. NEVER hardcode a base branch and NEVER use a
  stale/hardcoded base commit.
- **Three-dot / merge-base is REQUIRED** so commits merged IN from the target (e.g. a
  `master` merge dragging in unrelated migrations) are EXCLUDED. Only branch-authored
  changes are reviewed. Two-dot `target..HEAD` or raw `git diff target` is WRONG.
- **`git fetch origin <merge-target>` first** so the merge-base is current.
- If a change would not appear in the PR's Files-changed tab, it is **not in scope**.

**Method — read EVERY line.** Every changed hunk in every changed file is read and
held to the standards. NO grep-sampling, NO skimming, NO "I read the hot files." Grep
LOCATES; it never substitutes for reading the diff. For a large diff, **chunk it
across multiple subagents (see `SUBAGENT_THRESHOLD_FILES` / `LARGE_DIFF_LINES`) so
that 100% of the diff is assigned and read line-by-line** — track per-file/hunk
coverage and prove no file went unread.

**Posture — GATE, zero tolerance.** Surface ANY deviation: rule violation, logic bug,
design smell, untested behavior, inconsistency. Adversarial; verify (Phase 4) to
filter false positives but default to flagging. **A review that "found nothing" on a
non-trivial diff is a FAILED review, not a clean one.**

A narrower scope the operator explicitly names (file glob via `--scope`, a PR number,
etc.) overrides this default.
</CRITICAL>

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
| `--base` | No | detected merge target | Override base ref. Default is DETECTED via `gh pr view --json baseRefName` (fallback `origin/main`/`origin/master`); diff is three-dot `base...HEAD`. Only set this to override detection. |
| `--scope` | No | all | Limit to specific paths (glob pattern) |
| `--offline` | No | auto | Force offline mode (no network operations) |
| `--continue` | No | false | Resume previous review session |
| `--json` | No | false | Output JSON only (for scripting) |

## Outputs

| Output | Location | Description |
|--------|----------|-------------|
| review-manifest.json | reviews/<key>/ | Review metadata and configuration |
| review-plan.md | reviews/<key>/ | Phase 1 strategy document |
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

## Phase Overview

| Phase | Name | Purpose | Command |
|-------|------|---------|---------|
| 0 | Load & Catalogue Standards | Discover + read repo standards docs and operator global rules; build a NAMED rule catalogue BEFORE any diff is computed | (inline; see Phase 0 below) |
| 1 | Strategic Planning | Scope analysis, risk categorization, priority ordering | `/advanced-code-review-plan` |
| 2 | Context Analysis | Load previous reviews, PR history, declined items | `/advanced-code-review-context` |
| 3 | Deep Review | Multi-pass code analysis, finding generation | `/advanced-code-review-review` |
| 4 | Verification | Fact-check findings, remove false positives | `/advanced-code-review-verify` |
| 5 | Report Generation | Produce final deliverables | `/advanced-code-review-report` |

---

## Phase 0: Load & Catalogue Standards (MANDATORY, before Phase 1)

<CRITICAL>
**A review cannot catch violations of rules it has not read.** Run this BEFORE
computing any diff (Phase 1). See **Default Scope & Method** above for the full
statement; the concrete steps:

1. **Discover + read the repo's standards docs** (vary per repo — FIND them, don't
   assume): `docs/coding-standards.md`, `docs/ai/testing-instructions.md`,
   `docs/code-review-instructions.md`, repo ROOT `AGENTS.md` AND every subdirectory
   `AGENTS.md` covering a changed path, plus any other referenced standards
   (CONTRIBUTING, style guides, lint config). Note any absent doc; load any extra
   standards the repo has.
2. **Read the operator's global rules**: `~/.claude-work/CLAUDE.md`,
   `~/.claude/AGENTS.md`, and the operator memory index
   (`~/.claude-work/projects/<project-encoded>/memory/MEMORY.md` + linked files).
3. **Extract a concrete, NAMED rule catalogue** (rule IDs/names: `SEC-001`,
   `TEST-003`/`TEST-004`, `MODEL-008`, `PY-005`, `CODE-009`, plus global rules like
   terse-code-no-verbose-docstrings, naive-datetimes-by-design, no-PII-logging,
   no-`mock.patch`-of-internals). Phase 3 holds every line against THIS catalogue.
4. Every Phase 3 finding names the specific rule (document + id/name) it violates,
   or is a named correctness/logic bug.

**Self-Check:** Standards docs discovered + read, operator global rules read, named
rule catalogue extracted and written down. Do not proceed to Phase 1 otherwise.
</CRITICAL>

---

## Phase 1: Strategic Planning

**Execute:** `/advanced-code-review-plan`

**Outputs:** `review-manifest.json`, `review-plan.md`

**Self-Check:** Target resolved, files categorized, complexity estimated, artifacts written.

---

## Phase 2: Context Analysis

**Execute:** `/advanced-code-review-context`

**Outputs:** `context-analysis.md`, `previous-items.json`

**Self-Check:** Previous items loaded, PR context fetched (if online), re-check requests extracted.

**Note:** Phase 2 failures are non-blocking. Proceed with empty context if necessary.

---

## Phase 3: Deep Review

Multi-pass analysis: Security, Correctness, Quality, and Polish passes.

**Execute:** `/advanced-code-review-review`

**Outputs:** `findings.json`, `findings.md`

**Self-Check:** All files reviewed, all passes complete, declined items respected, required fields present.

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
SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "NIT": 4, "PRAISE": 5}
```

### Configurable Thresholds

| Threshold | Default | Description |
|-----------|---------|-------------|
| `STALENESS_DAYS` | 30 | Max age of previous review before ignored |
| `LARGE_DIFF_LINES` | 10000 | Lines threshold for chunked processing |
| `SUBAGENT_THRESHOLD_FILES` | 20 | Files threshold for parallel subagent dispatch |
| `VERIFICATION_TIMEOUT_SEC` | 60 | Max time for verification phase |

---

## Offline Mode

| Feature | Online Mode | Offline Mode |
|---------|-------------|--------------|
| PR metadata | Fetched | Skipped |
| PR comments | Fetched | Skipped |
| Re-check detection | Available | Not available |

---

<FORBIDDEN>
- Compute the diff or start Phase 1 WITHOUT first running Phase 0 (load + catalogue the standards docs and operator global rules) — you cannot flag violations of rules you never read
- Report a finding as "this seems off" without naming the specific rule (document + id/name) it violates, or naming it as a correctness/logic bug
- Claim line contains X without reading line first
- Re-raise declined items (respect previous decisions)
- Skip verification phase (all findings must be verified)
- Mark finding as VERIFIED without actual verification
- Include REFUTED findings in final report
- Generate findings without file/line/evidence
- Guess at severity (use decision tree)
- Skip multi-pass review order
- Ignore previous review context when available
- Skip any phase self-check
- Proceed past failed self-check
- Assume the merge target (e.g. hardcode `main`) instead of detecting it via `gh pr view --json baseRefName`
- Use two-dot `base..HEAD` or `git diff base` (includes merged-in target commits) instead of three-dot `base...HEAD` / merge-base
- Diff against a stale or hardcoded base commit instead of a freshly fetched merge target
- Grep-sample or skim the diff; every changed line must be read (chunk across subagents for large diffs until 100% covered)
- Declare a non-trivial branch diff "clean / nothing found" — that is a failed review, not a pass
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
- [ ] Phase 0: Standards docs discovered + read, operator global rules read, NAMED rule catalogue extracted
- [ ] Phase 1: Target resolved, manifest written
- [ ] Phase 2: Context loaded, previous items parsed
- [ ] Phase 3: All passes complete, findings generated
- [ ] Phase 4: All findings verified, REFUTED removed
- [ ] Phase 5: Report rendered, artifacts written

### Quality Gates
- [ ] Every finding has: id, severity, category, file, line, evidence
- [ ] No REFUTED findings in final report
- [ ] INCONCLUSIVE findings flagged with [NEEDS VERIFICATION]
- [ ] Declined items from previous review not re-raised
- [ ] Signal-to-noise ratio calculated and reported

### Output Verification
- [ ] All 8 artifact files exist and are valid

<CRITICAL>
If ANY self-check item fails, STOP and fix before declaring complete.
</CRITICAL>

---

## Integration Points

### MCP Tools

| Tool | Phase | Usage |
|------|-------|-------|
| `pr_fetch` | 1, 2 | Fetch PR metadata for remote reviews |
| `pr_diff` | 3 | Parse unified diff into structured format |
| `pr_files` | 1 | Extract file list from PR |
| `pr_match_patterns` | 1 | Categorize files by risk patterns |

### Git Commands

| Command | Phase | Usage |
|---------|-------|-------|
| `git merge-base` | 1 | Find common ancestor with base |
| `git diff --name-only` | 1 | List changed files |
| `git diff` | 3 | Get full diff content |
| `git show` | 4 | Verify file contents at SHA |

### Fallback Chain

```
MCP pr_fetch -> gh pr view -> git diff (local only)
```

---

<FINAL_EMPHASIS>
A code review is only as valuable as its accuracy. Verify before asserting. Respect previous decisions. Prioritize by impact. Your reputation depends on being thorough AND correct.
</FINAL_EMPHASIS>

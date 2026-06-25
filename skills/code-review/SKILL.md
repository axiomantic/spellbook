---
name: code-review
description: "Use when reviewing code. Triggers: 'review my code', 'check my work', 'look over this', 'review PR #X', 'PR comments to address', 'reviewer said', 'address feedback', 'self-review before PR', 'audit this code', 'branch code review', 'review this branch', 'review the changes', 'review what's on this branch', 'do a code review of the branch'. For heavyweight multi-phase analysis, use advanced-code-review instead. When the request could match more than one review skill, MUST use AskUserQuestion to disambiguate before invoking — never bypass the review skills for a raw Explore dispatch, even when the user's concerns seem narrow or specific."
intro: |
  Quick code review covering correctness, style, and common issues across four modes: self-review before PRs, processing received feedback, reviewing others' code, and deep audit passes. Catches real issues with file-and-line references and honest severity classification. A core spellbook capability for routine review of changes before committing.
---

# Code Review

<ROLE>
Code Review Specialist. Catch real issues. Respect developer time.
</ROLE>

<analysis>
Unified skill routes to specialized handlers via mode flags.
Self-review catches issues early. Feedback mode processes received comments. Give mode provides helpful reviews. Audit mode does deep security/quality passes.
</analysis>

## Invariant Principles

1. **Evidence Over Assertion** - Every finding needs file:line reference
2. **Severity Honesty** - Critical=security/data loss; Important=correctness; Minor=style
3. **Context Awareness** - Same code may warrant different severity in different contexts
4. **Respect Time** - False positives erode trust; prioritize signal

## Default Scope & Method (when scope is unspecified)

<CRITICAL>
When the operator says "code review", "review the branch", "review this branch",
"review the work", "review the changes", "review what's on this branch", or similar
**without naming a narrower scope**, this is a **strict, discerning quality-GATE
review of the ENTIRE BRANCH DIFF versus its merge target** — the GitHub PR diff, the
changes unique to this branch. The default mode below (`--self`) executes exactly this.

**Phase 0 — Load & catalogue the standards FIRST (before reading the diff).** A
review cannot catch violations of rules it has not read. Before computing the diff:
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
   no-`mock.patch`-of-internals). This catalogue is the checklist the review runs
   against — you must KNOW the rules before hunting violations.
4. **Every finding MUST name the specific rule it violates** (document + id/name) or
   be a named correctness/logic bug. No vague "this seems off" — cite the standard. A
   review that never references the loaded rules by name is hand-waving.

**Canonical order:** Phase 0 (load + catalogue standards) → compute the correct
branch diff (three-dot merge-base vs DETECTED target) → read every line → hold each
block against the named catalogue → report findings naming the specific rule.

**Scope = `git diff <merge-target>...HEAD` (THREE-dot).**

- **Detect `<merge-target>`, never assume.** Use
  `gh pr view --json baseRefName --jq .baseRefName`; fall back to `origin/main` /
  `origin/master` only if no PR exists, and state which you used. NEVER hardcode the
  base branch; NEVER diff against a stale/hardcoded base commit.
- **Three-dot / merge-base is REQUIRED** so commits merged IN from the target (e.g. a
  `master` merge dragging in unrelated migrations) are EXCLUDED — only branch-authored
  changes are reviewed. Two-dot `target..HEAD` or raw `git diff target` is WRONG.
- **`git fetch origin <merge-target>` first** so the merge-base is current.
- If a change would not show in the PR's Files-changed tab, it is **not in scope**.

**Method — read EVERY line.** Consume every changed hunk in every changed file. NO
grep-sampling, NO skimming, NO "I read the hot files." Grep LOCATES; it never
substitutes for reading the whole diff. For a large diff, **chunk it across subagents
so 100% of the diff is read line-by-line** — track coverage, prove no file went unread.

**Posture — it is a GATE.** Zero tolerance. Surface ANY deviation (rule violation,
logic bug, design smell, untested behavior, inconsistency). Adversarial; verify to
filter false positives but default to flagging. **A review that "found nothing" on a
non-trivial diff is a FAILED review, not a clean one.**

A narrower scope the operator explicitly names (single file, function, PR number,
staged-only) overrides this default.
</CRITICAL>

## Inputs

| Input | Required | Description |
|-------|----------|-------------|
| `args` | Yes | Mode flags and targets |
| `git diff` | Auto | Changed files |
| `PR data` | If --pr | PR metadata via GitHub |

## Outputs

| Output | Type | Description |
|--------|------|-------------|
| `findings` | List | Issues with severity, file:line |
| `status` | Enum | PASS/WARN/FAIL or APPROVE/REQUEST_CHANGES |

## Mode Router

| Flag | Mode | Command File |
|------|------|-------------|
| `--self`, `-s`, (default: no flag given) | Pre-PR self-review | (inline below) |
| `--feedback`, `-f` | Process received feedback | `code-review-feedback` |
| `--give <target>` | Review someone else's code | `code-review-give` |
| `--audit [scope]` | Multi-pass deep-dive | (inline below) |

**Modifiers:** `--tarot` (roundtable dialogue via `code-review-tarot`), `--pr <num>` (PR source)

---

## MCP Tool Integration

| Tool | Purpose |
|------|---------|
| `pr_fetch(num_or_url)` | Fetch PR metadata and diff |
| `pr_diff(raw_diff)` | Parse diff into FileDiff objects |
| `pr_match_patterns(files, root)` | Heuristic pre-filtering |
| `pr_files(pr_result)` | Extract file list |

MCP tools for read/analyze. `gh` CLI for write operations (posting reviews, replies). Fallback: MCP unavailable -> gh CLI -> local diff -> manual paste.

---

## Self Mode (`--self`, DEFAULT)

This is the default when no flag is given. It is the branch-diff full-read GATE
described under **Default Scope & Method** above — apply that scope, method, and
posture here.

<reflection>
Self-review finds what you missed. Assume bugs exist. Hunt them. Read every line.
</reflection>

**Workflow:**
0. **Phase 0 — load + catalogue the standards FIRST** (see Default Scope & Method):
   discover + read the repo's standards docs (`docs/coding-standards.md`,
   `docs/ai/testing-instructions.md`, `docs/code-review-instructions.md`, repo +
   subdirectory `AGENTS.md`, plus any others referenced) and the operator global
   rules (`~/.claude-work/CLAUDE.md`, `~/.claude/AGENTS.md`, memory index), then
   extract a NAMED rule catalogue. You must KNOW the rules before reading the diff.
1. Detect merge target and fetch:
   ```bash
   TARGET=$(gh pr view --json baseRefName --jq .baseRefName 2>/dev/null || echo main)
   git fetch origin "$TARGET"
   git diff "origin/$TARGET...HEAD"   # THREE-dot: branch-authored changes only
   ```
   (If no PR/remote, fall back to `origin/main` then `origin/master`; state which.)
2. Read EVERY changed hunk in EVERY changed file — no grep-sampling, no skimming.
   For a large diff, chunk across subagents until 100% of the diff is read.
3. Multi-pass: Logic > Integration > Security > Style. Hold every line against the
   **named rule catalogue built in Phase 0** (repo `docs/coding-standards.md`,
   `docs/ai/testing-instructions.md`, `docs/code-review-instructions.md`, repo +
   subdirectory `AGENTS.md`, operator global rules) and general correctness. Each
   finding cites the specific rule by document + id/name, or is a named bug.
4. Generate findings with severity, file:line, description

Example finding: `src/auth/login.py:42 [Critical] Token written to log — data exposure risk`

5. Gate (zero tolerance): Critical=FAIL, Important=WARN, Minor only=PASS. A
   non-trivial diff with zero findings is a FAILED review — look harder.

---

## Audit Mode (`--audit [scope]`)

Scopes: (none)=branch changes (`git diff origin/<detected-target>...HEAD`, three-dot;
see Default Scope & Method), file.py, dir/, security, all

When scope is `(none)` / branch changes, the every-line full-read mandate and gate
posture from **Default Scope & Method** apply: read 100% of the diff, no
grep-sampling, chunk across subagents for large diffs.

**Passes:** Correctness > Security > Performance > Maintainability > Edge Cases

**API Hallucination Detection (Correctness Pass):**

During the Correctness pass, check for API hallucination patterns:

- [ ] Method calls use APIs that exist in the imported library version (not invented methods)
- [ ] Function signatures match actual library definitions (parameter names, types, order)
- [ ] Configuration keys and environment variables are real (not plausible-sounding inventions)
- [ ] Import paths resolve to actual modules (not hallucinated package structures)
- [ ] Return types match actual API contracts (not assumed shapes)

When reviewing AI-generated code, these checks are elevated to HIGH severity. LLMs frequently generate syntactically valid but non-existent API calls that pass linting but fail at runtime.

Output: Executive Summary, findings by category (same severity thresholds as Self Mode), Risk Assessment (LOW/MEDIUM/HIGH/CRITICAL)

---

<FORBIDDEN>
- Skip self-review for "small" changes
- Ignore Critical findings
- Dismiss feedback without evidence
- Give vague feedback without file:line
- Approve to avoid conflict
- Rate severity by effort instead of impact
- Review the diff WITHOUT first loading + cataloguing the standards docs (Phase 0) — you cannot flag violations of rules you never read
- Report a finding as "this seems off" without naming the specific rule (document + id/name) it violates, or naming it as a correctness/logic bug
- Grep-sample or skim the diff instead of reading every changed line
- Assume the merge target (e.g. hardcode `main`) instead of detecting it via `gh pr view`
- Use two-dot `target..HEAD` or `git diff target` (includes merged-in target commits) instead of three-dot `target...HEAD`
- Declare a non-trivial branch diff "clean / nothing found" — that is a failed review, not a pass
</FORBIDDEN>

## Self-Check

- [ ] Correct mode identified
- [ ] All findings have file:line
- [ ] Severity based on impact, not effort
- [ ] Output matches mode spec

<FINAL_EMPHASIS>
Every finding without file:line is noise. Every severity inflated by effort is a lie. Your credibility as a reviewer depends on signal quality — accurate severity, concrete evidence, zero false positives that waste developer time.
</FINAL_EMPHASIS>

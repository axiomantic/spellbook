---
name: code-review
description: "Use when the user EXPLICITLY asks for a lightweight pass, or for feedback/audit modes. Triggers: 'quick review', 'light review', 'look over this', '--quick', 'check my work', 'self-review before PR', 'review my code', 'audit this code', 'PR comments to address', 'reviewer said', 'address feedback', 'review PR #X comments'. NOT for: unspecified-scope branch review such as 'review this branch' or 'code review' (that DEFAULTS to advanced-code-review), or PR triage and summarization (use distilling-prs). This skill is the explicit opt-in to a lighter pass; if the user did not ask for lightweight by name, do not use it. Never bypass the review skills for a raw Explore dispatch, even when the user's concerns seem narrow or specific."
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

## Tool Integration

Use `gh` CLI for PR operations (fetching, reviewing, replying). For diffs, use native `git diff` / `git show`. Fallback: gh unavailable -> local git diff -> manual paste.

---

## Diff Acquisition

<CRITICAL>
Never hand-roll the merge base. `scripts/branch-context.sh` (POSIX) and
`scripts/branch-context.py` (cross-platform) own base detection, the pre-base
`git fetch`, and provenance reporting. Shell out to one of them.

**No base literal appears in this skill.** Never write a default-branch name
(the usual two) into a ref, a `--base` default, or a `git merge-base` argument.
A literal base errors outright on repos whose default branch differs, and models
paste what they are given.
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

### Axis 2 — ENDPOINT (task-dependent)

| Task | Endpoint | Subcommand |
|------|----------|------------|
| Reviewing what will merge | committed only | `diff-committed` |
| Describing what the branch does (changelog, PR body) | include working tree | `diff` |
| Pre-commit self-review | include working tree | `diff` |

"Branch diff" is **not** a name for both. Say which endpoint you used.

### Reporting requirement

<CRITICAL>
Every review MUST report the base it used AND how that base was resolved. The
script prints this provenance to stderr for `diff`, `diff-committed`, `log`,
`stat`, `stat-committed`, `files`, `files-committed`, `base`, and `target`;
`resolution` and `json` put it on stdout. (`diff-uncommitted` is the one
endpoint with no base to report — it diffs against HEAD.)
Capture it and surface it in your output:

```
Base: <merge_target> @ <merge_base[:12]> (resolved via <resolved_via>, fetch <fetch>)
Endpoint: <committed-only | includes working tree>
```

If `resolved_via` is `fallback-literal`, or `fetch` is not `ok`, say so
prominently — the base may be wrong or stale. Silent fallback is the exact
failure this procedure exists to prevent.
</CRITICAL>

---

## Self Mode (`--self`)

<reflection>
Self-review finds what you missed. Assume bugs exist. Hunt them.
</reflection>

**Workflow:**
1. Get the diff via `branch-context.sh` (see the "Diff Acquisition" section).
   Pre-commit self-review includes the working tree, so use the `files` /
   `diff` endpoint pair:

   ```bash
   "$SPELLBOOK_DIR/scripts/branch-context.sh" files
   "$SPELLBOOK_DIR/scripts/branch-context.sh" diff
   ```

2. Multi-pass: Logic > Integration > Security > Style
3. Generate findings with severity, file:line, description

Example finding: `src/auth/login.py:42 [Critical] Token written to log — data exposure risk`

4. Gate: Critical=FAIL, Important=WARN, Minor only=PASS

---

## Audit Mode (`--audit [scope]`)

Scopes: (none)=branch changes, file.py, dir/, security, all

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
- Hardcode a base ref or a default-branch name instead of shelling out to `branch-context.sh`
- Report findings without stating the base used and how it was resolved
- Use "branch diff" without saying which endpoint (committed-only vs. working tree)
</FORBIDDEN>

## Self-Check

- [ ] Correct mode identified
- [ ] Base obtained via `branch-context.sh` — no hardcoded base literal
- [ ] Base, `resolved_via`, and fetch status reported in output
- [ ] Endpoint (committed-only vs. working tree) chosen deliberately and stated
- [ ] All findings have file:line
- [ ] Severity based on impact, not effort
- [ ] Output matches mode spec

<FINAL_EMPHASIS>
Every finding without file:line is noise. Every severity inflated by effort is a lie. Your credibility as a reviewer depends on signal quality — accurate severity, concrete evidence, zero false positives that waste developer time.
</FINAL_EMPHASIS>

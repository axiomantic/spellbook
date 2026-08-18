# code-review

Quick code review covering correctness, style, and common issues across four modes: self-review before PRs, processing received feedback, reviewing others' code, and deep audit passes. Catches real issues with file-and-line references and honest severity classification. A core spellbook capability for routine review of changes before committing.

**Auto-invocation:** Your coding assistant will automatically invoke this skill when it detects a matching trigger.

> Use when the user EXPLICITLY asks for a lightweight pass, or for feedback/audit modes. Triggers: 'quick review', 'light review', 'look over this', '--quick', 'check my work', 'self-review before PR', 'review my code', 'audit this code', 'PR comments to address', 'reviewer said', 'address feedback', 'review PR #X comments'. NOT for: unspecified-scope branch review such as 'review this branch' or 'code review' (that DEFAULTS to advanced-code-review), or PR triage and summarization (use distilling-prs). This skill is the explicit opt-in to a lighter pass; if the user did not ask for lightweight by name, do not use it. Never bypass the review skills for a raw Explore dispatch, even when the user's concerns seem narrow or specific.
## Skill Content

````markdown
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

<CRITICAL>
**With `--pr <num>`, load the `reviewing-prs` skill BEFORE dispatching any
review subagent.** It owns `review_source` (`LOCAL_FILES` vs `DIFF_ONLY`) and
the mandatory PR-review context block every dispatched subagent must receive.
A `REFUTED` verdict produced by reading a local file in `DIFF_ONLY` mode is a
wrong verdict — the local tree is on a different branch, so a real bug the PR
introduced reads as absent.
</CRITICAL>

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

## Phase 0 — Load and Catalogue the Standards FIRST

A review cannot catch violations of rules it has not read. Before computing the
diff or reading a single changed line:

1. **Discover and read the repository's own standards documents.** They vary per
   repository, so find them rather than assuming a fixed set. Typical locations
   include a coding-standards document, testing instructions, code-review
   instructions, the root `AGENTS.md`, and every subdirectory `AGENTS.md`
   covering a changed path. Also read whatever those documents reference:
   contributing guides, style guides, and lint configuration. If a document you
   expected is absent, note that and adapt; if the repository carries standards
   documents you did not expect, load those too.
2. **Read the operator's standing rules** and any project memory the environment
   provides.
3. **Extract a concrete, NAMED rule catalogue** — the enforceable rules with
   whatever identifiers or names the documents give them. That catalogue is the
   checklist the review runs against.
4. **Every finding names the rule it violates** — the document plus the rule's
   identifier or name — or it is a named correctness or logic bug. No vague
   "this seems off": cite the standard.

Finding *no* standards document is not a failure — record it, proceed, and raise
no style or convention findings. Skipping the load is: a review that never cites
a loaded rule by name is not a review.

## Scope Obligation

Consume every changed hunk in every changed file and hold each against the
catalogue from Phase 0. No grep-sampling. No skimming. No "I read the hot files."
Grep is fine to LOCATE things; it is never a substitute for reading the whole
diff. For a large diff, chunk it across subagents so that 100% of the diff is
assigned and read line by line; track file and hunk coverage and be able to prove
no file went unread.

When the user names a narrower scope — a single file, a specific function, one
subsystem, a numbered pull request, staged changes only — honor that scope
instead. The full-read obligation is the default for an unspecified scope, not an
override of an explicit one.

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

### Audit Posture — zero tolerance

An audit is a GATE, not a courtesy pass. This posture governs `--audit` only; the
other modes of this skill are the explicit opt-in to a lighter pass and keep
ordinary judgement about what is worth raising.

- Surface ANY deviation: rule violation, logic bug, design smell, untested
  behavior, inconsistency — anything off.
- Be **adversarial**. Verify each finding to filter false positives, but
  **default to flagging** when in doubt.
- An audit that "found nothing" on a non-trivial diff is a **FAILED audit**, not
  a clean one. Treat an empty finding list as evidence about the audit, not
  about the code.

**Build the failure. Do not just check the author's claim.** Both actions cost
the same dispatch. Building the failure finds more problems.

- Ask "can I make this fail?" Do not ask "does this pass?" The second question
  only checks the author's own transcript. The first question does not.
- A check that has never failed is not proven. If nobody has watched a check's
  failure path fire, the check is a claim, not a mechanism.
- For a claimed clean result — a mutation that should change nothing, a guard
  that should stay silent — prove the change reached the code under test. A
  no-op edit looks the same as a correct no-effect. Only the exit status cannot
  tell them apart.
- Reproduce the defect before you fix it. If you never saw the gap yourself, you
  are guessing at the gap. A guessed fix cannot be tested.

**Observed.** One guard failed four times, in four versions, each broken one level deeper than the last. Version 1 baked a path in at configure time; a reviewer defeated it by copying the tree. Version 2 replaced the real check with a flag; the reviewer deleted the check but kept the flag set. Version 3 checked a token at the end of the branch; the reviewer deleted one part of the branch and kept the token. Version 4 used per-site counters. Every version passed its own author's tests. A reviewer who rebuilt the failure — not one who reran the author's tests — broke every version. Separately, a reviewer built three silent failure modes in an isolated copy of the code. This method found a false-pass path that four prior readings of the same file had missed.

**The known cost, stated plainly:** this posture produces more findings, and some
of them will be noise. That trade is the point of the posture, and it is why it
scopes to `--audit` rather than to every mode of this skill.

**API Hallucination Detection (Correctness Pass):**

During the Correctness pass, check for API hallucination patterns:

- [ ] Method calls use APIs that exist in the imported library version (not invented methods)
- [ ] Function signatures match actual library definitions (parameter names, types, order)
- [ ] Configuration keys and environment variables are real (not plausible-sounding inventions)
- [ ] Import paths resolve to actual modules (not hallucinated package structures)
- [ ] Return types match actual API contracts (not assumed shapes)

When reviewing AI-generated code, these checks are elevated to HIGH severity. LLMs frequently generate syntactically valid but non-existent API calls that pass linting but fail at runtime.

Output: Executive Summary, findings by category (same severity thresholds as Self Mode), Risk Assessment (LOW/MEDIUM/HIGH/CRITICAL)

**Test-quality scope:** if the audit scope includes judging whether tests would catch regressions, dispatch a subagent invoking auditing-green-mirage for those tests; do not run mutation reasoning inline.

---

<FORBIDDEN>
- Skip self-review for "small" changes
- Ignore Critical findings
- Dismiss feedback without evidence
- Give vague feedback without file:line
- Generate any finding before Phase 0 has loaded and catalogued the standards
- Report a style or convention finding when the standards load found nothing
- Substitute grep for reading a hunk (grep LOCATES; it never COVERS)
- Sample the diff and treat the remainder as covered
- Approve to avoid conflict
- Rate severity by effort instead of impact
- Hardcode a base ref or a default-branch name instead of shelling out to `branch-context.sh`
- Report findings without stating the base used and how it was resolved
- Use "branch diff" without saying which endpoint (committed-only vs. working tree)
- Assess whether a test is a green mirage with an inline/ad hoc mutation
  table. Test-quality verdicts MUST come from a dispatch that invokes the
  auditing-green-mirage skill. An inline mutation check in this project
  class has already produced a false "robust" verdict that a dedicated
  audit reversed.
</FORBIDDEN>

## Self-Check

- [ ] Correct mode identified
- [ ] Phase 0 completed: standards discovered, read, catalogued by name (or absence recorded)
- [ ] Every changed hunk read; no grep-sampling; coverage provable
- [ ] Base obtained via `branch-context.sh` — no hardcoded base literal
- [ ] Base, `resolved_via`, and fetch status reported in output
- [ ] Endpoint (committed-only vs. working tree) chosen deliberately and stated
- [ ] All findings have file:line
- [ ] Severity based on impact, not effort
- [ ] Output matches mode spec

<FINAL_EMPHASIS>
Every finding without file:line is noise. Every severity inflated by effort is a lie. Your credibility as a reviewer depends on signal quality — accurate severity, concrete evidence, zero false positives that waste developer time.
</FINAL_EMPHASIS>
````

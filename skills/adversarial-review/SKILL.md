---
name: adversarial-review
description: "Use when dispatching a subagent to re-check work against external feedback (PR review comments, audit findings, multi-comment review cycles, 'did I really address X' verifications). Triggers: 'verify all the review comments are addressed', 'check that I really fixed all the audit findings', 'did I miss anything from the reviewer', 'final check before re-review', 'verify cycle N review'. NOT for: writing the initial response to a review (use code-review), or self-reviewing your own design (use devils-advocate)."
intro: |
  Corrective for the failure mode where a "verify each review comment" dispatch returns unanimous AGREE while obvious violations of the reviewer's underlying principles survive untouched. The naive prompt produces confirmation-shaped output: row-scoped tunnel vision, confirmation bias from pre-supplied greps, audit-doc-shaped scope, and uncritical unanimity. This skill rewrites the dispatched prompt to extract meta-principles, scope to the full diff, derive its own evidence, and force a disagreement quota.
---

<ROLE>
Adversarial Review Architect. The agent you are dispatching is about to act as a rubber stamp unless you structure the prompt against that gravity. Your job is to make confirmation impossible — not by reminding the agent to "be thorough," but by giving it a workflow whose shape forbids the easy answer.
</ROLE>

<analysis>
Verification dispatches gravitate toward unanimous agreement: row-scoped tunnel vision, confirmation bias from pre-supplied greps, audit-doc-shaped scope, and reflexive unanimity. This skill rewrites the dispatched prompt so its shape forbids the easy answer — principle extraction first, diff-scoped evidence, mandatory disagreement quota, separate additions pass.
</analysis>

## Why this skill exists

A naive verification dispatch fails in five reinforcing ways. Every clause of the dispatched prompt must counter one of them.

| Failure mode | Mechanism | Counter |
|---|---|---|
| Row-scoped tunnel vision | Agent verifies only the lines the reviewer cited; never extracts the principle the citations imply. | Principle extraction first; per-row work second. |
| Confirmation bias from supplied greps | Requester hands the agent greps as "evidence to fact-check." Agent runs them, gets the expected result, declares VERIFIED. | Forbid pre-supplied greps. Agent derives its own. |
| Audit-doc-shaped scope | Agent reviews against the N rows of a self-audit doc. Anything in the diff but not in the audit is invisible. | Scope is the diff. Audit is a cross-check, not the source of truth. |
| Unanimity not flagged | 26/26 AGREE looks like quality but is the signature of confirmation. | Mandatory disagreement quota: identify weakest links and stress-test them. |
| No explicit additions pass | Newly ADDED lines (not just changed ones) are most likely to violate principles the reviewer hasn't cited yet. | Force a separate pass over `git diff | grep '^+'` lines. |

## Invariant Principles

1. **Scope is the diff, not the audit.** `git diff <merge-base>` defines what is in scope. A self-audit doc is a cross-check, never the boundary.
2. **Principles before rows.** Distill the reviewer's meta-rules first. Apply them project-wide. Then descend to per-row verdicts.
3. **The agent derives its own evidence.** Pre-supplied search terms test the requester's framing, not the codebase's state.
4. **Unanimity is a smell.** Genuine adversarial review surfaces edge cases even when the verdict is overall AGREE.
5. **Additions deserve their own pass.** Lines the requester ADDED in the same session as the audit are the highest-risk surface for unflagged violations.

---

## When to invoke

Load this skill BEFORE dispatching a subagent for any of:

- "Verify all N review comments are addressed" against a PR review.
- "Confirm all audit findings are resolved" against an audit doc.
- Multi-comment review cycles where a reviewer has left ≥5 inline comments.
- Pre-`@<reviewer>` re-request checks before asking for another review pass.
- Any "did I really fix X" verification against external feedback.

Skip for: self-review of your own design (use `devils-advocate`), initial code review of a branch (use `code-review`), debugging hypothesis verification (use `verifying-hunches`).

## Dispatched prompt: required structure

The dispatched subagent prompt MUST contain these sections in this order. Anything missing → stop and rewrite.

### 1. Scope declaration

```
Scope of this review: the full diff between <merge-base-sha> and the current
working tree. The audit doc at <path> is a cross-check. The diff is the
source of truth. Anything in the diff but missing from the audit is in scope.
```

### 2. Principle extraction (first instruction)

```
Step 1 — before any per-row work:

Read all <N> review comments. For each comment, distill the meta-principle
the reviewer is asserting as a single one-line rule (e.g., "no review
citations in comments", "no narrative about removed branch code", "test
files follow the same comment hygiene as production").

Output the principle list as a numbered list BEFORE proceeding to step 2.
Do not skip this step. Do not summarize principles inline with rows.
```

### 3. Project-wide pass against each principle

```
Step 2 — for each principle from step 1:

Derive your own search terms. Do not use any greps or queries the requester
may have supplied. Search the entire diff (not just the lines the reviewer
cited) for violations.

For each principle, report:
- Search terms you used and why they are the right test for this principle
- Hits (file:line + the offending text)
- For each hit, a verdict: VIOLATION / EDGE-CASE / FALSE-POSITIVE
```

### 4. Additions pass

```
Step 3 — explicit additions audit:

Run: git diff <merge-base> -- '*.<ext>' | grep '^+' | grep -iE '<patterns you derived from step 1>'

These are lines the requester ADDED in this branch. They are the most likely
to violate principles the reviewer has not yet seen. Review every match
against every principle from step 1.

Report each finding with: file:line, the added line, which principle it
violates (if any), and what the fix is.
```

### 5. Per-row verdicts

```
Step 4 — only after steps 1–3:

For each row in the audit doc, give a verdict: ADDRESSED / NOT-ADDRESSED /
PARTIALLY-ADDRESSED / WORSE-THAN-BEFORE. Cite file:line evidence the agent
derived independently (do not reuse the requester's citations as proof).
```

### 6. Disagreement quota

```
Step 5 — mandatory weakest-links pass:

If your verdict across all rows is unanimous (all ADDRESSED, or all AGREE),
re-examine. Identify the three weakest links — the rows where the evidence
is thinnest, the principle is most stretched, or the fix is most likely to
miss adjacent cases. Stress-test each as an adversarial case and report what
you found, even if you still end up agreeing.

Unanimity without a weakest-links section is a process failure.
```

### 7. Grep-skepticism rule

```
For every claim you mark VERIFIED based on a grep returning zero hits:
derive at least two alternative phrasings of the pattern and grep those
too. Zero hits on the literal string proves only that the literal string
is absent — the pattern may live under a different name.
```

### 8. Required output shape

```
Output sections, in order:
1. Principle list (from step 1)
2. Project-wide findings, one section per principle (from step 2)
3. Additions audit (from step 3)
4. Per-row verdicts (from step 4)
5. Weakest links (from step 5)
6. Must-fix list — real risk only, stylistic items in a separate "nice to have" list
```

---

## Anti-patterns: refuse and rewrite

If the dispatched prompt has ANY of these, stop and rewrite it before dispatching:

| Anti-pattern | Why it fails |
|---|---|
| Pre-supplied grep commands as "evidence to fact-check" | The agent runs them and confirms the requester's framing. Independent framing is the part being checked. |
| Scope tied to "the 26 rows in the audit doc" | Audit-doc-shaped scope hides newly added lines and adjacent violations. |
| No principle-extraction step | Without principles, the agent reviews citations, not the rules behind them. |
| No diff-wide or additions pass | Newly added comments and code escape every per-row check. |
| No disagreement quota / weakest-links section | Unanimity becomes the easy path and the most likely outcome. |
| "Verify each finding is addressed" with no instruction on how the agent should derive evidence | Defaults to confirming what the requester wrote. |

<FORBIDDEN>
- Passing the requester's own search commands ("here are the greps I ran, fact-check them") into the agent prompt
- Bounding the scope to the audit doc's row count when the diff contains more
- Treating a unanimous AGREE verdict as sufficient without a weakest-links pass
- Letting the agent verify only the file:line the reviewer cited (vs. the principle the citation implies)
- Skipping the additions audit when the requester added code in the same session as the audit doc
</FORBIDDEN>

---

## Self-Check

<reflection>
Before dispatching:
- [ ] Scope is `git diff <merge-base>`, not the audit doc
- [ ] Step 1 is principle extraction, output before any per-row work
- [ ] Agent is instructed to derive its own search terms; no greps are supplied
- [ ] Additions audit (`grep '^+'`) is a separate explicit step
- [ ] Disagreement quota is mandatory; weakest-links section required even on unanimous AGREE
- [ ] Grep-skepticism rule present (≥2 alternative phrasings per VERIFIED-by-grep claim)
- [ ] Output shape: principles → project-wide findings → additions → per-row → weakest links → must-fix
- [ ] No pre-supplied evidence anywhere in the prompt
</reflection>

<FINAL_EMPHASIS>
A naive "verify each row" prompt produces confirmation. The structural defense is principle-extraction first, diff-wide scope, agent-derived evidence, and a forced disagreement quota. Without these, 26/26 AGREE is the predictable output — and the violations the reviewer hasn't cited yet are guaranteed to survive.
</FINAL_EMPHASIS>

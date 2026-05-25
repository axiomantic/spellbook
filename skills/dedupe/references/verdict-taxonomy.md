# Verdict Taxonomy + INLINE-MANDATORY Predicate

**This file is the SINGLE canonical home** for the /dedupe verdict taxonomy and
the INLINE-MANDATORY predicate. The SKILL and every `dedupe-*` command reference
this file **by path** and never restate its contents inline. (Re-stating any of
these definitions elsewhere would be /dedupe duplicating its own core
definitions — the exact anti-pattern the tool exists to remove, M6 anti-irony.)

---

## The 5-Verdict Taxonomy

The classifier assigns exactly one verdict per candidate pair (design §4.2):

| Verdict | Meaning | Apply behavior |
|---------|---------|----------------|
| `EXTRACT` | Accidental duplication; consolidating to one canonical home loses nothing. | Eligible for replace-with-reference (subject to the INLINE-MANDATORY screen below). |
| `KEEP-placement` | Repetition is load-bearing because of WHERE it appears (just-in-time at point of use). | Keep both. |
| `KEEP-reinforcement` | Deliberate defense-in-depth restatement; the multiplicity itself carries meaning. | Keep both. |
| `KEEP-contextual` | Surface text overlaps but the two serve different local purposes. | Keep both. |
| `RECONCILE-drifted` | Copies have diverged (drift); a latent bug. | NEVER auto-resolve; surface for human reconciliation (drift section of the report). |

Only `EXTRACT` is eligible for automated consolidation, and only after it
survives the INLINE-MANDATORY screen below. Every `KEEP-*` verdict means both
occurrences stay exactly where they are. `RECONCILE-drifted` is never applied —
it is surfaced as a bug for a human to reconcile.

---

## The INLINE-MANDATORY Predicate (C6, CRITICAL)

Before any pair may receive an `EXTRACT`-to-Read-on-demand routing, it is
screened by the INLINE-MANDATORY predicate, computed **mechanically** by
`dedupe.py` so it does not depend on the classifier's judgment (design §4.4).

A block is INLINE-MANDATORY if **ANY** of the following three clauses holds:

1. **Safety/criticality marker.** The block contains a safety or criticality
   marker token (surfaced as `contains_safety_marker` in the detect JSON).
2. **Imperative safety language.** The block uses imperative safety language
   directed at the agent (e.g. "you MUST", "NEVER do X", "ALWAYS check").
3. **Positional in-flow guard (enclosing-section test, as shipped).** The block
   *encloses* a dangerous action — a danger line `L` from the dangerous-action
   denylist falls within the block's own span (`start_line <= L <= end_line`). A
   heading-section block that contains a dangerous-action line is an in-flow
   guard for that action and must stay inline. (The default segmenter folds a
   sub-floor guard paragraph into its enclosing heading-section block, which then
   *encloses* the danger line.)

   > **DEFERRED (design §4.4, plan "Task 7").** The stricter child-level variant
   > — a child block whose `parent_key` equals the *danger line's*
   > enclosing-section `block_id` and whose `end_line` **strictly precedes** the
   > danger line (`end_line` < dangerous-line) — is a tracked follow-up, not the
   > current behavior. It needs per-line parent membership, which the chosen
   > `all_lines={line: text}` boundary does not carry. The enclosing-section test
   > above is the MVP behavior `dedupe.py` actually ships.

### Safety-marker list

The marker tokens (case-insensitive; configurable denylist in the script,
surfaced as `contains_safety_marker`):

- `CRITICAL`
- `FORBIDDEN`
- `<RULE>`
- `<CRITICAL>`
- `NEVER`
- `ALWAYS`
- `MUST NOT`
- "Inviolable"
- "Git Safety"
- similar imperative-safety tokens

### Dangerous-action denylist

A heading-section line matching any of these (case-insensitive, matched as
whole-word/command tokens to avoid substring false positives) is treated as a
dangerous action for Clause 3. This is a module-level constant in the MVP; the
`--danger-denylist` override flag is a deferred follow-up:

- `git push`
- `rm` (and `rm -rf`)
- `apply` (e.g. `/dedupe-apply`, `terraform apply`, `kubectl apply`)
- `delete` / `--delete`
- `force` / `--force` / `-f`
- `reset --hard`
- `git commit`, `git checkout`, `git rebase`, `git merge`, `git stash`
- `drop`, `truncate` (destructive DB verbs)
- `chmod`, `chown` (permission changes)

### Consequences

- An INLINE-MANDATORY block is **NEVER** routed to Read-on-demand
  (`skills/shared-references/` or a per-skill `references/`). A
  referenced-but-unread file costs 0 tokens precisely because it is not loaded —
  which is exactly the wrong property for an in-flow safety rule.
- INLINE-MANDATORY blocks may ONLY be (a) KEPT in place, or (b) consolidated to
  an **always-on** home (`CLAUDE.md`), and even then only **human-flagged**,
  never auto-applied (see the routing table in `dedupe-apply` / `dedupe-report`).
- Read-on-demand is reserved for reference/explanatory content; never for
  imperative in-flow rules.

### Low-confidence-safety backstop

Any block carrying a safety marker **defaults to KEEP regardless of the
classifier's self-reported confidence.** Confidence is one input, never the sole
gate. This structural predicate is the backstop that pairs with C6: even a
*confident* `EXTRACT` on a safety block is overridden to KEEP (or human-flagged
to `CLAUDE.md`). When in doubt about whether a block is a safety rule, the
default is KEEP.

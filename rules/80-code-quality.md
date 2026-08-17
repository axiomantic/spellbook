---
id: code-quality
name: Code Quality
class: preference
default: "on"
description: >
  The standing quality bar for produced code, the comment discipline that keeps
  stale claims out of source files, and the rule against silently skipping
  pre-existing issues.
benefit: >
  No `any` types, no blanket try/catch, no test shortcuts, no resource leaks,
  and no counts or coverage claims in comments that go stale on the next change.
declining_means: >
  The agent applies no standing quality bar beyond the harness default, may
  write counts and coverage claims into comments, and may pass over
  pre-existing issues without mentioning them.
related:
  - skills/enforcing-code-quality
renamed_from: []
superseded_by: null
paths: []
---

## Code Quality

<RULE>No `any` types, no blanket try-catch, no test shortcuts, no resource leaks, no non-null assertions without validation. Read existing patterns first. Production-quality or nothing.</RULE>

If you encounter pre-existing issues, do NOT skip them. Ask if the user wants them fixed. Users usually say yes, so propose the fix alongside the question.

### Comments

<RULE>Comments are sparse. Write one only where a reader must otherwise reconstruct a DECISION. The code says what it does. The comment says why you chose it instead of the alternative.</RULE>

<FORBIDDEN>
- A count in a comment — cases, tests, scenarios, mutations, symbols, files, or lines. The next change makes the count wrong, and nothing catches it.
- A present-tense claim about what the tests cover, or about what a wrong implementation would fail. If coverage matters, assert it in a test. A failing test is the only durable statement about coverage.
- A note about history ("this used to...", "the previous version..."). Git holds that.
</FORBIDDEN>

**One exception, and it is the only one.** A number that a mechanism reads and checks at build time or at test time may stay. The check is then the source of truth, not the comment, and it fails loudly when the number drifts. A number that no mechanism reads is a liability.

**A date does not rescue a stale claim.** Within a day of churn, a date discriminates nothing.

**Applies to code you write.** In a fork or a vendored tree, leave the comments that came from upstream. Repair a comment you made wrong; do not sweep comments you did not author.

**Observed.** One review-and-repair loop fired four times on a single class of defect. Each repair arrived with a new claim about the tree that outran what was measured — a suite size, a coverage assertion. Two mechanisms and one prose convention were built to stop it, and none did. Every dated claim in the affected files carried the same date, because the suite changed several times in that one day. One figure had its number re-derived and its date left alone, so it advertised a measurement older than both changes it was wrong about. The machinery built to verify these claims grew larger than the code it guards. **What did work was a registry that pins a mutation's red count and is CHECKED at test time** — it caught a test weakened from a whole-tuple comparison to a single boolean while every other gate stayed silent. That is the one exception this module allows, and it earned its place.

Load `enforcing-code-quality` skill for full standards and checklist.

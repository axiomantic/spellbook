---
id: review-posture
name: Review Posture (Zero Tolerance)
class: preference
default: "off"
description: >
  An adversarial, zero-tolerance quality-gate posture for code review.
benefit: >
  Treats review as a gate: surfaces every deviation and defaults to flagging.
declining_means: >
  Reviews use ordinary judgement about what is worth raising, which produces fewer
  findings and fewer false positives.
related:
  - skills/code-review
  - skills/advanced-code-review
  - agents/code-reviewer
renamed_from: []
superseded_by: null
paths: []
---

## Review Posture

<RULE>A review is a GATE, not a courtesy pass. Be extremely discerning and apply zero tolerance.</RULE>

- Surface ANY deviation: rule violation, logic bug, design smell, untested behavior,
  inconsistency — anything off.
- Be **adversarial**. Verify each finding to filter false positives, but **default to flagging**
  when in doubt.
- A review that "found nothing" on a non-trivial diff is a **FAILED review**, not a clean one.
  Treat an empty finding list as evidence about the review, not about the code.

<RULE>Build the failure. Do not just check the author's claim. Both actions cost the same dispatch. Building the failure finds more problems.</RULE>

- Ask "can I make this fail?" Do not ask "does this pass?" The second question only checks the author's own transcript. The first question does not.
- A check that has never failed is not proven. If nobody has watched a check's failure path fire, the check is a claim, not a mechanism.
- For a claimed clean result — a mutation that should change nothing, a guard that should stay silent — prove the change reached the code under test. A no-op edit looks the same as a correct no-effect. Only the exit status cannot tell them apart.
- Reproduce the defect before you fix it. If you never saw the gap yourself, you are guessing at the gap. A guessed fix cannot be tested.

**Observed.** One guard failed four times, in four versions, each broken one level deeper than the last. Version 1 baked a path in at configure time; a reviewer defeated it by copying the tree. Version 2 replaced the real check with a flag; the reviewer deleted the check but kept the flag set. Version 3 checked a token at the end of the branch; the reviewer deleted one part of the branch and kept the token. Version 4 used per-site counters. Every version passed its own author's tests. A reviewer who rebuilt the failure — not one who reran the author's tests — broke every version. Separately, a reviewer built three silent failure modes in an isolated copy of the code. This method found a false-pass path that four prior readings of the same file had missed.

**The known cost, stated plainly:** this posture produces more findings, and some of them will
be noise. That trade is the point of the posture, and it is why this module is opt-in rather
than installed by default.

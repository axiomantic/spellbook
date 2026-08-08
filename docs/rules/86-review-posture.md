# Review Posture (Zero Tolerance)

!!! info "Optional module"
    The installer offers this module unchecked. Config key: `rules.module.review-posture`.

An adversarial, zero-tolerance quality-gate posture for code review.

**Why keep it:** Treats review as a gate: surfaces every deviation and defaults to flagging.

**If you decline:** Reviews use ordinary judgement about what is worth raising, which produces fewer findings and fewer false positives.

**Related artifacts:**

- `skills/code-review`
- `skills/advanced-code-review`
- `agents/code-reviewer`

## Rule Content

``````````markdown
## Review Posture

<RULE>A review is a GATE, not a courtesy pass. Be extremely discerning and apply zero tolerance.</RULE>

- Surface ANY deviation: rule violation, logic bug, design smell, untested behavior,
  inconsistency — anything off.
- Be **adversarial**. Verify each finding to filter false positives, but **default to flagging**
  when in doubt.
- A review that "found nothing" on a non-trivial diff is a **FAILED review**, not a clean one.
  Treat an empty finding list as evidence about the review, not about the code.

**The known cost, stated plainly:** this posture produces more findings, and some of them will
be noise. That trade is the point of the posture, and it is why this module is opt-in rather
than installed by default.
``````````

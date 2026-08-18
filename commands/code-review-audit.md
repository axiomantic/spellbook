---
description: "Audit mode for code-review: multi-pass deep-dive with zero-tolerance posture, API hallucination detection, and risk assessment"
---

# Code Review: Audit Mode (`--audit [scope]`)

<ROLE>
Code Review Specialist running the deepest pass this skill offers. An audit is the
gate a change passes before it is trusted. A defect you wave through here reaches
production with your approval attached to it.
</ROLE>

<analysis>
Audit is the one mode of code-review that is not a lighter pass. Scope decides how
much surface the passes cover; posture decides how hard each pass pushes.
</analysis>

<reflection>
Did I try to make each mechanism fail, or did I only re-run the author's checks?
Is an empty finding list evidence about the code, or about the audit?
</reflection>

## Invariant Principles

1. **Zero tolerance** — surface any deviation; the noise cost is accepted deliberately.
2. **Build the failure** — a check nobody has watched fail is a claim, not a mechanism.
3. **Evidence Over Assertion** — every finding needs a file:line reference.
4. **Severity Honesty** — Critical=security/data loss; Important=correctness; Minor=style.

## Scopes

`(none)`=branch changes, `file.py`, `dir/`, `security`, `all`

**Passes:** Correctness > Security > Performance > Maintainability > Edge Cases

## Audit Posture — zero tolerance

An audit is a GATE, not a courtesy pass. This posture governs `--audit` only; the
other modes of `code-review` are the explicit opt-in to a lighter pass and keep
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
scopes to `--audit` rather than to every mode of `code-review`.

## API Hallucination Detection (Correctness Pass)

During the Correctness pass, check for API hallucination patterns:

- [ ] Method calls use APIs that exist in the imported library version (not invented methods)
- [ ] Function signatures match actual library definitions (parameter names, types, order)
- [ ] Configuration keys and environment variables are real (not plausible-sounding inventions)
- [ ] Import paths resolve to actual modules (not hallucinated package structures)
- [ ] Return types match actual API contracts (not assumed shapes)

When reviewing AI-generated code, these checks are elevated to HIGH severity. LLMs frequently generate syntactically valid but non-existent API calls that pass linting but fail at runtime.

## Output

Executive Summary, findings by category (same severity thresholds as Self Mode),
Risk Assessment (LOW/MEDIUM/HIGH/CRITICAL).

**Test-quality scope:** if the audit scope includes judging whether tests would
catch regressions, dispatch a subagent invoking auditing-green-mirage for those
tests; do not run mutation reasoning inline.

<FORBIDDEN>
- Treating an empty finding list on a non-trivial diff as a clean result rather than a failed audit
- Suppressing a finding to avoid noise — this posture accepts the noise deliberately
- Re-running the author's own checks and calling that verification
- Assess whether a test is a green mirage with an inline/ad hoc mutation
  table. Test-quality verdicts MUST come from a dispatch that invokes the
  auditing-green-mirage skill. An inline mutation check in this project
  class has already produced a false "robust" verdict that a dedicated
  audit reversed.
</FORBIDDEN>

<FINAL_EMPHASIS>
An audit is the last gate before trust. Every finding you suppress to keep the
report tidy is a defect you approved.
</FINAL_EMPHASIS>

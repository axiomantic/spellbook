# Example SOP — Single Rule Original

This is the original (pre-crystallize) source document. It contains exactly
one rule that the verifier will track for byte-fidelity in the corrupted
output.

## Mission

Demonstrate that `/crystallize-verify` catches a one-character drift inside
a rule body.

<RULE>NEVER call `/sharpen-improve` from inside a `develop` subagent.</RULE>

## Phase 1

General guidance for Phase 1 lives here. This is residual prose, not a rule.
The verifier should not flag changes in this paragraph; only rule-body
content is under byte-fidelity contract.

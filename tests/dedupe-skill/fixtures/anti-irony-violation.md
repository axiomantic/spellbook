# Anti-Irony Violation Negative Control Fixture

This fixture deliberately violates each D3 sub-gate. If D3 misses any of
these planted violations, it has a false-negative bug.

## Sub-gate (a): Verdict definitions outside canonical home

NEGATIVE CONTROL — D3(a) must catch this:

EXTRACT: the block is consolidatable across multiple homes.

NEGATIVE CONTROL — D3(a) must catch this:

KEEP-placement: stays where it is for navigational reasons.

NEGATIVE CONTROL — D3(a) must catch this:

KEEP-reinforcement - intentional repetition for emphasis.

NEGATIVE CONTROL — D3(a) must catch this:

KEEP-contextual: locally adapted to surrounding text.

NEGATIVE CONTROL — D3(a) must catch this:

RECONCILE-drifted: copies have diverged and need reconciliation.

## Sub-gate (b): Safety markers outside canonical home

NEGATIVE CONTROL — D3(b) must catch this:

| Rule | Marker |
|------|--------|
| `NEVER do X` | <CRITICAL> |
| `ALWAYS Y` | <FORBIDDEN> |
| `MUST verify` | <RULE> |
| `DO NOT skip` | <ROLE> |

The <FINAL_EMPHASIS> tag is for closing remarks. See the Inviolable Rules
section, particularly Git Safety, where the principle of production-quality
or nothing applies.

## Sub-gate (c): Classifier schema fields outside canonical home

NEGATIVE CONTROL — D3(c) must catch this:

```json
{
  "verdict": "EXTRACT",
  "rationale": "consolidates duplicate guidance",
  "confidence": 0.92,
  "counterfactual_loss": "low",
  "inline_mandatory": false,
  "prompt_version": "v1"
}
```

## Sub-gate (d): Segmentation internals outside canonical home

NEGATIVE CONTROL — D3(d) must catch this:

The bucket_key is computed via sha256(first_3_normalized_lines) with the
\x1f field separator. For code blocks the bucket_key prefix is code:python,
and for prose blocks without headings it is <file-stem>:no-headings, or
when marked the form is marked:<file-stem>.

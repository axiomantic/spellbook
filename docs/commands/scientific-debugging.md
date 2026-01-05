# /scientific-debugging

Rigorous theory-experiment debugging methodology using the scientific method.

## Overview

Scientific debugging enforces formal theory-experiment cycles with clear evidence requirements. It's designed for complex issues where the root cause is unclear and multiple hypotheses need systematic testing.

## When to Use

- Complex system failures with unclear root cause
- Intermittent/non-deterministic bugs
- When you need to avoid confirmation bias
- High-stakes debugging where guessing is unacceptable
- Team debugging where methodology must be documented

## Invocation

```
/scientific-debugging
```

Or via the unified debug skill:
```
/debug --scientific
```

## Core Methodology

### 1. Form Exactly 3 Theories

From the symptom description ONLY (no data gathering first):

```markdown
## Theories
1. [Theory 1 - description]
2. [Theory 2 - description]
3. [Theory 3 - description]
```

**Key rules:**
- Exactly 3 theories (not 2, not 5)
- No rankings or probabilities ("most likely", "60%")
- All theories are equal until tested

### 2. Design Experiments

For each theory, design 3+ experiments with explicit criteria:

```markdown
- Experiment 1a: [description]
  - Proves theory if: [specific observable outcome]
  - Disproves theory if: [specific observable outcome]
```

### 3. Execute Systematically

1. Test Theory 1 completely (all experiments)
2. If disproven, move to Theory 2
3. If disproven, move to Theory 3
4. If all disproven, generate 3 NEW theories from experiment data

## Forbidden Patterns

- Gathering data before forming theories (confirmation bias)
- Ranking theories by probability
- Using fewer or more than 3 theories
- Testing Theory 2 before completing Theory 1

## Supporting Files

The command directory includes additional guides:
- No additional supporting files (self-contained methodology)

## Related

- [debug skill](../skills/debug.md) - Unified debugging entry point
- [/systematic-debugging](systematic-debugging.md) - Alternative methodology for clearer bugs
- [/verify](verify.md) - Verification after fix

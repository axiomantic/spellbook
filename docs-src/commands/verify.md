# /verify

Run verification commands and confirm output before making success claims.

## Overview

The verify command enforces "evidence before assertions" - you cannot claim work is complete, fixed, or passing without fresh verification evidence.

## When to Use

- Before claiming tests pass
- Before claiming a bug is fixed
- Before committing or creating PRs
- Before claiming build succeeds
- After any fix attempt
- Before moving to next task

## Invocation

```
/verify
```

This command is also auto-invoked at the end of every `/debug` session.

## The Gate Function

```
1. IDENTIFY: What command proves this claim?
2. RUN: Execute the FULL command (fresh, complete)
3. READ: Full output, check exit code, count failures
4. VERIFY: Does output confirm the claim?
5. ONLY THEN: Make the claim
```

## Common Verification Requirements

| Claim | Requires | Not Sufficient |
|-------|----------|----------------|
| Tests pass | Test command output: 0 failures | Previous run, "should pass" |
| Linter clean | Linter output: 0 errors | Partial check |
| Build succeeds | Build command: exit 0 | Linter passing |
| Bug fixed | Test original symptom: passes | Code changed |
| Regression test works | Red-green cycle verified | Test passes once |

## Red Flags

- Using "should", "probably", "seems to"
- Expressing satisfaction before verification
- About to commit/push/PR without verification
- Trusting agent success reports
- Relying on partial verification
- "Just this once"

## Key Patterns

**Tests:**
```
[Run test command] [See: 34/34 pass] "All tests pass"
```

**Regression tests (TDD Red-Green):**
```
Write -> Run (pass) -> Revert fix -> Run (MUST FAIL) -> Restore -> Run (pass)
```

## Related

- [debug skill](../skills/debug.md) - Auto-invokes verify after debugging
- [test-driven-development](../skills/test-driven-development.md) - TDD workflow

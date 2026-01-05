# debug

Unified debugging entry point that triages issues and routes to the appropriate methodology.

## Overview

The `debug` skill is the single entry point for ALL debugging scenarios. It intelligently selects between scientific and systematic debugging based on issue characteristics, enforces the 3-fix rule, and ensures verification before completion.

## When to Use

- ANY bug, test failure, or unexpected behavior
- When you're not sure which debugging approach to use
- When you've already tried multiple fixes (3-fix rule enforcement)

## Invocation

```
/debug                  # Full triage and methodology selection
/debug --scientific     # Skip triage, use scientific debugging
/debug --systematic     # Skip triage, use systematic debugging
```

## Key Features

### Triage Phase

Asks questions to understand:
- Symptom type (error, test failure, unexpected behavior, intermittent)
- Reproducibility (every time, sometimes, never)
- Prior fix attempts

### Methodology Selection

| Situation | Recommended Approach |
|-----------|---------------------|
| Intermittent/flaky issues | Scientific debugging |
| Unclear root cause, multiple theories | Scientific debugging |
| Clear error with stack trace | Systematic debugging |
| Test failures | Systematic debugging |
| 3+ failed fix attempts | Architecture review |

### 3-Fix Rule

After 3 failed fix attempts, the skill enforces a pause:

> **3-FIX RULE THRESHOLD REACHED**
>
> You've attempted 3+ fixes without resolving this issue.
> This is a strong signal the problem may be architectural.

Options presented:
- Stop debugging, investigate architecture
- Continue with explicit acknowledgment
- Escalate to human architect
- Create spike ticket

### Auto-Verification

Every debug session automatically invokes the `/verify` command at completion to ensure the fix actually works.

## Related Commands

- [/scientific-debugging](../commands/scientific-debugging.md) - Rigorous theory-experiment methodology
- [/systematic-debugging](../commands/systematic-debugging.md) - 4-phase root cause analysis
- [/verify](../commands/verify.md) - Verification before completion claims
- [finishing-a-development-branch](finishing-a-development-branch.md) - Complete development branch

## See Also

- [fix-tests](fix-tests.md) - For test-specific issues
- [test-driven-development](test-driven-development.md) - TDD workflow

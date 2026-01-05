# /systematic-debugging

4-phase root cause debugging methodology focused on finding the actual cause before attempting fixes.

## Overview

Systematic debugging enforces a disciplined 4-phase approach: investigate root cause, analyze patterns, form and test hypotheses, then implement fixes. The core principle is "NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST."

## When to Use

- Test failures after code changes
- Bugs with clear error messages and stack traces
- Production bugs under time pressure
- Build failures
- Integration issues

## Invocation

```
/systematic-debugging
```

Or via the unified debug skill:
```
/debug --systematic
```

## The Four Phases

### Phase 1: Root Cause Investigation

BEFORE attempting ANY fix:

1. **Read error messages carefully** - Complete stack traces, line numbers
2. **Reproduce consistently** - Exact steps, every time?
3. **Check recent changes** - Git diff, dependencies, config
4. **Gather evidence in multi-component systems** - Log inputs/outputs at boundaries
5. **Trace data flow** - Where does the bad value originate?

### Phase 2: Pattern Analysis

1. Find working examples in same codebase
2. Compare against references
3. Identify ALL differences
4. Understand dependencies

### Phase 3: Hypothesis and Testing

1. Form single hypothesis: "I think X because Y"
2. Test minimally (smallest possible change)
3. One variable at a time
4. Verify before continuing

### Phase 4: Implementation

1. Create failing test case FIRST
2. Implement single fix
3. Verify fix works
4. **If 3+ fixes failed: Question architecture**

## The 3-Fix Rule

If you've tried 3+ fixes without success:

> STOP. This is not a bug - this is an architectural problem.

Signs:
- Each fix reveals new issue in different location
- Fixes require "massive refactoring"
- Each fix creates new symptoms elsewhere

## Red Flags

- "Quick fix for now, investigate later"
- "Just try changing X"
- Adding multiple changes at once
- "One more fix attempt" after 2+ failures

## Supporting Files

The command directory includes additional guides:

- `root-cause-tracing.md` - Backward tracing technique
- `defense-in-depth.md` - Multi-layer validation
- `condition-based-waiting.md` - Replace arbitrary timeouts
- `condition-based-waiting-example.ts` - Code example
- `find-polluter.sh` - Test isolation script

## Related

- [debug skill](../skills/debug.md) - Unified debugging entry point
- [/scientific-debugging](scientific-debugging.md) - Alternative for unclear root causes
- [/verify](verify.md) - Verification after fix
- [test-driven-development](../skills/test-driven-development.md) - For Phase 4 test creation

---
name: test-driven-development
description: Use when implementing any feature or bugfix, before writing implementation code
---

# Test-Driven Development

<ROLE>
Quality Engineer with zero-defect mindset. Reputation depends on shipping code that works, not code that "should work."
</ROLE>

## Invariant Principles

1. **Failure Proves Testing** - Test passing immediately proves nothing. Only watching failure proves test detects what it claims.
2. **Order Creates Trust** - Tests-first answer "what should this do?" Tests-after answer "what does this do?" Fundamentally different questions.
3. **Minimal Sufficiency** - Write exactly enough code to pass. YAGNI violations compound into untested complexity.
4. **Deletion Over Adaptation** - Code written before tests is contaminated. Keeping "as reference" means testing after. Delete means delete.

## Inputs

| Input | Required | Description |
|-------|----------|-------------|
| Feature/bugfix description | Yes | What behavior to implement or fix |
| Existing test patterns | No | Project's testing conventions and frameworks |
| API contracts | No | Expected interface signatures |

## Outputs

| Output | Type | Description |
|--------|------|-------------|
| Failing test | File | Test demonstrating missing behavior |
| Minimal implementation | File | Code passing the test |
| Test execution evidence | Inline | Observed failure before green |

## The Iron Law

```
NO PRODUCTION CODE WITHOUT FAILING TEST FIRST
```

Code before test? Delete. Start over. No "reference," no "adapting," no looking at it.

## Reasoning Schema

<analysis>
Before writing ANY code:
- What behavior needs verification?
- What assertion proves that behavior?
- What's the simplest API shape?
</analysis>

<reflection>
After EACH phase:
- RED: Did test fail? Why? Expected failure mode?
- GREEN: Minimal code? No extra features?
- REFACTOR: Still green? Behavior unchanged?
</reflection>

## Red-Green-Refactor

### RED: Write Failing Test

One behavior. Clear name. Real code (mocks only if unavoidable).

```typescript
test('retries failed operations 3 times', async () => {
  let attempts = 0;
  const operation = () => {
    attempts++;
    if (attempts < 3) throw new Error('fail');
    return 'success';
  };
  const result = await retryOperation(operation);
  expect(result).toBe('success');
  expect(attempts).toBe(3);
});
```

Run test. Confirm:
- Fails (not errors)
- Failure message expected
- Fails because feature missing (not typos)

Test passes? Testing existing behavior. Fix test.

### GREEN: Minimal Code

Simplest code to pass. No features, no refactoring, no "improvements."

```typescript
async function retryOperation<T>(fn: () => Promise<T>): Promise<T> {
  for (let i = 0; i < 3; i++) {
    try { return await fn(); }
    catch (e) { if (i === 2) throw e; }
  }
  throw new Error('unreachable');
}
```

Run test. Confirm all tests pass. Output pristine.

### REFACTOR: Clean Up

After green only. Remove duplication, improve names, extract helpers. Keep tests green. Don't add behavior.

## Evidence Requirements

| Claim | Required Evidence |
|-------|-------------------|
| "Test works" | Observed failure output with expected message |
| "Feature complete" | All tests pass, watched each fail first |
| "Refactor safe" | Tests stayed green throughout |

## Anti-Patterns

<FORBIDDEN>
- Code before test
- Test passes immediately
- Can't explain why test failed
- "Just this once" / "already manually tested"
- "Keep as reference" / "adapt existing"
- "Tests after achieve same goals"
- "TDD is dogmatic, being pragmatic"
</FORBIDDEN>

All mean: Delete code. Start over with TDD.

## Common Rationalizations

| Excuse | Reality |
|--------|---------|
| "Too simple to test" | Simple code breaks. Test takes 30 seconds. |
| "I'll test after" | Tests passing immediately prove nothing. |
| "Deleting X hours is wasteful" | Sunk cost. Unverified code is debt. |
| "Need to explore first" | Fine. Throw away exploration, start TDD. |
| "Test hard = design unclear" | Listen to test. Hard to test = hard to use. |

## Self-Check

Before marking complete:
- [ ] Every function has test
- [ ] Watched each test fail before implementing
- [ ] Failed for expected reason (feature missing, not typo)
- [ ] Wrote minimal code to pass
- [ ] All tests pass, output pristine
- [ ] Edge cases and errors covered

If ANY unchecked: Skipped TDD. Start over.

## When Stuck

| Problem | Solution |
|---------|----------|
| Don't know how to test | Write wished-for API. Assertion first. Ask human. |
| Test too complicated | Design too complicated. Simplify interface. |
| Must mock everything | Code too coupled. Dependency injection. |

## Bug Fix Pattern

1. **RED**: Write test reproducing bug
2. **Verify**: See expected failure
3. **GREEN**: Minimal fix
4. **Verify**: All pass

Never fix bugs without test.

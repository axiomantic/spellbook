# /audit-mirage-cross

## Command Content

``````````markdown
# Phase 4: Cross-Test Analysis

After auditing individual tests, analyze the suite as a whole.

## Invariant Principles

1. **Coverage gaps matter more than individual test quality** - A function with no test is a bigger risk than a function with a weak test
2. **Side-effect coverage is not direct coverage** - A function exercised as a side effect of another test is not meaningfully tested
3. **Error paths deserve equal attention** - Happy-path-only suites are the primary source of production incidents

## Functions/Methods Never Tested

```
## Functions/Methods Never Tested
- module.function_a() - no direct test
- module.function_b() - only tested as side effect
```

Identify every public function/method in the production code that has NO direct test coverage. "Tested as side effect" means the function runs during another test but its behavior is never directly asserted.

## Error Paths Never Tested

```
## Error Paths Never Tested
- What happens when X fails?
- What happens when Y returns None?
```

For each production function, enumerate the error branches (exceptions, null returns, timeout, invalid input) and check whether any test exercises that path.

## Edge Cases Never Tested

```
## Edge Cases Never Tested
- Empty input
- Maximum size input
- Boundary values
- Concurrent access
```

Consider the domain-specific boundary conditions. What inputs sit at the edges of valid ranges? What about zero-length, max-length, negative, Unicode, or concurrent scenarios?

## Test Isolation Issues

```
## Test Isolation Issues
- Tests that depend on other tests (shared state)
- Tests that depend on external state
- Tests that don't clean up
```

Identify tests that share mutable state, depend on test execution order, rely on external services or files, or fail to restore state after execution.
``````````

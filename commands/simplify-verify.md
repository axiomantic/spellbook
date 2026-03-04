---
description: "Verify simplification candidates pass all gates. Part of simplify-* family."
---

# /simplify-verify

<ROLE>
Verification Gatekeeper. Your reputation depends on never allowing an untested or complexity-increasing transformation through. A transformation that corrupts behavior is worse than no transformation. This is very important to my career.
</ROLE>

Run multi-gate verification on proposed simplifications before transformation. Part of the simplify-* command family; runs after `/simplify-analyze`, produces output for `/simplify-transform`.

## Invariant Principles

1. **All gates must pass** - Parse, type check, test run, and complexity delta; failure at any gate aborts the transformation
2. **Abort on failure, continue pipeline** - Failed candidates are recorded and skipped; pipeline continues to next candidate
3. **Complexity must decrease** - Transformations that do not reduce cognitive complexity are rejected
4. **Test coverage required** - Untested functions are skipped unless explicitly allowed with `--allow-uncovered` and higher risk acknowledgment

## Step 4: Verification Gate

### 4.1 Verification Pipeline

```
parse_check -> type_check -> test_run -> complexity_delta
     |             |            |             |
     v             v            v             v
  FAIL?         FAIL?        FAIL?        report
  abort         abort        abort
```

<reflection>
Each gate: FAIL -> abort transformation, record reason, continue to next candidate.
Must record before/after complexity scores as evidence.
</reflection>

### 4.2 Gate 1: Parse Check

Verify syntax validity:

```bash
# Python
python -m py_compile <file>

# TypeScript
tsc --noEmit <file>

# Nim
nim check <file>

# C/C++
gcc -fsyntax-only <file>
# or
clang -fsyntax-only <file>
```

**If parse fails:** Abort transformation. Mark as "verification failed - syntax error". Continue to next candidate.

### 4.3 Gate 2: Type Check

**If language has a type system AND type annotations are present:**

```bash
# Python (if type hints present)
mypy <file>

# TypeScript
tsc --noEmit <file>

# C/C++
# Covered by Gate 1 compile check
```

**If types are absent or language lacks a type checker:** Skip this gate, proceed to Gate 3.

**If type check fails:** Abort transformation. Mark as "verification failed - type error". Continue to next candidate.

### 4.4 Gate 3: Test Run

Run test suite with coverage mapping. Find tests that execute the function. Run ONLY those tests (for speed).

```bash
# Python
pytest --cov=<module> --cov-report=term-missing <test_file>

# TypeScript/JavaScript
jest --coverage --testNamePattern=<function_name>

# C/C++
# Project-specific test runner with coverage
```

**If tests fail:** Abort transformation. Mark as "verification failed - tests failed". Continue to next candidate.

**If no tests found:**
- `--allow-uncovered` not set: abort transformation, mark as "skipped - no coverage"
- `--allow-uncovered` set: proceed with high-risk flag

### 4.5 Gate 4: Complexity Delta

Calculate cognitive complexity of original and transformed function. Compute delta: `after - before`.

**Verify improvement:** Delta must be negative (reduction). If delta >= 0: transformation did not improve complexity, abort.

**Record metrics:**
```
before: <score>
after: <score>
delta: <delta> (<percentage>%)
```

<FORBIDDEN>
- Allowing a transformation through with a non-negative complexity delta
- Skipping the test gate because "the change looks safe"
- Proceeding without recording before/after complexity scores
- Treating `--allow-uncovered` as a default; it must be explicitly set
</FORBIDDEN>

## Output

This command produces:
1. Verification status for each candidate (PASS/FAIL with reason)
2. Before/after complexity metrics for passing candidates
3. A SESSION_STATE object for use by `/simplify-transform`

**Next:** Run `/simplify-transform` to apply verified simplifications.

<FINAL_EMPHASIS>
You are a Verification Gatekeeper. Passing a transformation that breaks behavior or increases complexity is a failure - regardless of how "obvious" the simplification looks. Record evidence. Abort on doubt.
</FINAL_EMPHASIS>

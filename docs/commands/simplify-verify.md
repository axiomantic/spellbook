# /simplify-verify

## Workflow Diagram

Multi-gate verification pipeline for simplification candidates. Each candidate passes through parse, type, test, and complexity gates.

```mermaid
flowchart TD
    Start([Analyzed Candidates]) --> NextCandidate["Load Next\nCandidate"]
    NextCandidate --> Gate1["Gate 1:\nParse Check"]
    Gate1 --> ParseResult{"Syntax Valid?"}
    ParseResult -->|No| AbortParse["Abort: Syntax Error"]
    ParseResult -->|Yes| Gate2["Gate 2:\nType Check"]
    Gate2 --> TypeResult{"Types Valid?"}
    TypeResult -->|No| AbortType["Abort: Type Error"]
    TypeResult -->|Yes| Gate3["Gate 3:\nTest Run"]
    Gate3 --> TestCoverage{"Tests Found?"}
    TestCoverage -->|No| AllowUncovered{"--allow-uncovered\nFlag Set?"}
    AllowUncovered -->|No| AbortCoverage["Abort: No Coverage"]
    AllowUncovered -->|Yes| HighRisk["Proceed with\nHigh Risk Flag"]
    TestCoverage -->|Yes| RunTests["Run Covering Tests"]
    RunTests --> TestResult{"Tests Pass?"}
    TestResult -->|No| AbortTest["Abort: Tests Failed"]
    TestResult -->|Yes| Gate4["Gate 4:\nComplexity Delta"]
    HighRisk --> Gate4
    Gate4 --> CalcDelta["Calculate\nBefore/After Scores"]
    CalcDelta --> DeltaResult{"Complexity\nReduced?"}
    DeltaResult -->|No| AbortDelta["Abort: No Improvement"]
    DeltaResult -->|Yes| RecordMetrics["Record Metrics\nBefore/After/Delta"]
    AbortParse --> RecordFail["Record Failure\nReason"]
    AbortType --> RecordFail
    AbortCoverage --> RecordFail
    AbortTest --> RecordFail
    AbortDelta --> RecordFail
    RecordFail --> MoreCandidates{"More\nCandidates?"}
    RecordMetrics --> MoreCandidates
    MoreCandidates -->|Yes| NextCandidate
    MoreCandidates -->|No| Output([Verified Candidates\n+ SESSION_STATE])

    style Start fill:#4CAF50,color:#fff
    style Output fill:#4CAF50,color:#fff
    style NextCandidate fill:#2196F3,color:#fff
    style RunTests fill:#2196F3,color:#fff
    style CalcDelta fill:#2196F3,color:#fff
    style RecordMetrics fill:#2196F3,color:#fff
    style RecordFail fill:#2196F3,color:#fff
    style HighRisk fill:#2196F3,color:#fff
    style AbortParse fill:#2196F3,color:#fff
    style AbortType fill:#2196F3,color:#fff
    style AbortCoverage fill:#2196F3,color:#fff
    style AbortTest fill:#2196F3,color:#fff
    style AbortDelta fill:#2196F3,color:#fff
    style Gate1 fill:#f44336,color:#fff
    style Gate2 fill:#f44336,color:#fff
    style Gate3 fill:#f44336,color:#fff
    style Gate4 fill:#f44336,color:#fff
    style ParseResult fill:#FF9800,color:#fff
    style TypeResult fill:#FF9800,color:#fff
    style TestCoverage fill:#FF9800,color:#fff
    style AllowUncovered fill:#FF9800,color:#fff
    style TestResult fill:#FF9800,color:#fff
    style DeltaResult fill:#FF9800,color:#fff
    style MoreCandidates fill:#FF9800,color:#fff
```

## Legend

| Color | Meaning |
|-------|---------|
| Green (#4CAF50) | Skill invocation |
| Blue (#2196F3) | Command/action |
| Orange (#FF9800) | Decision point |
| Red (#f44336) | Quality gate |

## Command Content

``````````markdown
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
``````````

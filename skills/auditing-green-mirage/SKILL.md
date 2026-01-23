---
name: auditing-green-mirage
description: "Use when reviewing test suites, after test runs pass, or when user asks about test quality"
version: 1.1.0
---

<ROLE>
Test Suite Forensic Analyst for mission-critical systems. Your reputation depends on proving that tests actually verify correctness, or exposing where they don't. Treat every passing test with suspicion until you've traced its execution path and verified it would catch real failures.

This is very important to my career.
</ROLE>

<CRITICAL>
A green test suite means NOTHING if tests don't consume their outputs and verify correctness.

You MUST:
1. Read every test file line by line
2. Trace every code path from test through production code and back
3. Verify each assertion would catch actual failures
4. Identify all gaps where broken code would still pass

This is NOT optional. Take as long as needed. You'd better be sure.
</CRITICAL>

## Invariant Principles

1. **Passage Not Presence** - Test value = catching failures, not passing. Question: "Would broken code fail this?"
2. **Consumption Validates** - Assertions must USE outputs (parse, compile, execute), not just check existence
3. **Complete Over Partial** - Full object assertions expose truth; substring/partial checks hide bugs
4. **Trace Before Judge** - Follow test -> production -> return -> assertion path completely before verdict
5. **Evidence-Based Findings** - Every finding requires exact line, exact fix code, traced failure scenario

## Reasoning Schema

<analysis>
Before analyzing ANY test, think step-by-step:
1. CLAIM: What does name/docstring promise?
2. PATH: What code actually executes?
3. CHECK: What do assertions verify?
4. ESCAPE: What garbage passes this test?
5. IMPACT: What breaks in production?
</analysis>

<reflection>
Before concluding:
- Every test traced through production code?
- All 8 patterns checked per test?
- Each finding has: line number, exact fix code, effort, depends_on?
- Dependencies between findings identified?
- YAML block at START with all required fields?
</reflection>

## Inputs

| Input | Required | Description |
|-------|----------|-------------|
| Test files | Yes | Test suite to audit (directory or file paths) |
| Production files | Yes | Source code the tests are meant to protect |
| Test run results | No | Recent test output showing pass/fail status |

## Outputs

| Output | Type | Description |
|--------|------|-------------|
| Audit report | File | YAML + markdown at `$SPELLBOOK_CONFIG_DIR/docs/<project-encoded>/audits/auditing-green-mirage-<timestamp>.md` |
| Summary | Inline | Test counts, mirage counts, fix time estimate |
| Next action | Inline | Suggested `/fixing-tests [path]` invocation |

## Execution Protocol

### Phase 1: Inventory

<!-- SUBAGENT: CONDITIONAL - For file discovery, use Explore subagent if scope unknown. For 5+ test files, consider dispatching parallel audit subagents per file. For small scope, stay in main context. -->

Before auditing, create complete inventory:

```
## Test Inventory

### Files to Audit
1. path/to/test_file1.py - N tests
2. path/to/test_file2.py - M tests

### Production Code Under Test
1. path/to/module1.py - tested by: test_file1.py
2. path/to/module2.py - tested by: test_file1.py, test_file2.py

### Estimated Scope
- Total test files: X
- Total test functions: Y
- Total production modules: Z
```

### Phase 2: Systematic Line-by-Line Audit

For EACH test file, work through EVERY test function:

```
### Test: `test_function_name` (file.py:line)

**Purpose (from name/docstring):** What this test claims to verify

**Setup Analysis:**
- Line X: [what's being set up]
- Line Y: [dependencies/mocks introduced]
- Concern: [any setup that hides real behavior?]

**Action Analysis:**
- Line Z: [the actual operation being tested]
- Code path: function() -> calls X -> calls Y -> returns
- Side effects: [files created, state modified, etc.]

**Assertion Analysis:**
- Line A: `assert condition` - Would catch: [what failures] / Would miss: [what failures]

**Verdict:** SOLID | GREEN MIRAGE | PARTIAL
**Gap (if any):** [Specific scenario that passes test but breaks production]
**Fix (if any):** [Concrete code to add]
```

#### Code Path Tracing

For each test action, trace the COMPLETE path:

```
test_function()
  |-> production_function(args)
        |-> helper_function()
        |     |-> external_call() [mocked? real?]
        |     |-> returns value
        |-> processes result
        |-> returns final
  |-> assertion checks final

Questions at each step:
- Is this step tested or assumed to work?
- If this step returned garbage, would the test catch it?
- Are error paths tested or only happy paths?
```

### Phase 3: The 8 Green Mirage Patterns

Check EVERY test against ALL patterns:

#### Pattern 1: Existence vs. Validity
**Symptom:** Checking something exists without validating correctness.
```python
# GREEN MIRAGE
assert output_file.exists()
assert len(result) > 0
assert response is not None
```
**Question:** If the content was garbage, would this catch it?

#### Pattern 2: Partial Assertions (CODE SMELL - INVESTIGATE DEEPER)
**Symptom:** Using `in`, substring checks, or partial matches instead of complete values.

This pattern is a STRONG CODE SMELL requiring deeper investigation. Tests should shine a bright light on data, not make a quick glance.

```python
# GREEN MIRAGE - Partial assertions hide bugs
assert 'SELECT' in query           # Garbage SQL could contain SELECT
assert 'error' not in output       # Wrong output might not have 'error'
assert expected_id in result       # Result could have wrong structure
assert key in response_dict        # Value at key could be garbage
```

**SOLID tests assert COMPLETE objects:**
```python
# SOLID - Full assertions expose everything
assert query == "SELECT id, name FROM users WHERE active = true"
assert result == {"id": 123, "name": "test", "status": "active"}
```

**Investigation Required:**
1. WHY is this a partial assertion? What is the test avoiding checking?
2. WHAT could be wrong with the unchecked parts?
3. HOW would a complete assertion change this test?

#### Pattern 3: Shallow String/Value Matching
**Symptom:** Checking keywords without validating structure.
```python
# GREEN MIRAGE
assert 'SELECT' in query
assert 'error' not in output
assert result.status == 'success'  # But is the data correct?
```
**Question:** Could syntactically broken output still contain this keyword?

#### Pattern 4: Lack of Consumption
**Symptom:** Never USING the generated output in a way that validates it.
```python
# GREEN MIRAGE
generated_code = compiler.generate()
assert generated_code  # Never compiled!

result = api.fetch_data()
assert result  # Never deserialized or used!
```
**Question:** Is this output ever compiled/parsed/executed/deserialized?

#### Pattern 5: Mocking Reality Away
**Symptom:** Mocking the system under test, not just external dependencies.
```python
# GREEN MIRAGE - tests the mock, not the code
@mock.patch('mymodule.core_logic')
def test_processing(mock_logic):
    mock_logic.return_value = expected
    result = process()  # core_logic never runs!
```
**Question:** Is the ACTUAL code path exercised, or just mocks?

#### Pattern 6: Swallowed Errors
**Symptom:** Exceptions caught and ignored, error codes unchecked.
```python
# GREEN MIRAGE
try:
    risky_operation()
except Exception:
    pass  # Bug hidden!

result = command()  # Return code ignored
```
**Question:** Would this test fail if an exception was raised?

#### Pattern 7: State Mutation Without Verification
**Symptom:** Test triggers side effects but never verifies the resulting state.
```python
# GREEN MIRAGE
user.update_profile(new_data)
assert user.update_profile  # Checked call happened, not result

db.insert(record)
# Never queries DB to verify record exists and is correct
```
**Question:** After the mutation, is the actual state verified?

#### Pattern 8: Incomplete Branch Coverage
**Symptom:** Happy path tested, error paths assumed.
```python
# Tests only success case
def test_process_data():
    result = process(valid_data)
    assert result.success

# Missing: test_process_invalid_data, test_process_empty, test_process_malformed
```
**Question:** What happens when input is invalid/empty/malformed/boundary?

### Phase 4: Cross-Test Analysis

After auditing individual tests, analyze the suite as a whole:

```
## Functions/Methods Never Tested
- module.function_a() - no direct test
- module.function_b() - only tested as side effect

## Error Paths Never Tested
- What happens when X fails?
- What happens when Y returns None?

## Edge Cases Never Tested
- Empty input
- Maximum size input
- Boundary values
- Concurrent access

## Test Isolation Issues
- Tests that depend on other tests (shared state)
- Tests that depend on external state
- Tests that don't clean up
```

### Phase 5: Findings Report

<CRITICAL>
The findings report MUST include both:
1. Machine-parseable YAML block at START
2. Human-readable summary and detailed findings

This enables the fixing-tests skill to consume the output directly.
</CRITICAL>

#### Machine-Parseable YAML Block

```yaml
---
# GREEN MIRAGE AUDIT REPORT
# Generated: [ISO 8601 timestamp]

audit_metadata:
  timestamp: "2024-01-15T10:30:00Z"
  test_files_audited: 5
  test_functions_audited: 47
  production_files_touched: 12

summary:
  total_tests: 47
  solid: 31
  green_mirage: 12
  partial: 4

patterns_found:
  pattern_1_existence_vs_validity: 3
  pattern_2_partial_assertions: 4
  pattern_3_shallow_matching: 2
  pattern_4_lack_of_consumption: 1
  pattern_5_mocking_reality: 0
  pattern_6_swallowed_errors: 1
  pattern_7_state_mutation: 1
  pattern_8_incomplete_branches: 4

findings:
  - id: "finding-1"
    priority: critical          # critical | important | minor
    test_file: "tests/test_auth.py"
    test_function: "test_login_success"
    line_number: 45
    pattern: 2
    pattern_name: "Partial Assertions"
    effort: trivial             # trivial | moderate | significant
    depends_on: []              # IDs of findings that must be fixed first
    blind_spot: "Login could return malformed user object and test would pass"
    production_impact: "Broken user sessions in production"

  - id: "finding-2"
    priority: critical
    test_file: "tests/test_auth.py"
    test_function: "test_logout"
    line_number: 78
    pattern: 7
    pattern_name: "State Mutation Without Verification"
    effort: moderate
    depends_on: ["finding-1"]   # Shares fixtures with finding-1
    blind_spot: "Session not actually cleared, just returns success"
    production_impact: "Session persistence after logout"

remediation_plan:
  phases:
    - phase: 1
      name: "Foundation fixes"
      findings: ["finding-1"]
      rationale: "Other tests depend on auth fixtures"

    - phase: 2
      name: "Auth suite completion"
      findings: ["finding-2"]
      rationale: "Depends on phase 1 fixtures"

  total_effort_estimate: "2-3 hours"
  recommended_approach: sequential  # sequential | parallel | mixed
---
```

#### Effort Estimation Guidelines

| Effort | Criteria | Examples |
|--------|----------|----------|
| **trivial** | < 5 minutes, single assertion change | Add `.to_equal(expected)` instead of `.to_be_truthy()` |
| **moderate** | 5-30 minutes, requires reading production code | Add state verification, strengthen partial assertions |
| **significant** | 30+ minutes, requires new test infrastructure | Add schema validation, create edge case tests, refactor mocked tests |

#### Dependency Detection

Identify dependencies between findings:

| Dependency Type | Detection | YAML Format |
|-----------------|-----------|-------------|
| Shared fixtures | Two tests share setup | `depends_on: ["finding-1"]` |
| Cascading assertions | Test A's output feeds test B | `depends_on: ["finding-3"]` |
| File-level batching | Multiple findings in one file | Note in rationale |
| Independent | No dependencies | `depends_on: []` |

#### Human-Readable Summary

```
## Audit Summary

Total Tests Audited: X
|-- SOLID (would catch failures): Y
|-- GREEN MIRAGE (would miss failures): Z
|-- PARTIAL (some gaps): W

Patterns Found:
|-- Pattern 1 (Existence vs. Validity): N instances
|-- Pattern 2 (Partial Assertions): N instances
|-- Pattern 3 (Shallow Matching): N instances
|-- Pattern 4 (Lack of Consumption): N instances
|-- Pattern 5 (Mocking Reality): N instances
|-- Pattern 6 (Swallowed Errors): N instances
|-- Pattern 7 (State Mutation): N instances
|-- Pattern 8 (Incomplete Branches): N instances

Effort Breakdown:
|-- Trivial fixes: N (< 5 min each)
|-- Moderate fixes: N (5-30 min each)
|-- Significant fixes: N (30+ min each)

Estimated Total Remediation: [X hours]
```

#### Detailed Findings Template

For each critical finding:

```
---
**Finding #1: [Descriptive Title]**

| Field | Value |
|-------|-------|
| ID | `finding-1` |
| Priority | CRITICAL |
| File | `path/to/test.py::test_function` (line X) |
| Pattern | 2 - Partial Assertions |
| Effort | trivial / moderate / significant |
| Depends On | None / [finding-N, ...] |

**Current Code:**
```python
[exact code from test]
```

**Blind Spot:**
[Specific scenario where broken code passes this test]

**Trace:**
```
test_function()
  |-> production_function(args)
        |-> returns garbage
  |-> assertion checks [partial thing]
  |-> PASSES despite garbage because [reason]
```

**Production Impact:**
[What would break in production that this test misses]

**Consumption Fix:**
```python
[exact code to add/change]
```

**Why This Fix Works:**
[How the fix would catch the failure]

---
```

### Phase 6: Report Output

Write to: `$SPELLBOOK_CONFIG_DIR/docs/<project-encoded>/audits/auditing-green-mirage-<YYYY-MM-DD>-<HHMMSS>.md`

Project encoding:
```bash
PROJECT_ENCODED=$(echo "$PROJECT_ROOT" | sed 's|^/||' | tr '/' '-')
mkdir -p "$SPELLBOOK_CONFIG_DIR/docs/${PROJECT_ENCODED}/audits"
```

**If not in git repo:** Ask user if they want to run `git init`. If no, use: `$SPELLBOOK_CONFIG_DIR/docs/_no-repo/$(basename "$PWD")/audits/`

Final user output:
```
## Audit Complete

Report: ~/.local/spellbook/docs/<project-encoded>/audits/auditing-green-mirage-<timestamp>.md

Summary:
- Tests audited: X
- Green mirages found: Y
- Estimated fix time: Z

Next Steps:
/fixing-tests [report-path]
```

## Anti-Patterns

<FORBIDDEN>
### Surface-Level Auditing
- "Tests look comprehensive"
- "Good coverage overall"
- Skimming without tracing code paths
- Flagging only obvious issues

### Vague Findings
- "This test should be more thorough"
- "Consider adding validation"
- Findings without exact line numbers
- Fixes without exact code

### Rushing
- Skipping tests to finish faster
- Not tracing full code paths
- Assuming code works without verification
- Stopping before full audit complete
</FORBIDDEN>

## Self-Check

Before completing audit, verify:

**Audit Completeness:**
- [ ] Did I read every line of every test file?
- [ ] Did I trace code paths from test through production and back?
- [ ] Did I check every test against all 8 patterns?
- [ ] Did I verify assertions would catch actual failures?
- [ ] Did I identify untested functions/methods?
- [ ] Did I identify untested error paths?

**Finding Quality:**
- [ ] Does every finding include exact line numbers?
- [ ] Does every finding include exact fix code?
- [ ] Does every finding have effort estimate (trivial/moderate/significant)?
- [ ] Does every finding have depends_on specified (even if empty [])?
- [ ] Did I prioritize findings (critical/important/minor)?

**Report Structure:**
- [ ] Did I output YAML block at START?
- [ ] Does YAML include: audit_metadata, summary, patterns_found, findings, remediation_plan?
- [ ] Does each finding have: id, priority, test_file, test_function, line_number, pattern, pattern_name, effort, depends_on, blind_spot, production_impact?
- [ ] Did I generate remediation_plan with dependency-ordered phases?
- [ ] Did I provide human-readable summary after YAML?
- [ ] Did I include "Quick Start" section pointing to fixing-tests?

If NO to ANY item, go back and complete it.

<CRITICAL>
The question is NOT "does this test pass?"

The question is: "Would this test FAIL if the production code was broken?"

For EVERY assertion, ask: "What broken code would still pass this?"

If you can't answer with confidence that the test catches failures, it's a Green Mirage.

Find it. Trace it. Fix it. Take as long as needed.
</CRITICAL>

<FINAL_EMPHASIS>
Green test suites mean NOTHING if they don't catch failures. Your reputation depends on exposing every test that lets broken code slip through. Every assertion must CONSUME and VALIDATE. Every code path must be TRACED. Every finding must have EXACT fixes. Thoroughness over speed.
</FINAL_EMPHASIS>

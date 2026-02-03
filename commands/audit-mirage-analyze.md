---
description: "Phase 2-3 of auditing-green-mirage: Systematic line-by-line audit and 8 Green Mirage Patterns"
---

# Phase 2-3: Systematic Audit and Green Mirage Patterns

This command file contains the detailed audit templates and all 8 Green Mirage Patterns for subagent execution.

## Invariant Principles

1. **Every test function gets audited** - No skipping tests because they "look fine"; line-by-line analysis catches what scanning misses
2. **Assertions determine test value** - A test without meaningful assertions is worse than no test; it creates false confidence
3. **Score by pattern, not by gut** - Use the 8 Green Mirage Patterns as the scoring rubric, not subjective assessment

## Phase 2: Systematic Line-by-Line Audit

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

### Code Path Tracing

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

## Phase 3: The 8 Green Mirage Patterns

Check EVERY test against ALL patterns:

### Pattern 1: Existence vs. Validity
**Symptom:** Checking something exists without validating correctness.
```python
# GREEN MIRAGE
assert output_file.exists()
assert len(result) > 0
assert response is not None
```
**Question:** If the content was garbage, would this catch it?

### Pattern 2: Partial Assertions (CODE SMELL - INVESTIGATE DEEPER)
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

### Pattern 3: Shallow String/Value Matching
**Symptom:** Checking keywords without validating structure.
```python
# GREEN MIRAGE
assert 'SELECT' in query
assert 'error' not in output
assert result.status == 'success'  # But is the data correct?
```
**Question:** Could syntactically broken output still contain this keyword?

### Pattern 4: Lack of Consumption
**Symptom:** Never USING the generated output in a way that validates it.
```python
# GREEN MIRAGE
generated_code = compiler.generate()
assert generated_code  # Never compiled!

result = api.fetch_data()
assert result  # Never deserialized or used!
```
**Question:** Is this output ever compiled/parsed/executed/deserialized?

### Pattern 5: Mocking Reality Away
**Symptom:** Mocking the system under test, not just external dependencies.
```python
# GREEN MIRAGE - tests the mock, not the code
@mock.patch('mymodule.core_logic')
def test_processing(mock_logic):
    mock_logic.return_value = expected
    result = process()  # core_logic never runs!
```
**Question:** Is the ACTUAL code path exercised, or just mocks?

### Pattern 6: Swallowed Errors
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

### Pattern 7: State Mutation Without Verification
**Symptom:** Test triggers side effects but never verifies the resulting state.
```python
# GREEN MIRAGE
user.update_profile(new_data)
assert user.update_profile  # Checked call happened, not result

db.insert(record)
# Never queries DB to verify record exists and is correct
```
**Question:** After the mutation, is the actual state verified?

### Pattern 8: Incomplete Branch Coverage
**Symptom:** Happy path tested, error paths assumed.
```python
# Tests only success case
def test_process_data():
    result = process(valid_data)
    assert result.success

# Missing: test_process_invalid_data, test_process_empty, test_process_malformed
```
**Question:** What happens when input is invalid/empty/malformed/boundary?

## Effort Estimation Guidelines

| Effort | Criteria | Examples |
|--------|----------|----------|
| **trivial** | < 5 minutes, single assertion change | Add `.to_equal(expected)` instead of `.to_be_truthy()` |
| **moderate** | 5-30 minutes, requires reading production code | Add state verification, strengthen partial assertions |
| **significant** | 30+ minutes, requires new test infrastructure | Add schema validation, create edge case tests, refactor mocked tests |

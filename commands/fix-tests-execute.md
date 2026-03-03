---
description: "Phase 2 of fixing-tests: Fix Execution - investigate, classify, fix, verify, and commit each work item"
---

# Phase 2: Fix Execution

## Invariant Principles

1. **Read before fixing** - Always read the test file and production code before making any changes; never guess at code structure
2. **Verify the fix, not just the pass** - A test that passes after modification must be confirmed to catch the originally identified blind spot
3. **One fix per commit** - Each work item fix is verified and committed independently for traceability and safe rollback
4. **ALL output demands exact equality** - Every assertion MUST be `assert result == expected_complete_output`. `assert "substring" in result` is BANNED. No exceptions. For dynamic output, construct the expected value dynamically. See: `patterns/assertion-quality-standard.md`.
5. **Fixes must reach Level 4+** - Replacing one weak assertion with another weak assertion is NOT a fix. Every new assertion must be Level 4+ on the Assertion Strength Ladder. Moving from Level 1 to Level 2 is still BANNED.

Process by priority: critical > important > minor.

<CRITICAL>
## Assertion Quality Requirements (Non-Negotiable)

Read the assertion quality standard (`patterns/assertion-quality-standard.md`) in full before writing ANY fix.

### The Full Assertion Principle

Every assertion MUST assert exact equality against the COMPLETE expected output. This applies to ALL output -- static, dynamic, or partially dynamic. For dynamic output, construct the complete expected value dynamically, then assert `==`.

```python
# CORRECT
assert result == "the complete expected output, every character"

# CORRECT - dynamic output: construct expected dynamically
assert message == f"Today's date is {datetime.date.today().isoformat()}"

# BANNED - still a green mirage even if it looks like an "improvement"
assert "some keyword" in result
assert "struct Point" in result
assert "expected_field" in result and "other_field" in result

# BANNED - mock.ANY hides argument values
mock_fn.assert_called_with(mock.ANY, mock.ANY)
```

### BANNED Assertion Patterns

These patterns are NEVER acceptable in a fix. If your fix introduces any of these, it is not a fix:

- `assert "X" in output` (bare substring on any output -- static or dynamic)
- `assert len(result) > 0` (existence only)
- `assert len(result) == N` without content verification
- `assert result is not None` without value assertion
- `assert result == function_under_test(same_input)` (tautological)
- Multiple `assert "X" in result` checks (still partial, still BANNED)
- `mock.ANY` in any mock call assertion (BANNED -- construct expected argument)

### Required Assertion Level

Every new or modified assertion must be:
- **Level 5 (GOLD):** `assert result == expected` (exact equality on complete output)
- **Level 4 (PREFERRED):** Parse output, assert on full parsed structure

Levels 3 and below require written justification. Levels 1-2 are BANNED outright.

### Per-Assertion Verification

For EACH assertion you write, answer in your reasoning:
1. Does this assertion verify the COMPLETE expected output? If not, only Level 5 is acceptable.
2. What specific production code mutation would cause this assertion to fail?
3. If the production code returned garbage, would this assertion catch it?

If you cannot answer #2 with a specific mutation, the assertion is too weak.
</CRITICAL>

## 2.1 Investigation

<analysis>
For EACH work item:
- What does test claim to do? (name, docstring)
- What is actually wrong? (error, audit finding)
- What production code involved?
</analysis>

<RULE>Always read before fixing. Never guess at code structure.</RULE>

1. Read test file (specific function + setup/teardown)
2. Read production code being tested
3. If audit_report: suggested fix is starting point, verify it makes sense

## 2.2 Fix Type Classification

| Situation | Fix Type |
|-----------|----------|
| Weak assertions (green mirage) | Replace with exact equality assertions (Level 4+). "Strengthen" means reaching `assert result == expected_complete_output`, NOT replacing one partial check with another. |
| Missing edge cases | Add test cases |
| Wrong expectations | Correct expectations |
| Broken setup | Fix setup, not weaken test |
| Flaky (timing/ordering) | Fix isolation/determinism |
| Tests implementation details | Rewrite to test behavior |
| **Production code buggy** | STOP and report |

## 2.4 Fix Examples

**Green Mirage Fix (Pattern 2: Partial Assertions):**

```python
# BEFORE: Checks existence only (Level 1 - BANNED)
def test_generate_report():
    report = generate_report(data)
    assert report is not None
    assert len(report) > 0

# WRONG "FIX": Still partial (Level 2 - STILL BANNED)
def test_generate_report():
    report = generate_report(data)
    assert "Expected Title" in str(report)  # STILL A GREEN MIRAGE
    assert len(report["sections"]) == 3     # Count without content

# CORRECT FIX: Exact equality on complete output (Level 5 - GOLD)
def test_generate_report():
    report = generate_report(data)
    assert report == {
        "title": "Expected Title",
        "sections": [
            {"name": "Section 1", "valid": True, "content": "..."},
            {"name": "Section 2", "valid": True, "content": "..."},
            {"name": "Section 3", "valid": True, "content": "..."},
        ],
        "generated_at": mock_timestamp
    }
```

**Edge Case Addition:**

```python
def test_generate_report_empty_data():
    """Edge case: empty input."""
    with pytest.raises(ValueError, match="Data cannot be empty"):
        generate_report([])

def test_generate_report_malformed_data():
    """Edge case: malformed input."""
    result = generate_report({"invalid": "structure"})
    assert result["error"] == "Invalid data format"
```

**Flaky Test Fix:**

```python
# BEFORE: Sleep and hope
def test_async_operation():
    start_operation()
    time.sleep(1)  # Hope it's done!
    assert get_result() is not None

# AFTER: Deterministic waiting
def test_async_operation():
    start_operation()
    result = wait_for_result(timeout=5)  # Polls with timeout
    assert result == expected_value
```

**Implementation-Coupling Fix:**

```python
# BEFORE: Tests implementation
def test_user_save():
    user = User(name="test")
    user.save()
    assert user._db_connection.execute.called_with("INSERT...")

# AFTER: Tests behavior
def test_user_save():
    user = User(name="test")
    user.save()
    loaded = User.find_by_name("test")
    assert loaded is not None
    assert loaded.name == "test"
```

## 2.5 Verify Fix

```bash
# Run fixed test
pytest path/to/test.py::test_function -v

# Check file for side effects
pytest path/to/test.py -v
```

Verification checklist:
- [ ] Specific test passes
- [ ] Other tests in file still pass
- [ ] Fix would actually catch the failure it should catch
- [ ] Every new assertion is Level 4+ on the Assertion Strength Ladder
- [ ] No bare substring checks (`assert "X" in result`) on any output (static or dynamic)
- [ ] For each assertion: named a specific production code mutation it catches
- [ ] Fix is NOT just moving from one BANNED level to another (Pattern 10)

## 2.6 Commit (per-fix strategy)

```bash
git add path/to/test.py
git commit -m "fix(tests): strengthen assertions in test_function

- [What was weak/broken]
- [What fix does]
- Pattern: N - [Pattern name] (if from audit)
"
```

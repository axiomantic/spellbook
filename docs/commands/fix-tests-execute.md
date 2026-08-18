# /fix-tests-execute
## Command Content

````markdown
<ROLE>
Test Quality Enforcer. Your reputation depends on fixes that ELIMINATE false confidence, not just fix syntax. A test that passes with weak assertions is worse than a failing test — it lies. This is very important to my career.
</ROLE>

# Phase 2: Fix Execution

## Invariant Principles

1. **Read before fixing** — Read the test file and production code before any changes; never guess at code structure.
2. **Verify the fix, not just the pass** — A test that passes after modification must be confirmed to catch the originally identified blind spot.
3. **One fix per commit** — Each work item fix is verified and committed independently for traceability and safe rollback.
4. **ALL output demands exact equality** — See `<FORBIDDEN>` below and `patterns/assertion-quality-standard.md`.
5. **Fixes must reach Level 4+** — Level 1→2 is still banned. Replacing one weak assertion with another is NOT a fix.

<CRITICAL>
## Assertion Quality Requirements (Non-Negotiable)

Read `patterns/assertion-quality-standard.md` in full before writing ANY fix.

### The Full Assertion Principle

Every assertion MUST assert exact equality against the COMPLETE expected output — static, dynamic, or partially dynamic. For dynamic output, construct the complete expected value dynamically, then assert `==`.

```python
# CORRECT
assert result == "the complete expected output, every character"

# CORRECT - dynamic output
assert message == f"Today's date is {datetime.date.today().isoformat()}"
```

`assert "substring" in result` is BANNED. ALWAYS. NO EXCEPTIONS. Dynamic content is no
excuse for a partial check.

When fixing a partial assertion on dynamic output, construct the complete expected value
using the same logic the function uses, then assert `==`. Prefer construct-then-compare
over normalization; normalization is a last resort for truly unknowable values only
(random UUIDs, OS-assigned PIDs, memory addresses).

When fixing a partial mock assertion, also check whether ALL mock calls are fully
asserted. Assert EVERY call with ALL args and verify the call count. NEVER use
`mock.ANY` — construct the expected argument dynamically when it is dynamic.

### Required Assertion Level

Every new or modified assertion must be:
- **Level 5 (GOLD):** `assert result == expected` (exact equality on complete output)
- **Level 4 (PREFERRED):** Parse output, assert on full parsed structure

Levels 3 and below require written justification. Levels 1–2 are BANNED outright.

### Per-Assertion Verification

For EACH assertion you write, answer in your reasoning:
1. Does this assertion verify the COMPLETE expected output?
2. What specific production code mutation would cause this assertion to fail?
3. If the production code returned garbage, would this assertion catch it?

If you cannot answer #2 with a specific mutation, the assertion is too weak.

### The Assertion Quality Gate (ALL input modes)

This gate applies to every fix, regardless of the input mode that produced the work
item. It is NOT limited to `audit_report` mode. Before marking any fix complete:

1. Read `patterns/assertion-quality-standard.md` — the Full Assertion Principle and the Assertion Strength Ladder
2. Classify each new or modified assertion on the Assertion Strength Ladder
3. REJECT any assertion at Level 2 (bare substring) or Level 1 (length/existence)
4. REJECT any fix that moves from one BANNED level to another (Pattern 10)
5. Level 3 (structural containment) requires written justification in the code
6. For each new assertion, name the specific production code mutation it catches
7. If you cannot name a mutation, the assertion is too weak — strengthen it
</CRITICAL>

<FORBIDDEN>
- `assert "X" in output` (bare substring on any output — static or dynamic)
- `assert len(result) > 0` (existence only)
- `assert len(result) == N` without content verification
- `assert result is not None` without value assertion
- `assert result == function_under_test(same_input)` (tautological)
- Multiple `assert "X" in result` checks (still partial)
- `mock.ANY` in any mock call assertion (construct expected argument instead)
- `assert_called()` or `assert_called_once()` without argument verification
- Asserting only some of the mock calls
</FORBIDDEN>

A fix that introduces ANY of these is not a fix. Every assertion must reach Level 4+ on
the Assertion Strength Ladder; replacing a Level 1 assertion with a Level 2 assertion is
not a fix either.

Process work items by priority: critical > important > minor.

## 2.1 Investigation

<analysis>
For EACH work item:
- What does the test claim to do? (name, docstring)
- What is actually wrong? (error, audit finding)
- What production code is involved?
</analysis>

<RULE>Always read before fixing. Never guess at code structure.</RULE>

1. Read test file (specific function + setup/teardown).
2. Read production code being tested.
3. If audit output from Phase 1 is available: treat suggested fix as starting point; verify it makes sense in context.

## 2.2 Fix Type Classification

| Situation | Fix Type |
|-----------|----------|
| Weak assertions (green mirage) | Replace with Level 4+ exact equality assertions. See FORBIDDEN and CRITICAL blocks above. |
| Missing edge cases | Add test cases |
| Wrong expectations | Correct expectations |
| Broken setup | Fix setup, not weaken test |
| Flaky (timing/ordering) | Fix isolation/determinism |
| Tests implementation details | Rewrite to test behavior |
| **Production code buggy** | STOP and report |

### Production Bug Protocol

<CRITICAL>
If investigation reveals a production bug, stop and put the decision to the user:

```
PRODUCTION BUG DETECTED

Test: [test_function]
Expected behavior: [what test expects]
Actual behavior: [what code does]

This is not a test issue - production code has a bug.

Options:
A) Fix production bug (then test will pass)
B) Update test to match buggy behavior (not recommended)
C) Skip test, create issue for bug

Your choice: ___
```

Do NOT silently fix production bugs as "test fixes."
</CRITICAL>

## 2.3 Fix Examples

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
    with pytest.raises(ValueError, match="Data cannot be empty"):
        generate_report([])

def test_generate_report_malformed_data():
    result = generate_report({"invalid": "structure"})
    assert result["error"] == "Invalid data format"
```

**Flaky Test Fix:**

```python
# BEFORE: Sleep and hope
def test_async_operation():
    start_operation()
    time.sleep(1)
    assert get_result() is not None

# AFTER: Deterministic waiting
def test_async_operation():
    start_operation()
    result = wait_for_result(timeout=5)
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
    assert loaded == User(name="test")
```

## 2.4 Special Cases

**Flaky tests:** Identify the non-determinism source (time, random, ordering, external state). Mock or control it. Use deterministic waits, not sleep-and-hope.

**Implementation-coupled tests:** Identify the BEHAVIOR the test should verify. Rewrite to test through the public interface. Remove mocks of the unit under test's own internals; do not remove mocks of external services.

**Missing tests entirely:** Read the production code. Identify key behaviors. Write tests following existing test file patterns in the codebase. Ensure the tests would catch real failures.

**Slow/bloated tests:** Tests taking >5s often hide issues: heavy fixtures, unnecessary I/O, or oversized test data (e.g., 1024x1024 matrix where 4x4 suffices). Separate slow tests with marks (`@pytest.mark.slow`, `@pytest.mark.integration`, etc.). Shrink test inputs to the minimum that exercises the behavior. Move real I/O to the integration tier. If a fixture takes longer than the test itself, it is too heavy for a unit test.

## 2.5 Verify Fix

```bash
pytest path/to/test.py::test_function -v
pytest path/to/test.py -v
```

<reflection>
Verification checklist:
- [ ] Specific test passes
- [ ] Other tests in file still pass
- [ ] Fix would actually catch the failure it should catch
- [ ] Every new assertion is Level 4+ on the Assertion Strength Ladder
- [ ] No bare substring checks (`assert "X" in result`) on any output (static or dynamic)
- [ ] For each assertion: named a specific production code mutation it catches
- [ ] Fix is NOT just moving from one BANNED level to another
</reflection>

## 2.6 Commit (per-fix strategy)

```bash
git add path/to/test.py
git commit -m "fix(tests): strengthen assertions in test_function

- [What was weak/broken]
- [What fix does]
- Pattern: N - [Pattern name] (if from audit)
"
```

## Post-Fix Adversarial Review (fixing-tests Phase 3.5)

After ALL fixes are applied, the orchestrator dispatches a Test Adversary subagent. That
review is mandatory — it catches Pattern 10 violations, the partial-to-partial upgrades
that look like improvements and are not. Dispatch prompt:

```
First, read these files to understand the quality requirements:
- Read patterns/assertion-quality-standard.md (especially The Full Assertion Principle)
- Copy in the full Test Adversary Template from skills/dispatching-parallel-agents/SKILL.md

ROLE: Test Adversary. Your job is to BREAK the new/modified test assertions.

## Context
- Modified test files: [list of files changed during fix phase]
- Git diff of changes: [paste or reference the diff]
- Production files under test: [paths]

## Mandatory Checks

1. IMMEDIATE REJECTION: Flag any assertion that is:
   - assert "X" in result on deterministic output (BANNED)
   - assert len(x) > 0 or assert x is not None (BANNED)
   - A fix that replaced one BANNED pattern with another (Pattern 10)

2. For each new/modified assertion:
   - Classify on Assertion Strength Ladder (must be Level 4+)
   - Determine if function under test is deterministic
   - If deterministic: only Level 5 (exact equality) is acceptable
   - Construct a plausible broken implementation that still passes
   - Verdict: KILLED or SURVIVED

3. Overall verdict:
   - Any SURVIVED or BANNED assertion: FAIL (list required re-fixes)
   - All KILLED + Level 4+: PASS

Return: Per-assertion verdicts and overall PASS/FAIL.
```

A FAIL verdict sends the failed items back through this fix protocol with explicit
instructions about what went wrong.

<FINAL_EMPHASIS>
You are a Test Quality Enforcer. Every weak assertion you leave in place is a lie waiting to ship to production. A test that passes without catching real failures is worse than no test — it creates false confidence. Each fix must eliminate the blind spot entirely, not shuffle it sideways. Errors here propagate through every future deployment.
</FINAL_EMPHASIS>
````

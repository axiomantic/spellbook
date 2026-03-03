# Testing Anti-Patterns

**Load this reference when:** writing or changing tests, adding mocks, or tempted to add test-only methods to production code.

## Overview

Tests must verify real behavior, not mock behavior. Mocks are a means to isolate, not the thing being tested.

**Core principle:** Test what the code does, not what the mocks do.

**Following strict TDD prevents these anti-patterns.**

## The Iron Laws

```
1. NEVER test mock behavior
2. NEVER add test-only methods to production classes
3. NEVER mock without understanding dependencies
```

## Anti-Pattern 1: Testing Mock Behavior

**The violation:**
```typescript
// ❌ BAD: Testing that the mock exists
test('renders sidebar', () => {
  render(<Page />);
  expect(screen.getByTestId('sidebar-mock')).toBeInTheDocument();
});
```

**Why this is wrong:**
- You're verifying the mock works, not that the component works
- Test passes when mock is present, fails when it's not
- Tells you nothing about real behavior

**your human partner's correction:** "Are we testing the behavior of a mock?"

**The fix:**
```typescript
// ✅ GOOD: Test real component or don't mock it
test('renders sidebar', () => {
  render(<Page />);  // Don't mock sidebar
  expect(screen.getByRole('navigation')).toBeInTheDocument();
});

// OR if sidebar must be mocked for isolation:
// Don't assert on the mock - test Page's behavior with sidebar present
```

### Gate Function

```
BEFORE asserting on any mock element:
  Ask: "Am I testing real component behavior or just mock existence?"

  IF testing mock existence:
    STOP - Delete the assertion or unmock the component

  Test real behavior instead
```

## Anti-Pattern 2: Test-Only Methods in Production

**The violation:**
```typescript
// ❌ BAD: destroy() only used in tests
class Session {
  async destroy() {  // Looks like production API!
    await this._workspaceManager?.destroyWorkspace(this.id);
    // ... cleanup
  }
}

// In tests
afterEach(() => session.destroy());
```

**Why this is wrong:**
- Production class polluted with test-only code
- Dangerous if accidentally called in production
- Violates YAGNI and separation of concerns
- Confuses object lifecycle with entity lifecycle

**The fix:**
```typescript
// ✅ GOOD: Test utilities handle test cleanup
// Session has no destroy() - it's stateless in production

// In test-utils/
export async function cleanupSession(session: Session) {
  const workspace = session.getWorkspaceInfo();
  if (workspace) {
    await workspaceManager.destroyWorkspace(workspace.id);
  }
}

// In tests
afterEach(() => cleanupSession(session));
```

### Gate Function

```
BEFORE adding any method to production class:
  Ask: "Is this only used by tests?"

  IF yes:
    STOP - Don't add it
    Put it in test utilities instead

  Ask: "Does this class own this resource's lifecycle?"

  IF no:
    STOP - Wrong class for this method
```

## Anti-Pattern 3: Mocking Without Understanding

**The violation:**
```typescript
// ❌ BAD: Mock breaks test logic
test('detects duplicate server', () => {
  // Mock prevents config write that test depends on!
  vi.mock('ToolCatalog', () => ({
    discoverAndCacheTools: vi.fn().mockResolvedValue(undefined)
  }));

  await addServer(config);
  await addServer(config);  // Should throw - but won't!
});
```

**Why this is wrong:**
- Mocked method had side effect test depended on (writing config)
- Over-mocking to "be safe" breaks actual behavior
- Test passes for wrong reason or fails mysteriously

**The fix:**
```typescript
// ✅ GOOD: Mock at correct level
test('detects duplicate server', () => {
  // Mock the slow part, preserve behavior test needs
  vi.mock('MCPServerManager'); // Just mock slow server startup

  await addServer(config);  // Config written
  await addServer(config);  // Duplicate detected ✓
});
```

### Gate Function

```
BEFORE mocking any method:
  STOP - Don't mock yet

  1. Ask: "What side effects does the real method have?"
  2. Ask: "Does this test depend on any of those side effects?"
  3. Ask: "Do I fully understand what this test needs?"

  IF depends on side effects:
    Mock at lower level (the actual slow/external operation)
    OR use test doubles that preserve necessary behavior
    NOT the high-level method the test depends on

  IF unsure what test depends on:
    Run test with real implementation FIRST
    Observe what actually needs to happen
    THEN add minimal mocking at the right level

  Red flags:
    - "I'll mock this to be safe"
    - "This might be slow, better mock it"
    - Mocking without understanding the dependency chain
```

## Anti-Pattern 4: Incomplete Mocks

**The violation:**
```typescript
// ❌ BAD: Partial mock - only fields you think you need
const mockResponse = {
  status: 'success',
  data: { userId: '123', name: 'Alice' }
  // Missing: metadata that downstream code uses
};

// Later: breaks when code accesses response.metadata.requestId
```

**Why this is wrong:**
- **Partial mocks hide structural assumptions** - You only mocked fields you know about
- **Downstream code may depend on fields you didn't include** - Silent failures
- **Tests pass but integration fails** - Mock incomplete, real API complete
- **False confidence** - Test proves nothing about real behavior

**The Iron Rule:** Mock the COMPLETE data structure as it exists in reality, not just fields your immediate test uses.

**The fix:**
```typescript
// ✅ GOOD: Mirror real API completeness
const mockResponse = {
  status: 'success',
  data: { userId: '123', name: 'Alice' },
  metadata: { requestId: 'req-789', timestamp: 1234567890 }
  // All fields real API returns
};
```

### Gate Function

```
BEFORE creating mock responses:
  Check: "What fields does the real API response contain?"

  Actions:
    1. Examine actual API response from docs/examples
    2. Include ALL fields system might consume downstream
    3. Verify mock matches real response schema completely

  Critical:
    If you're creating a mock, you must understand the ENTIRE structure
    Partial mocks fail silently when code depends on omitted fields

  If uncertain: Include all documented fields
```

## Anti-Pattern 5: Integration Tests as Afterthought

**The violation:**
```
✅ Implementation complete
❌ No tests written
"Ready for testing"
```

**Why this is wrong:**
- Testing is part of implementation, not optional follow-up
- TDD would have caught this
- Can't claim complete without tests

**The fix:**
```
TDD cycle:
1. Write failing test
2. Implement to pass
3. Refactor
4. THEN claim complete
```

## Anti-Pattern 6: Existence-Only and Partial Assertions

**The violation:**
```python
# BANNED: Existence-only -- would pass with garbage data
assert len(results) > 0
assert response is not None
assert output_file.exists()
assert "key" in response_dict
```

```python
# BANNED: Count-only -- right number, wrong content
assert len(results) == 3
assert len(response["items"]) == 2
```

```python
# BANNED: Wildcard matchers -- accepts anything
mock_handler.assert_called_with(mock.ANY, mock.ANY)
assert result == {"id": unittest.mock.ANY, "name": unittest.mock.ANY}
```

```python
# BANNED: Partial assertions on any output (dynamic content is no excuse)
assert "struct Point" in result      # Wrong fields, extra garbage pass
assert "SELECT" in query             # Garbage SQL passes
assert "foo" in r and "bar" in r     # Still partial, still BANNED
# BANNED: Dynamic content used as excuse for partial assertion
assert datetime.date.today().isoformat() in message  # Construct full expected instead
# BANNED: mock.ANY -- accepts literally anything, proves nothing
mock_handler.assert_called_with(mock.ANY, mock.ANY)
# BANNED: Asserting only some mock calls
mock_sender.send.assert_called_once_with(...)  # when send was called multiple times
```

**Why this is wrong:**
- Existence checks pass when the value is garbage
- Count checks pass when every item is wrong but the right number exist
- Substring checks on ANY output hide structural errors, missing content, and extra garbage -- dynamic content does not excuse partial assertions
- Multiple substring checks are STILL partial and STILL BANNED
- `mock.ANY` / `unittest.mock.ANY` accepts literally anything, defeating the assertion
- Asserting only some mock calls hides behavior gaps -- every call must be verified
- These create **false confidence**: the test suite is green but validates nothing
- See also: Green Mirage Pattern 1 (Existence vs. Validity) and Pattern 2 (Partial Assertion on Deterministic Output) in `commands/audit-mirage-analyze.md`
- See also: The Full Assertion Principle in `patterns/assertion-quality-standard.md`

**The fix:**
```python
# GOOD: Assert exact content
assert results == [
    {"id": 1, "name": "Alice", "role": "admin"},
    {"id": 2, "name": "Bob", "role": "user"},
]

# GOOD: Assert complete response
assert response == {"status": "ok", "data": expected_data, "meta": expected_meta}

# GOOD: Assert exact call arguments
mock_handler.assert_called_with("expected_event", expected_payload)

# GOOD: Assert ALL mock calls with ALL args and verify call count
mock_sender.send.assert_has_calls([
    call(to="alice@example.com", subject="Welcome", body="Hello Alice"),
    call(to="bob@example.com", subject="Welcome", body="Hello Bob"),
])
assert mock_sender.send.call_count == 2  # verify no unexpected extra calls

# GOOD: For dynamic output, construct full expected and assert ==
assert message == f"Today's date is {datetime.date.today().isoformat()}"
```

**Pychoir exception:** Pychoir matchers (including custom subclasses) are allowed for genuinely unknowable values (random UUIDs, OS-assigned PIDs, memory addresses). Each use requires a justification comment explaining why the value cannot be known ahead of time.

### Gate Function

```
BEFORE writing any assertion:
  Ask: "If the value was garbage, would this assertion catch it?"

  IF answer is NO:
    STOP - Assert the actual expected value instead

  IF value is genuinely unknowable (UUID, timestamp):
    Use pychoir matcher with justification comment
    NOT mock.ANY (mock.ANY is never the right tool for assertions)

  Red flags (always replace with content assertions):
    - len(x) > 0
    - len(x) == N (without also checking content)
    - x is not None (without also checking value)
    - "key" in dict (without also checking value at key)
    - x.exists()
    - mock.ANY / unittest.mock.ANY (BANNED -- construct expected value)
    - assert_called() or assert_called_once() without argument verification
    - Asserting only some mock calls (assert every call)
    - Partial assertion on dynamic output (construct full expected instead)
```

## Anti-Pattern 7: "Strengthened" Assertion That Is Still Partial (Pattern 10)

**The violation:**
```python
# BEFORE: Existence-only (Level 1 - BANNED)
assert result is not None
assert len(result) > 0

# "FIX" that is STILL a green mirage (Level 2 - STILL BANNED):
assert "struct Point" in result
assert "expected_field" in result

# ANOTHER BAD "FIX" (tautological):
assert result == writer.write(data)  # Tests function against itself
```

**Why this is wrong:**
- Replacing one BANNED assertion with a different BANNED assertion is not a fix
- Moving from Level 1 (existence) to Level 2 (substring) still fails to catch structural errors, missing content, extra garbage, and wrong ordering
- Tautological assertions (testing a function against itself) test nothing
- This creates the most dangerous illusion: the appearance of improvement without actual improvement
- See also: Green Mirage Pattern 10 in `commands/audit-mirage-analyze.md`

**The fix:**
```python
# CORRECT: Exact equality on complete output (Level 5 - GOLD)
expected = textwrap.dedent("""\
    struct Point {
        int x;
        int y;
    };
""")
assert result == expected
```

### Gate Function

```
AFTER writing a "strengthened" assertion:
  Ask: "What Assertion Strength Ladder level was the OLD assertion?"
  Ask: "What level is my NEW assertion?"

  IF new level <= 2 (BANNED):
    STOP - Your fix is still a green mirage
    Rewrite to Level 4+ (exact equality or parsed structural)

  IF new assertion tests function against itself:
    STOP - Tautological. Compute expected value independently.

  The goal is Level 5 (exact equality) for all output.
  Construct the expected value dynamically if output contains dynamic content.
  Level 4 (parsed structural) with normalization is LAST RESORT for truly unknowable values only.
```

## When Mocks Become Too Complex

**Warning signs:**
- Mock setup longer than test logic
- Mocking everything to make test pass
- Mocks missing methods real components have
- Test breaks when mock changes

**your human partner's question:** "Do we need to be using a mock here?"

**Consider:** Integration tests with real components often simpler than complex mocks

## TDD Prevents These Anti-Patterns

**Why TDD helps:**
1. **Write test first** → Forces you to think about what you're actually testing
2. **Watch it fail** → Confirms test tests real behavior, not mocks
3. **Minimal implementation** → No test-only methods creep in
4. **Real dependencies** → You see what the test actually needs before mocking

**If you're testing mock behavior, you violated TDD** - you added mocks without watching test fail against real code first.

## Quick Reference

| Anti-Pattern | Fix |
|--------------|-----|
| Assert on mock elements | Test real component or unmock it |
| Test-only methods in production | Move to test utilities |
| Mock without understanding | Understand dependencies first, mock minimally |
| Incomplete mocks | Mirror real API completely |
| Tests as afterthought | TDD - tests first |
| Over-complex mocks | Consider integration tests |
| Existence-only assertions | Assert exact expected values, not just existence/count |
| Partial assertions on any output | `assert result == expected_complete_output` (construct dynamically for dynamic output) |
| Dynamic content used as excuse for partial assertion | Construct full expected value dynamically, then assert == |
| mock.ANY in call assertions | Construct expected argument and assert exactly |
| Asserting only some mock calls | Assert every call with all args; verify call count |
| "Strengthened" assertion still partial | Must reach Level 4+, not just move from Level 1 to Level 2 |

## Red Flags

- Assertion checks for `*-mock` test IDs
- Methods only called in test files
- Mock setup is >50% of test
- Test fails when you remove mock
- Can't explain why mock is needed
- Mocking "just to be safe"
- `assert len(x) > 0` without content verification
- `assert x is not None` without value verification
- `mock.ANY` in assertions (BANNED -- construct expected value)
- `assert_called()` or `assert_called_once()` without argument verification
- Asserting only some mock calls (every call must be asserted)
- Partial assertion on dynamic output (construct full expected instead of membership check)

## The Bottom Line

**Mocks are tools to isolate, not things to test.**

If TDD reveals you're testing mock behavior, you've gone wrong.

Fix: Test real behavior or question why you're mocking at all.

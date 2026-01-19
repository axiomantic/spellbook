# Code Review Anti-Patterns

Shared reference for code review skills. Each anti-pattern includes detection heuristics, impact assessment, and examples.

---

## Test Anti-Patterns

### Green Mirage

**Description:** Tests pass but do not verify actual behavior. The green checkmark creates false confidence.

**Detection Heuristics:**
- Assertions only check truthy/falsy, not specific values
- Test mocks the function being tested
- No assertions after async operations complete
- `expect(result).toBeTruthy()` on complex objects

**Impact:** Bugs ship to production despite "passing" test suite. Regressions go undetected. Team loses trust in tests.

**Example:**
```javascript
// GREEN MIRAGE: Passes but verifies nothing meaningful
test('processes order', async () => {
  const result = await processOrder(mockOrder);
  expect(result).toBeTruthy();  // Only checks not null/undefined
});

// CORRECT: Verifies actual behavior
test('processes order', async () => {
  const result = await processOrder(mockOrder);
  expect(result.status).toBe('completed');
  expect(result.totalCharged).toBe(99.99);
  expect(mockPaymentService.charge).toHaveBeenCalledWith(99.99);
});
```

---

### Assertion-Free

**Description:** Test executes code but never asserts outcomes. Passes as long as no exception thrown.

**Detection Heuristics:**
- No `expect()`, `assert`, or equivalent calls
- Test body only calls functions without checking returns
- Comments like "// just checking it doesn't crash"

**Impact:** Zero regression detection. Code can return wrong values indefinitely. Maintenance burden without benefit.

**Example:**
```javascript
// ASSERTION-FREE: No verification whatsoever
test('user registration', async () => {
  await registerUser({ email: 'test@example.com', password: 'secret' });
  // Test ends here - what was verified?
});

// CORRECT: Explicit outcome verification
test('user registration', async () => {
  const user = await registerUser({ email: 'test@example.com', password: 'secret' });
  expect(user.id).toBeDefined();
  expect(user.email).toBe('test@example.com');
  expect(await findUserByEmail('test@example.com')).toEqual(user);
});
```

---

### Mock Everything

**Description:** Over-mocking hides integration bugs. Every dependency is mocked, so tests verify mock behavior, not real interactions.

**Detection Heuristics:**
- More mock setup lines than test logic
- Database, filesystem, and network ALL mocked in unit tests
- No integration tests exist
- Mocks return hardcoded "happy path" data

**Impact:** Components work in isolation but fail when integrated. Production bugs in seams between components. False confidence in test coverage.

**Example:**
```javascript
// MOCK EVERYTHING: Tests the mocks, not the code
test('saves user preferences', async () => {
  const mockDb = { save: jest.fn().mockResolvedValue({ id: 1 }) };
  const mockCache = { set: jest.fn().mockResolvedValue(true) };
  const mockLogger = { info: jest.fn() };

  await savePreferences(mockDb, mockCache, mockLogger, { theme: 'dark' });

  expect(mockDb.save).toHaveBeenCalled();  // Only verifies mock was called
});

// CORRECT: Integration test with real (test) database
test('saves user preferences', async () => {
  const db = await createTestDatabase();
  await savePreferences(db, cache, logger, { theme: 'dark' });

  const saved = await db.query('SELECT * FROM preferences WHERE user_id = ?', [userId]);
  expect(saved.theme).toBe('dark');
});
```

---

### Happy Path Only

**Description:** Tests only cover success scenarios. Edge cases, error conditions, and boundary values are ignored.

**Detection Heuristics:**
- No tests with invalid input
- No tests checking error messages or error types
- No boundary value tests (empty arrays, zero, max values)
- Test names all describe success ("should work", "handles data")

**Impact:** Error handling untested and likely broken. Edge cases cause production crashes. Defensive code never exercised.

**Example:**
```javascript
// HAPPY PATH ONLY
test('divides numbers', () => {
  expect(divide(10, 2)).toBe(5);
});

// CORRECT: Covers edge cases and errors
test('divides numbers', () => {
  expect(divide(10, 2)).toBe(5);
  expect(divide(0, 5)).toBe(0);
  expect(divide(-10, 2)).toBe(-5);
});

test('throws on division by zero', () => {
  expect(() => divide(10, 0)).toThrow('Division by zero');
});

test('handles floating point edge cases', () => {
  expect(divide(1, 3)).toBeCloseTo(0.333, 3);
});
```

---

### Test the Mock

**Description:** Assertions verify mock behavior rather than the code under test. The test passes even if the real implementation is broken.

**Detection Heuristics:**
- Assertions only on mock functions (`expect(mock).toHaveBeenCalled()`)
- No assertions on return values or state changes
- Mock configured to return expected value, then test asserts that value

**Impact:** Real implementation can drift from mock. Tests pass but production fails. Mocks become documentation of wishful thinking.

**Example:**
```javascript
// TEST THE MOCK: Verifies mock, not implementation
test('fetches user data', async () => {
  const mockApi = { getUser: jest.fn().mockResolvedValue({ name: 'Alice' }) };

  await displayUserProfile(mockApi, 123);

  expect(mockApi.getUser).toHaveBeenCalledWith(123);  // Only tests mock was called
});

// CORRECT: Verifies observable outcome
test('fetches user data', async () => {
  const mockApi = { getUser: jest.fn().mockResolvedValue({ name: 'Alice' }) };
  const container = document.createElement('div');

  await displayUserProfile(mockApi, 123, container);

  expect(container.textContent).toContain('Alice');  // Tests actual behavior
  expect(container.querySelector('.user-name').textContent).toBe('Alice');
});
```

---

## Code Anti-Patterns

### Silent Swallow

**Description:** Catching exceptions without handling, logging, or re-throwing. Errors disappear into the void.

**Detection Heuristics:**
- Empty catch blocks
- Catch blocks with only `console.log` of generic message
- `catch (e) { return null; }` without context
- No error monitoring or alerting integration

**Impact:** Debugging becomes impossible. Failures manifest far from root cause. Data corruption goes unnoticed.

**Example:**
```javascript
// SILENT SWALLOW: Error disappears
async function saveData(data) {
  try {
    await database.save(data);
  } catch (e) {
    // Swallowed - caller thinks save succeeded
  }
}

// CORRECT: Appropriate error handling
async function saveData(data) {
  try {
    await database.save(data);
  } catch (e) {
    logger.error('Failed to save data', { error: e, data: sanitize(data) });
    throw new DataPersistenceError('Save failed', { cause: e });
  }
}
```

---

### Type Erosion

**Description:** Using `any`, `object`, untyped casts, or disabling type checks. Type safety is undermined.

**Detection Heuristics:**
- `as any` casts
- Function parameters typed as `any` or `object`
- `@ts-ignore` or `@ts-expect-error` without explanation
- `eslint-disable @typescript-eslint/no-explicit-any`

**Impact:** Runtime type errors in production. Refactoring becomes dangerous. IDE assistance degraded.

**Example:**
```typescript
// TYPE EROSION: Safety abandoned
function processResponse(data: any) {
  return data.results.map((r: any) => r.value);  // Runtime crash if structure differs
}

// CORRECT: Explicit types with validation
interface ApiResponse {
  results: Array<{ value: string; id: number }>;
}

function processResponse(data: unknown): string[] {
  const validated = ApiResponseSchema.parse(data);  // Runtime validation
  return validated.results.map(r => r.value);
}
```

---

### Resource Leak

**Description:** Not cleaning up connections, file handles, timers, or event listeners. Resources accumulate until system fails.

**Detection Heuristics:**
- `setInterval` without corresponding `clearInterval`
- Database connections opened but not closed in error paths
- Event listeners added without removal logic
- File handles not closed in finally blocks

**Impact:** Memory exhaustion. Connection pool depletion. Test pollution. Gradual performance degradation.

**Example:**
```javascript
// RESOURCE LEAK: Timer never cleared
function startPolling(callback) {
  setInterval(async () => {
    const data = await fetchData();
    callback(data);
  }, 5000);
  // No way to stop polling - runs forever
}

// CORRECT: Returns cleanup function
function startPolling(callback) {
  const intervalId = setInterval(async () => {
    const data = await fetchData();
    callback(data);
  }, 5000);

  return () => clearInterval(intervalId);  // Caller can stop polling
}
```

---

### Plan Drift

**Description:** Implementation deviates from agreed design or plan without documented justification. Reviewer discovers unexpected changes.

**Detection Heuristics:**
- PR description references plan but implementation differs
- New dependencies added without design discussion
- API contracts changed from what was agreed
- Scope creep: features added beyond plan

**Impact:** Review cycles extended. Integration assumptions broken. Technical debt from ad-hoc decisions.

**Example:**
```
# PLAN DRIFT

Plan said: "Add caching layer using Redis"
Implementation: Uses in-memory Map with custom eviction

No comment explaining why Redis was abandoned.
Reviewer must guess: Was Redis tried and failed? Budget constraint?
Time pressure? Intentional simplification?

# CORRECT: Document deviations

// NOTE: Switched from Redis to in-memory cache.
// Redis added 50ms latency in testing due to network hop.
// In-memory acceptable for <1000 items. See ADR-042.
```

---

### Zombie Code

**Description:** Dead code paths that appear reachable. Code that cannot execute but looks like it should.

**Detection Heuristics:**
- Conditions that can never be true
- Functions defined but never called
- Branches after unconditional returns
- Feature flags that are always false

**Impact:** Maintenance burden. Confusion for future developers. False coverage metrics.

**Example:**
```javascript
// ZOMBIE CODE: Unreachable branch
function getDiscount(user) {
  if (user.isPremium) {
    return 0.2;
  }
  return 0;

  // ZOMBIE: This code cannot execute
  if (user.hasPromo) {
    return 0.1;
  }
}

// CORRECT: Remove or make reachable
function getDiscount(user) {
  if (user.isPremium) {
    return 0.2;
  }
  if (user.hasPromo) {
    return 0.1;
  }
  return 0;
}
```

---

## Review Anti-Patterns

### Rubber Stamp

**Description:** Approving without meaningful review. LGTM without reading the code.

**Detection Heuristics:**
- Approval within seconds of PR creation
- No comments on non-trivial changes
- Same reviewer always approves same author
- Review time shorter than reading time

**Impact:** Bugs reach production. Standards erode. Code review becomes theater.

**Example:**
```
# RUBBER STAMP

PR: 500 lines changing authentication logic
Review: "LGTM" (approved in 2 minutes)

# CORRECT: Substantive review

PR: 500 lines changing authentication logic
Review:
- "Line 45: This allows null passwords - intentional?"
- "The token expiration logic differs from our RFC. See doc link."
- "Missing test for expired token rejection."
- Approved after issues addressed
```

---

### Nitpick Overload

**Description:** Blocking PR on style issues while ignoring logic bugs. Focusing on cosmetics over correctness.

**Detection Heuristics:**
- Comments about naming, spacing, line length dominate
- Logic errors mentioned as "minor" or not at all
- Request changes for formatting only
- No comments on test coverage or error handling

**Impact:** Real bugs merge. Authors become defensive. Review fatigue. Style debates consume energy.

**Example:**
```
# NITPICK OVERLOAD

Author wrote: `if (x == null)` instead of `if (x === null)` (actual bug!)
Also wrote: `functionName` instead of `function_name` (style preference)

Reviewer comments:
- "Please use snake_case for function names"
- "Add blank line before return"
- "This comment should be on the line above"
(No mention of == vs === bug)

# CORRECT: Prioritize correctness

Reviewer comments:
- "BLOCKING: Line 23 uses == instead of ===. This will coerce undefined to null incorrectly."
- "nit: Consider snake_case per style guide (non-blocking)"
```

---

### Drive-by Feedback

**Description:** Vague comments without evidence, reproduction steps, or suggested fixes. Comments that add confusion rather than clarity.

**Detection Heuristics:**
- "This seems wrong" without explaining why
- "Can you improve this?" without specifics
- "I don't like this approach" without alternative
- Questions that could be answered by reading the code

**Impact:** Back-and-forth clarification cycles. Author guesses at reviewer intent. Delays and frustration.

**Example:**
```
# DRIVE-BY FEEDBACK

"This could be better."
"Are you sure about this?"
"Hmm."

# CORRECT: Actionable feedback

"This O(n^2) loop will be slow for our expected 10k items.
Consider using a Map for O(1) lookup. Example:
```
const lookup = new Map(items.map(i => [i.id, i]));
return ids.map(id => lookup.get(id));
```"
```

---

### Authority Deference

**Description:** Accepting questionable code because a senior engineer or respected team member wrote it.

**Detection Heuristics:**
- Junior reviewers only approve senior PRs
- Challenging questions never asked of certain authors
- Standards applied inconsistently based on author
- "They must have a reason" without asking

**Impact:** Senior engineers' bad habits propagate. Juniors don't learn to think critically. Codebase quality varies by author.

**Example:**
```
# AUTHORITY DEFERENCE

Junior reviewer thinking: "This looks like it could deadlock,
but Sarah is a principal engineer. She must know what she's doing."
Review: "LGTM"

# CORRECT: Respectful challenge

Junior reviewer: "I'm not sure I understand the concurrency model here.
Lines 34-40 acquire locks in different order than lines 78-84.
Could this deadlock? Happy to discuss if I'm missing something."
```

---

### Verdict-Finding Mismatch

**Description:** Review comments express concerns but the event type contradicts them. Saying "LGTM" while leaving blocking comments.

**Detection Heuristics:**
- APPROVE event with unresolved questions
- COMMENT event saying "looks good, ship it"
- REQUEST_CHANGES with only nitpicks
- Inconsistent signals between comment text and action

**Impact:** Author unsure whether to merge. CI/CD gates bypassed inappropriately. Confusion about review state.

**Example:**
```
# VERDICT-FINDING MISMATCH

Comments:
- "This will break in production when X happens"
- "Missing error handling for Y"
- "Tests don't cover the main code path"
Event: APPROVE

# CORRECT: Verdict matches findings

Comments:
- "This will break in production when X happens"
- "Missing error handling for Y"
- "Tests don't cover the main code path"
Event: REQUEST_CHANGES

Or if issues are truly minor:
- "nit: Consider renaming for clarity (non-blocking)"
Event: APPROVE
```

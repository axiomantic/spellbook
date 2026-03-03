# Assertion Quality Standard

## Invariant Principles

1. **Assert EVERYTHING.** A test must verify the COMPLETE observable behavior of the unit under test: return value, every mock call with all args, all side effects, all state mutations. No observation left unverified.
2. **ALL assertions must be full.** Assert exact equality against the COMPLETE expected output, always, for all output types -- static, dynamic, or partially dynamic. No partial assertions. No exceptions. (See: The Full Assertion Principle below.)
3. **Assertions must catch garbage.** If broken production code still passes the test, the assertion is worthless.
4. **Position matters, not just presence.** Proving X exists SOMEWHERE is not proving X is WHERE it should be.
5. **Stronger is always better.** Downgrade from exact match only with written justification.
6. **Every assertion must name its kill.** If you cannot name a specific mutation the assertion catches, it catches nothing.

## The Full Assertion Principle

<CRITICAL>
Every assertion MUST assert exact equality against the COMPLETE expected output. This applies to ALL output -- static, dynamic, or partially dynamic. There are no categories of output exempt from this rule.

```python
# CORRECT: exact equality on complete output (static)
assert result == "the entire expected string, every character"

# CORRECT: exact equality with dynamically constructed expected value
def get_message():
    return f"Today's date is {datetime.date.today().isoformat()}"

message = get_message()
assert message == f"Today's date is {datetime.date.today().isoformat()}"

# WRONG: partial assertion. Dynamic value is no excuse for a partial check.
assert datetime.date.today().isoformat() in message

# WRONG: meaningless
assert len(result) > 0

# WRONG: still partial. Doesn't verify structure, ordering,
# completeness, or absence of unexpected content.
assert "foo" in result and "bar" in result
```

**Even dynamic content must be fully asserted.** When output contains dynamic values (timestamps, computed IDs, derived strings), construct the complete expected value using the same logic, then assert `==`. Do not assert partial membership of the dynamic value.

```python
# CORRECT: construct full expected object dynamically
user = create_user(name="Alice", role="admin")
assert user == User(
    name="Alice",
    role="admin",
    created_at=user.created_at,  # dynamic field: assert the actual value roundtrips
    slug="alice",
)

# WRONG: partial field check, misses ordering bugs, missing fields, extra fields
assert user.name == "Alice"
assert user.role == "admin"

# CORRECT: full dict equality with dynamically constructed expected
result = build_config(env="prod")
assert result == {
    "env": "prod",
    "host": "prod.example.com",
    "timeout": 30,
    "features": ["a", "b", "c"],
}

# WRONG: key presence check
assert "env" in result
assert result["env"] == "prod"

# CORRECT: full list equality
items = get_sorted_items()
assert items == ["alpha", "beta", "gamma"]

# WRONG: count + membership, misses order and extra items
assert len(items) == 3
assert "alpha" in items
```

**Normalization is the last resort, not a technique.** Strip or replace a value only when it is genuinely unknowable at test time (random UUIDs, OS-assigned PIDs, memory addresses). Never use normalization to avoid constructing a complete expected value.

```python
# LAST RESORT ONLY: normalize a truly unknowable value (random UUID),
# then assert exact equality on everything else
result = create_session(user_id=42)
assert result == {
    "user_id": 42,
    "token": result["token"],  # token is cryptographically random: assert it roundtrips
    "expires_in": 3600,
}

# WRONG: using normalization to avoid a full assertion
normalized = re.sub(r'[0-9a-f-]{36}', 'UUID', result_str)
assert "user_id" in normalized  # still partial after normalization!
```

This principle is the FOUNDATION of assertion quality. Every other rule in this document supports it. If you remember nothing else: ALL assertions must be full, regardless of whether output is static or dynamic. Build the expected value -- do not skip it.
</CRITICAL>

## Mock Call Assertions

<CRITICAL>
When a dependency is mocked, you MUST assert EVERY call made to that mock, with ALL arguments, in order. Partial mock assertions are BANNED with no exceptions.

```python
# CORRECT: assert every call, all args, in order
mock_sender.send.assert_has_calls([
    call(to="alice@example.com", subject="Welcome", body="Hello Alice"),
    call(to="bob@example.com", subject="Welcome", body="Hello Bob"),
])
mock_sender.send.assert_call_count == 2  # verify no extra calls

# WRONG: only asserted one call, missed the second
mock_sender.send.assert_called_once_with(
    to="alice@example.com", subject="Welcome", body="Hello Alice"
)

# WRONG: only checked it was called, no argument verification
mock_sender.send.assert_called()

# WRONG: only checked some arguments
mock_sender.send.assert_called_with(to="alice@example.com")

# WRONG: mock.ANY hides argument values -- BANNED
mock_sender.send.assert_called_with(to=mock.ANY, subject=mock.ANY, body=mock.ANY)
```

**Rules for mock assertions:**

1. **Every mock call must be verified.** If the code calls a mock 3 times, assert all 3 calls. Missing calls means missing behavior verification.
2. **All arguments must be specified.** Never use `mock.ANY` as a substitute for an actual expected value. Construct the expected argument if it is dynamic.
3. **Call count must be verified.** After `assert_has_calls`, also assert `call_count` to prevent unexpected extra calls from passing.
4. **Order matters.** Use `assert_has_calls([...], any_order=False)` by default. Use `any_order=True` only when order is genuinely irrelevant and document why.
5. **No `mock.ANY`.** If the value is dynamic, construct the expected value dynamically and assert it exactly. `mock.ANY` is as weak as `assert "foo" in result` -- it proves nothing.

```python
# CORRECT: dynamic argument -- construct expected, assert exactly
expected_payload = build_expected_payload(user_id=42, timestamp=freeze_time.now())
mock_client.post.assert_called_once_with("/api/events", json=expected_payload)

# WRONG: dynamic argument -- mock.ANY hides the content
mock_client.post.assert_called_once_with("/api/events", json=mock.ANY)
```
</CRITICAL>

## Side Effects and State Mutations

<CRITICAL>
Every observable side effect of the unit under test MUST be asserted. Do not limit assertions to the return value.

**What counts as a side effect (must be asserted):**
- Database writes: assert the complete record as written, all fields
- File writes: assert the complete file contents
- Cache updates: assert the exact cached value
- Event emissions: assert every event, all payload fields
- Queue publishes: assert every message, all fields
- External API calls: assert via mock (see Mock Call Assertions above)

```python
# CORRECT: assert return value AND all side effects
result = process_order(order)
assert result == OrderResult(id=order.id, status="confirmed", total=99.99)

# Assert the database write happened with all fields
saved = db.orders.get(order.id)
assert saved == Order(
    id=order.id,
    user_id=order.user_id,
    status="confirmed",
    total=99.99,
    confirmed_at=saved.confirmed_at,  # dynamic: assert it roundtrips
    items=order.items,
)

# Assert the event was emitted
mock_event_bus.publish.assert_called_once_with(
    "order.confirmed",
    {"order_id": order.id, "user_id": order.user_id, "total": 99.99},
)

# WRONG: only asserted return value, missed database write and event
assert result.status == "confirmed"
```
</CRITICAL>

## The Assertion Strength Ladder

Per output type, a strict hierarchy. Use the highest level achievable. Levels below PREFERRED require written justification (inline comment explaining why).

### String/Text Output (writers, formatters, serializers)

| Level | Name | Status |
|-------|------|--------|
| 5 | Exact match (`assert output == expected`) | GOLD |
| 4 | Parsed structural (parse output, assert on parsed structure) | PREFERRED |
| 3 | Structural containment (verify X inside Y's block by index) | ACCEPTABLE with justification |
| 2 | Bare substring (`assert "X" in output`) | BANNED |
| 1 | Length/existence (`assert len(x) > 0`) | BANNED |

### Object Output

| Level | Name | Status |
|-------|------|--------|
| 5 | Full equality (`assert result == expected`) | GOLD |
| 4 | All-field assertions (every semantically important field) | PREFERRED |
| 3 | Partial field assertions (some fields only) | BANNED without justification |
| 2 | Type/structure only (`isinstance`) | BANNED |
| 1 | Existence (`is not None`) | BANNED |

### Collection Output

| Level | Name | Status |
|-------|------|--------|
| 5 | Full equality (`assert items == [expected1, expected2]`) | GOLD |
| 4 | Content verification (specific items present + content verified) | PREFERRED |
| 3 | Count + name-only (`len == 3` + name in items) | BANNED |
| 2 | Count only | BANNED |
| 1 | Non-empty | BANNED |

## The Bare Substring Problem

`assert "X" in output` is always a mirage because:

- X could appear in a comment, different section, error message, or anywhere
- Proves X exists SOMEWHERE but not WHERE
- A writer emitting fields outside their struct block passes the check
- A formatter dumping all content into a single line passes the check
- An error handler including the keyword in its message passes the check

**The only valid use of substring checks** is when combined with structural containment: verify the position of X within the correct block (by index range, line number, or parsing).

```python
# BANNED: bare substring
assert "data" in output

# ACCEPTABLE (Level 3): substring + structural containment with justification
lines = output.splitlines()
struct_start = next(i for i, l in enumerate(lines) if "struct Foo" in l)
struct_end = next(i for i, l in enumerate(lines) if l.strip() == "}" and i > struct_start)
struct_body = "\n".join(lines[struct_start:struct_end + 1])
assert "int data;" in struct_body  # field must be inside struct block

# PREFERRED (Level 4): parse and assert on structure
parsed = parse_c_header(output)
foo_struct = parsed.structs["Foo"]
assert "data" in foo_struct.fields
assert foo_struct.fields["data"].type == "int"

# GOLD (Level 5): exact match
assert output == expected_output
```

## The Broken Implementation Test

Every new assertion must pass this annotation test. Write it as a comment or in your output:

```
MUTATION CHECK: [assertion text]
  FAILS IF: [specific production code mutation]
  PLAUSIBLE? [Yes/No + reasoning]
```

Rules:
- "None" or "nothing" are NOT valid FAILS IF answers
- The mutation must be PLAUSIBLE (a real bug: off-by-one, wrong variable, missing field, swapped arguments, dropped section)
- Adversarial construction ("return the exact expected string minus one character") does not count
- If you cannot fill in FAILS IF with a specific, plausible mutation, the assertion is too weak

### Examples

```
MUTATION CHECK: assert len(result) > 0
  FAILS IF: nothing plausible -- empty result only
  PLAUSIBLE? No. Any garbage non-empty output passes. ASSERTION TOO WEAK.

MUTATION CHECK: assert result == {"status": "ok", "count": 3, "items": ["a", "b", "c"]}
  FAILS IF: count field returns 2 instead of 3, or items list is missing "c"
  PLAUSIBLE? Yes. Off-by-one in count, dropped item in iteration. ASSERTION VALID.

MUTATION CHECK: assert "data" in output
  FAILS IF: "data" not present at all
  PLAUSIBLE? No. Only catches complete omission. "data" in a comment or error
  message passes. Field in wrong struct passes. ASSERTION TOO WEAK.

MUTATION CHECK: assert foo_struct.fields["data"].type == "int"
  FAILS IF: type resolver returns "unsigned int" or "char" instead of "int"
  PLAUSIBLE? Yes. Wrong type mapping in resolver. ASSERTION VALID.
```

## Justification Requirements

Using levels below PREFERRED requires an inline comment explaining why:

| Reason | Valid? | Required Mitigation |
|--------|--------|---------------------|
| Output contains dynamic values (timestamps, IDs) | Never alone | Construct expected value dynamically, assert == full output |
| Truly unknowable runtime values (random UUIDs, OS PIDs, memory addresses) | Sometimes | Assert the field roundtrips OR strip ONLY the unknowable part and assert == on everything else |
| Platform-dependent output (line endings, paths) | Yes | Normalize platform differences before comparing; assert == on normalized form |
| Output too large for exact match | Sometimes | Parse and assert on structure (Level 4); justify why parsing is impossible if using Level 3 |
| "It's just a quick test" | Never | No such thing as a quick test. Tests outlive the code they test. |
| "The important thing is that it contains X" | Never | WHERE it contains X matters. Use structural containment at minimum. |
| "Output is too long for exact match" | Never | Use triple-quoted strings or dedent helpers. Length is not a justification for partial assertions. |
| "I'll just check the key parts" | Never | ALL output demands complete verification. Partial checks miss structural errors, ordering bugs, and extra garbage. |
| "Output has a dynamic element so I can't do exact match" | Never | Construct the expected value dynamically. Dynamic content is not an excuse for partial assertions. |
| "I'll use mock.ANY for the dynamic argument" | Never | Construct the expected argument dynamically. `mock.ANY` proves nothing. |
| "I only need to verify the important calls" | Never | Assert every mock call. Unverified calls hide behavior gaps. |

## Usage Reference

```markdown
Read assertion quality standard (patterns/assertion-quality-standard.md) in full.
Classify each assertion on the Assertion Strength Ladder.
```

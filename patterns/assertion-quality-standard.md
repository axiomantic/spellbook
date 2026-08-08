# Assertion Quality Standard

<ROLE>
Test Assertion Auditor. Your reputation depends on assertions that actually catch bugs. A test that passes on broken production code is not a test -- it is a liability that gives false confidence and survives indefinitely in the codebase.
</ROLE>

## Invariant Principles

1. **Assert EVERYTHING.** Verify the COMPLETE observable behavior: return value, every mock call with all args, all side effects, all state mutations.
2. **ALL assertions must be full.** Assert exact equality against the COMPLETE expected output, always, for all output types -- static, dynamic, or partially dynamic. No partial assertions. No exceptions. (See: The Full Assertion Principle below.)
3. **Assertions must catch garbage.** If broken production code still passes, the assertion is worthless.
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

When output contains dynamic values (timestamps, computed IDs, derived strings), construct the complete expected value using the same logic, then assert `==`. Do not assert partial membership of the dynamic value.

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

ALL assertions must be full, regardless of whether output is static or dynamic. Build the expected value -- do not skip it. The most common failure mode is treating dynamic output as an excuse for partial checks.
</CRITICAL>

## Mock Call Assertions

<CRITICAL>
When a dependency is mocked, MUST assert EVERY call made to that mock, with ALL arguments, in order. Partial mock assertions are BANNED with no exceptions.

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

# WRONG: a wildcard matcher hides argument values -- BANNED
mock_sender.send.assert_called_with(to=mock.ANY, subject=mock.ANY, body=mock.ANY)
```

**Rules for mock assertions:**

1. **Assert every call.** If a mock is called 3 times, assert all 3 calls.
2. **Specify all arguments.** Never use a wildcard matcher; construct the expected argument if it is dynamic.
3. **Verify call count.** After `assert_has_calls`, assert `call_count` to prevent unexpected extra calls from passing.
4. **Order matters.** Use `any_order=False` by default. Use `any_order=True` only when genuinely irrelevant and document why.
5. **No wildcard matchers.** Construct the expected value dynamically and assert it exactly. (See: The Wildcard Matcher Ban below.)

```python
# CORRECT: dynamic argument -- construct expected, assert exactly
expected_payload = build_expected_payload(user_id=42, timestamp=freeze_time.now())
mock_client.post.assert_called_once_with("/api/events", json=expected_payload)

# WRONG: dynamic argument -- the wildcard hides the content
mock_client.post.assert_called_once_with("/api/events", json=mock.ANY)
```
</CRITICAL>

## The Wildcard Matcher Ban

<CRITICAL>
**The rule is about the property, not the name.** A wildcard matcher is any value whose
equality comparison returns True against every possible value. An assertion built from
wildcards cannot fail, so it proves nothing and certifies nothing. Ban it on that
property, regardless of which library supplies it or what that library calls it.

**Known spellings (NOT an exhaustive list):**

| Spelling | Source |
|----------|--------|
| `mock.ANY`, `unittest.mock.ANY` | stdlib `unittest.mock` |
| `ANY` (bare import, pytest-style helpers) | any library re-exporting a wildcard sentinel |
| `AnyThing`, `AnyThing()` | `dirty-equals` (reachable from tripwire assertions; NOT part of `tripwire.__all__`) |
| `IsStr`, `IsInt`, `IsList(...)` used with no constraint arguments | `dirty-equals` -- constrained forms are fine, unconstrained ones approach wildcards |
| `mocker.ANY`, matcher objects named `Any*`, `_`, `IsAnything`, `anything()` | assorted mock/matcher libraries |

<RULE>This table is a list of EXAMPLES, not the definition. A new test framework brings a new
spelling, and the new spelling is banned the moment it exists -- no edit to this document is
needed to make that true. Check the PROPERTY ("does this compare equal to everything?"), never
the name.</RULE>

### Failure 1: a wildcard anywhere in a tripwire assertion defeats tripwire's premise

This is the primary point, and it is NOT limited to the all-wildcard case.

Tripwire exists to make unasserted and unverified interactions into errors. Every call must
be pre-authorized, every interaction asserted, every mock used. A wildcard in an
`assert_call` satisfies that machinery while verifying nothing: the interaction is formally
"asserted", the teardown check passes, and the value that was actually passed is never
examined. The framework reports certainty it does not have.

That failure begins at the FIRST wildcard, not at the last one. One wildcard in a position
where a real value was knowable is already a weakened assertion. An assertion where every
position is a wildcard is merely the degenerate end of the same spectrum -- the point at
which the assertion has decayed into a bare "this was called at some point."

```python
# WEAKENED: kwargs were knowable; the wildcard drops them from verification
mock_client.post.assert_call(args=("/api/events",), kwargs=AnyThing(), returned=AnyThing())

# DEGENERATE: the same failure taken to its limit -- proves only that a call happened
mock_client.post.assert_call(args=AnyThing(), kwargs=AnyThing(), returned=AnyThing())
```

<RULE>Judge a tripwire assertion by how many positions carry a REAL value, not by whether it
tripped the framework's all-wildcard guard. An assertion that clears the guard can still be
worthless.</RULE>

### Failure 2: the bare-class trap (a second, subtler defect layered on the first)

`AnyThing` belongs to `dirty-equals`, not to tripwire. It is an optional, lazily imported
dependency and is absent from `tripwire.__all__`.

`dirty-equals` deliberately supports comparing against the bare CLASS.
`DirtyEqualsMeta.__eq__` (`dirty_equals/_base.py`) implements `AnyThing == 5` as
`AnyThing() == 5`, and the library's own front page demonstrates the idiom
(`assert 1 == IsPositive`). So writing `AnyThing` rather than `AnyThing()` is IMITATION OF A
DOCUMENTED UPSTREAM IDIOM. It is a trap, not carelessness, and treating it as carelessness
will mislead any reader who knows the library.

The trap is what happens when that idiom crosses into tripwire. Tripwire's all-wildcard
guard (`_verifier.py`) tests `all(isinstance(v, AnyThing) ...)`. `isinstance(AnyThing,
AnyThing)` is False, so the bare class slips past the guard while still comparing equal to
everything. The wildcard matches everything AND evades the check built to catch it.
Upstream's own `tests/unit/test_wildcard_detection.py` exercises only the instance form,
which is why their CI never surfaced this.

```python
# WORST: asserts nothing, and evades tripwire's own all-wildcard guard
mock.assert_call(args=AnyThing, kwargs=AnyThing, returned=AnyThing)

# STILL BANNED as an assertion, but at least the framework guard can see it
mock.assert_call(args=AnyThing(), kwargs=AnyThing(), returned=AnyThing())
```

<RULE>Never pass the bare class inside a tripwire assertion. If a wildcard is genuinely
justified (see below), it MUST be an INSTANCE so the framework's guards stay live -- and
better still, use a real value or a type constraint so no wildcard is needed at all. Fixing
class to instance is NOT a fix for Failure 1; it only restores the guard.</RULE>

<RULE>Tripwire accepting a wildcard at all is a defect in tripwire -- it short-circuits the
framework's entire purpose. Do not treat the framework's silence as permission. The
corresponding defect on our side is a prompt that taught the API without teaching that the
assertion must be meaningful.</RULE>

### The dynamic-value case, done correctly

Wildcards get reached for when the expected value is not known at authoring time. That is
not a justification -- it is a prompt to capture the real value and assert it.

```python
# CORRECT: capture the actual argument, then assert it exactly
captured = {}
mock_client.post.calls(lambda *args, **kwargs: captured.update(kwargs))
send_event(user_id=42)
assert captured == {"json": {"user_id": 42, "type": "signup"}}

# CORRECT: run once, read the real repr from the failure hint, assert against it
# (tripwire's format_assert_hint prints actual args/kwargs/returned)
mock_client.post.assert_call(
    args=("/api/events",),
    kwargs={"json": {"user_id": 42, "type": "signup"}},
    returned=Response(status=201),
)

# WRONG: wildcard standing in for a value the test could have captured
mock_client.post.assert_call(args=AnyThing, kwargs=AnyThing, returned=AnyThing)
```

### Harvested values are UNTRUSTED until you read them

<CRITICAL>
Capturing the real value is the right instinct, and it is also where secrets leak into the
repository. Diagnostic output -- tripwire's failure hints, a captured object's `repr`, a
debugger dump -- reflects the LIVE process. It can contain environment variables,
credentials, API tokens, absolute home directories, hostnames, and other machine-specific
data.

<RULE>NEVER paste a harvested value verbatim into an assertion without reading it first,
line by line. Reduce it to the strongest PORTABLE form that still constrains the
behavior.</RULE>

**Worked example (this actually happened).** An agent fixing wildcard assertions harvested
the reported value for one mock from a tripwire hint. The value was a full `AgentOptions`
object whose repr embedded the entire `os.environ`, including `TWILIO_AUTH_TOKEN` and
`TWILIO_ACCOUNT_SID`. Pasted verbatim, it would have committed live credentials to the
repository. It was caught in review before it landed.

**Reduction ladder, strongest first:**

1. **A short portable literal** -- the specific field(s) the behavior actually depends on
   (`{"model": "opus", "timeout": 30}`). Best: constrains the most, leaks nothing.
2. **A type constraint** -- `IsInstance(AgentOptions)`. This is a genuine constraint, not a
   wildcard: it fails on the wrong type, and being an INSTANCE it keeps tripwire's guards
   live. Use it when the object is large or environment-derived but its type is the thing
   under test.
3. **`AnyThing()`** -- instance form, with an inline comment naming why the value is
   incidental. Last resort only, per the rules above.

```python
# WRONG: harvested verbatim -- embeds os.environ, ships live credentials
runner.run.assert_call(
    args=(AgentOptions(env={"TWILIO_AUTH_TOKEN": "SK9f...", ...}, cwd="/Users/me/dev"),),
)

# CORRECT: reduced to a type constraint -- portable, still fails on the wrong type
runner.run.assert_call(args=(IsInstance(AgentOptions),), kwargs={"stream": True})
```

Scan every harvested value for: `*_TOKEN`, `*_SECRET`, `*_KEY`, `*_PASSWORD`, anything
resembling a credential, `/Users/<name>` or `/home/<name>` paths, hostnames, and full
environment dumps. If any are present, the value is NOT usable as written.
</CRITICAL>

**The only admissible wildcard** is one covering a value that is genuinely incidental to
the behavior under test -- a wall-clock timestamp, a tmp path, an object identity, an OS
PID. Every such use MUST be an instance AND carry an inline comment naming which value is
incidental and why.

```python
# ACCEPTABLE: tmp path is assigned by the OS and irrelevant to the behavior asserted
mock_writer.write.assert_call(
    args=(AnyThing(),),  # incidental: pytest tmp_path, differs every run
    kwargs={"encoding": "utf-8", "newline": "\n"},
    returned=None,
)
```

MUTATION CHECK: `assert_call(args=AnyThing, kwargs=AnyThing, returned=AnyThing)`
  FAILS IF: the call is never made at all
  PLAUSIBLE? No. Wrong args, wrong kwargs, wrong return, swapped parameters, wrong
  types -- all pass. ASSERTION PROVES NOTHING.
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

`assert "X" in output` is always a mirage -- it proves X exists SOMEWHERE but not WHERE:

- A writer emitting fields outside their struct block passes the check
- A formatter dumping all content into a single line passes the check
- An error handler including the keyword in its message passes the check

**The only valid use of substring checks** is combined with structural containment: verify the position of X within the correct block (by index range, line number, or parsing).

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

<analysis>
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
</analysis>

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
| "I'll use a wildcard (`mock.ANY`, `AnyThing`, ...) for the dynamic argument" | Never | Construct or capture the expected argument. A matcher that equals every value proves nothing. |
| "The wildcard is fine, our framework guards against all-wildcard assertions" | Never | Guards test `isinstance`; a bare CLASS silently evades them. The guard's existence is not the assertion's strength. |
| "This library's wildcard isn't the one the standard names" | Never | The ban is on the property, not the spelling. Every new framework brings a new name for it. |
| "I only need to verify the important calls" | Never | Assert every mock call. Unverified calls hide behavior gaps. |

## Usage Reference

```markdown
Read assertion quality standard (patterns/assertion-quality-standard.md) in full.
Classify each assertion on the Assertion Strength Ladder.
```

<FORBIDDEN>
- Using any wildcard matcher (`mock.ANY`, `unittest.mock.ANY`, dirty-equals `AnyThing`/`AnyThing()`, or any equivalent under another name) as a substitute for a real expected value
- Leaving a wildcard in ANY position of a tripwire `assert_call` where the real value was knowable -- the all-wildcard case is the limit of this failure, not its only form
- Passing a wildcard CLASS (`AnyThing`) inside a tripwire assertion -- it matches everything AND defeats tripwire's own all-wildcard guard, which tests `isinstance`
- Pasting a harvested diagnostic value into an assertion without reading it -- harvested reprs carry environment variables, credentials, and absolute paths
- Using a wildcard without an inline comment naming the incidental value it covers
- Using `assert "X" in output` without structural containment
- Asserting only the return value when side effects exist
- Using `assert len(x) > 0` or `assert x is not None` as the sole assertion
- Partial field checks on objects when full equality is achievable
- Asserting fewer mock calls than were made
- Using normalization to avoid constructing a complete expected value
- Writing FAILS IF as "nothing" or "nothing plausible" and keeping the assertion
- Justifying a downgrade with "output is dynamic" without constructing the full expected value
- Skipping call count verification after assert_has_calls
</FORBIDDEN>

<FINAL_EMPHASIS>
You are a Test Assertion Auditor. Every weak assertion you allow to pass will outlive the bug it was meant to catch, silently certifying broken code for years. Demand full assertions -- not because the standard says so, but because partial assertions are worse than no assertions: they suppress the instinct to look closer.
</FINAL_EMPHASIS>

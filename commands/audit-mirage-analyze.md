---
description: "Phases 2-3 and 7 of auditing-green-mirage: systematic line-by-line audit, the Green Mirage Patterns, named assertion shapes, and the fix-verification Test Adversary prompt"
---

<ROLE>
Green Mirage Auditor. Your reputation depends on exposing every false-positive test. A missed green mirage passes your review but ships a hidden defect to production. Be thorough and unsparing.
</ROLE>

# Phases 2-3 and 7: Systematic Audit, Green Mirage Patterns, Fix Verification

## Invariant Principles

1. **Every test function gets audited** - No skipping tests that "look fine"; line-by-line analysis catches what scanning misses
2. **Assertions determine test value** - A test without meaningful assertions is worse than no test: it creates false confidence and hides production defects
3. **Score by pattern, not by intuition** - Apply every Green Mirage Pattern as the scoring rubric
4. **A fix is a new suspect** - A remediated assertion gets the same adversarial treatment as the assertion it replaced

## Phase 2: Systematic Line-by-Line Audit

For EACH test file, work through EVERY test function. For tests with multiple actions, apply one "Action Analysis" block per action.

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

Trace the COMPLETE path for each test action:

```
test_function()
  |-> production_function(args)
        |-> helper_function()
        |     |-> external_call() [mocked? real?]
        |     |-> returns value
        |-> processes result
        |-> returns final
  |-> assertion checks final
```

At each step:
- Is this step tested or assumed to work?
- If this step returned garbage, would the test catch it?
- Are error paths tested or only happy paths?

## Phase 3: The Green Mirage Patterns

Check EVERY test against ALL patterns.

### Pattern 1: Existence vs. Validity
**Symptom:** Checking existence or count without validating content.
```python
# GREEN MIRAGE - Existence-only
assert output_file.exists()
assert len(result) > 0
assert response is not None

# GREEN MIRAGE - Count-only (right number, wrong content)
assert len(result) == 3
assert len(response["items"]) == expected_count

# GREEN MIRAGE - Wildcard matchers (accept anything)
mock_handler.assert_called_with(mock.ANY, mock.ANY)
assert result == {"id": unittest.mock.ANY, "name": unittest.mock.ANY}
```
**Detection patterns:** `len(x) > 0`, `len(x) == <number>` without content assertion on same object, `is not None` without value assertion, `.exists()`, `key in dict` without value assertion, `mock.ANY`, `unittest.mock.ANY`.

**Question:** If the content was garbage (right count/type/existence), would this catch it?

### Pattern 2: Partial Assertion on Any Output (BANNED)
**Symptom:** Using `in`, substring checks, or partial matches on any output -- static, dynamic, or partially dynamic.

<CRITICAL>
**This is not a code smell to investigate. This is BANNED.** The Full Assertion Principle requires exact equality against the COMPLETE expected output. `assert "substring" in result` is NEVER acceptable. For dynamic output, construct the expected value using the same logic, then assert `==`. No exceptions.

See: The Full Assertion Principle in `patterns/assertion-quality-standard.md`.
</CRITICAL>

```python
# BANNED - Partial assertions on any output
assert 'SELECT' in query           # Garbage SQL could contain SELECT
assert 'error' not in output       # Wrong output might not have 'error'
assert "struct Point" in result    # Wrong fields, missing fields, extra garbage all pass
assert expected_id in result       # Result could have wrong structure
assert key in response_dict        # Value at key could be garbage
assert "foo" in result and "bar" in result  # Doesn't verify ordering, completeness, structure

# BANNED - Pychoir/matcher used to avoid computing expected value
from pychoir import IsInstance
assert result == {"count": IsInstance(int), "items": IsInstance(list)}  # Accepts any int/list
```

**CORRECT tests assert COMPLETE output:**
```python
# CORRECT - Exact equality on complete output
assert query == "SELECT id, name FROM users WHERE active = true"
assert result == {"id": 123, "name": "test", "status": "active"}

# CORRECT - Multi-line output uses exact equality
expected = textwrap.dedent("""\
    struct Point {
        int x;
        int y;
    };
""")
assert result == expected
```

**Classification:**
1. `assert "x" in result` is BANNED on ALL output -- static or dynamic. Assert `result == expected_complete_output`.
2. For dynamic values: construct the complete expected value using the same logic, then assert `==`.
3. Normalization (masking non-deterministic parts) is LAST RESORT only -- for truly unknowable values (random UUIDs, OS-assigned PIDs, memory addresses). Never use normalization to avoid constructing a complete expected value.
4. Pychoir matchers require a justification comment per use. If the value is constructable, compute it and assert exact equality.

### Pattern 3: Shallow String/Value Matching
**Symptom:** Checking keywords without validating structure; also catches single-field checks on multi-field objects. When both Pattern 2 and Pattern 3 apply, report as Pattern 2.
```python
# GREEN MIRAGE
assert 'SELECT' in query              # BANNED for any output (Pattern 2)
assert 'error' not in output           # Absence check proves nothing about correctness
assert result.status == 'success'      # Other fields unchecked
```
**Question:** Could syntactically broken output still contain this keyword? Is only one field being checked on a multi-field object?

### Pattern 4: Lack of Consumption
**Symptom:** Generated output is never used in a way that validates it.
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
**Question:** Would this test fail if an exception was raised in the specific code block under test?

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

Mock calls fall under this pattern too: EVERY call a test provokes must be asserted, with
all arguments and with the call count verified. "Not all mock calls asserted" is a GREEN
MIRAGE in its own right -- an unverified call is behavior the test provoked and never looked at.

### Pattern 8: Incomplete Branch Coverage
**Symptom:** Happy path tested, error paths assumed.
```python
# Tests only success case
def test_process_data():
    result = process(valid_data)
    assert result.success

# Missing: test_process_invalid_data, test_process_empty, test_process_malformed
```
**Question:** What happens when input is invalid/empty/malformed/at boundary?

### Pattern 9: Skipped Tests Hiding Failures
**Symptom:** Tests marked skipped, xfail, or conditionally excluded to avoid dealing with failures. A skipped test catches zero bugs. If the skip exists because the test exposes a real bug, the skip is hiding a production defect.

**The only legitimate skips** are environmental constraints where the test literally cannot execute:
- OS-specific tests on a different OS (`@pytest.mark.skipif(sys.platform != 'linux')`)
- Hardware-dependent tests without the hardware (GPU, TPU, FPGA)
- Framework-version-specific tests on an older version

**Everything else is a Green Mirage:**
```python
# GREEN MIRAGE - Skipping because it fails is not fixing it
@pytest.mark.skip(reason="flaky, needs investigation")
def test_concurrent_writes():
    ...

# GREEN MIRAGE - xfail used to sweep known bugs under the rug
@pytest.mark.xfail(reason="race condition in handler")
def test_event_ordering():
    ...

# GREEN MIRAGE - Conditional skip to dodge a bug on specific systems
@pytest.mark.skipif(sys.platform == 'darwin', reason="segfaults on macOS")
def test_memory_management():
    ...

# GREEN MIRAGE - unittest style
@unittest.skip("TODO: fix after refactor")
def test_data_migration():
    ...

# GREEN MIRAGE - Conditional import skip hiding missing dependency
pytest.importorskip("some_module")  # If the module is needed, install it
```

For each skipped test, answer:
1. WHY is this test skipped? Is it a real environmental constraint, or covering up a failure?
2. WHAT bug does the test expose when unskipped? That bug exists in production right now.
3. HOW long has this skip been in place? Stale skips are forgotten bugs.

If removing the skip causes the test to fail: that is a live production defect hidden by a green build.

### Pattern 10: "Strengthened" Assertion That Is Still Partial
**Symptom:** A fix that replaces one weak assertion with another weak assertion. Creates the illusion of improvement while leaving the same blind spots open.

<CRITICAL>
This pattern catches fixes that look like improvements but are NOT. It is especially common when subagents interpret "strengthen assertions" as permission to use `assert "some_string" in result` instead of the original `assert len(result) > 0`. Both are green mirages. Pattern 10 MUST be checked during fix verification (Phase 7).
</CRITICAL>

```python
# BEFORE: Pattern 1 (existence-only) - correctly identified as green mirage
assert result is not None
assert len(result) > 0

# "FIX" THAT IS STILL A GREEN MIRAGE:
assert "struct Point" in result      # Pattern 2: still partial!
assert "expected_field" in result    # Pattern 2: still partial!

# ANOTHER BAD "FIX":
assert result == writer.write(data)  # Tautological: testing function against itself

# CORRECT FIX:
expected = textwrap.dedent("""\
    struct Point {
        int x;
        int y;
    };
""")
assert result == expected            # Exact equality on complete output
```

**Detection:** Compare before and after assertions. If the fix replaced one BANNED pattern with another BANNED pattern (even a different one), it is Pattern 10.

**Question:** Did the fix actually reach Level 4+ (exact match or parsed structural), or did it just move from one BANNED level to another?

### Pattern 11: Self-Manufactured Evidence
**Symptom:** The test's setup creates the very condition the test then asserts. The
input comes from the fixture, not from the world the check is supposed to guard, so
the assertion holds whatever the real subject does.

```python
# GREEN MIRAGE - the fixture supplies the thing under test
def test_skill_directory_is_discovered(tmp_path):
    (tmp_path / "skills" / "fun-mode").mkdir(parents=True)   # fabricated here
    assert "fun-mode" in discover_skills(tmp_path)           # asserts the fixture

# The real defect: skills/fun-mode/ had been DELETED from the repository.
# The test passed before the deletion and after it, unchanged.
```

**Distinction from Pattern 5.** Pattern 5 substitutes a mock for the SUBJECT: the
production code path never executes. Pattern 11 executes the real code path in full —
what is fabricated is the ENVIRONMENT the code reads. Nothing is mocked, coverage
reports the subject as exercised, and a red-green cycle looks entirely normal, because
planting a bug in the subject genuinely turns it red. Only a defect in the *world* —
a deleted directory, a renamed key, a dropped config entry — passes through unseen.

**Detection recipe:**

1. For each assertion, name where its input originated. Walk it back through the
   fixtures to a source.
2. Classify that source: the repository/production artifact under guard, or something
   the test itself wrote.
3. If it is the latter, apply the deletion test: **would this test still pass if the
   real artifact were deleted?** If yes, it guards its own setup.

A fabricated environment is legitimate ONLY when the test drives the fabricated input
through the subject to observe behavior, and a separate check ties the fixture back to
the real artifact.

**Fix shape.** `tests/scripts/test_shell_harness_reports_failures.py` is the worked
example: it stages the REAL subject into a sandbox, links the repository paths the
subject reads back to the actual tree, asserts a GREEN baseline there, then plants one
deliberate failure and asserts the transition to RED. The sandbox exists to make the
plant safe, not to supply the evidence — and the green-to-red transition is what proves
the check is wired to the subject rather than to the fixture. Its docstring names why
running against the real repository alone would have reproduced the original silence.

**Question:** Does this assertion's input come from the world the check guards, or from
the check's own setup?

## Named Shapes

Two recurring shapes cut across the patterns. Pattern 1 and Pattern 2 name the wildcard
symptom; the first shape here supplies the detection recipe. The second shape guards the
standard REMEDY for a wildcard, so it applies during fix verification as well as audit.

### Named Shape: Assertion That Matches Everything

<CRITICAL>
An assertion built entirely from wildcard matchers cannot fail. It is the purest green
mirage: it occupies the line where verification belongs, reads as coverage, and certifies
nothing. Flag it on the PROPERTY -- "does this matcher compare equal to every possible
value?" -- never on the library-specific name.

**Detection recipe:**

1. Grep for known wildcard spellings across the test tree:
   ```bash
   rg -n 'mock\.ANY|unittest\.mock\.ANY|\bANY\b|\bAnyThing\b|IsAnything|anything\(\)' tests/
   ```
2. Flag any assertion where EVERY matcher position is a wildcard. Those assert literally
   nothing and are unconditionally GREEN MIRAGE.
3. Flag any wildcard in a non-incidental position (a value the test could have captured).
4. **For tripwire specifically, check CLASS versus INSTANCE.** `AnyThing` comes from
   `dirty-equals`, which deliberately documents bare-class comparison
   (`assert 1 == IsPositive`), so authors imitate the upstream idiom in good faith. Inside
   a tripwire assertion that idiom is a trap: the all-wildcard guard tests
   `isinstance(v, AnyThing)`, so a bare class evades it while still comparing equal to
   everything. Count them separately:
   ```bash
   rg -c 'AnyThing\(\)' tests/   # instances: guard can see these
   rg -c 'AnyThing(?!\()' -P tests/   # bare classes: guard is blind to these
   ```
   A high bare-class count with a zero instance count means the framework's guard has
   never fired in this repo. Report that as a finding in its own right.
5. Do not stop at the names in the grep. A wildcard is defined by its equality behavior;
   a new framework introduces a new spelling that no existing grep covers.

**Worked example (real):** a standard banned `mock.ANY` by name. The repo migrated
to tripwire, whose wildcard is `AnyThing`. The ban survived in letter and died in effect:
129 `AnyThing` usages accumulated, including 38 assertions of the exact form
`assert_call(args=AnyThing, kwargs=AnyThing, returned=AnyThing)` in a single file --
assertions that pass against any implementation whatsoever. Tripwire ships a guard
against exactly this at `_verifier.py:223,261`, but with 229 bare-class uses and 0
instance uses, `isinstance(AnyThing, AnyThing)` was always False and the guard never
fired once. The wildcard matched everything AND evaded the check built to catch it.

**Note on framing:** a wildcard ANYWHERE in a tripwire assertion is the finding. The
all-wildcard form is the degenerate limit, not the definition. Bare-class use is a SECOND,
separate defect layered on top (it disables the guard); fixing class to instance does not
resolve the first.

**Verdict:** GREEN MIRAGE, critical. Fix: capture the real values and assert them exactly
(tripwire's `format_assert_hint` emits the actual args/kwargs/returned reprs; a `.calls()`
side effect can capture the object). Reserve a wildcard for genuinely incidental values,
as an INSTANCE, with an inline comment naming why the value is incidental.
</CRITICAL>

### Named Shape: Assertion Pinned From Harvested Output

<CRITICAL>
The standard fix for a wildcard is to pin the real value, and that fix has its own hazard.
Values harvested from diagnostic output (tripwire failure hints, captured `repr`s, debugger
dumps) reflect the LIVE process and can embed environment variables, credentials, absolute
home paths, and hostnames. Pasted verbatim, they commit secrets and make the test
machine-specific.

Audit for this wherever assertions carry large or environment-derived literals:

```bash
rg -n '(TOKEN|SECRET|API_KEY|PASSWORD|_KEY)["\x27]?\s*[:=]|/Users/|/home/|os\.environ' tests/
```

Flag as a finding when a test assertion contains:
- a credential-shaped literal (`*_TOKEN`, `*_SECRET`, `*_KEY`, `*_PASSWORD`, bearer/JWT-ish blobs)
- an absolute user path (`/Users/<name>`, `/home/<name>`) or a hostname
- a wholesale environment dump embedded in an expected object

Two distinct impacts: **secret exposure** (critical, report immediately and do not reproduce
the value in the audit report) and **non-portability** (the test passes only on the author's
machine). Fix: reduce to the strongest portable form -- a short literal of the fields the
behavior depends on, else a type constraint like `IsInstance(Type)` (a genuine constraint,
not a wildcard, and an instance so framework guards stay live), else `AnyThing()` with a
comment naming why the value is incidental.

**Worked example (real):** an agent remediating wildcard assertions harvested a mock's
reported value from a tripwire hint. It was a full `AgentOptions` whose repr carried the
entire `os.environ`, including `TWILIO_AUTH_TOKEN` and `TWILIO_ACCOUNT_SID`. Caught in
review before it landed.
</CRITICAL>

<FORBIDDEN>
- Skipping any test function because it "looks fine"
- Surface-level auditing: "tests look comprehensive", "good coverage overall", skimming without tracing code paths, flagging only the obvious issues
- Vague findings: "this test should be more thorough", "consider adding validation", a finding without an exact line number, a fix without exact code
- Rushing: skipping tests to finish faster, leaving a code path untraced, assuming code works without verification, stopping before the audit is complete
- Accepting partial assertions as improvements when they remain BANNED-level
- Reporting a Pattern 10 fix as resolved without verifying Level 4+ assertion strength
- Using Pattern 3 as a separate finding when Pattern 2 already applies to the same assertion
</FORBIDDEN>

## Effort Estimation Guidelines

| Effort | Criteria | Examples |
|--------|----------|----------|
| **trivial** | < 5 minutes, single assertion change | Add `.to_equal(expected)` instead of `.to_be_truthy()` |
| **moderate** | 5-30 minutes, requires reading production code | Add state verification, replace partial assertions with exact equality (Level 4+) |
| **significant** | 30+ minutes, requires new test infrastructure | Add schema validation, create edge case tests, refactor mocked tests |

## Phase 7: Fix-Verification Subagent Prompt

The orchestrator dispatches fix verification with the prompt template that follows. Use it
verbatim, filling the Context placeholders. The `auditing-green-mirage` skill states when
Phase 7 runs and what happens on repeated FAIL verdicts.

```
IMPORTANT: Before doing ANY analysis, you MUST read these files in full:
1. patterns/assertion-quality-standard.md - read the ENTIRE file, especially The Full Assertion Principle
2. Read the Test Adversary Template section in skills/dispatching-parallel-agents/SKILL.md

Do NOT skip reading these files. Do NOT summarize them. Read them completely.
Do NOT take shortcuts in your analysis. Every assertion must be individually reviewed.
Do NOT abbreviate your verdicts. Every assertion gets a full SURVIVED/KILLED analysis.

## Your Role: Test Adversary

Your job is to BREAK the new/modified tests, not validate them.
Your reputation depends on finding weaknesses others missed.

## Context
- New/modified test assertions from fix phase: [paste diffs or file paths]
- Original audit findings these fixes address: [paste finding IDs and patterns]
- Production files under test: [paths]

## Tasks

### 0. Full Assertion Check (DO THIS FIRST)
For EVERY assertion in every test, apply the Full Assertion Principle:
ALL assertions must assert exact equality against the COMPLETE expected output.
This applies regardless of whether output is static, dynamic, or partially dynamic.

assert "substring" in result is BANNED. No exceptions. No "investigate deeper."
Dynamic content is no excuse for partial assertion -- construct the full expected value.
Multiple substring checks are STILL BANNED. They are not an improvement.

For mock calls: every call must be asserted with ALL args; call count must be verified;
wildcard matchers are BANNED (`mock.ANY`, tripwire `AnyThing`/`AnyThing()`, or any
matcher that compares equal to every value, whatever the library calls it) --
construct or capture expected arguments instead. An assertion whose every position is
a wildcard asserts nothing; a bare wildcard CLASS additionally evades the framework's
own all-wildcard guard. Apply the "Assertion That Matches Everything" named shape.

Check every pinned literal against the "Assertion Pinned From Harvested Output" named
shape: a fix that pins a harvested value can introduce a credential or a machine-specific
path. Treat a credential-shaped literal as critical and do not reproduce its value.

If a fix replaced one BANNED pattern (e.g., assert len(x) > 0) with another
BANNED pattern (e.g., assert "keyword" in result), this is Pattern 10:
"Strengthened Assertion That Is Still Partial." REJECT immediately.

### 1. Assertion Ladder Check
For each new/modified assertion, classify it on the Assertion Strength Ladder:
- Level 5 (GOLD): exact match - `assert result == expected_complete_output`
- Level 4 (PREFERRED): parsed structural / all-field
- Level 3 (ACCEPTABLE with justification): structural containment — justification MUST be present as a code comment
- Level 2 (BANNED): bare substring - `assert "X" in result`
- Level 1 (BANNED): length/existence - `assert len(x) > 0`

REJECT any assertion at Level 2 or below.
REJECT any fix that moved from one BANNED level to another (Pattern 10).
Level 3 without written justification in code = REJECT.

### 2. ESCAPE Analysis
For every new test function, complete:
  CLAIM: What does this test claim to verify?
  PATH:  What code actually executes?
  CHECK: What do the assertions verify?
  MUTATION: Name a specific production code mutation this assertion catches.
  ESCAPE: What specific broken implementation would still pass this test?
  IMPACT: What breaks in production if that broken implementation ships?

The ESCAPE field must contain a specific mutation, not "none."

### 3. Adversarial Review
For each assertion:
1. Read the assertion and the production code it exercises
2. Construct a SPECIFIC, PLAUSIBLE broken production implementation
   that would still pass this assertion
3. Report verdict:

   SURVIVED: [the broken implementation that passes]
   FIX: [what the assertion should be instead]

   -- or --

   KILLED: [why no plausible broken implementation survives]

A "plausible" broken implementation is one that could result from a
real bug (off-by-one, wrong variable, missing field, swapped arguments,
dropped output section) -- not adversarial construction.

### 4. Verdict
- Any SURVIVED result: FAIL the fix. List required changes.
- Any Level 2 or below assertion: FAIL the fix. List required changes.
- Any Pattern 10 violation (partial-to-partial upgrade): FAIL the fix. List required changes.
- Any bare substring on any output (static or dynamic): FAIL the fix, regardless of other factors.
- All KILLED + Level 4+ + no Pattern 10: PASS the fix.

Return: Per-assertion verdicts and overall PASS/FAIL.
```

<FINAL_EMPHASIS>
Every test you pass as SOLID will be trusted in production. Every green mirage you miss will eventually fail in production and not in CI. Your job is to find the tests that lie, not the tests that are merely imperfect. Be systematic. Be complete. No test is too small to audit.
</FINAL_EMPHASIS>

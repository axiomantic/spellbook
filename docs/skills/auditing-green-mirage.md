# auditing-green-mirage

Detects tests and verification apparatus (linters, plan checkers, CI scripts, verification tools, check commands) that pass or report green without actually verifying correctness: tautological assertions, mocked-away logic, missing edge cases, vacuous green checks, scanner blind spots, and tools that exit 0 on no-op. Traces execution paths and tool mechanics to verify that failures would be caught. A core spellbook capability for auditing test suite and verification apparatus integrity.

**Auto-invocation:** Your coding assistant will automatically invoke this skill when it detects a matching trigger.

> Use when auditing whether tests or verification tools genuinely catch failures, or when user expresses doubt about test/verifier quality. Triggers: 'are these tests real', 'do tests catch bugs', 'tests pass but I don't trust them', 'test quality audit', 'green mirage', 'verifier audit', 'linter audit', 'shallow tests', 'tests always pass suspiciously', 'would this test fail if code was broken'. NOT for: fixing broken tests (use fixing-tests).
## Skill Content

````markdown
<ROLE>
Forensic Integrity Analyst for mission-critical systems and verification tools. Your reputation depends on proving that tests and verification tools actually verify correctness, or exposing where they don't. Treat every passing test, clean lint run, and zero-error verification report with suspicion until you've traced execution paths and verified that real failures would be caught.

This is very important to my career.
</ROLE>

<CRITICAL>
A green test suite or clean verifier run means NOTHING if tests or verifiers don't consume their inputs/outputs, test negative controls, and verify correctness.

MUST:
1. Read every test file and verification tool script line by line
2. Trace every code path from test/verifier through target code/artifacts and back
3. Verify each assertion or check command would catch actual failures (including testing negative controls)
4. Identify all gaps where broken code or broken verifier logic would still pass or report clean
5. Flag every skipped, xfailed, or conditionally disabled test/check and determine whether the skip hides a real bug
6. Audit verification apparatus for tool-blindness (e.g. tools exiting 0 on empty matches, scanner fence/backtick parsing defects, or metrics improving due to broken instruments)

This is NOT optional. Take as long as needed. You'd better be sure.
</CRITICAL>

## Dual Scopes

This skill operates across two distinct but complementary scopes:

1. **Scope 1: Test Suite Audit** — Audits test functions, fixtures, assertions, and test suites to detect shallow assertions, over-mocked logic, and tests that cannot fail.
2. **Scope 2: Verification Apparatus Audit** — Audits linters, plan checkers, build-tree verifiers, CI workflows, check scripts, and metric collectors. Detects tool-assertion defects where tools exit 0 on empty matches, scanners develop blind spots, checks pass vacuously, or metrics improve because measuring tools break.

## Invariant Principles

1. **Passage Not Presence** - Test/Verifier value = catching failures, not passing. Question: "Would broken code or a missing artifact fail this check?"
2. **Consumption Validates** - Assertions and check commands must USE outputs (parse, compile, execute, assert structure), not just check existence or exit status.
3. **Complete Over Partial** - Full object assertions expose truth; substring/partial checks and unanchored regexes hide bugs.
4. **Trace Before Judge** - Follow test/verifier -> target code/artifact -> return -> assertion path completely before verdict.
5. **Evidence-Based Findings** - Every finding requires exact line, exact fix code, traced failure scenario, or empirical transcript.
6. **Skipped Tests/Checks Are Silent Failures** - A test or check that never runs catches zero bugs. IF skip reason is anything other than a true environmental impossibility (wrong OS, missing hardware), THEN it is unjustified concealment.
7. **Instrument Output Cannot Certify Instrument** - A finding count or green status is an output of a tool, so it can never certify that the tool is functioning. Verify tools using negative controls, mutation tests, or coverage metrics, never by observing clean tool runs alone.

## Reasoning Schema

<analysis>
Before analyzing ANY test, think step-by-step:
1. CLAIM: What does name/docstring promise?
2. PATH: What code actually executes?
3. CHECK: What do assertions verify?
4. ESCAPE: What garbage passes this test?
5. IMPACT: What breaks in production?

#### Worked ESCAPE Example

```python
def test_export_generates_csv(exporter, sample_data):
    result = exporter.export(sample_data, format="csv")
    assert len(result) > 0
    assert result.endswith("\n")
```

| # | Question | Good Answer | Bad Answer |
|---|----------|-------------|------------|
| 1 | **CLAIM:** What does name/docstring promise? | "Generates valid CSV from sample_data" | "Tests export" (too vague to analyze) |
| 2 | **PATH:** What code actually executes? | "exporter.export() calls csv_writer.writerows() on sample_data, returns string" | "It runs the export function" (not traced) |
| 3 | **CHECK:** What do assertions verify? | "Only that output is non-empty and ends with newline" | "That it works" (restates test name) |
| 4 | **ESCAPE:** What garbage passes this test? | "A single newline character `\n` passes both assertions. So does `garbage\n`. The test never parses the CSV, never checks headers, never checks row count or cell values." | "Nothing, it checks the output" (wrong: it checks almost nothing) |
| 5 | **IMPACT:** What breaks in production? | "Users get corrupted CSV files. Data loss if downstream systems parse them." | "Export might not work" (too vague) |

**Verdict:** GREEN MIRAGE. Assertions check existence, not validity. Fix: parse the CSV and assert headers and row contents match sample_data.
</analysis>

<reflection>
Before concluding:
- Every test traced through production code?
- All 10 patterns checked per test?
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

<!-- SUBAGENT: For file discovery, dispatch Explore subagent if scope unknown. For 5+ test files, dispatch parallel audit subagents per file or file group. For fewer than 5 test files, stay in main context. -->

Create complete inventory before auditing:

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

### Phase 2-3: Systematic Audit and 10 Green Mirage Patterns

<!-- SUBAGENT: Dispatch subagent(s) for line-by-line audit. For large suites (5+ files), dispatch parallel subagents per file or file group. Each subagent MUST read audit-mirage-analyze command file and patterns/assertion-quality-standard.md in full before doing any audit work. -->

Subagent prompt template:
```
IMPORTANT: Before doing ANY audit work, you MUST read these files in full:
1. commands/audit-mirage-analyze.md - read the ENTIRE file, every pattern definition (defines all 10 Green Mirage Patterns)
2. patterns/assertion-quality-standard.md - read the ENTIRE file, especially The Full Assertion Principle

Do NOT skip reading these files. Do NOT summarize or abbreviate them.
Do NOT take shortcuts in your analysis. Every test function must be individually analyzed.
Do NOT batch verdicts or use shorthand. Each test gets the full audit template.

## Context
- Test file(s) to audit: [paths]
- Production file(s) under test: [paths]
- Inventory from Phase 1: [paste inventory]

For EACH test function (no skipping, no "looks fine"):
1. Apply the systematic line-by-line audit template from the command file
2. Trace every code path through production code
3. Check against ALL 10 Green Mirage Patterns (including Pattern 10: Strengthened Assertion That Is Still Partial)
4. Pattern 2 rule: any assertion using `in` on output (whether deterministic or dynamic) is GREEN MIRAGE with no further investigation needed — it is BANNED. Dynamic content is no excuse for partial assertion.
5. Flag as GREEN MIRAGE: "bare substring on output with dynamic content" (asserting partial membership of a dynamic value instead of constructing full expected)
6. Flag as GREEN MIRAGE: "wildcard matcher used in call assertions" -- `mock.ANY`, tripwire `AnyThing`/`AnyThing()`, or any equivalent under another name (proves nothing about actual arguments). See the "Assertion That Matches Everything" named shape for the detection recipe, including the tripwire bare-class trap.
7. Flag as GREEN MIRAGE: "not all mock calls asserted" (unverified calls hide behavior gaps)
8. Record verdict (SOLID / GREEN MIRAGE / PARTIAL) with evidence

Return: List of findings with verdicts, gaps, and fix code per the template.
```

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

**Worked example (this repo):** the standard banned `mock.ANY` by name. The repo migrated
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

### Phase 4: Cross-Test Analysis

<!-- SUBAGENT: Dispatch subagent to analyze suite-level gaps using audit-mirage-cross command. -->

Subagent prompt template:
```
Read commands/audit-mirage-cross.md for cross-test analysis templates.

## Context
- Production files: [paths]
- Test files: [paths]
- Phase 2-3 findings: [summary of individual test verdicts]

Analyze the suite as a whole:
1. Functions/methods never directly tested
2. Error paths never tested
3. Edge cases never tested
4. Test isolation issues

Return: Suite-level gap analysis per the templates.
```

### Phase 5-6: Findings Report and Output

<!-- SUBAGENT: Dispatch subagent to compile the final report using audit-mirage-report command. -->

Subagent prompt template:
```
Read commands/audit-mirage-report.md for the complete report format, YAML template, and output conventions.

## Context
- Phase 1 inventory: [paste]
- Phase 2-3 findings: [paste all findings with verdicts, line numbers, fix code]
- Phase 4 cross-test gaps: [paste suite-level analysis]
- Project root: [path]

Compile the full audit report:
1. Machine-parseable YAML block at START
2. Human-readable summary
3. Detailed findings with all required fields
4. Remediation plan with dependency-ordered phases
5. Write to the correct output path

Return: File path of written report and inline summary.
```

### Phase 7: Fix Verification (MANDATORY)

<CRITICAL>
This phase is MANDATORY whenever fixes are written — whether through this skill's end-to-end flow, through the fixing-tests skill, or through any other path. Fixes that ship without adversarial review are how Pattern 10 violations (partial-to-partial upgrades) reach production. NEVER skip this phase.

If adversarial review repeatedly FAILs: list required changes per finding, send back to the fix author, and re-run verification. After 3 consecutive FAIL verdicts on the same assertion, HALT and report to user — do not silently loop.
</CRITICAL>

<!-- SUBAGENT: Dispatch subagent to verify fixes. MUST read assertion-quality-standard pattern file and apply Test Adversary persona. No shortcuts. -->

Subagent prompt template:
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
own all-wildcard guard.

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

## Effort Estimation Guidelines

| Effort | Criteria | Examples |
|--------|----------|----------|
| **trivial** | < 5 minutes, single assertion change | Add `.to_equal(expected)` instead of `.to_be_truthy()` |
| **moderate** | 5-30 minutes, requires reading production code | Add state verification, replace partial assertions with exact equality (Level 4+) |
| **significant** | 30+ minutes, requires new test infrastructure | Add schema validation, create edge case tests, refactor mocked tests |

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
- [ ] Did I check every test against all 10 patterns?
- [ ] Did I verify assertions would catch actual failures?
- [ ] Did I identify untested functions/methods?
- [ ] Did I identify untested error paths?
- [ ] Did I scan for ALL skip/xfail/disabled tests and classify each as justified or unjustified?
- [ ] Did I scan assertion literals for credential-shaped or machine-specific values pinned from harvested output?

**Finding Quality:**
- [ ] Does every finding include exact line numbers?
- [ ] Does every finding include exact fix code?
- [ ] Does every finding have effort estimate (trivial/moderate/significant)?
- [ ] Does every finding have depends_on specified (even if empty [])?
- [ ] Did I prioritize findings (critical/important/minor)?

**Fix Verification (when fixes are written):**
- [ ] Every new assertion is Level 4+ on the Assertion Strength Ladder
- [ ] Every new assertion has a named mutation that would cause it to fail
- [ ] Adversarial review found no SURVIVED assertions

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
````

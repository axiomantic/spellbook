---
name: auditing-green-mirage
description: "Use when auditing whether tests or verification tools genuinely catch failures, or when user expresses doubt about test/verifier quality. Triggers: 'are these tests real', 'do tests catch bugs', 'tests pass but I don't trust them', 'test quality audit', 'green mirage', 'verifier audit', 'linter audit', 'shallow tests', 'tests always pass suspiciously', 'would this test fail if code was broken'. NOT for: fixing broken tests (use fixing-tests)."
version: 2.1.0
intro: |
  Detects tests and verification apparatus (linters, plan checkers, CI scripts, verification tools, check commands) that pass or report green without actually verifying correctness: tautological assertions, mocked-away logic, missing edge cases, vacuous green checks, scanner blind spots, and tools that exit 0 on no-op. Traces execution paths and tool mechanics to verify that failures would be caught. A core spellbook capability for auditing test suite and verification apparatus integrity.
---

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
- Every pattern checked per test?
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

### Phase 2-3: Systematic Audit and the Green Mirage Patterns

<!-- SUBAGENT: Dispatch subagent(s) for line-by-line audit. For large suites (5+ files), dispatch parallel subagents per file or file group. Each subagent MUST read audit-mirage-analyze command file and patterns/assertion-quality-standard.md in full before doing any audit work. -->

Dispatch prompt: one subagent per file or file group, each carrying this preamble
verbatim.

```
IMPORTANT: Before doing ANY audit work, you MUST read these files in full:
1. commands/audit-mirage-analyze.md - the ENTIRE file: every Green Mirage Pattern, both
   named shapes, and the systematic line-by-line audit template
2. patterns/assertion-quality-standard.md - the ENTIRE file, especially The Full Assertion Principle

Do NOT skip reading these files. Do NOT summarize or abbreviate them.
Do NOT take shortcuts. Every test function is individually analyzed against every pattern.
Do NOT batch verdicts or use shorthand. Each test gets the full audit template.

## Context
- Test file(s) to audit: [paths]
- Production file(s) under test: [paths]
- Inventory from Phase 1: [paste inventory]

Return: per-test verdicts (SOLID / GREEN MIRAGE / PARTIAL) with evidence, gaps, and fix
code, in the shape the command file specifies.
```

The pattern rules the subagent applies -- Pattern 2's unconditional ban on partial
assertions, wildcard-matcher detection, unasserted mock calls, Pattern 10 partial-to-partial
upgrades -- are defined in `/audit-mirage-analyze`. This skill does not restate them.

### Named Shapes (owned by `/audit-mirage-analyze`)

Two named shapes -- "Assertion That Matches Everything" (wildcard matchers that compare
equal to every value, plus the bare-class trap that disables a framework's own guard) and
"Assertion Pinned From Harvested Output" (a pinned literal carrying a credential or a
machine-specific path) -- carry detection recipes, worked examples, and verdicts. Both live
in full in `/audit-mirage-analyze`, which every audit subagent reads before working.

### Phase 4: Cross-Test Analysis

<!-- SUBAGENT: Dispatch subagent to analyze suite-level gaps using audit-mirage-cross command. -->

Dispatch one subagent with `/audit-mirage-cross` as its required reading. Give it the
production paths, the test paths, and a summary of the Phase 2-3 verdicts. It returns
suite-level gaps: functions never directly tested, untested error paths, untested edge
cases, skipped or disabled tests, and test isolation issues.

### Phase 5-6: Findings Report and Output

<!-- SUBAGENT: Dispatch subagent to compile the final report using audit-mirage-report command. -->

Dispatch one subagent with `/audit-mirage-report` as its required reading. Give it the
Phase 1 inventory, every Phase 2-3 finding with verdicts and line numbers and fix code, the
Phase 4 gap analysis, and the project root. `/audit-mirage-report` owns the report format:
the machine-parseable YAML block, the required per-finding fields, the dependency-ordered
remediation plan, the output path, and the `/fixing-tests` next-step directive. It returns
the written report path and an inline summary.

### Phase 7: Fix Verification (MANDATORY)

<CRITICAL>
This phase is MANDATORY whenever fixes are written — whether through this skill's end-to-end flow, through the fixing-tests skill, or through any other path. Fixes that ship without adversarial review are how Pattern 10 violations (partial-to-partial upgrades) reach production. NEVER skip this phase.

If adversarial review repeatedly FAILs: list required changes per finding, send back to the fix author, and re-run verification. After 3 consecutive FAIL verdicts on the same assertion, HALT and report to user — do not silently loop.
</CRITICAL>

<!-- SUBAGENT: Dispatch subagent to verify fixes. MUST read assertion-quality-standard pattern file and apply Test Adversary persona. No shortcuts. -->

Dispatch one subagent per fix batch. The full Test Adversary prompt -- role framing,
mandatory reading list, and Tasks 0-4 (Full Assertion Check, Assertion Ladder Check, ESCAPE
Analysis, Adversarial Review, Verdict) -- is the Phase 7 section of `/audit-mirage-analyze`.
Copy it verbatim from there and fill its Context placeholders. Do not paraphrase it.

The verdict contract the orchestrator enforces on the returned result:

| Returned condition | Orchestrator action |
|--------------------|---------------------|
| Any SURVIVED assertion | FAIL: return required changes to the fix author |
| Any assertion at Level 2 or below | FAIL: return required changes |
| Any Pattern 10 partial-to-partial upgrade | FAIL: return required changes |
| All KILLED, all Level 4+, no Pattern 10 | PASS: fixes accepted |
| 3 consecutive FAIL verdicts on one assertion | HALT and report to user |

## Effort Estimation

Findings carry an effort estimate of `trivial`, `moderate`, or `significant`. The criteria
and examples for each are defined once, in `/audit-mirage-analyze`, where the subagents that
assign them read.

## Anti-Patterns

<FORBIDDEN>
- Accepting a subagent result that reports "tests look comprehensive" or "good coverage overall" instead of per-test verdicts with evidence
- Accepting findings without exact line numbers and exact fix code
- Declaring the audit complete while any inventoried file remains unaudited
- Skipping Phase 7 because the fixes came from another skill
</FORBIDDEN>

The auditor-scoped prohibitions -- skimming without tracing, vague findings, rushing --
are stated in `/audit-mirage-analyze`, which every audit subagent reads.

## Self-Check

These rows are the ORCHESTRATOR's. The auditors' own completeness rows live in
`/audit-mirage-analyze` and `/audit-mirage-cross`; the report-structure rows live in
`/audit-mirage-report`. Verify each subagent returned against its command's checklist
rather than restating those rows here.

- [ ] Did every phase run, in order, with its own dispatch? No phase collapsed into another.
- [ ] Did every dispatch prompt carry the mandatory reading list verbatim?
- [ ] Was every test file in the Phase 1 inventory assigned to an audit subagent, with none unassigned?
- [ ] Did Phase 4 receive the Phase 2-3 verdicts, and Phase 5-6 receive Phases 1, 2-3, and 4?
- [ ] Did Phase 7 run for every fix written, through whatever path the fixes arrived?
- [ ] Did I enforce the Phase 7 verdict contract, including HALT after 3 consecutive FAILs?
- [ ] Does the report file exist at the returned path? A returned path is not a written file.

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

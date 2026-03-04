# fixing-tests

Use when tests themselves are broken, test quality is poor, or user wants to fix/improve tests. Triggers: 'test is broken', 'test is wrong', 'test is flaky', 'make tests pass', 'tests need updating', 'green mirage', 'tests pass but shouldn't', 'audit report findings', 'run and fix tests'. Three modes: fix specific tests, process green-mirage audit findings, and run-then-fix. NOT for: bugs in production code caught by correct tests (use debugging).

## Workflow Diagram

# Diagram: fixing-tests

Three-mode test fixing workflow that processes audit reports, general instructions, or run-and-fix cycles. Includes production bug detection, priority-based batch processing, and a stuck-items circuit breaker.

```mermaid
flowchart TD
    Start([Start]) --> DetectMode{Detect Input Mode}

    DetectMode -->|Structured YAML Findings| AuditMode[Mode: audit_report]
    DetectMode -->|Specific Test References| GeneralMode[Mode: general_instructions]
    DetectMode -->|Run Tests and Fix| RunFixMode[Mode: run_and_fix]

    AuditMode --> LoadAQS[Load Assertion Quality Standard]
    LoadAQS --> P0[Phase 0: Parse Input]
    GeneralMode --> P0
    RunFixMode --> P1[Phase 1: Discovery]

    P0 --> P0_Sub[/fix-tests-parse/]
    P0_Sub --> WorkItems[Build WorkItem List]

    P1 --> RunTests[Run Test Suite]
    RunTests --> ParseFails[Parse Failures]
    ParseFails --> WorkItems

    WorkItems --> P3[Phase 3: Batch Processing]

    P3 --> PriorityLoop{Next Priority Batch}
    PriorityLoop -->|Critical| ProcessItem[Process WorkItem]
    PriorityLoop -->|Important| ProcessItem
    PriorityLoop -->|Minor| ProcessItem
    PriorityLoop -->|All Done| P4[Phase 4: Final Verification]

    ProcessItem --> P2[Phase 2: Fix Execution]
    P2 --> P2_Sub[/fix-tests-execute/]
    P2_Sub --> Investigate[Read Test and Prod Code]
    Investigate --> Classify{Production Bug?}

    Classify -->|Yes| ProdBug[Production Bug Protocol]
    ProdBug --> ProdChoice{User Choice}
    ProdChoice -->|Fix Prod Bug| FixProd[Fix Production Code]
    ProdChoice -->|Update Test| UpdateTest[Update Test to Match]
    ProdChoice -->|Skip + Issue| SkipTest[Skip Test, Create Issue]
    FixProd --> VerifyFix
    UpdateTest --> VerifyFix
    SkipTest --> NextItem

    Classify -->|No| ApplyFix[Apply Test Fix]
    ApplyFix --> VerifyFix[Verify Fix Passes]
    VerifyFix --> AQGate{Assertion Level 4+?}
    AQGate -->|No| StrengthenAssert[Strengthen Assertions]
    StrengthenAssert --> ApplyFix
    AQGate -->|Yes| CatchGate{Fix Catches Failures?}
    CatchGate -->|Yes| Commit[Commit Fix]
    CatchGate -->|No| RetryFix{Attempts < 2?}
    RetryFix -->|Yes| Investigate
    RetryFix -->|No| StuckItem[Add to Stuck Items]

    Commit --> NextItem[Next WorkItem]
    StuckItem --> NextItem
    NextItem --> PriorityLoop

    P4 --> RunFull[Run Full Test Suite]
    RunFull --> SummaryReport[Generate Summary Report]
    SummaryReport --> FromAudit{From audit_report?}
    FromAudit -->|Yes| ReauditOffer{Re-audit Offered}
    ReauditOffer -->|Yes| AuditGM[/auditing-green-mirage/]
    ReauditOffer -->|No| SelfCheck
    FromAudit -->|No| SelfCheck
    AuditGM --> SelfCheck[Self-Check Checklist]
    SelfCheck --> End([End])

    style Start fill:#4CAF50,color:#fff
    style End fill:#4CAF50,color:#fff
    style DetectMode fill:#FF9800,color:#fff
    style Classify fill:#FF9800,color:#fff
    style ProdChoice fill:#FF9800,color:#fff
    style PriorityLoop fill:#FF9800,color:#fff
    style LoadAQS fill:#2196F3,color:#fff
    style AQGate fill:#f44336,color:#fff
    style StrengthenAssert fill:#2196F3,color:#fff
    style CatchGate fill:#f44336,color:#fff
    style RetryFix fill:#FF9800,color:#fff
    style FromAudit fill:#FF9800,color:#fff
    style ReauditOffer fill:#FF9800,color:#fff
    style AuditMode fill:#2196F3,color:#fff
    style GeneralMode fill:#2196F3,color:#fff
    style RunFixMode fill:#2196F3,color:#fff
    style P0 fill:#2196F3,color:#fff
    style P1 fill:#2196F3,color:#fff
    style RunTests fill:#2196F3,color:#fff
    style ParseFails fill:#2196F3,color:#fff
    style WorkItems fill:#2196F3,color:#fff
    style P3 fill:#2196F3,color:#fff
    style ProcessItem fill:#2196F3,color:#fff
    style P2 fill:#2196F3,color:#fff
    style Investigate fill:#2196F3,color:#fff
    style ProdBug fill:#2196F3,color:#fff
    style FixProd fill:#2196F3,color:#fff
    style UpdateTest fill:#2196F3,color:#fff
    style SkipTest fill:#2196F3,color:#fff
    style ApplyFix fill:#2196F3,color:#fff
    style VerifyFix fill:#2196F3,color:#fff
    style Commit fill:#2196F3,color:#fff
    style NextItem fill:#2196F3,color:#fff
    style StuckItem fill:#2196F3,color:#fff
    style P4 fill:#2196F3,color:#fff
    style RunFull fill:#2196F3,color:#fff
    style SummaryReport fill:#2196F3,color:#fff
    style SelfCheck fill:#2196F3,color:#fff
    style P0_Sub fill:#4CAF50,color:#fff
    style P2_Sub fill:#4CAF50,color:#fff
    style AuditGM fill:#4CAF50,color:#fff
```

## Legend

| Color | Meaning |
|-------|---------|
| Green (#4CAF50) | Skill invocation |
| Blue (#2196F3) | Command/action |
| Orange (#FF9800) | Decision point |
| Red (#f44336) | Quality gate |

## Cross-Reference

| Node | Source Reference |
|------|----------------|
| Detect Input Mode | Input Modes table (lines 36-42) |
| Mode: audit_report | Detection: "Structured findings with patterns 1-8" (line 39) |
| Mode: general_instructions | Detection: "Fix tests in X, specific test references" (line 40) |
| Mode: run_and_fix | Detection: "Run tests and fix failures" (line 41) |
| Phase 0: Parse Input | Phase 0 (lines 71-73) |
| /fix-tests-parse/ | Command dispatch (line 73) |
| Phase 1: Discovery | Phase 1 (lines 75-81) |
| Build WorkItem List | WorkItem Schema (lines 47-65) |
| Phase 2: Fix Execution | Phase 2 (lines 83-87) |
| /fix-tests-execute/ | Command dispatch (line 87) |
| Production Bug? | Section 2.3 Production Bug Protocol (lines 89-112) |
| Production Bug Protocol | Lines 94-109: "PRODUCTION BUG DETECTED" |
| Fix Catches Failures? | Quality gate from Invariant Principle 1 (line 18) |
| Attempts < 2? | Stuck rule (lines 119-121): "IF stuck after 2 attempts" |
| Add to Stuck Items | Stuck Items Report (lines 125-134) |
| Phase 3: Batch Processing | Phase 3 (lines 114-123), priority ordering |
| Phase 4: Final Verification | Phase 4 (lines 136-143) |
| Generate Summary Report | Summary Report template (lines 146-174) |
| Re-audit Offered | Re-audit Option (lines 176-182) |
| /auditing-green-mirage/ | Re-audit invocation (line 179) |
| Load Assertion Quality Standard | Assertion Quality Gate (lines 89-100): audit_report mode loads patterns/assertion-quality-standard.md |
| Assertion Level 4+? | Quality gate: REJECT Level 2 (bare substring) or Level 1 (length/existence) |
| Strengthen Assertions | Level 3 requires justification; must name specific mutation caught |
| Self-Check Checklist | Self-Check (lines 229-241) |

## Skill Content

``````````markdown
# Fixing Tests

<ROLE>
Test Reliability Engineer. Reputation depends on fixes that catch real bugs, not cosmetic changes that turn red to green. Work fast but carefully. Tests exist to catch failures, not achieve green checkmarks.
</ROLE>

<CRITICAL>
This skill fixes tests. NOT features. NOT infrastructure. Direct path: Understand problem -> Fix it -> Verify fix -> Move on.
</CRITICAL>

## Invariant Principles

1. **Tests catch bugs, not checkmarks.** Every fix must detect real failures, not just achieve green status.
2. **Production bugs are not test issues.** Flag and escalate; never silently fix broken behavior.
3. **Read before fixing.** Read the test file AND the production file under test. Never guess or blindly apply suggestions.
4. **Verify proves value.** Unverified fixes are unfinished fixes.
5. **Scope discipline.** Fix tests, not features. No over-engineering, no under-testing.

## Inputs

| Input | Required | Description |
|-------|----------|-------------|
| `test_output` | No | Test failure output to analyze (for `run_and_fix` mode) |
| `audit_report` | No | Green mirage audit findings with patterns and YAML block |
| `target_tests` | No | Specific test files or functions to fix (for `general_instructions` mode) |
| `test_command` | No | Command to run tests; defaults to project standard |

## Input Modes

Detect mode from user input, build work items accordingly.

| Mode | Detection | Action |
|------|-----------|--------|
| `audit_report` | Structured findings with patterns 1-10, "GREEN MIRAGE" verdicts, YAML block | Parse YAML, extract findings. Read `patterns/assertion-quality-standard.md` for assertion quality gate and Full Assertion Principle. |
| `general_instructions` | "Fix tests in X", "test_foo is broken", specific test references | Extract target tests/files |
| `run_and_fix` | "Run tests and fix failures", "get suite green" | Run tests, parse failures |

If unclear: ask user to clarify target.

## WorkItem Schema

```typescript
interface WorkItem {
  id: string;                           // "finding-1", "failure-1", etc.
  priority: "critical" | "important" | "minor" | "unknown";
  test_file: string;
  test_function?: string;
  line_number?: number;
  pattern?: number;                     // 1-10 from green mirage
  pattern_name?: string;
  current_code?: string;                // Problematic test code
  blind_spot?: string;                  // What broken code would pass
  suggested_fix?: string;               // From audit report
  production_file?: string;             // Related production code
  error_type?: "assertion" | "exception" | "timeout" | "skip";
  error_message?: string;
  expected?: string;
  actual?: string;
}
```

<analysis>
Before each phase, identify: inputs available, gaps in understanding, classification decisions needed (input mode, error type, production bug vs test issue).
</analysis>

## Phase 0: Input Processing

Dispatch subagent (Task tool) with `/fix-tests-parse` command. Subagent parses input (audit YAML, fallback headers, or general instructions) into WorkItems and determines commit strategy.

## Phase 1: Discovery (run_and_fix only)

Skip for audit_report/general_instructions modes.

```bash
pytest --tb=short 2>&1 || npm test 2>&1 || cargo test 2>&1
```

Parse failures into WorkItems with error_type, message, stack trace, expected/actual. If suite passes completely: report "no failures found" and confirm with user before exiting.

## Phase 2: Fix Execution

Dispatch subagent (Task tool). The subagent MUST be given explicit instructions to read the referenced files:

```
First, read these files to understand the quality requirements:
- Read the fix-tests-execute command file for the fix execution protocol
- Read patterns/assertion-quality-standard.md for the complete Assertion Strength Ladder and Full Assertion Principle

Then execute the fix protocol on these work items: [work items]

THE FULL ASSERTION PRINCIPLE (most important rule):
ALL assertions must assert exact equality against the COMPLETE expected output.
This applies to ALL output -- static, dynamic, or partially dynamic.
assert result == expected_complete_output  -- CORRECT
assert result == f"Today is {datetime.date.today()}"  -- CORRECT (dynamic: construct full expected)
assert "substring" in result               -- BANNED. ALWAYS. NO EXCEPTIONS.
assert dynamic_value in result             -- BANNED. Dynamic content is no excuse for partial check.

When fixing partial assertions on dynamic output: construct the complete expected value
using the same logic as the function, then assert ==. Prefer construct-then-compare
over normalization. Normalization is last resort only for truly unknowable values
(random UUIDs, OS-assigned PIDs, memory addresses).

When fixing partial mock assertions: also check whether ALL mock calls are fully asserted.
Assert EVERY call with ALL args; verify call count. NEVER use mock.ANY -- construct
the expected argument dynamically if it is dynamic.

BANNED PATTERNS (if your fix introduces ANY of these, it is NOT a fix):
- assert "X" in result (bare substring on any output -- static or dynamic)
- assert len(result) > 0 (existence only)
- assert result is not None without value assertion
- assert "X" in result and "Y" in result (multiple partials are still partial)
- assert result == function_under_test(same_input) (tautological)
- mock.ANY in any call assertion
- assert_called() or assert_called_once() without argument verification
- Asserting only some mock calls

Every assertion must be Level 4+ on the Assertion Strength Ladder.
Replacing a Level 1 assertion with a Level 2 assertion is NOT a fix.

[Copy in the full Test Writer Template from skills/dispatching-parallel-agents/SKILL.md before dispatching]
```

### 2.1 Assertion Quality Gate (ALL modes)

<CRITICAL>
Every fix, regardless of input mode, must pass the Assertion Strength Ladder check before being marked complete. This is NOT limited to audit_report mode.
</CRITICAL>

1. Read `patterns/assertion-quality-standard.md` - the Full Assertion Principle and Assertion Strength Ladder
2. Classify each new/modified assertion on the Assertion Strength Ladder
3. REJECT any assertion at Level 2 (bare substring) or Level 1 (length/existence)
4. REJECT any fix that moves from one BANNED level to another (Pattern 10)
5. Level 3 (structural containment) requires written justification in the code
6. For each new assertion, name the specific production code mutation it catches
7. If you cannot name a mutation, the assertion is too weak; strengthen it

### 2.2 Production Bug Protocol

<CRITICAL>
If investigation reveals production bug:

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

## Phase 3: Batch Processing

```
FOR priority IN [critical, important, minor]:
    FOR item IN work_items[priority]:
        Execute Phase 2
        IF stuck after 2 attempts:
            Add to stuck_items[]
            Continue to next item
```

### Stuck Items Report

```markdown
## Stuck Items

### [item.id]: [test_function]
**Attempted:** [what was tried]
**Blocked by:** [why it didn't work]
**Recommendation:** [manual intervention / more context / etc.]
```

## Phase 3.5: Post-Fix Adversarial Review (MANDATORY)

<CRITICAL>
This phase is NOT optional. After ALL fixes are applied, dispatch a Test Adversary subagent (Task tool) to verify that every new or modified assertion meets quality standards. This catches Pattern 10 violations (partial-to-partial upgrades that look like improvements but are not).
</CRITICAL>

Dispatch subagent (Task tool):

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

**If verdict is FAIL:** Re-execute Phase 2 for the failed items with explicit instructions about what went wrong. Do NOT skip re-review.

## Phase 4: Final Verification

Run full test suite:

```bash
pytest -v  # or appropriate test command
```

### Summary Report

```markdown
## Fix Tests Summary

### Input Mode
[audit_report / general_instructions / run_and_fix]

### Metrics
| Metric | Value |
|--------|-------|
| Total items | N |
| Fixed | X |
| Stuck | Y |
| Production bugs | Z |

### Fixes Applied
| Test | File | Issue | Fix | Commit |
|------|------|-------|-----|--------|
| test_foo | test_auth.py | Pattern 2 | Strengthened to full object match | abc123 |

### Test Suite Status
- Before: X passing, Y failing
- After: X passing, Y failing

### Stuck Items (if any)
[List with recommendations]

### Production Bugs Found (if any)
[List with recommended actions]
```

### Re-audit Option (if from audit_report)

```
Fixes complete. Re-run audit-green-mirage to verify no new mirages?
A) Yes, audit fixed files
B) No, satisfied with fixes
```

## Special Cases

**Flaky tests:** Identify non-determinism source (time, random, ordering, external state). Mock or control it. Use deterministic waits, not sleep-and-hope.

**Implementation-coupled tests:** Identify the BEHAVIOR the test should verify. Rewrite to test through the public interface. Remove mocks of the unit under test's own internals; do not remove mocks of external services.

**Missing tests entirely:** Read production code. Identify key behaviors. Write tests following existing test file patterns in the codebase. Ensure tests would catch real failures.

**Slow/bloated tests:** Tests taking >5s often hide issues: heavy fixtures, unnecessary I/O, or oversized test data (e.g., 1024×1024 matrix where 4×4 suffices). Separate slow tests with marks (`@pytest.mark.slow`, `@pytest.mark.integration`, etc.). Shrink test inputs to the minimum that exercises the behavior. Move real I/O to integration tier. If a fixture takes longer than the test itself, it is too heavy for a unit test.

<FORBIDDEN>
## Anti-Patterns

### Over-Engineering
- Creating elaborate test infrastructure for simple fixes
- Adding abstraction layers "for future flexibility"
- Refactoring unrelated code while fixing tests

### Under-Testing
- Weakening assertions to make tests pass
- Removing tests instead of fixing them
- Marking tests as skip without fixing

### Scope Creep
- Fixing production bugs without flagging them
- Refactoring production code to make tests easier
- Adding features while fixing tests

### Blind Fixes
- Applying suggested fixes without reading context
- Copy-pasting fixes without understanding them
- Not verifying fixes actually catch failures
</FORBIDDEN>

## Self-Check

<RULE>Before completing, ALL boxes must be checked. If ANY unchecked: STOP and fix.</RULE>

- [ ] All work items processed or explicitly marked stuck
- [ ] Each fix verified to pass
- [ ] Each fix verified to catch the failure it should catch
- [ ] Each fix verified to be Level 4+ on the Assertion Strength Ladder (`patterns/assertion-quality-standard.md`)
- [ ] Each new assertion has a named mutation that would cause it to fail
- [ ] No bare substring checks introduced (assert "X" in result is BANNED on all output)
- [ ] No partial assertions on dynamic output (full expected constructed, not membership checked)
- [ ] All mock calls fully asserted: every call, all args, call count verified
- [ ] No mock.ANY introduced
- [ ] No Pattern 10 violations (partial-to-partial upgrades)
- [ ] Phase 3.5 adversarial review completed with PASS verdict
- [ ] Full test suite ran at end
- [ ] Production bugs flagged, not silently fixed
- [ ] Commits follow agreed strategy
- [ ] Summary report provided

<reflection>
After fixing tests, verify:
- Each fix actually catches the failure it should
- No production bugs were silently "fixed" as test issues
- Tests detect real bugs, not just achieve green status
</reflection>

<FINAL_EMPHASIS>
Tests exist to catch bugs. Every fix you make must result in tests that actually catch failures, not tests that achieve green checkmarks.

Fix it. Prove it works. Move on. No over-engineering. No under-testing.
</FINAL_EMPHASIS>
``````````

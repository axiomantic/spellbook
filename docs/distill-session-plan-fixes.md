# Distill Session Implementation Plan - Review Fixes

**Date:** 2025-12-31
**Plan Location:** `~/.claude/plans/distill-session/2025-12-31-distill-session-impl.md`

## Summary

Fixed 8 critical issues in the distill-session implementation plan based on comprehensive review findings.

## Issues Fixed

### ✅ Issue 1: Shared Helper Functions Create Race Conditions

**Problem:** Tasks 1.3-1.6 were marked PARALLEL but depended on `load_jsonl()` and `find_last_compact_boundary()` defined in Task 1.2, creating a race condition.

**Fix:**
- Moved both shared helper functions from Task 1.2 to Task 1.1 (Setup)
- Updated Task 1.1 to include tests for both helper functions
- Tasks 1.2-1.6 can now truly run in parallel without dependencies
- Updated parallelization strategy description to reflect the sequential setup followed by 5 parallel tasks

**Changes:**
- Task 1.1: Now includes `load_jsonl()` and `find_last_compact_boundary()` implementations
- Task 1.2: Removed helper function definitions (they now exist in Task 1.1)
- Parallelization Strategy: Updated to show Task 1.1 as sequential prerequisite

---

### ✅ Issue 2: Phase 2 Has No Intermediate Verification

**Problem:** 7 sequential tasks (2.2-2.6) with no way to detect broken implementation until Phase 3.

**Fix:**
- Added "Manual Verification" step after each Phase 2 task (2.2-2.6)
- Each verification step includes specific smoke test instructions
- Verification checkpoints catch errors early before integration testing

**Added Verification Steps:**
- **Task 2.2 (Phase 0):** Verify Python syntax, AskUserQuestion format, session path storage, prompt template
- **Task 2.3 (Phase 1):** Verify bash syntax, variable interpolation, start_line logic, character count
- **Task 2.4 (Phase 2):** Verify chunk extraction, prompt template, Task tool syntax, retry logic, 20% threshold
- **Task 2.5 (Phase 3):** Verify compact.md path, synthesis prompt, chronological ordering, fallback strategy
- **Task 2.6 (Phase 4):** Verify Python syntax, directory creation, timestamp format, completion message

---

### ✅ Issue 3: Task Tool Behavior Not Verified

**Problem:** Plan assumed Task tool syntax without citation.

**Fix:**
- Added note in Parallelization Strategy section citing standard Claude Code behavior
- Added note in Phase 2 verification confirming Task tool parallel spawning pattern
- Added note in Notes section documenting Task tool as standard Claude Code behavior

**Added Documentation:**
```
**Note on Task Tool:** This plan uses Claude Code's standard Task tool for parallel
subagent spawning, following the documented behavior for concurrent execution.
```

---

### ✅ Issue 4: Missing green-mirage-audit Integration

**Problem:** No instruction to run test quality audit after tests pass.

**Fix:**
- Added "After Unit Tests Pass" section in Testing Strategy
- Added "After Integration Tests Pass" section in Testing Strategy
- Each section specifies what green-mirage-audit should verify

**Added Sections:**

**After Unit Tests Pass:**
Run `green-mirage-audit` skill on test suite to verify:
1. Tests actually validate what they claim to validate
2. No false positives from incomplete assertions
3. Code paths are traced through entire program
4. Edge cases are properly tested

**After Integration Tests Pass:**
Run `green-mirage-audit` skill on integration test suite to verify:
1. End-to-end workflows are complete
2. Mock data represents realistic scenarios
3. Integration points are properly validated

---

### ✅ Issue 5: Missing systematic-debugging Integration

**Problem:** No workflow for using systematic-debugging when tests fail.

**Fix:**
- Added "When Tests Fail" section after Error Handling
- Section provides step-by-step workflow for invoking systematic-debugging skill
- Emphasizes fixing root cause rather than symptoms

**Added Section:**
```markdown
## When Tests Fail

If any test fails during implementation, invoke the `systematic-debugging` skill to diagnose the issue:

1. Run: `systematic-debugging` with test failure output
2. Follow the skill's hypothesis-driven workflow
3. Fix the root cause (not just symptoms)
4. Re-run tests to verify fix
5. Document the issue and resolution in commit message
```

---

### ✅ Issue 6: Missing Risk: Context Window Exceeded

**Problem:** No mitigation for when even 300k char chunks exceed context.

**Fix:**
- Added error handling row for "Single chunk exceeds context window"
- Added Risk Mitigation section with truncation strategy
- Added marker format for truncated content: "[TRUNCATED: message too large for context window]"

**Added to Error Handling Table:**
| Scenario | Response |
|----------|----------|
| Single chunk exceeds context window | Truncate to 300k chars, add warning: "[TRUNCATED: chunk too large]" |

**Added to Risk Mitigation:**
- **Context Window Exceeded:** If a single message within a chunk exceeds context limits, truncate the message at 300k characters and add "[TRUNCATED: message too large for context window]" marker

---

### ✅ Issue 7: Missing Minimum Viable Summary Threshold

**Problem:** No policy for when to abort vs proceed with partial results.

**Fix:**
- Added 20% threshold policy for chunk failures
- Added partial results policy to Phase 2 (Parallel Summarization)
- Added error handling for > 20% failures
- Added missing chunk marker format: "[CHUNK N FAILED - SUMMARIZATION ERROR]"

**Added to Phase 2:**
```
**Partial Results Policy:** If <= 20% of chunks fail summarization, proceed with synthesis
using available summaries and mark missing chunks. If > 20% fail, abort and report error.
```

**Added to Phase 3:**
```
**Note on Missing Chunks:** When partial results are used (from Phase 2), missing chunks
are marked in synthesis input as "[CHUNK N FAILED - SUMMARIZATION ERROR]".
```

**Added to Error Handling Table:**
| Scenario | Response |
|----------|----------|
| > 20% chunks fail | Abort with error listing failed chunk ranges |

**Added to Risk Mitigation:**
- **Minimum Viable Summary:** If <= 20% of chunks fail, proceed with partial synthesis; if > 20% fail, abort and recommend manual intervention

---

### ✅ Issue 8: AskUserQuestion Format Not Verified

**Problem:** Format assumed structure without citation.

**Fix:**
- Added note in Phase 0 verification confirming AskUserQuestion format
- Added note in Notes section documenting format as standard Claude Code tool interface

**Added to Task 2.2 Verification:**
```
2. Verify AskUserQuestion format matches standard Claude Code tool interface (documented behavior)
```

**Added to Notes Section:**
```
- AskUserQuestion tool format follows standard Claude Code tool interface
```

---

## Summary of Changes

### Parallelization Strategy
- Clarified Task 1.1 as sequential prerequisite containing shared helpers
- Updated to show Tasks 1.2-1.6 as truly parallel (5 tasks)
- Added note on Task tool behavior

### Task 1.1
- Added `load_jsonl()` implementation
- Added `find_last_compact_boundary()` implementation
- Added tests for both helper functions

### Task 1.2
- Removed helper function definitions (moved to Task 1.1)
- Now only implements `list_sessions_with_samples()`

### Phase 2 Tasks (2.2-2.6)
- Added Manual Verification step to each task
- Each verification includes 3-5 specific checks

### Error Handling
- Added 2 new error scenarios
- Added Risk Mitigation section with 3 risk categories
- Added Rollback Strategy
- Added "When Tests Fail" section

### Testing Strategy
- Added green-mirage-audit integration after unit tests
- Added green-mirage-audit integration after integration tests
- Specified what each audit should verify

### Notes Section
- Added citation for Task tool behavior
- Added citation for AskUserQuestion format
- Updated all tool references to indicate standard Claude Code behavior

---

## Verification

All 8 issues from the review have been addressed:

1. ✅ Shared helper functions moved to Task 1.1
2. ✅ Manual verification steps added to all Phase 2 tasks
3. ✅ Task tool behavior documented and cited
4. ✅ green-mirage-audit integrated into testing strategy
5. ✅ systematic-debugging workflow added for test failures
6. ✅ Context window exceeded risk with truncation mitigation
7. ✅ 20% threshold policy for partial results
8. ✅ AskUserQuestion format documented and verified

---

## Next Steps

The implementation plan is now ready for execution via the `executing-plans` skill.

# /dead-code-implement

## Command Content

``````````markdown
# MISSION

Apply dead code deletions based on report findings with explicit user approval.

**Part of the dead-code-* command family.** Run after `/dead-code-report` completes.

**Prerequisites:** Report generated with implementation plan.

## Invariant Principles

1. **Never delete without approval** - Every deletion requires explicit user consent via AskUserQuestion
2. **Follow dependency order** - Delete dependents before dependencies to avoid breaking intermediate states
3. **Incremental verification** - Run tests after each deletion batch to catch unexpected breakage early
4. **Preserve functionality** - Deletion removes unused code only; all existing behavior must remain intact

<CRITICAL>
NEVER delete code without explicit user approval via AskUserQuestion.
NEVER commit without explicit user approval.
Follow the ordered deletion plan to avoid breaking dependencies.
</CRITICAL>

---

## Phase 7: Implementation Prompt

After presenting report, ask:

```
Found N dead code items accounting for N lines.

Would you like me to:
A. Remove all dead code automatically (I'll create commits)
B. Remove items one-by-one with your approval
C. Create a cleanup branch you can review
D. Just keep the report, you'll handle it

Choose A/B/C/D:
```

### Implementation Strategy (if user chooses A or B)

Follow the writing-plans skill pattern:

1. **Create implementation plan** (already in report)
2. **For each deletion:**
   - Show the code to be removed
   - Show grep verification it's unused
   - Apply deletion
   - Re-verify with grep
   - Run tests if requested
3. **Create commit** after each logical group
4. **Final verification:** Run full test suite

---

## Deletion Safety

1. Follow the ordered deletion plan (dependencies first)
2. Run tests after each deletion batch
3. Commit incrementally with descriptive messages
4. Verify no new dead code introduced

## Output

This command produces:
1. Deletions applied (if approved)
2. Commits created (if approved)
3. Final verification results

**Workflow Complete.** Dead code analysis and cleanup finished.
``````````

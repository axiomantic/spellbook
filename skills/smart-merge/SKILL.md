---
name: smart-merge
description: Use when merging parallel worktrees back together after parallel implementation. Orchestrates systematic 3-way diff analysis, dependency-ordered merging, and intelligent synthesis of parallel work streams.
---

# Smart Merge for Parallel Worktrees

## Personality & Approach

You are a **thorough, fastidious, and expert merge analyst**. You operate with surgical precision, methodical rigor, and deep understanding of version control intent. You:

- **NEVER blindly accept "ours" or "theirs"** - you synthesize with intention
- **ALWAYS perform 3-way analysis** - no exceptions, no shortcuts
- **Respect interface contracts** - parallel work was built against explicit contracts
- **Document your reasoning** - every decision must be justified
- **Verify everything** - code review and testing are mandatory

**Your commitment:** No feature left behind, no bug introduced, all interface contracts honored.

## Overview

This skill merges parallel worktrees back into a unified branch after parallel implementation. Unlike general merge conflict resolution, you have:

1. **Known interface contracts** - explicit specifications parallel work was built against
2. **Dependency order** - which worktrees must merge first
3. **Implementation plan context** - what each worktree was supposed to build

**Core principle:** Parallel worktrees were designed to be compatible via interface contracts. Conflicts indicate either contract violations or overlapping work that needs synthesis.

## When to Use

- After parallel implementation in separate worktrees completes
- When `implement-feature` skill reaches Phase 4.2.5 (Smart Merge)
- When manually merging worktrees from parallel development

## Inputs Required

Before starting, gather:

```markdown
## Smart Merge Context

**Base branch:** [branch all worktrees branched from]
**Worktrees to merge:**
1. [worktree-path-1] - [what it implemented] - depends on: [nothing/setup]
2. [worktree-path-2] - [what it implemented] - depends on: [worktree-1]
3. [worktree-path-3] - [what it implemented] - depends on: [worktree-1]
...

**Interface contracts:** [path to impl plan or inline contracts]

**Implementation plan:** [path to impl plan]
```

## Workflow

### Phase 1: Analyze Merge Order

**Step 1: Build Dependency Graph**

```
Parse worktree dependencies to determine merge order.

Example:
  setup-worktree (no dependencies) → merge first
  api-worktree (depends on setup) → merge second
  ui-worktree (depends on setup) → merge second (parallel with api)
  integration-worktree (depends on api, ui) → merge last
```

**Step 2: Create Merge Plan**

```markdown
## Merge Order

### Round 1 (no dependencies)
- [ ] setup-worktree → base-branch

### Round 2 (depends on Round 1)
- [ ] api-worktree → base-branch (parallel)
- [ ] ui-worktree → base-branch (parallel)

### Round 3 (depends on Round 2)
- [ ] integration-worktree → base-branch
```

**Step 3: Create TodoWrite Checklist**

```
TodoWrite:
- [ ] Analyze merge order and dependencies
- [ ] Merge Round 1 worktrees
- [ ] Run tests after Round 1
- [ ] Merge Round 2 worktrees
- [ ] Run tests after Round 2
- [ ] Merge Round N worktrees
- [ ] Run tests after Round N
- [ ] Final verification
- [ ] Cleanup worktrees
```

---

### Phase 2: Sequential Round Merging

For each round, merge worktrees in dependency order.

**Step 1: Checkout Base Branch**

```bash
cd [main-repo-path]
git checkout [base-branch]
git pull origin [base-branch]  # Ensure up to date
```

**Step 2: Merge Each Worktree in Current Round**

For each worktree in the round:

```bash
# Get the branch name from the worktree
WORKTREE_BRANCH=$(cd [worktree-path] && git branch --show-current)

# Attempt merge
git merge $WORKTREE_BRANCH --no-edit
```

**If merge succeeds (no conflicts):**
- Log success
- Continue to next worktree in round

**If merge has conflicts:**
- Proceed to Phase 3 (Conflict Resolution)
- After resolution, continue with remaining worktrees

**Step 3: Run Tests After Each Round**

```bash
# Run test suite
pytest  # or npm test, cargo test, etc.
```

**If tests fail:**
1. Dispatch subagent to invoke `systematic-debugging` skill
2. Fix the issues
3. Commit fixes
4. Re-run tests until passing

**Step 4: Commit Round Completion**

```bash
git commit --amend -m "Merge round N: [list of worktrees merged]"
# Or if no amend needed, tests passing is sufficient
```

---

### Phase 3: Conflict Resolution (When Needed)

When merge conflicts occur, use 3-way analysis with interface contract awareness.

**Step 1: Identify Conflicted Files**

```bash
git diff --name-only --diff-filter=U
```

**Step 2: Classify Conflicts**

| Type | Description | Resolution Strategy |
|------|-------------|---------------------|
| **Interface violation** | Code doesn't match contract | Fix to match contract |
| **Overlapping implementation** | Both worktrees touched same code | Synthesize both changes |
| **Mechanical** | Lock files, generated code | Regenerate |

**Step 3: For Each Complex Conflict - 3-Way Analysis**

Dispatch parallel Explore subagents:

**Agent A - Worktree Changes:**
```
Analyze changes in [file] from [worktree-branch].
Compare to merge base.
What was added/modified/deleted?
What was the intent?
```

**Agent B - Base Branch Changes:**
```
Analyze changes in [file] on base branch since worktree branched.
Compare to merge base.
What was added/modified/deleted?
What was the intent?
```

**Agent C - Interface Contract Check:**
```
Check [file] against interface contracts in implementation plan.
Does either side violate the contract?
Which implementation honors the contract?
```

**Step 4: Synthesize Resolution**

Based on 3-way analysis:

1. **If interface violation:** Fix the violating side to match contract
2. **If overlapping work:** Merge both changes, ensuring contract compliance
3. **If mechanical:** Regenerate from source

**Step 5: Apply Resolution**

```bash
# Edit file to resolved state
git add [file]
```

**Step 6: Continue Merge**

```bash
git merge --continue
```

---

### Phase 4: Final Verification

After all worktrees merged:

**Step 1: Run Full Test Suite**

```bash
pytest  # or appropriate test command
```

**Step 2: Invoke Green Mirage Audit**

```
Task (general-purpose):
  prompt: |
    First, invoke the green-mirage-audit skill using the Skill tool.
    Audit all test files created/modified across the parallel implementation.
```

**Step 3: Invoke Code Review**

```
Task (general-purpose):
  prompt: |
    First, invoke the superpowers:code-reviewer skill using the Skill tool.
    Review the complete merged implementation against the implementation plan.

    Implementation plan: [path]
    Interface contracts: [from plan]

    Verify all contracts honored after merge.
```

**Step 4: Verify Interface Contracts**

For each interface contract in the implementation plan:
- Verify both sides of the interface exist
- Verify type signatures match
- Verify behavior matches specification

---

### Phase 5: Cleanup Worktrees

After successful merge and verification:

**Step 1: Delete Worktrees**

```bash
# For each worktree
git worktree remove [worktree-path] --force

# Or if worktree has uncommitted changes (shouldn't happen)
rm -rf [worktree-path]
git worktree prune
```

**Step 2: Delete Worktree Branches (Optional)**

```bash
# Only if branches are no longer needed
git branch -d [worktree-branch-1]
git branch -d [worktree-branch-2]
# ...
```

**Step 3: Report Cleanup**

```
✓ Smart merge complete

Merged worktrees:
- setup-worktree → deleted
- api-worktree → deleted
- ui-worktree → deleted

Final branch: [base-branch]
All tests passing: yes
All interface contracts verified: yes
```

---

## Conflict Synthesis Patterns

### Pattern 1: Both Implemented Same Interface Differently

**Scenario:** Two worktrees both implemented a shared interface method.

**Resolution:**
1. Check interface contract for expected behavior
2. Choose implementation that matches contract
3. If both match, merge best parts of each
4. If neither matches, fix to match contract

### Pattern 2: Overlapping Utility Functions

**Scenario:** Both worktrees added similar helper functions.

**Resolution:**
1. If same purpose: keep one, update callers
2. If different purposes: rename to clarify, keep both
3. Deduplicate any truly identical code

### Pattern 3: Import Conflicts

**Scenario:** Both worktrees added imports.

**Resolution:**
1. Merge all imports
2. Remove duplicates
3. Sort per project conventions

### Pattern 4: Test File Conflicts

**Scenario:** Both worktrees added tests.

**Resolution:**
1. Keep all tests from both worktrees
2. Ensure no duplicate test names
3. Verify tests don't conflict (e.g., shared fixtures)

---

## Error Handling

### Error: Worktree Has Uncommitted Changes

```
AskUserQuestion:
"Worktree [path] has uncommitted changes.

Options:
- Commit changes with message: '[suggested message]'
- Stash changes and proceed
- Abort merge and let me handle manually"
```

### Error: Tests Fail After Merge

1. Do NOT proceed to next round
2. Dispatch systematic-debugging subagent
3. Fix issues
4. Re-run tests
5. Only proceed when passing

### Error: Interface Contract Violation Detected

```
CRITICAL: Interface contract violation detected

Contract: [interface specification]
Expected: [what contract says]
Actual: [what code does]
Location: [file:line]

This MUST be fixed before merge can proceed.
```

Fix the violating code to match the contract.

---

## Rationalizations to Resist

| Rationalization | Why It's Wrong | What To Do Instead |
|-----------------|----------------|---------------------|
| "Worktrees should merge cleanly" | Interface contracts don't guarantee no conflicts | **Always check for conflicts. Synthesize when needed.** |
| "I'll skip tests between rounds" | Bugs compound. Catching early is cheaper. | **Run tests after EVERY round.** |
| "Contract was just a suggestion" | Contracts enable parallel work. Violating them breaks integration. | **Treat contracts as mandatory. Fix violations.** |
| "I'll clean up worktrees later" | Stale worktrees cause confusion and disk bloat. | **Delete worktrees immediately after successful merge.** |
| "One worktree's version is obviously better" | Both had reasons. Synthesis preserves both intents. | **3-way analysis. Understand both. Synthesize.** |

---

## Self-Check

Before completing smart merge:

- [ ] Did I merge worktrees in dependency order?
- [ ] Did I run tests after each round?
- [ ] Did I perform 3-way analysis for all conflicts?
- [ ] Did I verify interface contracts are honored?
- [ ] Did I run green-mirage-audit on tests?
- [ ] Did I run code review on final result?
- [ ] Did I delete all worktrees after success?
- [ ] Are all tests passing?

If NO to ANY item, go back and complete it.

---

## Success Criteria

Smart merge succeeds when:

- ✓ All worktrees merged into base branch
- ✓ All interface contracts verified
- ✓ All tests passing
- ✓ Code review passes
- ✓ All worktrees cleaned up
- ✓ Single unified branch ready for next steps

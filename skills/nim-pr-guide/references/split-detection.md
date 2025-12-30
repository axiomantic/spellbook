# Branch Split Detection Logic

Detailed analysis for determining when staged changes should be a separate branch/PR.

## Decision Framework

### Primary Question
> "Would this change make sense as a standalone PR that could be merged independently?"

If YES → Consider splitting
If NO → Same branch is fine

## Cohesion Signals

### SAME BRANCH indicators (keep together):

| Signal | Example |
|--------|---------|
| Same issue reference | Both changes address #25341 |
| Same module/file focus | Both in `compiler/sempass2.nim` |
| Dependent changes | Change B only makes sense after Change A |
| Same type of work | Both are fixing edge cases in same feature |
| Shared test file | Both tested by same test case |

### SPLIT BRANCH indicators (separate):

| Signal | Example |
|--------|---------|
| Different issue references | #25341 vs #25350 |
| Different modules | `lib/system.nim` vs `compiler/parser.nim` |
| Independent changes | Either could be merged without the other |
| Mixed work types | Bug fix + unrelated refactoring |
| Different test files | Require separate test cases |

## Analysis Commands

### Step 1: Get Existing Branch Context

```bash
# What files has this branch already touched?
EXISTING_FILES=$(git diff $(git merge-base HEAD devel)...HEAD --name-only)

# What issues are referenced in existing commits?
EXISTING_ISSUES=$(git log $(git merge-base HEAD devel)..HEAD --oneline | grep -oE '#[0-9]+' | sort -u)

# What's the current size?
CURRENT_SIZE=$(git diff $(git merge-base HEAD devel) --stat | tail -1 | grep -oE '[0-9]+' | head -1)
```

### Step 2: Analyze Staged Changes

```bash
# What files are staged?
STAGED_FILES=$(git diff --cached --name-only)

# What's the staged size?
STAGED_SIZE=$(git diff --cached --stat | tail -1 | grep -oE '[0-9]+' | head -1)

# What would combined size be?
COMBINED_SIZE=$(git diff $(git merge-base HEAD devel) --stat | tail -1 | grep -oE '[0-9]+' | head -1)
```

### Step 3: Compare

```bash
# Check file overlap
comm -12 <(echo "$EXISTING_FILES" | sort) <(echo "$STAGED_FILES" | sort)

# Check module overlap (first directory level)
EXISTING_MODULES=$(echo "$EXISTING_FILES" | cut -d/ -f1-2 | sort -u)
STAGED_MODULES=$(echo "$STAGED_FILES" | cut -d/ -f1-2 | sort -u)
comm -12 <(echo "$EXISTING_MODULES") <(echo "$STAGED_MODULES")
```

## Decision Matrix

| Condition | Action |
|-----------|--------|
| Staged touches SAME files as existing | Same branch |
| Staged touches DIFFERENT modules AND combined > 50 lines | Consider split |
| Staged touches DIFFERENT modules AND combined > 150 lines | Strongly recommend split |
| Staged is refactoring AND existing is bug fix | MUST split |
| Staged is new feature AND existing is bug fix | MUST split |
| Staged references different issue | Strongly recommend split |
| Combined would exceed 300 lines | MUST split |

## Work Type Detection

### Bug Fix Indicators
- Commit message contains "fix", "fixes", "bug", "issue"
- Changes are small and focused
- Adds test that was previously failing
- Modifies existing logic minimally

### Refactoring Indicators
- Commit message contains "refactor", "cleanup", "reorganize"
- Moves code between files
- Renames variables/functions
- No behavior change expected
- Changes are widespread

### New Feature Indicators
- Commit message contains "add", "implement", "new", "feature"
- Adds new exported symbols
- Adds new test file (not just test case)
- Adds documentation

### Documentation Indicators
- Only touches `.md`, `.rst` files
- Commit message contains "doc", "docs", "documentation"
- No code changes

## Split Patterns

### Pattern A: Sequential Split (Dependent)

When changes are related but too large:

```
Original: 250 lines of related work
    ↓
PR 1: Foundation/cleanup (100 lines)
    ↓ (merge PR 1)
PR 2: "Continuation of #PR1" - Main changes (150 lines)
```

### Pattern B: Parallel Split (Independent)

When changes are unrelated:

```
Original: Fix #100 + Fix #200 in same branch
    ↓
Branch A: Fix #100 (can merge independently)
Branch B: Fix #200 (can merge independently)
```

### Pattern C: Type Split

When mixing work types:

```
Original: Bug fix + refactoring
    ↓
Branch A: Bug fix only (merge first - more urgent)
Branch B: Refactoring only (can wait)
```

## Splitting Procedure

### For Parallel Split (staged changes are independent):

```bash
# 1. Stash the unrelated staged changes
git stash push -m "work-for-separate-branch" -- <specific-files>
# OR for all staged:
git stash push --staged -m "work-for-separate-branch"

# 2. Complete current branch work, commit, push

# 3. Create new branch from devel
git checkout devel
git pull
git checkout -b fix/ISSUE-description

# 4. Apply stashed work
git stash pop

# 5. Commit and push new branch
git add .
git commit -m "fixes #ISSUE; description"
git push -u origin fix/ISSUE-description
```

### For Sequential Split (dependent changes):

```bash
# 1. Commit what you have so far (foundation)
git add .
git commit -m "fixes #ISSUE; part 1 - foundation"
git push

# 2. Create PR for part 1

# 3. After PR 1 merges, create continuation
git checkout devel
git pull
git checkout -b fix/ISSUE-part2

# 4. Continue work
# Reference: "Continuation of #PR1_NUMBER"
```

## Red Flags: When to STOP and Split

| Red Flag | Why It's Bad | Action |
|----------|--------------|--------|
| Branch > 300 lines | Will likely never merge | MUST split immediately |
| 3+ unrelated modules touched | Too scattered for one review | Split by module |
| Bug fix + refactoring mixed | Confuses review, risks regression | Split by type |
| Multiple issue references | Different problems, different PRs | Split by issue |
| "While I was here..." changes | Scope creep | Revert or split |

## Commit Message Check

### Good (focused):
```
fixes #25341; Handle edge case in lifecycle hooks
```

### Bad (scope creep):
```
fixes #25341; Handle edge case in lifecycle hooks, also cleaned up some imports and fixed typo in docs
```

If commit message has "also" or multiple unrelated items → Split needed

## Pre-Commit Checklist

Before committing, verify:

1. [ ] Staged changes relate to the same issue as existing work
2. [ ] Staged changes touch the same module area
3. [ ] Combined size stays under threshold (or is justified)
4. [ ] Work type is consistent (all fix, all refactor, etc.)
5. [ ] Commit message describes ONE focused change

If ANY check fails → Consider splitting before committing

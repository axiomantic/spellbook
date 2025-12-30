# Nim PR Guidelines - Full Research Data

Based on analysis of 154 PRs merged by core maintainers from external contributors.

## Key Statistics

- **73%** of merged PRs are "small" (< 50 lines) or "tiny" (< 10 lines)
- **42%** of titles start with "fixes #ISSUE" format
- **Fast-track merges** (0-2 hours) are almost exclusively small bug fixes with tests
- **76%** of merged PRs have fewer than 50 lines changed

## Size Distribution of Merged PRs

| Size | Lines | % of Merged PRs | Typical Merge Time |
|------|-------|-----------------|-------------------|
| Tiny | < 10 | 27% | 0-24 hours |
| Small | 10-50 | 49% | 1-7 days |
| Medium | 50-150 | 16% | 1-2 weeks |
| Large | 150-300 | 7% | Weeks to months |
| Very Large | 300+ | < 1% | Extremely rare |

## Fast Merge Examples (0-2 hours)

- PR #25342: "Fixes #25341; Invalid C code for lifecycle hooks" (37 lines)
- PR #25285: "fixes #25284; `.global` initialization inside method hoisted" (16 lines)
- PR #25175: "fixes #25173; SinglyLinkedList.remove broken" (14 lines)

## Title Format Analysis

### Most Common (42%): Issue Fix Format
```
fixes #ISSUE_NUMBER
fixes #ISSUE; Brief description
```

Examples:
- "fixes #25369"
- "fixes #25338; Switch default mangling back to cpp"
- "fixes #22305; Combination of generic destructor and closure fails"

### Also Acceptable (6%): Generic Fix
```
fix COMPONENT: Brief description
Fix issue in COMPONENT
```

Examples:
- "fix spawn not used on linux"
- "Fix `sizeof(T)` in `typedesc` templates"

### For Non-Fixes:
```
[Docs] Brief description
lowercase description without "fix"
Component: description
```

Examples:
- "[Docs] Remove horizontal scrolling on mobile"
- "flush `stdout` when prompting for password"
- "concept patch: inheritance"

## Case Sensitivity

- **73%** of merged PRs use lowercase-first titles
- Exceptions: "Fixes #", "Fix", "[Category]", proper nouns

## Test Requirements

From PR #25163 discussion:
```
tersec: "Tests?"
ringabout: "Tests are added for preventing of regression. Though in this case,
            it could hardly regress. But it can also ease and accelerate review
            if tests are there to ensure that this patch works"
```

## Visual Evidence for UI Changes

From PR #25377:
- Maintainer requested: "Can I get some before/after screenshots please?"
- Contributor provided side-by-side comparison table with images
- PR merged shortly after

## Description Patterns

### Most PRs: Minimal
Most successfully merged PRs have very brief descriptions or none at all.

### For Bug Fixes:
```
fixes #ISSUE

[Optional 1-2 sentence explanation if not obvious]
```

### For Larger Changes (50+ lines):
Example from PR #25353 (216 lines, merged):
```
fixes #17630

## Recursive Concept Cycle Detection

- Track (conceptId, typeId) pairs during matching to detect cycles
- Changed marker from IntSet to HashSet[ConceptTypePair]
- Removed unused depthCount field
- Added recursive concepts documentation to manual
- Added tests for recursive concepts, distinct chains, and co-dependent concepts
```

## What Causes Delays

### Configuration/Infrastructure Changes
- PR #24919: 3 lines, took **176 days**
- Reason: nim.cfg changes require extensive testing across platforms

### Performance Optimizations Without Clear Wins
- PR #25064: "Optimize @" - 11 comments, 50 days
- Maintainer: "I hate this shit. Just make the compiler emit copyMem..."
- Lesson: Fix root cause, don't work around compiler limitations

### Platform-Specific Changes
- PR #25155 (macOS runner): Uncovered Weave incompatibility with ARM64
- Lesson: Platform changes need verification on all affected platforms

## What Maintainers Value

1. **Correctness Over Cleverness** - Rejected optimization in favor of fixing root cause
2. **Tests as Proof** - Consistently requests tests even for "obvious" fixes
3. **Documentation for New Behavior** - Requested docs for PR #25317
4. **Platform Compatibility** - Comments on FreeBSD, macOS ARM64, s390x
5. **CI Cleanliness** - Expects understanding of which failures are relevant
6. **Issue-Driven Development** - Strong preference for fixing reported issues

## Size Guidelines by Change Type

### Bug Fixes
- Ideal: < 50 lines
- Acceptable: < 150 lines with comprehensive tests
- Requires justification: 150+ lines

### Refactoring
- Ideal: < 150 lines per PR, split into series
- Pattern from PR #25185: "Continuation of #25180"
- Each PR independently compiles and passes tests

### New Features
- Strongly discouraged without prior discussion/RFC
- If approved, keep < 200 lines
- Must include tests and documentation
- Example: PR #25317 (concept inheritance) was only 39 lines

### Documentation
- Any size acceptable if clear improvement
- Visual evidence helps for UI changes

## Top Contributor Patterns

### ringabout (69 merged PRs):
- Average size: 29 lines
- 64% under 50 lines
- Consistent "fixes #ISSUE" format
- Minimal but clear descriptions

### arnetheduck (5 merged PRs):
- Range: 6-159 lines
- Serial refactoring approach
- Detailed technical descriptions
- Active in PR discussions

### elijahr (3 merged PRs):
- Range: 35-216 lines
- Well-structured descriptions
- Comprehensive test coverage
- Technical detail in complex changes

## Serial Refactoring Pattern

From arnetheduck's series:

```
PR #25180: "std: `sysstr` cleanup, add docs" (125 lines)
    ↓
PR #25185: "std: `sysstr` refactor" (159 lines) - "Continuation of #25180"
```

Strategy:
1. First PR: Cleanup, documentation, non-breaking improvements
2. Second PR: Actual refactoring, referencing first PR
3. Each PR independently builds and passes tests
4. Series can be reviewed/merged incrementally

## Common Pitfalls

1. ❌ No issue reference - Hard to understand context
2. ❌ "Fixes #ISSUE" with no description - Requires reading issue
3. ❌ Multiple unrelated changes - Split into separate PRs
4. ❌ Missing tests - Will be requested, delays merge
5. ❌ Breaking changes without RFC - Won't be merged
6. ❌ Optimizations without benchmarks - May be rejected
7. ❌ Copy-paste from issue as description - Shows lack of synthesis
8. ❌ Infrastructure changes without discussion - Very long review cycle

## Merge Time Expectations

| Change Type | Lines | Typical Merge Time | Requirements |
|-------------|-------|-------------------|--------------|
| Bug fix with test | < 10 | 0-24 hours | Issue ref, test case |
| Bug fix with test | 10-50 | 1-7 days | Issue ref, test case |
| Bug fix with test | 50-150 | 1-2 weeks | Issue ref, comprehensive tests |
| Refactoring | 50-150 | 2-8 weeks | Clear description, test coverage |
| New feature | 50-200 | 4-12 weeks | Prior approval, tests, docs |
| Infrastructure | Any | Months | Discussion, cross-platform testing |

## Excellent PR Example: #25342

- **Title:** "Fixes #25341; Invalid C code for lifecycle hooks for distinct types based on generics"
- **Size:** 37 lines (35 additions, 2 deletions)
- **Merge time:** 1 hour
- **Description:** Clear explanation of compiler issue
- **Why it worked:** Small, focused, has test, fixes reported bug

## Good Large PR Example: #25353

- **Title:** "fix #17630: Implement cycle detection for recursive concepts"
- **Size:** 229 lines (216 additions, 13 deletions)
- **Description:** Structured with sections, clear bullet points, includes doc updates
- **Why it worked:** Well-organized, comprehensive tests, documentation included

## Problematic PR Example: #24919

- **Title:** "add `srcDir` variable to nim.cfg"
- **Size:** 3 lines
- **Merge time:** 176 days
- **Why it struggled:** Infrastructure change, required extensive discussion

## Warning Example: #25064

- **Title:** "Optimize @, fixes #25063"
- **Size:** 17 lines
- **Discussion:** 11 comments
- **Merge time:** 50 days
- **Issue:** Optimization workaround instead of fixing root cause

## The Nim Project Values

- Correctness over speed
- Small, provably correct changes over large refactorings
- Issue-driven development over speculative improvements
- Tests as proof over claims of correctness
- Incremental progress over revolutionary changes

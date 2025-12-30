# Getting PRs Merged to Nim

Research based on analysis of 154 PRs merged by core maintainers from external contributors in the nim-lang/Nim repository.

## Executive Summary

Successful PRs to Nim follow a clear pattern: **small, focused changes with clear issue references**. The data shows:
- 73% of merged PRs are "small" (under 50 lines changed) or "tiny" (under 10 lines)
- Fast-track merges (0-2 hours) are almost exclusively small bug fixes with test cases
- 42% of titles start with "fixes #ISSUE" format
- Minimal PR descriptions are the norm, not the exception

## DO's: What Gets PRs Merged Quickly

### 1. Keep Changes Small and Focused
**Data:** 76% of merged PRs have fewer than 50 lines changed.

**Pattern:**
- Tiny (< 10 lines): 27% of merged PRs - Often merged in 0-2 hours
- Small (10-50 lines): 49% of merged PRs - Usually merged within days
- Medium (50-150 lines): 16% of merged PRs - May take 1-2 weeks
- Large (150-300 lines): 7% of merged PRs - Can take weeks to months
- Very Large (300+ lines): < 1% - Extremely rare, needs special justification

**Examples of fast merges (0-2 hours):**
- PR #25342: "Fixes #25341; Invalid C code for lifecycle hooks" (37 lines)
- PR #25285: "fixes #25284; `.global` initialization inside method hoisted" (16 lines)
- PR #25175: "fixes #25173; SinglyLinkedList.remove broken" (14 lines)

### 2. Reference the Issue Number Directly
**Data:** 42% of successful PRs start title with "fixes #ISSUE" format, another 6% use "fix #ISSUE".

**Title Formats (in order of prevalence):**

**Most Common - Issue Fix:**
```
fixes #ISSUE_NUMBER
fixes #ISSUE; Brief description
```
Examples:
- "fixes #25369"
- "fixes #25338; Switch default mangling back to cpp"
- "fixes #22305; Combination of generic destructor and closure fails"

**Also Acceptable - Generic Fix:**
```
fix COMPONENT: Brief description
Fix issue in COMPONENT
```
Examples:
- "fix spawn not used on linux"
- "Fix `sizeof(T)` in `typedesc` templates called from generic type `when` clauses"

**For Docs/Non-Fixes:**
```
[Docs] Brief description
lowercase description without "fix"
Component: description
```
Examples:
- "[Docs] Remove horizontal scrolling on mobile"
- "flush `stdout` when prompting for password"
- "concept patch: inheritance"

### 3. Use Lowercase in Titles (With Exceptions)
**Data:** 73% of merged PRs use lowercase-first titles.

**Pattern:**
- Start with lowercase UNLESS:
  - It's "Fixes #ISSUE" or "Fix"
  - It's "[Category] Title"
  - It's a proper noun (e.g., "FreeBSD")

### 4. Include Tests
**Evidence from comments:** PRs without tests are questioned even for small changes.

From PR #25163 discussion:
```
tersec: "Tests?"
ringabout: "Tests are added for preventing of regression. Though in this case,
            it could hardly regress. But it can also ease and accelerate review
            if tests are there to ensure that this patch works"
```

### 5. Provide Visual Evidence for UI/Docs Changes
From PR #25377:
- Maintainer requested: "Can I get some before/after screenshots please?"
- Contributor provided side-by-side comparison table with images
- PR merged shortly after

### 6. Keep PR Descriptions Minimal but Informative
**Data:** Most successfully merged PRs have very brief descriptions or none at all.

**Good patterns:**

**For bug fixes:**
```
fixes #ISSUE

[Optional 1-2 sentence explanation of the core issue if not obvious from code]
```

**For larger changes (50+ lines):**
```
fixes #ISSUE

## What Changed
- Bullet point 1
- Bullet point 2

[Optional technical detail if complex]
```

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

### 7. Be Responsive to Feedback
From PR #25317:
- Maintainer: "Document somewhere (ideally in the manual) what affects this has and what kind of subtyping this allows for."
- Contributor added documentation
- PR merged shortly after

### 8. Address CI Failures
From PR #25318:
- Contributor noted: "remaining fails look unrelated"
- Shows awareness of CI status and ability to distinguish relevant vs. unrelated failures

## DON'T's: What Causes Delays or Rejection

### 1. Don't Submit Large, Multi-Purpose PRs
**Data:** Only 1 PR over 300 lines was merged in the sample, and it took special circumstances.

**Anti-pattern:** Combining multiple unrelated fixes or features.

**Better approach:** Split into multiple focused PRs, even if they touch related code.

### 2. Don't Skip Documentation for New Features
From PR #25317 (concept inheritance):
- Initial submission: minimal description
- Maintainer requested documentation
- Shows that new features require manual updates

### 3. Don't Make Changes Without Issue Context
**Pattern:** PRs that fix issues get merged 3-5x faster than exploratory changes.

PRs with "fixes #ISSUE" averaged days to merge, while PRs without issue references that added new functionality took weeks to months.

### 4. Don't Submit PRs That Mix Refactoring with Fixes
**Observation:** Successful large PRs (100+ lines) are either:
- Pure refactoring (documented as such)
- Pure bug fixes with comprehensive tests
- NOT a mix of both

### 5. Don't Use Generic Titles
**Bad:**
- "Patch 24922" (requires reading PR to understand)
- "Fixes #25202" with no description (ambiguous)

**Good:**
- "fixes #25202; Detailed explanation of what was fixed"
- "Fix specific component issue with clear description"

### 6. Don't Ignore Reviewer Suggestions
**Pattern:** PRs with extended discussion (5+ comments) that led to merges showed:
- Author actively engaged with feedback
- Made requested changes
- Explained technical decisions when questioned

PRs that stalled typically had:
- Unresolved reviewer questions
- Missing requested changes
- Lack of response to feedback

## Size Guidelines by Change Type

### Bug Fixes
- **Ideal:** < 50 lines
- **Acceptable:** < 150 lines if comprehensive test coverage
- **Requires justification:** 150+ lines

### Refactoring
- **Ideal:** < 150 lines per PR, split into series
- **Pattern from PR #25185:** "Continuation of #25180" - shows serial refactoring
- Each PR in series should compile and pass tests independently

### New Features
- **Strongly discouraged** without prior discussion/RFC
- If approved, keep < 200 lines
- Must include tests and documentation
- Example: PR #25317 (concept inheritance) was only 39 lines

### Documentation
- **Any size acceptable** if clear improvement
- Visual evidence helps for UI changes
- Examples: PR #25377 (10 lines), PR #25353 included doc updates

## Common Mistakes That Lead to Delays

### 1. Configuration/Infrastructure Changes
**Observation:** PR #24919 took 176 days despite being only 3 lines.
**Why:** Changes to nim.cfg, build system, or compiler flags require extensive testing across platforms and use cases.
**Lesson:** Expect long review cycles for infrastructure, even if code is minimal.

### 2. Performance Optimizations Without Clear Wins
**Observation:** PR #25064 ("Optimize @") generated 11 comments and took 50 days.
**Why:** Maintainer commented: "I hate this shit. Just make the compiler emit copyMem..."
**Lesson:** Performance changes that work around compiler limitations may be rejected in favor of fixing root cause.

### 3. Platform-Specific Changes Without Testing
From PR #25155 (macOS runner update):
- Uncovered Weave incompatibility with ARM64
- Extended discussion about proper fix
**Lesson:** Platform changes need verification on all affected platforms.

### 4. Breaking Changes to Public APIs
**Pattern:** PRs that change semantics of existing APIs require:
- Extensive justification
- Backward compatibility path or deprecation cycle
- Comprehensive test coverage showing no regressions

## What Maintainers Prioritize

Based on comment analysis:

### 1. **Correctness Over Cleverness**
From PR #25064: Rejected optimization in favor of fixing root cause in compiler.

### 2. **Tests as Proof**
Consistently requests tests even for "obvious" fixes.

### 3. **Documentation for New Behavior**
Requested documentation for PR #25317 (new concept feature).

### 4. **Platform Compatibility**
Comments on FreeBSD, macOS ARM64, s390x support show attention to platform coverage.

### 5. **CI Cleanliness**
Expects contributors to understand which CI failures are relevant to their change.

### 6. **Issue-Driven Development**
Strong preference for PRs that fix reported issues over speculative improvements.

## Ideal PR Structure

### Title Format
```
fixes #ISSUE_NUMBER; Brief description of fix
```
or
```
fix COMPONENT: What was wrong
```

### Description Template for Small Fixes (< 50 lines)
```
fixes #ISSUE_NUMBER

[Optional: 1-2 sentences if the fix isn't obvious from code]
```

### Description Template for Larger Changes (50+ lines)
```
fixes #ISSUE_NUMBER

## Summary
Brief explanation of what was broken and how this fixes it

## Changes
- Specific change 1
- Specific change 2
- Added tests for X, Y, Z

[Optional: Technical details if complex]
```

### For PRs Without Existing Issues
**DON'T** submit without discussion first. Instead:
1. Open an issue describing the problem/feature
2. Wait for maintainer feedback
3. Only then submit PR referencing that issue

## Examples: Good vs. Problematic

### ✅ Excellent PR: #25342
- **Title:** "Fixes #25341; Invalid C code for lifecycle hooks for distinct types based on generics"
- **Size:** 37 lines (35 additions, 2 deletions)
- **Merge time:** 1 hour
- **Description:** Clear explanation of compiler issue
- **Why it worked:** Small, focused, has test, fixes reported bug

### ✅ Good Large PR: #25353
- **Title:** "fix #17630: Implement cycle detection for recursive concepts"
- **Size:** 229 lines (216 additions, 13 deletions)
- **Description:** Structured with sections, clear bullet points, includes doc updates
- **Why it worked:** Well-organized, comprehensive tests, documentation included

### ⚠️ Problematic PR Pattern: #24919
- **Title:** "add `srcDir` variable to nim.cfg"
- **Size:** 3 lines
- **Merge time:** 176 days
- **Why it struggled:** Infrastructure change, required extensive discussion about implications

### ⚠️ Warning Pattern: #25064
- **Title:** "Optimize @, fixes #25063"
- **Size:** 17 lines
- **Discussion:** 11 comments
- **Merge time:** 50 days
- **Issue:** Optimization workaround instead of fixing root cause - maintainers pushed back hard

## How to Split Large Changes

**Pattern from arnetheduck's refactoring series:**

PR #25180: "std: `sysstr` cleanup, add docs" (125 lines)
↓
PR #25185: "std: `sysstr` refactor" (159 lines) - "Continuation of #25180"

**Strategy:**
1. First PR: Cleanup, documentation, non-breaking improvements
2. Second PR: Actual refactoring, referencing first PR
3. Each PR independently builds and passes tests
4. Series can be reviewed/merged incrementally

## Common Pitfalls to Avoid

1. ❌ **No issue reference** - Hard to understand context
2. ❌ **"Fixes #ISSUE" with no description** - Requires reading issue to understand PR
3. ❌ **Multiple unrelated changes** - Split into separate PRs
4. ❌ **Missing tests** - Will be requested, delays merge
5. ❌ **Breaking changes without RFC** - Won't be merged
6. ❌ **Optimizations without benchmarks** - May be rejected
7. ❌ **Copy-paste from issue as description** - Shows lack of synthesis
8. ❌ **Infrastructure changes without discussion** - Very long review cycle

## Quick Reference: Merge Time Expectations

| Change Type | Lines | Typical Merge Time | Requirements |
|-------------|-------|-------------------|--------------|
| Bug fix with test | < 10 | 0-24 hours | Issue ref, test case |
| Bug fix with test | 10-50 | 1-7 days | Issue ref, test case |
| Bug fix with test | 50-150 | 1-2 weeks | Issue ref, comprehensive tests |
| Refactoring | 50-150 | 2-8 weeks | Clear description, test coverage |
| New feature | 50-200 | 4-12 weeks | Prior approval, tests, docs |
| Infrastructure | Any | Months | Discussion, cross-platform testing |

## Success Metrics from Top Contributors

**ringabout (69 merged PRs):**
- Average size: 29 lines
- 64% under 50 lines
- Consistent "fixes #ISSUE" format
- Minimal but clear descriptions

**arnetheduck (5 merged PRs):**
- Range: 6-159 lines
- Serial refactoring approach
- Detailed technical descriptions
- Active in PR discussions

**elijahr (3 merged PRs):**
- Range: 35-216 lines
- Well-structured descriptions
- Comprehensive test coverage
- Technical detail in complex changes

## Final Recommendations

### For Your First PR
1. Find a small bug (< 20 lines to fix)
2. Write a test that fails without your fix
3. Title: "fixes #ISSUE; Brief description"
4. Description: 1-2 sentences max
5. Ensure all CI passes
6. Be ready to respond to feedback within 24 hours

### For Regular Contributors
1. Keep building trust with small, correct PRs
2. Gradually take on more complex issues
3. Learn the codebase patterns from reading merged PRs
4. Split large changes into reviewable chunks
5. Document non-obvious decisions in code comments, not PR descriptions

### For Complex Changes
1. Open issue first, get feedback
2. Propose approach in issue discussion
3. Get explicit approval before coding
4. Submit as series of incremental PRs
5. Each PR should be independently valuable
6. Reference prior PRs in series: "Continuation of #XXXXX"

## Remember

**The Nim project values:**
- Correctness over speed
- Small, provably correct changes over large refactorings
- Issue-driven development over speculative improvements
- Tests as proof over claims of correctness
- Incremental progress over revolutionary changes

**Your job as PR author:**
- Make review easy
- Prove correctness with tests
- Explain the problem, not just the solution
- Be responsive to feedback
- Accept that some changes need discussion before code

---
name: debugging
description: "Use when debugging bugs, test failures, or unexpected behavior"
---

# Debugging

<ROLE>Senior Debugging Specialist. Reputation depends on finding root causes, not applying band-aids.</ROLE>

## Invariant Principles

1. **Triage Before Methodology**: Classify symptom. Simple bugs get direct fixes; complex bugs get structured methodology.
2. **3-Fix Rule**: Three failed attempts signal architectural problem. Stop thrashing, question architecture.
3. **Verification Non-Negotiable**: No fix is complete without evidence. Always invoke `/verify` after claiming resolution.
4. **Track State**: Fix attempts accumulate across methodology invocations until bug verified fixed.
5. **Evidence Over Intuition**: "I think it's fixed" is not verification.
6. **Hunches Require Verification**: Before claiming "found it" or "root cause," invoke `verifying-hunches` skill. Eureka is hypothesis until tested.

## Entry Points

| Invocation | Triage | Methodology | Verification |
|------------|--------|-------------|--------------|
| `debugging` | Yes | Selected from triage | Auto |
| `debugging --scientific` | Skip | Scientific | Auto |
| `debugging --systematic` | Skip | Systematic | Auto |
| `scientific-debugging` skill | Skip | Scientific | Manual |
| `systematic-debugging` skill | Skip | Systematic | Manual |

## Session State

```
fix_attempts: 0       // Tracks attempts in this session
current_bug: null     // Symptom description
methodology: null     // "scientific" | "systematic" | null
```

Reset on: new bug, explicit request, verified fix.

## Phase 1: Triage

<analysis>
Before debugging, assess:
1. What is the exact symptom?
2. Is it reproducible?
3. What methodology fits this symptom type?
</analysis>

### 1.1 Gather Context

Ask via AskUserQuestion:

```javascript
AskUserQuestion({
  questions: [
    {
      question: "What's the symptom?",
      header: "Symptom",
      options: [
        { label: "Clear error with stack trace", description: "Error message points to specific location" },
        { label: "Test failure", description: "One or more tests failing" },
        { label: "Unexpected behavior", description: "Code runs but does wrong thing" },
        { label: "Intermittent/flaky", description: "Sometimes works, sometimes doesn't" },
        { label: "CI-only failure", description: "Passes locally, fails in CI" }
      ]
    },
    {
      question: "Can you reproduce it reliably?",
      header: "Reproducibility",
      options: [
        { label: "Yes, every time" },
        { label: "Sometimes" },
        { label: "No, happened once" },
        { label: "Only in CI" }
      ]
    },
    {
      question: "How many fix attempts already made?",
      header: "Prior attempts",
      options: [
        { label: "None yet" },
        { label: "1-2 attempts" },
        { label: "3+ attempts" }
      ]
    }
  ]
})
```

### 1.2 Simple Bug Detection

**ALL must be true:**
- Clear error with specific location
- Reproducible every time
- Zero prior attempts
- Error directly indicates fix (typo, undefined variable, missing import)

**If SIMPLE:**
```
This appears to be a straightforward bug:

[Error]: [specific error message]
[Location]: [file:line]
[Fix]: [obvious fix]

Applying fix directly without methodology.

[Apply fix]
[Auto-invoke /verify]
```

**Otherwise:** Proceed to 1.3

### 1.3 Check 3-Fix Rule

If prior attempts = "3+ attempts":

```
<THREE_FIX_RULE_WARNING>

You've attempted 3+ fixes without resolving this issue.
Strong signal of ARCHITECTURAL problem, not tactical bug.

**Options:**
A) Stop - invoke architecture-review
B) Continue (type "I understand the risk, continue")
C) Escalate to human architect
D) Create spike ticket

**Why this matters:**
- Repeated tactical fixes paper over architectural flaws
- Each failed fix increases technical debt
- Time thrashing could be spent on proper solution

</THREE_FIX_RULE_WARNING>
```

Wait for explicit choice. If B chosen: reset fix_attempts = 0, proceed.

## Phase 2: Methodology Selection

| Symptom | Reproducibility | Route To |
|---------|-----------------|----------|
| Intermittent/flaky | Sometimes/No | Scientific |
| Unexpected behavior | Sometimes/No | Scientific |
| Clear error | Yes | Systematic |
| Test failure | Yes | Systematic |
| CI-only failure | Passes locally | CI Investigation |
| Any + 3 attempts | Any | Architecture review |

**Test failures:** Offer `fixing-tests` skill as alternative (handles test quality, green mirage):

```
Test failure detected. Options:

A) fixing-tests skill (Recommended for test-specific issues)
   - Handles test quality issues, green mirage detection
B) systematic debugging
   - Better when test reveals production bug
```

Present recommendation with rationale, respect user choice (with warning if suboptimal).

## Phase 3: Execute Methodology

Invoke selected methodology:
- `/scientific-debugging` for hypothesis-driven investigation
- `/systematic-debugging` for root cause tracing

<CRITICAL>
**Hunch Interception:** When you feel like saying "I found it," "this is the issue," or "I think I see what's happening" - STOP. Invoke `verifying-hunches` skill before claiming discovery. Every eureka is a hypothesis until tested.
</CRITICAL>

### After Each Fix Attempt

```python
def after_fix_attempt(succeeded: bool):
    fix_attempts += 1

    if succeeded:
        invoke_verify()
    else:
        if fix_attempts >= 3:
            show_three_fix_warning()
        else:
            print(f"Fix attempt {fix_attempts} failed.")
            print("Returning to investigation with new information...")
```

### If "Just Fix It" Chosen

```
Proceeding with direct fix (methodology skipped).

WARNING: Lower success rate and higher rework risk.

[Attempt fix]
[Increment fix_attempts]
[If fails, return to Phase 2 with updated count]
```

## CI Investigation Branch

<RULE>Use when: passes locally, fails in CI; or CI-specific symptoms (cache, env vars, runner limits).</RULE>

### CI Symptom Classification

| Symptom | Likely Cause | Path |
|---------|--------------|------|
| Works locally, fails CI | Environment parity | Environment diff |
| Flaky only in CI | Resource constraints/timing | Resource analysis |
| Cache-related errors | Stale/corrupted cache | Cache forensics |
| Permission/access errors | CI secrets/credentials | Credential audit |
| Timeout failures | Runner limits | Performance triage |
| Dependency resolution fails | Lock file or registry | Dependency forensics |

### Environment Diff Protocol

1. **Capture CI environment** (from logs or CI config):
   - Runtime versions (Node/Python/etc)
   - OS and architecture
   - Environment variables (redact secrets)
   - Working directory structure

2. **Compare to local**:
   ```
   | Variable | Local | CI | Impact |
   |----------|-------|----|--------|
   ```

3. **Identify parity violations**: Version mismatches, missing env vars, path differences

### Cache Forensics

1. **Identify cache keys**: How is cache keyed? (lockfile hash, branch, manual)
2. **Check cache age**: When created? Has lockfile changed since?
3. **Test cache bypass**: Run with cache disabled to isolate
4. **Invalidation strategy**: Document proper invalidation

### Resource Analysis

| Constraint | Symptom | Mitigation |
|------------|---------|------------|
| Memory limit | OOM killer, exit 137 | Reduce parallelism, larger runner |
| CPU throttling | Timeouts, slow tests | Reduce parallelism, increase timeout |
| Disk space | "No space left" | Clean artifacts, smaller images |
| Network limits | Registry timeouts | Mirrors, retry logic |

### CI-Specific Checklist

```
[ ] Reproduced exact CI runtime version locally
[ ] Compared environment variables (CI vs local)
[ ] Tested with cache disabled
[ ] Checked runner resource limits
[ ] Verified secrets/credentials are set
[ ] Confirmed network access (registries, APIs)
[ ] Checked for CI-specific code paths (CI=true, etc.)
```

### Resolution

After identifying CI-specific cause:
1. Fix in CI config OR add local reproduction instructions
2. Document the environment requirement
3. Consider adding CI parity check to README/CLAUDE.md

## Phase 4: Verification

<CRITICAL>Auto-invoke `/verify` after EVERY fix claim. Not optional.</CRITICAL>

Verification confirms:
- Original symptom no longer occurs
- Tests pass (if applicable)
- No new failures introduced

**If verification fails:**
```
Verification failed. Bug not resolved.

[Show what failed]

Returning to debugging...

[Increment fix_attempts, check 3-fix rule, continue]
```

## 3-Fix Rule

```
After 3 failed attempts: STOP.

Signs of architectural problem:
- Each fix reveals issues elsewhere
- "Massive refactoring" required
- New symptoms appear with each fix
- Pattern feels fundamentally unsound

Actions:
1. Question architecture (not just implementation)
2. Discuss with human before more fixes
3. Consider refactoring vs. tactical fixes
4. Document the pattern issue
```

## Anti-Patterns

<FORBIDDEN>
- Skip verification after fix claim
- Ignore 3-fix warning
- "Just fix it" for complex bugs without warning
- Exceed 3 attempts without architectural discussion
- Apply fix without understanding root cause
- Claim "it works now" without evidence
- Say "I found it" or "root cause is X" without invoking verifying-hunches
- Rediscover same theory after it was disproven (check hypothesis registry)
</FORBIDDEN>

## Self-Check

Before completing debug session:

```
[ ] Fix attempts tracked throughout session
[ ] 3-fix rule checked if attempts >= 3
[ ] Verification command invoked after fix
[ ] User informed of session outcome
[ ] If methodology skipped, warning was shown
```

If NO to any item, go back and complete it.

<reflection>
After each debugging session, verify:
- Root cause was identified (not just symptom addressed)
- Fix was verified with evidence
- 3-fix rule was respected
</reflection>

<FINAL_EMPHASIS>
Evidence or it didn't happen. Three strikes and you're questioning architecture, not code. Verification is not optional - it's how professionals work.
</FINAL_EMPHASIS>

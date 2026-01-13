---
name: debugging
description: "Use when debugging bugs, test failures, or unexpected behavior"
---

# Debugging

<ROLE>
Senior Debugging Specialist. Reputation depends on finding root causes, not applying band-aids that shift problems elsewhere.
</ROLE>

## Invariant Principles

1. **Triage Before Methodology**: Every debug session begins with symptom classification. Simple bugs get direct fixes; complex bugs get structured methodology.

2. **3-Fix Rule**: Three failed attempts signal architectural problem, not tactical bug. Stop thrashing, question architecture.

3. **Verification Non-Negotiable**: No fix is complete without evidence. Always invoke `/verify` after claiming resolution.

4. **Track State**: Fix attempts accumulate across methodology invocations. Session state persists until bug verified fixed.

5. **Evidence Over Intuition**: Claims require proof. "I think it's fixed" is not verification.

## Inputs

| Input | Required | Description |
|-------|----------|-------------|
| `symptom` | Yes | Error message, test failure, or unexpected behavior description |
| `reproducibility` | No | How consistently the bug occurs (always/sometimes/once) |
| `prior_attempts` | No | Number of previous fix attempts (default: 0) |
| `codebase_context` | No | Relevant files, recent changes, or suspected locations |

## Outputs

| Output | Type | Description |
|--------|------|-------------|
| `root_cause` | Inline | Identified cause of the bug with evidence |
| `fix` | Code change | Applied fix with explanation |
| `verification` | Inline | Evidence that fix resolved the issue |
| `session_state` | Internal | Tracked fix attempts, methodology used |

## Declarative Schema

```
<analysis>
- Symptom: [error message | unexpected behavior | test failure | intermittent]
- Reproducibility: [always | sometimes | once]
- Prior attempts: [0 | 1-2 | 3+]
- Simple bug criteria: clear error + reproducible + zero attempts + obvious fix
</analysis>

<reflection>
- If 3+ attempts: HALT. Architectural review required.
- If simple: Fix directly, verify, done.
- Otherwise: Route to methodology.
</reflection>
```

## Entry Points

| Invocation | Behavior |
|------------|----------|
| `debugging` | Full triage, methodology selection, auto-verify |
| `debugging --scientific` | Skip triage, scientific methodology, auto-verify |
| `debugging --systematic` | Skip triage, systematic methodology, auto-verify |

## Phase 1: Triage

**Gather via AskUserQuestion:**
- Symptom type (clear error / test failure / unexpected behavior / intermittent)
- Reproducibility (always / sometimes / never)
- Prior fix attempts (0 / 1-2 / 3+)

**Simple Bug Detection** (ALL must be true):
- Clear error with specific location
- Reproducible every time
- Zero prior attempts
- Error directly indicates fix

If simple: Apply fix, invoke `/verify`, done.

## Phase 2: Methodology Selection

| Symptom | Reproducibility | Route To |
|---------|-----------------|----------|
| Intermittent/flaky | Sometimes/No | Scientific |
| Unexpected behavior | Sometimes/No | Scientific |
| Clear error | Yes | Systematic |
| Test failure | Yes | Systematic |
| CI-only failure | Passes locally | CI Investigation |
| Any + 3 attempts | Any | Architecture review |

**Test failures**: Offer `fixing-tests` skill as alternative (handles test quality, green mirage).

**CI-only failures**: Route to CI Investigation branch when failure occurs only in CI environment.

## CI Investigation Branch

<RULE>
Use when: build passes locally but fails in CI, or CI-specific symptoms (cache issues, environment variables, runner limits).
</RULE>

### CI Symptom Classification

| Symptom | Likely Cause | Investigation Path |
|---------|--------------|-------------------|
| Works locally, fails CI | Environment parity | Environment diff |
| Flaky only in CI | Resource constraints or timing | Resource analysis |
| Cache-related errors | Stale/corrupted cache | Cache forensics |
| Permission/access errors | CI secrets/credentials | Credential audit |
| Timeout failures | Runner limits or slow tests | Performance triage |
| Dependency resolution fails | Lock file or registry | Dependency forensics |

### Environment Diff Protocol

1. **Capture CI environment**: Extract from logs or CI config
   - Node/Python/runtime version
   - OS and architecture
   - Environment variables (redacted secrets)
   - Working directory structure

2. **Compare to local**:
   ```
   | Variable | Local | CI | Impact |
   |----------|-------|----|---------|
   ```

3. **Identify parity violations**: Version mismatches, missing env vars, path differences

### Cache Forensics

1. **Identify cache keys**: How is cache keyed? (lockfile hash, branch, manual key)
2. **Check cache age**: When was cache created? Has lockfile changed since?
3. **Test cache bypass**: Run with cache disabled to isolate
4. **Invalidation strategy**: If cache is suspect, document proper invalidation

### Resource Analysis

CI runners have constraints local machines often don't:

| Constraint | Symptom | Mitigation |
|------------|---------|------------|
| Memory limit | OOM killer, process exit 137 | Reduce parallelism, increase runner size |
| CPU throttling | Timeouts, slow tests | Reduce parallelism, increase timeout |
| Disk space | "No space left" errors | Clean artifacts, use smaller base images |
| Network limits | Registry timeouts | Use mirrors, retry logic |

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

## Phase 3: Execute

Invoke selected methodology as command:
- `/scientific-debugging` for hypothesis-driven investigation
- `/systematic-debugging` for root cause tracing

Track fix attempts. After each attempt:
- Success: Proceed to verification
- Failure + <3 attempts: Return to investigation
- Failure + 3 attempts: Trigger 3-fix warning

## Phase 4: Verification

<CRITICAL>
Auto-invoke `/verify` after EVERY fix claim. Not optional.
</CRITICAL>

Verification confirms:
- Original symptom resolved
- Tests pass (if applicable)
- No regressions introduced

Failure: Increment attempts, check 3-fix rule, continue debugging.

## 3-Fix Rule

```
After 3 failed attempts: STOP.

Signs of architectural problem:
- Each fix reveals issues elsewhere
- "Massive refactoring" required
- New symptoms appear with each fix

Actions:
A) Architecture review
B) Continue (explicit risk acknowledgment)
C) Escalate to human
D) Spike ticket for alternatives
```

## Session State

```
fix_attempts: int    // Accumulates across methodology invocations
current_bug: string  // Symptom description
methodology: string  // "scientific" | "systematic" | null
```

Reset on: new bug, explicit request, verified fix.

## Anti-Patterns

<FORBIDDEN>
- Skip verification after fix claim
- Ignore 3-fix warning
- "Just fix it" for complex bugs without warning
- Exceed 3 attempts without architectural discussion
- Apply fix without understanding root cause
- Claim "it works now" without reproducible evidence
</FORBIDDEN>

## Self-Check

Before completing: fix_attempts tracked, 3-fix rule honored, verification invoked, user informed of outcome.

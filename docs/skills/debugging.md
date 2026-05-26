# debugging

Systematic bug investigation with structured methodology selection, hypothesis tracking, and a circuit breaker that prevents endless fix attempts. Covers scientific debugging, systematic elimination, and CI-specific investigation branches. Invoke with `/debugging` or describe a bug to trigger it automatically. A core spellbook capability for root cause analysis.

**Auto-invocation:** Your coding assistant will automatically invoke this skill when it detects a matching trigger.

> Use when debugging bugs, test failures, or unexpected behavior. Triggers: 'why isn't this working', 'this doesn't work', 'X is broken', 'something's wrong', 'getting an error', 'exception in', 'stopped working', 'regression', 'crash', 'hang', 'flaky test', 'intermittent failure', or when user pastes a stack trace/error output. NOT for: test quality issues (use fixing-tests), adding new behavior (use develop).

## Workflow Diagram

## Overview

High-level flow across all phases of the debugging skill.

```mermaid
flowchart TD
    subgraph ENTRY["Entry Points"]
        E1["debugging (full)"]
        E2["debugging --scientific"]
        E3["debugging --systematic"]
    end

    P0["Phase 0: Prerequisites\n(Baseline + Reproduction)"]
    P1["Phase 1: Triage\n(Gather Context)"]
    P2["Phase 2: Methodology Selection"]
    P3["Phase 3: Execute Methodology"]
    P4["Phase 4: Verification"]

    E1 --> P0
    E2 -->|"skip triage"| P0
    E3 -->|"skip triage"| P0

    P0 -->|"baseline ✓\nbug reproduced ✓"| ROUTE{Route}
    P0 -->|"bug not reproduced"| NOREPRO(["Refine steps /\ncheck env / stop"])

    ROUTE -->|"E1: full flow"| P1
    ROUTE -->|"E2: --scientific"| P3
    ROUTE -->|"E3: --systematic"| P3

    P1 -->|"simple bug"| SIMPLEFIX["Apply Direct Fix"]
    P1 -->|"3+ attempts"| ARCHREVIEW(["Architecture Review"])
    P1 -->|"complex bug"| P2

    P2 -->|"scientific / systematic / CI"| P3

    SIMPLEFIX --> P4
    P3 -->|"fix applied"| P4

    P4 -->|"verified ✓"| SUCCESS(["Bug Fixed"])
    P4 -->|"failed"| INCR["Increment fix_attempts"]
    INCR --> RULE{fix_attempts >= 3?}
    RULE -->|"yes"| ARCHREVIEW
    RULE -->|"no"| P3

    subgraph LEGEND["Legend"]
        L1["Process"]
        L2["Decision"]:::gate
        L3["Subagent / Skill Dispatch"]:::subagent
        L4(["Terminal"]):::success
    end

    classDef gate fill:#ff6b6b,color:#fff,stroke:#cc0000
    classDef subagent fill:#4a9eff,color:#fff,stroke:#0055cc
    classDef success fill:#51cf66,color:#fff,stroke:#2f9e44
    classDef fail fill:#ff6b6b,color:#fff,stroke:#cc0000

    class NOREPRO fail
    class ARCHREVIEW fail
    class SUCCESS success
    class SIMPLEFIX,P3 subagent
    class RULE,ROUTE gate
```

---

## Phase 0 — Prerequisites Detail

```mermaid
flowchart TD
    START(["Enter Phase 0"])

    subgraph P01["0.1 Establish Clean Baseline"]
        B1["Identify clean reference state\n(upstream main / last known-good / fresh install)"]
        B2{"Can reach\nclean state?"}
        B3["Checkout / stash / pull to clean state"]
        B4["Verify expected behavior works\non clean state"]
        B5["Record: commit SHA, verified status, timestamp"]
        B6["Set baseline_established = true\nSet code_state = 'clean'"]

        B1 --> B2
        B2 -->|"no"| BLOCKED(["STOP — cannot debug\nwithout baseline"])
        B2 -->|"yes"| B3
        B3 --> B4
        B4 --> B5
        B5 --> B6
    end

    subgraph P02["0.2 Prove Bug Exists"]
        R1["Start from clean baseline"]
        R2["Run specific test / action\nthat should trigger bug"]
        R3["Observe actual failure\n(error, wrong output, crash)"]
        R4["Record exact steps + output"]
        R5{"Bug\nreproduced?"}
        R6["Set bug_reproduced = true"]
        R7{{"Option A: refine steps\nOption B: check if already fixed\nOption C: investigate env diff"}}

        R1 --> R2 --> R3 --> R4 --> R5
        R5 -->|"yes"| R6
        R5 -->|"no"| R7
    end

    subgraph P03["0.3 Code State Tracking\n(before EVERY test)"]
        CS1["Verify: on clean baseline?"]
        CS2["List all modifications"]
        CS3["Confirm this is intended test state"]
    end

    GATE{{"HARD GATE:\nbaseline_established = true\nbug_reproduced = true"}}

    START --> P01
    B6 --> P02
    R6 --> P03
    P03 --> GATE
    GATE -->|"both true"| PROCEED(["Proceed to Phase 1 / Route"])
    GATE -->|"either false"| RETURN["Return to incomplete step"]

    subgraph LEGEND["Legend"]
        L1["Process"]
        L2{{"Quality Gate"}}:::gate
        L3(["Terminal / Blocker"]):::fail
    end

    classDef gate fill:#ff6b6b,color:#fff,stroke:#cc0000
    classDef fail fill:#ff6b6b,color:#fff,stroke:#cc0000
    classDef success fill:#51cf66,color:#fff,stroke:#2f9e44

    class GATE gate
    class BLOCKED,R7,RETURN fail
    class PROCEED success
```

---

## Phase 1 + 2 — Triage and Methodology Selection Detail

```mermaid
flowchart TD
    START(["Enter Phase 1: Triage"])

    subgraph P11["1.1 Gather Context via AskUserQuestion"]
        Q1["Q1: What is the symptom?\n• Clear error w/ stack trace\n• Test failure\n• Unexpected behavior\n• Intermittent/flaky\n• CI-only failure"]
        Q2["Q2: Reproducibility?\n• Every time / Sometimes / Once / CI-only"]
        Q3["Q3: Prior fix attempts?\n• None / 1-2 / 3+"]
    end

    subgraph P12["1.2 Simple Bug Check"]
        SIMPLE_CHK{"ALL true?\n• Clear error + specific location\n• Reproducible every time\n• Zero prior attempts\n• Fix is obvious (typo/import/undef)"}
        DIRECT["Apply direct fix\n(no methodology)"]
    end

    subgraph P13["1.3 Three-Fix Rule"]
        THREE_CHK{"Prior attempts\n= 3+?"}
        THREE_WARN["Show THREE_FIX_RULE_WARNING\nOptions: A) Stop+arch review\nB) Continue (reset counter)\nC) Escalate to human\nD) Create spike ticket"]
        FRACTAL["Invoke fractal-thinking skill\n(intensity: explore)\nSeed: 'Why does symptom persist\nafter N fix attempts?'"]
        WAIT["Wait for explicit user choice"]
        RESET["reset fix_attempts = 0\nproceed to Phase 2"]

        THREE_CHK -->|"yes"| THREE_WARN
        THREE_WARN --> FRACTAL
        FRACTAL --> WAIT
        WAIT -->|"B: continue"| RESET
        WAIT -->|"A/C/D"| ARCHSTOP(["Architecture Review /\nEscalate / Spike"])
    end

    subgraph P2["Phase 2: Methodology Selection"]
        SEL{"Symptom + Reproducibility"}
        SCIBRANCH["Scientific Debugging\n(hypothesis-driven)"]
        SYSBRANCH["Systematic Debugging\n(root cause tracing)"]
        CIBRANCH["CI Investigation Branch"]
        TESTOPT["Offer fixing-tests skill\nvs systematic debugging"]

        SEL -->|"intermittent/flaky\nor unexpected + sometimes"| SCIBRANCH
        SEL -->|"clear error\nor test failure + yes"| TESTOPT
        SEL -->|"CI-only failure"| CIBRANCH
        TESTOPT -->|"user picks fixing-tests"| FIXTESTS["Invoke fixing-tests skill"]:::subagent
        TESTOPT -->|"user picks systematic"| SYSBRANCH
    end

    START --> P11
    Q1 --> Q2 --> Q3
    Q3 --> SIMPLE_CHK
    SIMPLE_CHK -->|"yes"| DIRECT
    SIMPLE_CHK -->|"no"| THREE_CHK
    THREE_CHK -->|"no"| SEL
    RESET --> SEL
    DIRECT --> P4_OUT(["Proceed to Phase 4"])
    SCIBRANCH --> P3_SCI(["Invoke /scientific-debugging"]):::subagent
    SYSBRANCH --> P3_SYS(["Invoke /systematic-debugging"]):::subagent
    CIBRANCH --> P3_CI(["CI Investigation Branch"]):::subagent

    subgraph LEGEND["Legend"]
        L1["Process"]
        L2{"Decision"}:::gate
        L3["Subagent / Skill Dispatch"]:::subagent
        L4(["Terminal"]):::success
    end

    classDef gate fill:#ff6b6b,color:#fff,stroke:#cc0000
    classDef subagent fill:#4a9eff,color:#fff,stroke:#0055cc
    classDef success fill:#51cf66,color:#fff,stroke:#2f9e44
    classDef fail fill:#ff6b6b,color:#fff,stroke:#cc0000

    class SIMPLE_CHK,THREE_CHK,SEL gate
    class ARCHSTOP fail
    class P4_OUT success
    class FIXTESTS,P3_SCI,P3_SYS,P3_CI subagent
```

---

## Phase 3 — Execute Methodology Detail

```mermaid
flowchart TD
    START(["Enter Phase 3:\nExecute Methodology"])

    HUNCH_GATE{"Feeling 'I found it'\nor 'root cause is X'?"}
    HUNCH_STOP["STOP — invoke verifying-hunches skill\nbefore claiming discovery"]:::subagent

    ISO_GATE{"Before running\nany experiment"}
    ISO["1. Invoke isolated-testing skill\n2. Design complete repro test\n3. Get approval (unless autonomous)\n4. Test ONE theory at a time\n5. STOP on reproduction"]:::subagent

    CHAOS{"Chaos indicator\ndetected?\n'Let me try...' / 'Maybe if...'\n'What about...'"}
    CHAOS_STOP(["STOP — chaos debugging\nforbidden"])

    subgraph METH["Methodology Branches"]
        SCI["scientific-debugging skill\n(hypothesis-driven)\nFor: intermittent, unexpected behavior"]:::subagent
        SYS["systematic-debugging skill\n(root cause tracing)\nFor: clear errors, test failures"]:::subagent
        CI_INV["CI Investigation Branch\n(see CI diagram)"]
        DIRECT_FIX["Just Fix It (user request)\nWARN: lower success rate\nIncrement fix_attempts\nIf fails → Phase 2"]
    end

    FIX_RESULT{"Fix\nsucceeded?"}
    P4(["Proceed to Phase 4:\nVerification"])
    INCR["Increment fix_attempts"]
    THREE{"fix_attempts\n>= 3?"}
    ARCH(["Architecture Review\n(see Phase 1.3)"])
    RETRY["Return to investigation\nwith new information"]

    START --> HUNCH_GATE
    HUNCH_GATE -->|"yes"| HUNCH_STOP
    HUNCH_GATE -->|"no"| ISO_GATE
    HUNCH_STOP -->|"after verification"| ISO_GATE
    ISO_GATE --> ISO
    ISO --> CHAOS
    CHAOS -->|"yes"| CHAOS_STOP
    CHAOS -->|"no"| METH

    METH --> FIX_RESULT
    FIX_RESULT -->|"yes"| P4
    FIX_RESULT -->|"no"| INCR
    INCR --> THREE
    THREE -->|"yes"| ARCH
    THREE -->|"no"| RETRY
    RETRY --> ISO_GATE

    subgraph CI_DETAIL["CI Investigation Branch Detail"]
        CI1{"CI Symptom"}
        CI1 -->|"env parity"| ENV["Environment Diff Protocol\n(runtime versions, OS, env vars)"]
        CI1 -->|"flaky/resource"| RES["Resource Analysis\n(memory, CPU, disk, network)"]
        CI1 -->|"cache errors"| CACHE["Cache Forensics\n(keys, age, bypass test)"]
        CI1 -->|"permission errors"| CREDS["Credential Audit"]
        CI1 -->|"timeouts"| PERF["Performance Triage"]
        CI1 -->|"dep resolution"| DEP["Dependency Forensics"]
    end

    CI_INV --> CI_DETAIL

    subgraph LEGEND["Legend"]
        L1["Process"]
        L2{"Decision"}:::gate
        L3["Subagent / Skill Dispatch"]:::subagent
        L4(["Terminal"]):::success
        L5(["Blocker / Error"]):::fail
    end

    classDef gate fill:#ff6b6b,color:#fff,stroke:#cc0000
    classDef subagent fill:#4a9eff,color:#fff,stroke:#0055cc
    classDef success fill:#51cf66,color:#fff,stroke:#2f9e44
    classDef fail fill:#ff6b6b,color:#fff,stroke:#cc0000

    class HUNCH_GATE,ISO_GATE,CHAOS,FIX_RESULT,THREE,CI1 gate
    class HUNCH_STOP,SCI,SYS,ISO subagent
    class P4 success
    class CHAOS_STOP,ARCH fail
```

---

## Phase 4 — Verification Detail

```mermaid
flowchart TD
    START(["Enter Phase 4: Verification\n(auto-invoked after every fix claim)"])

    V1["Confirm: original symptom no longer occurs"]
    V2["Confirm: tests pass (if applicable)"]
    V3["Confirm: no new failures introduced"]

    VRESULT{"All checks\npassed?"}

    SHOW_FAIL["Show what failed\n(specific evidence)"]
    INCR["Increment fix_attempts"]
    THREE{"fix_attempts\n>= 3?"}
    ARCH(["THREE_FIX_RULE_WARNING\n→ Architecture Review"])
    RETRY(["Return to Phase 3\nwith new information"])

    subgraph SESSION_CLOSE["Session Close Checklist"]
        SC1["fix_attempts tracked throughout"]
        SC2["3-fix rule checked if attempts >= 3"]
        SC3["Phase 4 verification invoked"]
        SC4["User informed of outcome"]
        SC5["Methodology-skip warning shown (if applicable)"]
        SC6["Code state documented or returned to clean"]
    end

    subgraph REFLECTION["Post-Session Reflection"]
        RF1["Root cause identified (not just symptom)?"]
        RF2["Fix verified with evidence?"]
        RF3["3-fix rule respected?"]
    end

    SUCCESS(["Bug Fixed\nSession Complete"])

    START --> V1 --> V2 --> V3 --> VRESULT

    VRESULT -->|"yes"| SESSION_CLOSE
    VRESULT -->|"no"| SHOW_FAIL
    SHOW_FAIL --> INCR
    INCR --> THREE
    THREE -->|"yes"| ARCH
    THREE -->|"no"| RETRY

    SESSION_CLOSE --> REFLECTION
    REFLECTION --> SUCCESS

    subgraph LEGEND["Legend"]
        L1["Process"]
        L2{"Decision"}:::gate
        L4(["Terminal"]):::success
        L5(["Blocker / Error"]):::fail
    end

    classDef gate fill:#ff6b6b,color:#fff,stroke:#cc0000
    classDef success fill:#51cf66,color:#fff,stroke:#2f9e44
    classDef fail fill:#ff6b6b,color:#fff,stroke:#cc0000

    class VRESULT,THREE gate
    class SUCCESS success
    class ARCH,RETRY fail
```

---

## Cross-Reference Table

| Overview Node | Detail Diagram |
|---|---|
| Phase 0: Prerequisites | Phase 0 — Prerequisites Detail |
| Phase 1: Triage | Phase 1 + 2 — Triage and Methodology Selection Detail |
| Phase 2: Methodology Selection | Phase 1 + 2 — Triage and Methodology Selection Detail |
| Phase 3: Execute Methodology | Phase 3 — Execute Methodology Detail |
| CI Investigation Branch | Phase 3 — Execute Methodology Detail (CI_DETAIL subgraph) |
| Phase 4: Verification | Phase 4 — Verification Detail |

## Skill Content

``````````markdown
# Debugging

<ROLE>Senior Debugging Specialist. Reputation depends on finding root causes, not applying band-aids.</ROLE>

## Invariant Principles

1. **Baseline Before Investigation**: Establish clean, known-good state BEFORE any debugging. No baseline = no debugging.
2. **Prove Bug Exists First**: Reproduce the bug on clean baseline before ANY investigation or fix attempts. No repro = no bug.
3. **Triage Before Methodology**: Classify symptom. Simple bugs get direct fixes; complex bugs get structured methodology.
4. **3-Fix Rule**: Three failed attempts require architectural review, not more tactical fixes.
5. **Verification Non-Negotiable**: No fix is complete without evidence. Always invoke Phase 4 Verification after claiming resolution.
6. **Track State**: Fix attempts AND code state accumulate across methodology invocations. Always know what state you're testing.
7. **Evidence Over Intuition**: "I think it's fixed" is not verification.
8. **Hunches Require Verification**: Before claiming "found it" or "root cause," invoke `verifying-hunches` skill. Eureka is hypothesis until tested.
9. **Isolated Testing**: One theory, one test, full stop. No mixing theories, no "trying things," no chaos. Invoke `isolated-testing` skill before ANY experiment execution.

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
baseline_established: false  // Is clean baseline confirmed?
bug_reproduced: false        // Has bug been reproduced on clean baseline?
code_state: "unknown"        // "clean" | "modified" | "unknown"
```

Reset on: new bug, explicit request, verified fix.

---

## Phase 0: Prerequisites

<CRITICAL>
**THIS PHASE IS MANDATORY.** Cannot proceed to triage or investigation without completing Phase 0.

If you find yourself debugging without having completed this phase, STOP IMMEDIATELY and return here.
</CRITICAL>

### 0.1 Establish Clean Baseline

Before ANY investigation, establish a known-good reference state.

```
BASELINE CHECKLIST:
[ ] What is the "clean" state? (upstream main, last known working commit, fresh install)
[ ] Can I reach that clean state?
[ ] What does "working correctly" look like on clean state?
[ ] Have I tested clean state to confirm it works?
```

**If working with external code (upstream repo, dependency):**
```bash
git stash                    # Save local changes
git checkout main            # Or upstream branch
git pull                     # Get latest
# Build/run from clean state and verify expected behavior works
```

**Record the baseline:**
```
BASELINE ESTABLISHED:
- Reference: [commit SHA / version / state description]
- Verified working: [yes/no + what you tested]
- Date: [timestamp]
```

Set `baseline_established = true`, `code_state = "clean"` in session state.

### 0.2 Prove Bug Exists

<CRITICAL>
**HARD GATE: Cannot investigate or fix a bug you haven't reproduced.**

"Someone reported X" is not reproduction.
"I think I saw Y" is not reproduction.
"The code looks wrong" is not reproduction.

**Reproduction means:** You personally observed the failure, on a known code state, with a specific test.
</CRITICAL>

**Reproduction requirements:**
1. Start from CLEAN baseline (from 0.1)
2. Run SPECIFIC test/action that should trigger bug
3. Observe ACTUAL failure (error message, wrong output, crash)
4. Record EXACT steps and output

```
BUG REPRODUCTION:
- Code state: [clean baseline from 0.1]
- Steps to reproduce:
  1. [exact step]
  2. [exact step]
  3. [exact step]
- Expected: [what should happen]
- Actual: [what actually happened - paste output]
- Reproduced: [YES / NO]
```

Set `bug_reproduced = true` in session state on successful reproduction.

**If bug does NOT reproduce on clean baseline:**
```
BUG NOT REPRODUCED on clean baseline.

Options:
A) The bug doesn't exist (or is already fixed)
B) Reproduction steps are incomplete
C) Bug is environment-specific

DO NOT proceed to investigation. Either:
- Refine reproduction steps
- Check if bug was already fixed
- Investigate environment differences
```

### 0.3 Code State Tracking

Before EVERY test, verify:
```
CODE STATE CHECK:
- Am I on clean baseline? [yes/no]
- What modifications exist? [list changes]
- Is this the state I INTEND to test? [yes/no]
```

<FORBIDDEN>
- Testing without knowing code state
- Making changes and forgetting what you changed
- Assuming you're on clean state without verifying
- "Let me try this change" without recording it
</FORBIDDEN>

---

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
[Proceed to Phase 4 Verification]
```

**Otherwise:** Proceed to 1.3

### 1.3 Check 3-Fix Rule

If prior attempts = "3+ attempts":

```
<THREE_FIX_RULE_WARNING>

You've attempted 3+ fixes without resolving this issue.
Tactical fixes cannot solve architectural problems.

Options:
A) Stop - conduct architecture review with human
B) Continue (type "I understand the risk, continue")
C) Escalate to human architect
D) Create spike ticket

</THREE_FIX_RULE_WARNING>
```

Wait for explicit choice. If B chosen: reset fix_attempts = 0, proceed.

**Signs of architectural problem (stop and reassess when present):**
- Each fix reveals issues elsewhere
- "Massive refactoring" required
- New symptoms appear with each fix
- Pattern feels fundamentally unsound

**Actions when 3-fix rule triggered:**
1. **Fractal exploration:** Invoke `fractal-thinking` with intensity `explore` and seed: "Why does [symptom] persist after [N] fix attempts targeting [root causes]?" Invoke when stuck generating new hypotheses after 2+ disproven theories. Use synthesis to produce new hypothesis families.
2. Question architecture (not just implementation)
3. Discuss with human before more fixes
4. Consider refactoring vs. tactical fixes
5. Document the pattern issue

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

Present recommendation with rationale. Respect user choice; warn if user picks B for a test-quality issue (not a production bug) or A when the test is exposing real production behavior.

## Phase 3: Execute Methodology

Invoke selected methodology:
- `/scientific-debugging` for hypothesis-driven investigation
- `/systematic-debugging` for root cause tracing

<CRITICAL>
**Hunch Interception:** When you feel like saying "I found it," "this is the issue," or "I think I see what's happening" - STOP. Invoke `verifying-hunches` skill before claiming discovery. Every eureka is a hypothesis until tested.
</CRITICAL>

<CRITICAL>
**Isolated Testing Mandate:** Before running ANY experiment or test:
1. Invoke `isolated-testing` skill
2. Design the complete repro test BEFORE execution
3. Get approval (unless autonomous mode)
4. Test ONE theory at a time
5. STOP on reproduction - do not continue investigating

Chaos indicators (STOP if you catch yourself):
- "Let me try..." / "Maybe if I..." / "What about..."
- Making changes without a designed test
- Testing multiple theories simultaneously
- Continuing after bug reproduces
</CRITICAL>

### After Each Fix Attempt

```python
def after_fix_attempt(succeeded: bool):
    fix_attempts += 1

    if succeeded:
        invoke_phase4_verification()
    else:
        if fix_attempts >= 3:
            show_three_fix_warning()
        else:
            print(f"Fix attempt {fix_attempts} failed.")
            print("Returning to investigation with new information...")
```

### If "Just Fix It" Chosen

When user explicitly requests skipping methodology:

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
[ ] After identifying cause: fix in CI config OR add local reproduction instructions
[ ] Document the environment requirement
[ ] Add CI parity check to README/CLAUDE.md
```

## Phase 4: Verification

<CRITICAL>Auto-invoke Phase 4 Verification after EVERY fix claim. Not optional.</CRITICAL>

Verification confirms:
- Original symptom no longer occurs
- Tests pass (if applicable)
- No new failures introduced

**If verification succeeds:**

**If verification fails:**
```
Verification failed. Bug not resolved.

[Show what failed]

Returning to debugging...

[Increment fix_attempts, check 3-fix rule, continue]
```

## Anti-Patterns

<FORBIDDEN>
**Phase 0 violations:**
- Skip baseline establishment (no clean reference state)
- Investigate without reproducing bug first (prove it exists!)
- Test on unknown code state (always know what you're testing)
- Forget what modifications you've made
- Assume you're on clean state without verifying

**Investigation violations:**
- Skip verification after fix claim
- Ignore 3-fix warning
- "Just fix it" for complex bugs without warning
- Exceed 3 attempts without architectural discussion
- Apply fix without understanding root cause
- Claim "it works now" without evidence

**Methodology violations:**
- Say "I found it" or "root cause is X" without invoking verifying-hunches
- Rediscover same theory after it was disproven (check hypothesis registry)
- "Let me try" / "maybe if I" / "what about" (chaos debugging)
- Test multiple theories simultaneously (no isolation)
- Run experiments without designed repro test (action without design)
- Continue investigating after bug reproduces (stop on reproduction)

**Winging it:**
- Debugging without loading this skill
- Skipping phases because "it's obvious"
- Making elaborate fixes before proving bug exists
</FORBIDDEN>

## Self-Check

**Before starting investigation:**
```
[ ] Phase 0 completed (baseline + reproduction)
[ ] Clean baseline established and recorded
[ ] Bug reproduced on clean baseline with specific steps
[ ] Code state is known and tracked
```

**Before completing debug session:**
```
[ ] Fix attempts tracked throughout session
[ ] 3-fix rule checked if attempts >= 3
[ ] Phase 4 Verification invoked after fix
[ ] User informed of session outcome
[ ] If methodology skipped, warning was shown
[ ] Code returned to clean state (or changes documented)
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
``````````

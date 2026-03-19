# debugging

Systematic bug investigation with structured methodology selection, hypothesis tracking, and a circuit breaker that prevents endless fix attempts. Covers scientific debugging, systematic elimination, and CI-specific investigation branches. Invoke with `/debugging` or describe a bug to trigger it automatically. A core spellbook capability for root cause analysis.

**Auto-invocation:** Your coding assistant will automatically invoke this skill when it detects a matching trigger.

> Use when debugging bugs, test failures, or unexpected behavior. Triggers: 'why isn't this working', 'this doesn't work', 'X is broken', 'something's wrong', 'getting an error', 'exception in', 'stopped working', 'regression', 'crash', 'hang', 'flaky test', 'intermittent failure', or when user pastes a stack trace/error output. NOT for: test quality issues (use fixing-tests), adding new behavior (use develop).

## Workflow Diagram

# Debugging Skill Diagrams

## Overview Diagram

High-level flow through the debugging skill's phases, from entry to resolution.

```mermaid
flowchart TD
    subgraph Legend
        L1[Process]
        L2{Decision}
        L3([Terminal])
        L4[/"Subagent/Skill Dispatch"/]:::subagent
        L5[[Quality Gate]]:::gate
        L6([Success]):::success
    end

    Entry([User reports bug /<br>stack trace / trigger]) --> EntryCheck{Entry point?}

    EntryCheck -->|"--scientific"| SkipToSci[Skip triage:<br>methodology = scientific]
    EntryCheck -->|"--systematic"| SkipToSys[Skip triage:<br>methodology = systematic]
    EntryCheck -->|default| Phase0

    SkipToSci --> Phase0
    SkipToSys --> Phase0

    Phase0[[Phase 0: Prerequisites]]:::gate --> Phase1
    Phase1[Phase 1: Triage] --> Phase2
    Phase2[Phase 2: Methodology Selection] --> Phase3
    Phase3[Phase 3: Execute Methodology] --> Phase4
    Phase4[[Phase 4: Verification]]:::gate --> VerifyResult{Verified?}

    VerifyResult -->|Yes| StoreMemory[Store root cause<br>in memory]
    StoreMemory --> Done([Bug resolved]):::success

    VerifyResult -->|No| IncAttempts[Increment fix_attempts]
    IncAttempts --> ThreeCheck{fix_attempts >= 3?}
    ThreeCheck -->|No| Phase3
    ThreeCheck -->|Yes| ThreeFix[[3-Fix Rule Warning]]:::gate
    ThreeFix --> ThreeChoice{User choice?}
    ThreeChoice -->|"A: Architecture review"| ArchReview([Escalate to<br>architecture review])
    ThreeChoice -->|"B: Continue"| ResetContinue[Reset fix_attempts = 0]
    ThreeChoice -->|"C: Escalate"| Escalate([Escalate to<br>human architect])
    ThreeChoice -->|"D: Spike ticket"| Spike([Create spike ticket])
    ResetContinue --> Phase3

    classDef subagent fill:#4a9eff,stroke:#2d7cd6,color:#fff
    classDef gate fill:#ff6b6b,stroke:#d94f4f,color:#fff
    classDef success fill:#51cf66,stroke:#3da84e,color:#fff
```

## Cross-Reference Table

| Overview Node | Detail Diagram |
|---|---|
| Phase 0: Prerequisites | [Phase 0 Detail](#phase-0-prerequisites) |
| Phase 1: Triage | [Phase 1 Detail](#phase-1-triage) |
| Phase 2: Methodology Selection | [Phase 2 Detail](#phase-2-methodology-selection) |
| Phase 3: Execute Methodology | [Phase 3 Detail](#phase-3-execute-methodology) |
| Phase 4: Verification | [Phase 4 Detail](#phase-4-verification) |
| 3-Fix Rule Warning | [3-Fix Rule Detail](#3-fix-rule-circuit-breaker) |

---

## Phase 0: Prerequisites

Mandatory baseline establishment and bug reproduction before any investigation.

```mermaid
flowchart TD
    subgraph Legend
        L1[Process]
        L2{Decision}
        L3[[Quality Gate]]:::gate
        L4([Terminal]):::success
    end

    Start([Phase 0 Entry]) --> Step01[0.1 Establish Clean Baseline]

    Step01 --> BaselineQ{Clean state<br>reachable?}
    BaselineQ -->|No| BlockBaseline([Cannot debug:<br>no clean reference])

    BaselineQ -->|Yes| VerifyClean[Test clean state<br>to confirm it works]
    VerifyClean --> RecordBaseline[Record baseline:<br>commit SHA / version /<br>state description]
    RecordBaseline --> SetBaseline["Set baseline_established = true<br>code_state = clean"]

    SetBaseline --> Step02[0.2 Prove Bug Exists]
    Step02 --> StartClean[[Start from clean baseline]]:::gate
    StartClean --> RunRepro[Run specific test/action<br>that triggers bug]
    RunRepro --> ReproResult{Bug reproduced?}

    ReproResult -->|Yes| RecordRepro[Record exact steps<br>and output]
    RecordRepro --> SetRepro["Set bug_reproduced = true"]
    SetRepro --> Step03[0.3 Code State Tracking]
    Step03 --> CodeStateCheck[[Before EVERY test:<br>verify code state]]:::gate
    CodeStateCheck --> Phase0Done([Phase 0 Complete:<br>proceed to Phase 1]):::success

    ReproResult -->|No| NoRepro{Why no reproduction?}
    NoRepro -->|"Bug doesn't exist /<br>already fixed"| NoBug([No bug to debug])
    NoRepro -->|"Steps incomplete"| RefineSteps[Refine reproduction steps] --> RunRepro
    NoRepro -->|"Environment-specific"| EnvInvestigate[Investigate environment<br>differences] --> RunRepro

    classDef gate fill:#ff6b6b,stroke:#d94f4f,color:#fff
    classDef success fill:#51cf66,stroke:#3da84e,color:#fff
```

---

## Phase 1: Triage

Classify the symptom and determine whether the bug is simple enough for a direct fix or requires structured methodology.

```mermaid
flowchart TD
    subgraph Legend
        L1[Process]
        L2{Decision}
        L3[/"Skill Dispatch"/]:::subagent
        L4([Terminal]):::success
    end

    Start([Phase 1 Entry]) --> Gather[1.1 Gather Context<br>via AskUserQuestion]

    Gather --> SymptomType["Capture:<br>- Symptom type<br>- Reproducibility<br>- Prior fix attempts"]

    SymptomType --> MemoryPrime[1.4 Memory Priming:<br>recall prior root causes<br>for this component]
    MemoryPrime --> MemoryRecall[/"memory_recall(query=<br>symptom + component)"/]:::subagent

    MemoryRecall --> SimpleCheck{1.2 Simple Bug?<br>All must be true:<br>- Clear error + location<br>- Reproducible every time<br>- Zero prior attempts<br>- Fix is obvious}

    SimpleCheck -->|Yes| DirectFix[Apply fix directly<br>without methodology]
    DirectFix --> GoVerify([Proceed to<br>Phase 4 Verification]):::success

    SimpleCheck -->|No| ThreeCheck{1.3 Prior attempts<br>>= 3?}
    ThreeCheck -->|Yes| ThreeFixRule([Trigger 3-Fix Rule<br>circuit breaker])
    ThreeCheck -->|No| GoPhase2([Proceed to<br>Phase 2]):::success

    classDef subagent fill:#4a9eff,stroke:#2d7cd6,color:#fff
    classDef gate fill:#ff6b6b,stroke:#d94f4f,color:#fff
    classDef success fill:#51cf66,stroke:#3da84e,color:#fff
```

---

## Phase 2: Methodology Selection

Route to the appropriate debugging methodology based on symptom type and reproducibility.

```mermaid
flowchart TD
    subgraph Legend
        L1[Process]
        L2{Decision}
        L3[/"Skill Dispatch"/]:::subagent
        L4([Terminal]):::success
    end

    Start([Phase 2 Entry]) --> SymRoute{Symptom +<br>Reproducibility?}

    SymRoute -->|"Intermittent/flaky +<br>Sometimes/No"| Scientific
    SymRoute -->|"Unexpected behavior +<br>Sometimes/No"| Scientific
    SymRoute -->|"Clear error +<br>Reproducible"| Systematic
    SymRoute -->|"Test failure +<br>Reproducible"| TestDecision
    SymRoute -->|"CI-only failure"| CIBranch
    SymRoute -->|"Any + 3 attempts"| ArchReview([Architecture Review])

    TestDecision{Test failure route?} -->|"A: Test-quality issue"| FixingTests[/"fixing-tests skill"/]:::subagent
    TestDecision -->|"B: Production bug<br>exposed by test"| Systematic

    Scientific[/"scientific-debugging"/]:::subagent --> GoPhase3([Proceed to Phase 3]):::success
    Systematic[/"systematic-debugging"/]:::subagent --> GoPhase3
    CIBranch[CI Investigation Branch] --> GoPhase3

    classDef subagent fill:#4a9eff,stroke:#2d7cd6,color:#fff
    classDef success fill:#51cf66,stroke:#3da84e,color:#fff
```

---

## Phase 3: Execute Methodology

Invoke the selected methodology with hunch verification and isolated testing enforced at every step.

```mermaid
flowchart TD
    subgraph Legend
        L1[Process]
        L2{Decision}
        L3[/"Skill Dispatch"/]:::subagent
        L4[[Quality Gate]]:::gate
        L5([Terminal]):::success
    end

    Start([Phase 3 Entry]) --> MethodCheck{Methodology?}

    MethodCheck -->|Scientific| InvokeSci[/"Invoke<br>scientific-debugging"/]:::subagent
    MethodCheck -->|Systematic| InvokeSys[/"Invoke<br>systematic-debugging"/]:::subagent
    MethodCheck -->|"User said<br>just fix it"| JustFix[Attempt direct fix<br>with warning shown]

    InvokeSci --> Investigation
    InvokeSys --> Investigation

    Investigation[Investigation in progress] --> HunchCheck{Feeling<br>"I found it"?}

    HunchCheck -->|Yes| VerifyHunch[/"verifying-hunches skill:<br>test eureka hypothesis"/]:::subagent
    HunchCheck -->|No| ContinueInvestigation[Continue investigation]
    ContinueInvestigation --> Investigation

    VerifyHunch --> HunchResult{Hunch verified?}
    HunchResult -->|No| ContinueInvestigation

    HunchResult -->|Yes| DesignTest[[isolated-testing skill:<br>one theory, one test]]:::gate
    DesignTest --> RunExperiment[Run designed experiment]

    RunExperiment --> FixAttempt{Fix succeeded?}
    JustFix --> FixAttempt

    FixAttempt -->|Yes| GoVerify([Proceed to<br>Phase 4 Verification]):::success
    FixAttempt -->|No| IncAttempts[Increment fix_attempts]
    IncAttempts --> ThreeCheck{fix_attempts >= 3?}
    ThreeCheck -->|No| Investigation
    ThreeCheck -->|Yes| ThreeFix([Trigger 3-Fix Rule<br>circuit breaker])

    classDef subagent fill:#4a9eff,stroke:#2d7cd6,color:#fff
    classDef gate fill:#ff6b6b,stroke:#d94f4f,color:#fff
    classDef success fill:#51cf66,stroke:#3da84e,color:#fff
```

---

## Phase 4: Verification

Mandatory verification after every fix claim. Stores root cause on success; loops back on failure.

```mermaid
flowchart TD
    subgraph Legend
        L1[Process]
        L2{Decision}
        L3[/"MCP Tool Call"/]:::subagent
        L4[[Quality Gate]]:::gate
        L5([Terminal]):::success
    end

    Start([Phase 4 Entry]) --> VerifyGate[[Verification is<br>NOT optional]]:::gate

    VerifyGate --> CheckSymptom[Original symptom<br>no longer occurs?]
    CheckSymptom --> CheckTests[Tests pass?]
    CheckTests --> CheckRegression[No new failures<br>introduced?]

    CheckRegression --> VerifyResult{All checks pass?}

    VerifyResult -->|Yes| StoreRoot[/"memory_store_memories:<br>root cause + fix + symptom"/]:::subagent
    StoreRoot --> WasRecurring{Was 3-fix rule<br>triggered?}
    WasRecurring -->|Yes| StoreAntipattern[/"memory_store_memories:<br>antipattern for component"/]:::subagent
    WasRecurring -->|No| Done
    StoreAntipattern --> Done([Bug resolved]):::success

    VerifyResult -->|No| ShowFailure[Show what failed]
    ShowFailure --> IncAttempts[Increment fix_attempts]
    IncAttempts --> ThreeCheck{fix_attempts >= 3?}
    ThreeCheck -->|No| ReturnDebug([Return to Phase 3:<br>continue investigation])
    ThreeCheck -->|Yes| ThreeFix([Trigger 3-Fix Rule<br>circuit breaker])

    classDef subagent fill:#4a9eff,stroke:#2d7cd6,color:#fff
    classDef gate fill:#ff6b6b,stroke:#d94f4f,color:#fff
    classDef success fill:#51cf66,stroke:#3da84e,color:#fff
```

---

## 3-Fix Rule (Circuit Breaker)

Triggered when fix_attempts reaches 3. Forces architectural reassessment.

```mermaid
flowchart TD
    subgraph Legend
        L1[Process]
        L2{Decision}
        L3[/"Skill Dispatch"/]:::subagent
        L4[[Quality Gate]]:::gate
        L5([Terminal]):::success
    end

    Trigger([3-Fix Rule Triggered:<br>fix_attempts >= 3]) --> Warning[[THREE_FIX_RULE_WARNING:<br>Tactical fixes cannot solve<br>architectural problems]]:::gate

    Warning --> MemCheck[/"memory_recall(query=<br>architecture issue component)"/]:::subagent
    MemCheck --> FractalExplore[/"fractal-thinking:<br>intensity=explore<br>Why does symptom persist?"/]:::subagent

    FractalExplore --> ArchSigns{Architectural<br>problem signs?<br>- Fix reveals issues elsewhere<br>- Massive refactoring needed<br>- New symptoms per fix<br>- Pattern fundamentally unsound}

    ArchSigns --> UserChoice{User choice?}

    UserChoice -->|"A: Architecture<br>review"| ArchReview([Conduct architecture<br>review with human])
    UserChoice -->|"B: Continue<br>(acknowledged risk)"| Reset[Reset fix_attempts = 0]
    UserChoice -->|"C: Escalate"| Escalate([Escalate to<br>human architect])
    UserChoice -->|"D: Spike ticket"| Spike([Create spike ticket])

    Reset --> ReturnPhase3([Return to Phase 3]):::success

    classDef subagent fill:#4a9eff,stroke:#2d7cd6,color:#fff
    classDef gate fill:#ff6b6b,stroke:#d94f4f,color:#fff
    classDef success fill:#51cf66,stroke:#3da84e,color:#fff
```

---

## CI Investigation Branch

Specialized branch for failures that only occur in CI environments.

```mermaid
flowchart TD
    subgraph Legend
        L1[Process]
        L2{Decision}
        L3[[Quality Gate]]:::gate
        L4([Terminal]):::success
    end

    Start([CI Investigation<br>Entry]) --> Classify{CI Symptom?}

    Classify -->|"Works locally,<br>fails CI"| EnvDiff[Environment Diff Protocol]
    Classify -->|"Flaky only<br>in CI"| Resource[Resource Analysis]
    Classify -->|"Cache-related<br>errors"| Cache[Cache Forensics]
    Classify -->|"Permission /<br>access errors"| Creds[Credential Audit]
    Classify -->|"Timeout<br>failures"| Perf[Performance Triage]
    Classify -->|"Dependency<br>resolution fails"| Deps[Dependency Forensics]

    EnvDiff --> CaptureCI[Capture CI environment<br>from logs/config]
    CaptureCI --> CompareLocal[Compare to local:<br>versions, env vars,<br>OS, architecture]
    CompareLocal --> IdentifyParity[Identify parity violations]

    Resource --> CheckConstraints[Check: memory limits,<br>CPU throttling, disk space,<br>network limits]

    Cache --> IdentifyKeys[Identify cache keys]
    IdentifyKeys --> CheckAge[Check cache age vs lockfile]
    CheckAge --> TestBypass[Test with cache disabled]

    Creds --> VerifySecrets[Verify secrets/credentials<br>are set in CI]

    Perf --> CheckLimits[Check runner resource limits]

    Deps --> CheckLockfile[Check lock file and<br>registry access]

    IdentifyParity --> Checklist
    CheckConstraints --> Checklist
    TestBypass --> Checklist
    VerifySecrets --> Checklist
    CheckLimits --> Checklist
    CheckLockfile --> Checklist

    Checklist[[CI-Specific Checklist:<br>10 verification items]]:::gate --> FixApplied{Fix identified?}

    FixApplied -->|Yes| ApplyFix[Fix in CI config or<br>add local repro instructions]
    ApplyFix --> DocRequirement[Document environment<br>requirement in README]
    DocRequirement --> GoVerify([Proceed to<br>Phase 4 Verification]):::success

    FixApplied -->|No| Escalate([Escalate: could not<br>reproduce CI conditions])

    classDef gate fill:#ff6b6b,stroke:#d94f4f,color:#fff
    classDef success fill:#51cf66,stroke:#3da84e,color:#fff
```

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
1. **Memory check:** Call `memory_recall(query="architecture issue [component]")` to check for documented systemic problems in this area.
2. **Fractal exploration:** Invoke `fractal-thinking` with intensity `explore` and seed: "Why does [symptom] persist after [N] fix attempts targeting [root causes]?" Invoke when stuck generating new hypotheses after 2+ disproven theories. Use synthesis to produce new hypothesis families.
3. Question architecture (not just implementation)
4. Discuss with human before more fixes
5. Consider refactoring vs. tactical fixes
6. Document the pattern issue

### 1.4 Memory Priming

Before selecting a debugging methodology, check for relevant stored memories:

1. If you received `<spellbook-memory>` context from recent file reads, incorporate it.
2. Otherwise, call `memory_recall(query="[symptom_type] [component_or_module]")` to surface prior root causes, antipatterns, and debugging outcomes for this area.
3. If prior root causes are found, check whether they apply to the current symptom before pursuing new hypotheses.

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

**Memory Persistence:** After confirming a fix, store the root cause for future sessions:
```
memory_store_memories(memories='{"memories": [{"content": "Root cause: [description]. Fix: [what was changed]. Symptom: [what was observed].", "memory_type": "fact", "tags": ["root-cause", "[component]", "[symptom_type]"], "citations": [{"file_path": "[fixed_file]", "line_range": "[lines]"}]}]}')
```
For recurring issues (3-fix-rule triggers), also store an antipattern:
```
memory_store_memories(memories='{"memories": [{"content": "Recurring issue in [component]: [pattern description]. Consider architectural review.", "memory_type": "antipattern", "tags": ["recurring", "[component]", "architecture"], "citations": [{"file_path": "[file]"}]}]}')
```

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

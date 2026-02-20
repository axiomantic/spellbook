# fact-checking

Use when reviewing code changes, auditing documentation accuracy, validating technical claims before merge, or user says "verify claims", "factcheck", "audit documentation", "validate comments", "are these claims accurate".

## Workflow Diagram

# Diagram: fact-checking

Multi-phase fact-checking workflow that extracts claims from code/docs, triages them by severity, verifies each claim with evidence, generates a report, and applies approved fixes. Uses subagent dispatch for extraction, verification, and reporting phases.

```mermaid
flowchart TD
    Start([Fact-Check Requested])
    P0[Phase 0: Configuration]
    AutoMode{Autonomous Mode?}
    EnableAll[Enable All Modes]
    ModeSelect[User Selects Modes]
    P1[Phase 1: Scope Selection]
    ScopeChoice{Scope?}
    Branch[Branch Changes]
    Uncommitted[Uncommitted Changes]
    FullRepo[Full Repository]
    P2["Phase 2-3: Extract & Triage"]
    ExtractCmd[/fact-check-extract/]
    P4["Phase 4-5: Verify & Verdict"]
    VerifyCmd[/fact-check-verify/]
    CheckDB{AgentDB Checked?}
    SkipVerify[Use Cached Finding]
    RunVerify[Run Verification]
    P6["Phase 6-7: Report & Learn"]
    ReportCmd[/fact-check-report/]
    P8[Phase 8: Fixes]
    HasFixes{Non-verified Claims?}
    PresentFix[Present Fix Plan]
    ApproveGate{User Approves Fix?}
    ApplyFix[Apply Fix]
    SkipFix[Skip Fix]
    MoreFixes{More Fixes?}
    ReVerify{Re-verify?}
    Complete([Fact-Check Complete])

    Start --> P0
    P0 --> AutoMode
    AutoMode -- "Yes" --> EnableAll
    AutoMode -- "No" --> ModeSelect
    EnableAll --> P1
    ModeSelect --> P1
    P1 --> ScopeChoice
    ScopeChoice -- "A" --> Branch
    ScopeChoice -- "B" --> Uncommitted
    ScopeChoice -- "C" --> FullRepo
    Branch --> P2
    Uncommitted --> P2
    FullRepo --> P2
    P2 --> ExtractCmd
    ExtractCmd --> P4
    P4 --> CheckDB
    CheckDB -- "Cached" --> SkipVerify
    CheckDB -- "Not cached" --> RunVerify
    SkipVerify --> VerifyCmd
    RunVerify --> VerifyCmd
    VerifyCmd --> P6
    P6 --> ReportCmd
    ReportCmd --> P8
    P8 --> HasFixes
    HasFixes -- "Yes" --> PresentFix
    HasFixes -- "No" --> Complete
    PresentFix --> ApproveGate
    ApproveGate -- "Approved" --> ApplyFix
    ApproveGate -- "Rejected" --> SkipFix
    ApplyFix --> MoreFixes
    SkipFix --> MoreFixes
    MoreFixes -- "Yes" --> PresentFix
    MoreFixes -- "No" --> ReVerify
    ReVerify -- "Yes" --> P4
    ReVerify -- "No" --> Complete

    style Start fill:#4CAF50,color:#fff
    style AutoMode fill:#FF9800,color:#fff
    style ScopeChoice fill:#FF9800,color:#fff
    style CheckDB fill:#FF9800,color:#fff
    style HasFixes fill:#FF9800,color:#fff
    style MoreFixes fill:#FF9800,color:#fff
    style ReVerify fill:#FF9800,color:#fff
    style ApproveGate fill:#f44336,color:#fff
    style ExtractCmd fill:#4CAF50,color:#fff
    style VerifyCmd fill:#4CAF50,color:#fff
    style ReportCmd fill:#4CAF50,color:#fff
    style P0 fill:#2196F3,color:#fff
    style P1 fill:#2196F3,color:#fff
    style P2 fill:#2196F3,color:#fff
    style P4 fill:#2196F3,color:#fff
    style P6 fill:#2196F3,color:#fff
    style P8 fill:#2196F3,color:#fff
    style EnableAll fill:#2196F3,color:#fff
    style ModeSelect fill:#2196F3,color:#fff
    style Branch fill:#2196F3,color:#fff
    style Uncommitted fill:#2196F3,color:#fff
    style FullRepo fill:#2196F3,color:#fff
    style SkipVerify fill:#2196F3,color:#fff
    style RunVerify fill:#2196F3,color:#fff
    style PresentFix fill:#2196F3,color:#fff
    style ApplyFix fill:#2196F3,color:#fff
    style SkipFix fill:#2196F3,color:#fff
    style Complete fill:#4CAF50,color:#fff
```

## Legend

| Color | Meaning |
|-------|---------|
| Green (#4CAF50) | Skill invocation |
| Blue (#2196F3) | Command/action |
| Orange (#FF9800) | Decision point |
| Red (#f44336) | Quality gate |

## Cross-Reference

| Node | Source Reference |
|------|----------------|
| Phase 0: Configuration | Lines 88-95: Configuration wizard and modes |
| Autonomous Mode? | Line 95: Autonomous mode detection |
| Phase 1: Scope Selection | Lines 97-105: Scope selection options |
| Phase 2-3: Extract & Triage | Lines 107-110: Subagent dispatch to fact-check-extract |
| Phase 4-5: Verify & Verdict | Lines 112-115: Subagent dispatch to fact-check-verify |
| AgentDB Checked? | Lines 19, 164-166: AgentDB deduplication |
| Phase 6-7: Report & Learn | Lines 117-120: Subagent dispatch to fact-check-report |
| Phase 8: Fixes | Lines 122-129: Fix approval flow |
| User Approves Fix? | Line 124: NEVER apply fixes without explicit per-fix approval |

## Skill Content

``````````markdown
<ROLE>
Scientific Skeptic + ISO 9001 Auditor. Claims are hypotheses. Verdicts require data.
Professional reputation depends on evidence-backed conclusions. Are you sure?
</ROLE>

## Invariant Principles

1. **Claims are hypotheses** - Every claim requires empirical evidence before verdict
2. **Evidence before verdict** - No verdict without traceable, citable proof
3. **User controls scope** - User selects scope and approves all fixes
4. **Deduplicate findings** - Check AgentDB before verifying; store after
5. **Learn from trajectories** - Store verification trajectories in ReasoningBank

<ARH_INTEGRATION>
Uses Adaptive Response Handler for user responses during triage:
- RESEARCH_REQUEST ("research", "check", "verify") -> Dispatch research subagent
- UNKNOWN ("don't know", "not sure") -> Dispatch analysis subagent
- CLARIFICATION (ends with ?) -> Answer, then re-ask
- SKIP ("skip", "move on") -> Proceed to next item
</ARH_INTEGRATION>

<analysis>
Before ANY action:
- Current phase? (config/scope/extract/triage/verify/report/learn/fix)
- What EXACTLY is claimed?
- What proves TRUE? What proves FALSE?
- AgentDB checked for existing findings?
- Appropriate verification depth?
</analysis>

## Inputs/Outputs

| Input | Required | Description |
|-------|----------|-------------|
| `scope` | Yes | branch changes, uncommitted, or full repo |
| `modes` | No | Missing Facts, Extraneous Info, Clarity (default: all) |
| `autonomous` | No | Skip prompts, use defaults |

| Output | Type | Description |
|--------|------|-------------|
| `verification_report` | Inline | Summary, findings, bibliography |
| `implementation_plan` | Inline | Fixes for refuted/stale claims |
| `glossary` | Inline | Key facts (Clarity Mode) |
| `state_checkpoint` | File | `.fact-checking/state.json` |

---

## Shared Data Structures

### Verdict Table

| Verdict | Meaning | Evidence Required |
|---------|---------|-------------------|
| Verified | Claim is accurate | test output, code trace, docs, benchmark |
| Refuted | Claim is false | failing test, contradicting code |
| Incomplete | True but missing context | base verified + missing elements |
| Inconclusive | Cannot determine | document attempts, why insufficient |
| Ambiguous | Wording unclear | multiple interpretations explained |
| Misleading | Technically true, implies falsehood | what reader assumes vs reality |
| Jargon-heavy | Too technical for audience | unexplained terms, accessible version |
| Stale | Was true, no longer applies | when true, what changed, current state |
| Extraneous | Unnecessary/redundant | value analysis shows no added info |

### Bibliography Formats

| Type | Format |
|------|--------|
| Code trace | `file:lines - finding` |
| Test | `command - result` |
| Web source | `Title - URL - "excerpt"` |
| Git history | `commit/issue - finding` |
| Documentation | `Docs: source section - URL` |
| Benchmark | `Benchmark: method - results` |
| Paper/RFC | `Citation - section - URL` |

---

## Workflow

### Phase 0: Configuration

Present three optional modes (default: all enabled):
- **Missing Facts Detection** - gaps where claims lack critical context
- **Extraneous Info Detection** - redundant/LLM-style over-commenting
- **Clarity Mode** - generate glossaries for AI config files

Autonomous mode detected ("Mode: AUTONOMOUS")? Enable all automatically.

### Phase 1: Scope Selection

<RULE>Ask scope BEFORE extraction. No exceptions.</RULE>

| Option | Method |
|--------|--------|
| A. Branch changes | `git diff $(git merge-base HEAD main)...HEAD --name-only` + unstaged |
| B. Uncommitted | `git diff --name-only` + `git diff --cached --name-only` |
| C. Full repo | All code/doc patterns |

### Phases 2-3: Claim Extraction and Triage

**Subagent dispatch:** Invoke `fact-check-extract` command.
**Context to provide:** File list from Phase 1, scope selection, enabled modes.

### Phases 4-5: Parallel Verification and Verdicts

**Subagent dispatch:** Invoke `fact-check-verify` command.
**Context to provide:** Triaged claims list from Phases 2-3, depth assignments.

### Phases 6-7: Report and Learning

**Subagent dispatch:** Invoke `fact-check-report` command.
**Context to provide:** All verdicts and evidence from Phases 4-5, enabled modes (for Clarity Mode), bibliography entries.

### Phase 8: Fixes

<RULE>NEVER apply fixes without explicit per-fix user approval.</RULE>

1. Present implementation plan for non-verified claims
2. Show proposed change, ask approval
3. Apply approved fixes
4. Offer re-verification

---

## Interruption Handling

Checkpoint to `.fact-checking/state.json` after each claim:
```json
{
  "scope": "branch",
  "claims": [...],
  "completed": [0, 1, 2],
  "pending": [3, 4, 5],
  "findings": {...},
  "bibliography": [...]
}
```

Offer resume on next invocation.

---

<FORBIDDEN>
**Verdicts Without Evidence**
- "it looks correct" or "code seems fine" without trace
- Every verdict requires concrete, citable evidence

**Skipping Claims**
- No claim is "trivial" - verify individually
- No batching similar claims without individual verification

**Applying Fixes Without Approval**
- No auto-correcting comments
- Each fix requires explicit user approval

**Ignoring AgentDB**
- ALWAYS check before verifying
- ALWAYS store findings after verification
</FORBIDDEN>

---

<EXAMPLE>
**User**: "Factcheck my current branch"

**Phase 1**: Scope selection -> User selects "A. Branch changes"

**Phase 2**: Extract claims -> Found 8 claims in 5 files

**Phase 3**: Triage display with depths:
```
### Security (2 claims)
1. [MEDIUM] src/auth/password.ts:34 - "passwords hashed with bcrypt"
2. [DEEP] src/auth/session.ts:78 - "session tokens cryptographically random"
...
```

**Phase 4**: Verification (showing claim 1):
- Read src/auth/password.ts:34-60
- Found: `import { hash } from 'bcryptjs'`
- Found: `await hash(password, 12)`
- Confirmed cost factor 12 meets OWASP

Verdict: **VERIFIED**
Evidence: bcryptjs.hash() with cost factor 12 confirmed
Sources: [1] Code trace, [2] OWASP Password Storage

**Phase 6**: Report excerpt:
```markdown
# Fact-Checking Report
**Scope:** Branch feature/auth-refactor (12 commits)
**Verified:** 5 | **Refuted:** 1 | **Stale:** 1 | **Inconclusive:** 1

## Bibliography
[1] Code trace: src/auth/password.ts:34-60 - bcryptjs hash() call
[2] OWASP Password Storage - https://cheatsheetseries.owasp.org/...

## Implementation Plan
1. [ ] src/cache/store.ts:23 - TTL is 60s not 300s, update comment
```
</EXAMPLE>

---

<reflection>
Before finalizing:
- [ ] Configuration wizard completed (or autonomous mode)
- [ ] Scope explicitly selected by user
- [ ] ALL claims presented for triage before verification
- [ ] Each verdict has CONCRETE evidence
- [ ] AgentDB checked before, updated after
- [ ] Bibliography cites all sources
- [ ] Trajectories stored in ReasoningBank
- [ ] Fixes await explicit per-fix approval

If ANY unchecked: STOP and fix.
</reflection>

<FINAL_EMPHASIS>
You are a Scientific Skeptic with ISO 9001 Auditor rigor. Every claim is a hypothesis.
Every verdict requires evidence. NEVER issue verdicts without concrete proof.
NEVER skip triage. NEVER apply fixes without approval. ALWAYS use AgentDB.
This is very important to my career. Are you sure?
</FINAL_EMPHASIS>
``````````

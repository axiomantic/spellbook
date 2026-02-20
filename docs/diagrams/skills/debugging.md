<!-- diagram-meta: {"source": "skills/debugging/SKILL.md", "source_hash": "sha256:9142c384eaa292f6cedd73967ef01ae9e080a818e6e963ff05f8cec3de25b1a3", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: debugging

Multi-phase debugging workflow with mandatory prerequisites, triage-based methodology selection, and a 3-fix rule circuit breaker. Supports scientific debugging, systematic debugging, and CI-specific investigation branches.

```mermaid
flowchart TD
    Start([Start]) --> P0[Phase 0: Prerequisites]
    P0 --> P0_1[Establish Clean Baseline]
    P0_1 --> P0_2[Prove Bug Exists]
    P0_2 --> P0_2_G{Bug Reproduced?}
    P0_2_G -->|No| P0_NR[Refine Steps or Abort]
    P0_NR --> P0_2
    P0_2_G -->|Yes| P0_3[Track Code State]
    P0_3 --> P1[Phase 1: Triage]

    P1 --> P1_1[Gather Context]
    P1_1 --> P1_2{Simple Bug?}
    P1_2 -->|Yes| DirectFix[Apply Direct Fix]
    DirectFix --> Verify

    P1_2 -->|No| P1_3{3+ Prior Attempts?}
    P1_3 -->|Yes| ThreeFix{3-Fix Rule Warning}
    ThreeFix -->|Architecture Review| ArchReview[Invoke Architecture Review]
    ThreeFix -->|Continue| P2
    ThreeFix -->|Escalate| Escalate[Escalate to Human]
    ArchReview --> End
    Escalate --> End

    P1_3 -->|No| P2[Phase 2: Select Methodology]

    P2 --> P2_D{Symptom Type?}
    P2_D -->|Intermittent/Unexpected| SciDebug[/scientific-debugging/]
    P2_D -->|Clear Error/Test Failure| SysDebug[/systematic-debugging/]
    P2_D -->|CI-Only Failure| CI[CI Investigation Branch]
    P2_D -->|Test Quality Issue| FixTests[/fixing-tests/]

    CI --> CI_1{CI Symptom?}
    CI_1 -->|Environment| CI_ENV[Environment Diff Protocol]
    CI_1 -->|Cache| CI_CACHE[Cache Forensics]
    CI_1 -->|Resource| CI_RES[Resource Analysis]
    CI_1 -->|Credentials| CI_CRED[Credential Audit]
    CI_ENV --> CI_FIX[Fix CI Config]
    CI_CACHE --> CI_FIX
    CI_RES --> CI_FIX
    CI_CRED --> CI_FIX
    CI_FIX --> Verify

    SciDebug --> HunchGate{Hunch Detected?}
    SysDebug --> HunchGate
    HunchGate -->|Yes| VerifyHunch[/verifying-hunches/]
    VerifyHunch --> IsoTest[/isolated-testing/]
    HunchGate -->|No| IsoTest
    IsoTest --> AttemptFix[Apply Fix]
    AttemptFix --> FixCheck{Fix Succeeded?}
    FixCheck -->|Yes| Verify
    FixCheck -->|No| IncAttempts[Increment fix_attempts]
    IncAttempts --> AttemptGate{Attempts >= 3?}
    AttemptGate -->|Yes| ThreeFix
    AttemptGate -->|No| P2

    Verify[[Phase 4: /verify]]
    Verify --> VerifyGate{Verification Passed?}
    VerifyGate -->|Yes| SelfCheck[Self-Check Checklist]
    SelfCheck --> End([End])
    VerifyGate -->|No| IncAttempts

    FixTests --> End

    style Start fill:#4CAF50,color:#fff
    style End fill:#4CAF50,color:#fff
    style P0 fill:#2196F3,color:#fff
    style P0_1 fill:#2196F3,color:#fff
    style P0_2 fill:#2196F3,color:#fff
    style P0_3 fill:#2196F3,color:#fff
    style P1 fill:#2196F3,color:#fff
    style P1_1 fill:#2196F3,color:#fff
    style DirectFix fill:#2196F3,color:#fff
    style P2 fill:#2196F3,color:#fff
    style AttemptFix fill:#2196F3,color:#fff
    style IncAttempts fill:#2196F3,color:#fff
    style CI fill:#2196F3,color:#fff
    style CI_ENV fill:#2196F3,color:#fff
    style CI_CACHE fill:#2196F3,color:#fff
    style CI_RES fill:#2196F3,color:#fff
    style CI_CRED fill:#2196F3,color:#fff
    style CI_FIX fill:#2196F3,color:#fff
    style P0_NR fill:#2196F3,color:#fff
    style SelfCheck fill:#2196F3,color:#fff
    style P1_2 fill:#FF9800,color:#fff
    style P1_3 fill:#FF9800,color:#fff
    style P2_D fill:#FF9800,color:#fff
    style CI_1 fill:#FF9800,color:#fff
    style ThreeFix fill:#FF9800,color:#fff
    style HunchGate fill:#FF9800,color:#fff
    style FixCheck fill:#FF9800,color:#fff
    style AttemptGate fill:#FF9800,color:#fff
    style P0_2_G fill:#f44336,color:#fff
    style Verify fill:#f44336,color:#fff
    style VerifyGate fill:#f44336,color:#fff
    style SciDebug fill:#4CAF50,color:#fff
    style SysDebug fill:#4CAF50,color:#fff
    style FixTests fill:#4CAF50,color:#fff
    style VerifyHunch fill:#4CAF50,color:#fff
    style IsoTest fill:#4CAF50,color:#fff
    style ArchReview fill:#4CAF50,color:#fff
    style Escalate fill:#2196F3,color:#fff
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
| Phase 0: Prerequisites | Phase 0 (lines 47-148) |
| Establish Clean Baseline | Section 0.1 (lines 55-83) |
| Prove Bug Exists | Section 0.2 (lines 85-128) |
| Bug Reproduced? | Gate at line 88: "HARD GATE: You cannot investigate or fix a bug you haven't reproduced" |
| Track Code State | Section 0.3 (lines 130-148) |
| Phase 1: Triage | Phase 1 (lines 150-273) |
| Gather Context | Section 1.1 (lines 162-199) |
| Simple Bug? | Section 1.2 (lines 201-223) |
| 3+ Prior Attempts? | Section 1.3 (lines 225-249) |
| 3-Fix Rule Warning | 3-Fix Rule (lines 416-430) |
| Phase 2: Select Methodology | Phase 2 (lines 251-273) |
| /scientific-debugging/ | Phase 3 invocation (line 278) |
| /systematic-debugging/ | Phase 3 invocation (line 279) |
| /fixing-tests/ | Phase 2 alternative (lines 262-271) |
| CI Investigation Branch | CI Investigation Branch (lines 329-393) |
| /verifying-hunches/ | Hunch Interception (lines 281-283) |
| /isolated-testing/ | Isolated Testing Mandate (lines 285-298) |
| Phase 4: /verify | Phase 4: Verification (lines 394-412) |
| Verification Passed? | Gate at line 396: "Auto-invoke /verify after EVERY fix claim" |
| Self-Check Checklist | Self-Check (lines 464-482) |

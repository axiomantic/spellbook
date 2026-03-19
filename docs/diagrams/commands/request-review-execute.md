<!-- diagram-meta: {"source": "commands/request-review-execute.md","source_hash": "sha256:98380e97d3e40a193472d6768a9c1b8cc191acbece16765ab42d82ce8353305a","generator": "stamp"} -->
# Diagram: request-review-execute

Dispatch, triage, execute, and gate phases for code review. Invokes code-reviewer agent, triages findings by severity, applies fixes, and enforces quality gate with three possible verdicts.

## Overview: Phases 3-6 Pipeline

```mermaid
flowchart TD
    subgraph Legend
        L1[Process]
        L2{Decision}
        L3([Terminal])
        L4[Subagent Dispatch]:::subagent
        L5{Quality Gate}:::gate
        L6([Success]):::success
    end

    Start([Phase 2 Context]) --> P3[Phase 3: DISPATCH]:::subagent
    P3 --> P4[Phase 4: TRIAGE]
    P4 --> P5[Phase 5: EXECUTE]
    P5 --> P6{Phase 6: GATE}:::gate
    P6 -->|APPROVED| Approved([APPROVED]):::success
    P6 -->|APPROVED WITH FOLLOW-UP| FollowUp([APPROVED WITH FOLLOW-UP]):::success
    P6 -->|BLOCKED| Blocked([BLOCKED]):::blocked
    P6 -->|Re-review needed| P3

    classDef subagent fill:#4a9eff,stroke:#333,color:#fff
    classDef gate fill:#ff6b6b,stroke:#333,color:#fff
    classDef success fill:#51cf66,stroke:#333,color:#fff
    classDef blocked fill:#ff6b6b,stroke:#333,color:#fff
```

## Phase 3: DISPATCH - Review Agent Invocation

```mermaid
flowchart TD
    subgraph Legend
        L1[Process]
        L2{Decision}
        L4[Subagent Dispatch]:::subagent
        L5{Quality Gate}:::gate
        L6([Success]):::success
    end

    In([Phase 2 Context]) --> Invoke[Invoke code-reviewer agent<br>with files, plan, git range,<br>description]:::subagent
    Invoke --> Await[Await findings]
    Await --> Validate{Each finding has<br>location AND evidence?}:::gate
    Validate -->|Yes| Keep[Keep finding]
    Validate -->|No| Discard[Discard finding]
    Keep --> Done{All findings<br>processed?}
    Discard --> Done
    Done -->|No| Validate
    Done -->|Yes| Exit([Valid findings received]):::success

    classDef subagent fill:#4a9eff,stroke:#333,color:#fff
    classDef gate fill:#ff6b6b,stroke:#333,color:#fff
    classDef success fill:#51cf66,stroke:#333,color:#fff
```

## Phase 4: TRIAGE - Categorize and Prioritize

```mermaid
flowchart TD
    subgraph Legend
        L1[Process]
        L2{Decision}
        L3([Success]):::success
    end

    In([Phase 3 findings]) --> Sort[Sort by severity<br>Critical > High > Medium > Low]
    Sort --> Group[Group by file<br>for efficient fixing]
    Group --> Classify{Classify each finding}
    Classify -->|"Single-site, &lt;30 min"| Quick[Quick win]
    Classify -->|Multi-file or architectural| Substantial[Substantial fix]
    Quick --> Clarify{Needs clarification<br>before fixing?}
    Substantial --> Clarify
    Clarify -->|Yes| Flag[Flag for clarification]
    Clarify -->|No| Ready[Ready to fix]
    Flag --> More{More findings?}
    Ready --> More
    More -->|Yes| Classify
    More -->|No| Exit([All findings classified<br>and prioritized]):::success

    classDef success fill:#51cf66,stroke:#333,color:#fff
```

## Phase 5: EXECUTE - Apply Fixes by Severity

```mermaid
flowchart TD
    subgraph Legend
        L1[Process]
        L2{Decision}
        L3{Quality Gate}:::gate
        L4([Forbidden]):::blocked
        L5([Success]):::success
    end

    In([Phase 4 triaged findings]) --> Critical{Critical findings<br>exist?}
    Critical -->|Yes| FixCritical[Fix Critical findings<br>NO deferral permitted]:::gate
    Critical -->|No| High

    FixCritical --> High{High findings<br>exist?}
    High -->|Yes| FixHigh[Fix High findings<br>blocking threshold]
    High -->|No| MedLow

    FixHigh --> MedLow{Medium/Low<br>findings exist?}
    MedLow -->|Yes| CanFix{Can fix now?}
    MedLow -->|No| Exit

    CanFix -->|Yes| FixMedLow[Fix in severity order]
    CanFix -->|No, defer| DeferSev{Severity?}

    DeferSev -->|Critical| FORBIDDEN([FORBIDDEN:<br>Cannot defer Critical]):::blocked
    DeferSev -->|High| DocDefer[Document deferral:<br>1. Finding ID + summary<br>2. Reason for deferral<br>3. Follow-up tracking<br>4. Risk acknowledgment]
    DeferSev -->|Medium/Low| SimplDefer[Document rationale<br>for deferral]

    FixMedLow --> Exit
    DocDefer --> Exit
    SimplDefer --> Exit

    Exit([Blocking findings<br>addressed or escalated]):::success

    classDef gate fill:#ff6b6b,stroke:#333,color:#fff
    classDef success fill:#51cf66,stroke:#333,color:#fff
    classDef blocked fill:#ff6b6b,stroke:#333,color:#fff
```

## Phase 6: GATE - Verdict Decision

```mermaid
flowchart TD
    subgraph Legend
        L1[Process]
        L2{Quality Gate}:::gate
        L3([Success]):::success
        L4[Return to Phase 3]:::subagent
    end

    In([Phase 5 fix status]) --> CheckUnresolved{Unresolved Critical<br>or High findings?}:::gate

    CheckUnresolved -->|Critical remain| BLOCKED([BLOCKED]):::blocked
    CheckUnresolved -->|High remain| BLOCKED
    CheckUnresolved -->|None remain| ReReview{Re-review<br>triggered?}

    ReReview -->|Yes| BackToDispatch([Return to Phase 3:<br>DISPATCH]):::subagent
    ReReview -->|No| Deferred{Deferred items<br>with follow-up?}

    Deferred -->|Yes| ApproveFollowUp([APPROVED<br>WITH FOLLOW-UP]):::success
    Deferred -->|No| Approve([APPROVED]):::success

    subgraph "Re-Review Triggers (MUST re-review)"
        direction TB
        T1[Critical finding was fixed]
        T2[3+ High findings fixed]
        T3[Fix adds >100 lines new code]
        T4[Fix modifies files outside<br>original review scope]
    end

    subgraph "Skip Re-Review (MAY skip)"
        direction TB
        S1[Only Low/Nit/Medium addressed]
        S2["Fix is mechanical (rename,<br>formatting, typo)"]
    end

    classDef gate fill:#ff6b6b,stroke:#333,color:#fff
    classDef success fill:#51cf66,stroke:#333,color:#fff
    classDef blocked fill:#ff6b6b,stroke:#333,color:#fff
    classDef subagent fill:#4a9eff,stroke:#333,color:#fff
```

## Cross-Reference Table

| Overview Node | Detail Diagram | Key Logic |
|---|---|---|
| Phase 3: DISPATCH | Phase 3 diagram | Invoke code-reviewer agent, validate finding fields (location + evidence required) |
| Phase 4: TRIAGE | Phase 4 diagram | Sort by severity, group by file, classify quick-win vs substantial, flag clarifications |
| Phase 5: EXECUTE | Phase 5 diagram | Fix by severity order, Critical cannot be deferred, High deferral requires full documentation |
| Phase 6: GATE | Phase 6 diagram | Verdict based on unresolved findings, re-review triggers, three verdicts: APPROVED / APPROVED WITH FOLLOW-UP / BLOCKED |

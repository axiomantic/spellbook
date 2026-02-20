<!-- diagram-meta: {"source": "commands/feature-discover.md", "source_hash": "sha256:bd3cd9316c69ec4b4a86edc188604efbf6f6e153656a81e30b0f213fc95c0da7", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: feature-discover

Phase 1.5 of implementing-features: Informed discovery using research findings, disambiguation, 7-category question wizard with ARH pattern, understanding document creation, and devil's advocate review.

```mermaid
flowchart TD
    Start([Phase 1.5 Start])
    PrereqCheck{Prerequisites met?}
    PrereqFail([STOP: Return to Phase 1])

    DisambSession[Disambiguation session]
    PresentAmb[Present ambiguity with context]
    ARHDisamb{Response type?}
    DirectAnswer[Accept answer]
    ResearchReq[Dispatch research subagent]
    Unknown[Dispatch subagent, rephrase]
    Clarify[Rephrase with context]
    Skip[Mark out-of-scope]
    AllResolved{All ambiguities resolved?}

    GenQuestions[Generate 7-category questions]
    Cat1[Category 1: Architecture]
    Cat2[Category 2: Scope]
    Cat3[Category 3: Integration]
    Cat4[Category 4: Failure modes]
    Cat5[Category 5: Success criteria]
    Cat6[Category 6: Vocabulary]
    Cat7[Category 7: Assumptions]

    BuildGlossary[Build glossary]
    PersistChoice{Persist glossary?}
    PersistClaude[Append to CLAUDE.md]
    SessionOnly[Keep in session]

    SynthContext[Synthesize design_context]
    RunValidation[Run 11 validations]
    CompletenessGate{Score = 100%?}
    FixGap[Return for missing items]

    CreateDoc[Create understanding doc]
    UserApprove{User approves?}
    ReviseDoc[Revise document]

    DACheck{Devil's advocate available?}
    DAUnavailable[Handle unavailability]
    DispatchDA[Dispatch devil's advocate]
    PresentCritique[Present critique]
    HandleCritique{User response?}
    AddressIssues[Address critical issues]
    DocLimits[Document as limitations]
    ReviseScope[Revise scope]
    AcceptRisks[Proceed to design]

    Phase15Done([Phase 1.5 Complete])

    Start --> PrereqCheck
    PrereqCheck -->|No| PrereqFail
    PrereqCheck -->|Yes| DisambSession

    DisambSession --> PresentAmb
    PresentAmb --> ARHDisamb
    ARHDisamb -->|Direct| DirectAnswer
    ARHDisamb -->|Research| ResearchReq
    ARHDisamb -->|Unknown| Unknown
    ARHDisamb -->|Clarify| Clarify
    ARHDisamb -->|Skip| Skip
    DirectAnswer --> AllResolved
    ResearchReq --> PresentAmb
    Unknown --> PresentAmb
    Clarify --> PresentAmb
    Skip --> AllResolved
    AllResolved -->|No| PresentAmb
    AllResolved -->|Yes| GenQuestions

    GenQuestions --> Cat1
    Cat1 --> Cat2
    Cat2 --> Cat3
    Cat3 --> Cat4
    Cat4 --> Cat5
    Cat5 --> Cat6
    Cat6 --> Cat7

    Cat7 --> BuildGlossary
    BuildGlossary --> PersistChoice
    PersistChoice -->|Persist| PersistClaude
    PersistChoice -->|Session| SessionOnly
    PersistClaude --> SynthContext
    SessionOnly --> SynthContext

    SynthContext --> RunValidation
    RunValidation --> CompletenessGate
    CompletenessGate -->|No| FixGap
    FixGap --> RunValidation
    CompletenessGate -->|Yes| CreateDoc

    CreateDoc --> UserApprove
    UserApprove -->|No| ReviseDoc
    ReviseDoc --> UserApprove
    UserApprove -->|Yes| DACheck

    DACheck -->|No| DAUnavailable
    DAUnavailable --> Phase15Done
    DACheck -->|Yes| DispatchDA
    DispatchDA --> PresentCritique
    PresentCritique --> HandleCritique
    HandleCritique -->|Address| AddressIssues
    AddressIssues --> DisambSession
    HandleCritique -->|Document| DocLimits
    DocLimits --> Phase15Done
    HandleCritique -->|Revise| ReviseScope
    ReviseScope --> Phase15Done
    HandleCritique -->|Accept| AcceptRisks
    AcceptRisks --> Phase15Done

    style Start fill:#2196F3,color:#fff
    style Phase15Done fill:#2196F3,color:#fff
    style PrereqFail fill:#2196F3,color:#fff
    style DispatchDA fill:#4CAF50,color:#fff
    style ResearchReq fill:#4CAF50,color:#fff
    style PrereqCheck fill:#FF9800,color:#fff
    style ARHDisamb fill:#FF9800,color:#fff
    style AllResolved fill:#FF9800,color:#fff
    style PersistChoice fill:#FF9800,color:#fff
    style UserApprove fill:#FF9800,color:#fff
    style DACheck fill:#FF9800,color:#fff
    style HandleCritique fill:#FF9800,color:#fff
    style CompletenessGate fill:#f44336,color:#fff
```

## Legend

| Color | Meaning |
|-------|---------|
| Green (#4CAF50) | Skill invocation |
| Blue (#2196F3) | Command/action |
| Orange (#FF9800) | Decision point |
| Red (#f44336) | Quality gate |

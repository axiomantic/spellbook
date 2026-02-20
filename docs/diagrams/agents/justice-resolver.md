<!-- diagram-meta: {"source": "agents/justice-resolver.md", "source_hash": "sha256:ce8fa3062f227d427b5471626abee06ee85847e59184f478c1136f760e09cc4b", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: justice-resolver

Conflict synthesis agent that resolves tension between code (thesis) and critique (antithesis) into refined solutions (synthesis). Weighs both positions with equal honor.

```mermaid
flowchart TD
    Start([Start: Code + Critique\nReceived])
    Invoke[/Honor-Bound Invocation/]

    CritiqueLoop["For Each\nCritique Point"]
    StateCritique["State Critique\nExactly as Written"]
    IdentifyCode["Identify Target\nCode Section"]
    UnderstandWhy["Understand WHY\nIt's a Problem"]

    ValidityCheck{"Critique\nCorrect?"}
    PartiallyCorrect["Partially Correct:\nNote Valid Parts"]
    ContextuallyWrong["Contextually Wrong:\nDocument Reason"]
    FullyCorrect["Fully Correct:\nProceed to Fix"]

    InternalDebate[/"Internal Debate:\nChariot vs Hermit"/]
    ChariotPos["Chariot Position:\n'I Built This Because...'"]
    HermitPos["Hermit Position:\n'This Breaks Because...'"]
    FindSynthesis["Find: 'Both Right\nWhen We Consider...'"]

    StateResolution["State Resolution\nApproach"]
    WriteRefined["Write Refined\nCode"]

    IntentGate{"Original Intent\nPreserved?"}
    RestoreIntent["Restore Lost\nFunctionality"]

    CritiqueGate{"Critique Point\nAddressed?"}
    ReviseSynthesis["Revise Synthesis\nApproach"]

    NewIssueGate{"New Issues\nIntroduced?"}
    FixNewIssues["Fix Regression\nWithout Churn"]

    MoreCritiques{"More Critique\nPoints?"}

    AllAddressedGate{"All Points Have\nExplicit Resolution?"}
    AddressRemaining["Address Remaining\nPoints"]

    TestGate{"Original Tests\nStill Pass?"}
    FixTests["Fix Without\nBreaking Original"]

    BetterGate{"Genuinely Better,\nNot Just Different?"}
    Rethink["Rethink Approach\nEntirely"]

    GenResolve["Generate RESOLVE\nSpeech Act"]
    ResolutionTable["Output Resolution\nTable"]
    Verification["Output Verification\nChecklist"]

    Done([End: Matter\nSettled])

    Start --> Invoke
    Invoke --> CritiqueLoop
    CritiqueLoop --> StateCritique
    StateCritique --> IdentifyCode
    IdentifyCode --> UnderstandWhy

    UnderstandWhy --> ValidityCheck
    ValidityCheck -->|Partially| PartiallyCorrect
    ValidityCheck -->|Wrong Context| ContextuallyWrong
    ValidityCheck -->|Fully| FullyCorrect
    PartiallyCorrect --> InternalDebate
    ContextuallyWrong --> InternalDebate
    FullyCorrect --> InternalDebate

    InternalDebate --> ChariotPos
    ChariotPos --> HermitPos
    HermitPos --> FindSynthesis

    FindSynthesis --> StateResolution
    StateResolution --> WriteRefined

    WriteRefined --> IntentGate
    IntentGate -->|Lost| RestoreIntent
    RestoreIntent --> IntentGate
    IntentGate -->|Preserved| CritiqueGate

    CritiqueGate -->|Not Addressed| ReviseSynthesis
    ReviseSynthesis --> WriteRefined
    CritiqueGate -->|Addressed| NewIssueGate

    NewIssueGate -->|Yes| FixNewIssues
    FixNewIssues --> NewIssueGate
    NewIssueGate -->|No| MoreCritiques

    MoreCritiques -->|Yes| CritiqueLoop
    MoreCritiques -->|No| AllAddressedGate

    AllAddressedGate -->|No| AddressRemaining
    AddressRemaining --> CritiqueLoop
    AllAddressedGate -->|Yes| TestGate

    TestGate -->|Fail| FixTests
    FixTests --> TestGate
    TestGate -->|Pass| BetterGate

    BetterGate -->|No| Rethink
    Rethink --> StateResolution
    BetterGate -->|Yes| GenResolve

    GenResolve --> ResolutionTable
    ResolutionTable --> Verification
    Verification --> Done

    style Start fill:#4CAF50,color:#fff
    style Done fill:#4CAF50,color:#fff
    style Invoke fill:#4CAF50,color:#fff
    style InternalDebate fill:#4CAF50,color:#fff
    style CritiqueLoop fill:#2196F3,color:#fff
    style StateCritique fill:#2196F3,color:#fff
    style IdentifyCode fill:#2196F3,color:#fff
    style UnderstandWhy fill:#2196F3,color:#fff
    style PartiallyCorrect fill:#2196F3,color:#fff
    style ContextuallyWrong fill:#2196F3,color:#fff
    style FullyCorrect fill:#2196F3,color:#fff
    style ChariotPos fill:#2196F3,color:#fff
    style HermitPos fill:#2196F3,color:#fff
    style FindSynthesis fill:#2196F3,color:#fff
    style StateResolution fill:#2196F3,color:#fff
    style WriteRefined fill:#2196F3,color:#fff
    style RestoreIntent fill:#2196F3,color:#fff
    style ReviseSynthesis fill:#2196F3,color:#fff
    style FixNewIssues fill:#2196F3,color:#fff
    style AddressRemaining fill:#2196F3,color:#fff
    style FixTests fill:#2196F3,color:#fff
    style Rethink fill:#2196F3,color:#fff
    style GenResolve fill:#2196F3,color:#fff
    style ResolutionTable fill:#2196F3,color:#fff
    style Verification fill:#2196F3,color:#fff
    style ValidityCheck fill:#FF9800,color:#fff
    style MoreCritiques fill:#FF9800,color:#fff
    style IntentGate fill:#f44336,color:#fff
    style CritiqueGate fill:#f44336,color:#fff
    style NewIssueGate fill:#f44336,color:#fff
    style AllAddressedGate fill:#f44336,color:#fff
    style TestGate fill:#f44336,color:#fff
    style BetterGate fill:#f44336,color:#fff
```

## Legend

| Color | Meaning |
|-------|---------|
| Green (#4CAF50) | Skill invocation / start-end |
| Blue (#2196F3) | Command/action |
| Orange (#FF9800) | Decision point |
| Red (#f44336) | Quality gate |

## Cross-Reference

| Node | Source Reference |
|------|----------------|
| Honor-Bound Invocation | Lines 13-14: Honor pledge before resolution |
| State Critique Exactly as Written | Lines 53: Analysis step 1 |
| Identify Target Code Section | Lines 54: Analysis step 2 |
| Understand WHY It's a Problem | Lines 55: Analysis step 3 |
| Critique Correct? | Lines 56: Analysis step 4 - validity assessment |
| Internal Debate | Lines 60-63: Dialogue phase - Chariot vs Hermit |
| Chariot Position | Lines 62: "I built this because..." |
| Hermit Position | Lines 63: "This breaks because..." |
| Find Synthesis | Lines 64: "Both are right when we consider..." |
| State Resolution Approach | Lines 68: Synthesis step 1 |
| Write Refined Code | Lines 69: Synthesis step 2 |
| Original Intent Preserved? | Lines 70: Synthesis step 3 |
| Critique Point Addressed? | Lines 71: Synthesis step 4 |
| New Issues Introduced? | Lines 72: Synthesis step 5 |
| All Points Have Explicit Resolution? | Lines 77: Reflection check 1 |
| Original Tests Still Pass? | Lines 78: Reflection check 2 |
| Genuinely Better, Not Just Different? | Lines 80: Reflection check 4 |
| Generate RESOLVE Speech Act | Lines 86-106: RESOLVE format output |

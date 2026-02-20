<!-- diagram-meta: {"source": "agents/lovers-integrator.md", "source_hash": "sha256:d413aa470c13cf2d9b3d1deff7e5624a031c81745adbe10412f03e89019852b8", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: lovers-integrator

Integration harmony agent that reviews connections between modules. Ensures APIs speak the same language, data contracts align, and the whole exceeds the sum of its parts.

```mermaid
flowchart TD
    Start([Start: Integration\nReview Requested])
    Invoke[/Honor-Bound Invocation/]

    InterfaceLoop["For Each Interface"]
    IdentifyCaller["Identify Caller\nand Callee"]
    MapData["Map Data Crossing\nBoundary"]

    TypeMatch{"Types Match\nExactly?"}
    FlagTypeMismatch["Flag: Type\nMismatch"]

    ErrorConsistent{"Error Handling\nConsistent Both Sides?"}
    FlagErrorAmnesia["Flag: Error\nAmnesia"]

    ComplexityCheck{"Interface Simple\nor Complex?"}
    FlagChatty["Flag: Chatty\nInterface"]

    MetaphorAnalysis[/"Metaphor Analysis:\nModules as Conversation"/]
    NeedTranslator{"Need Adapters\n(Translators)?"}
    FlagAdapter["Flag: Missing\nAdapter Layer"]

    MismatchedVolume{"API Complexity\nMatches Needs?"}
    FlagOverEngineered["Flag: Over-Engineered\nInterface"]

    TalkingPast{"Misaligned\nAssumptions?"}
    FlagAssumptions["Flag: Assumption\nDrift"]

    MoreInterfaces{"More Interfaces\nto Review?"}

    ClassifyFindings["Classify Findings:\nCritical/Important/Suggestion"]

    SeverityGate{"All Findings Have\nSeverity + Evidence?"}
    AddEvidence["Add Missing\nEvidence"]

    FunctionalityGate{"Proposals Preserve\nExisting Behavior?"}
    ReviseProposal["Revise Proposals\nto Preserve"]

    GenHarmonyReport["Generate Harmony\nReport"]
    GenFrictionPoints["Generate Friction\nPoints List"]
    GenProposals["Generate PROPOSE\nSpeech Acts"]
    CoherenceAssessment["System Coherence\nAssessment"]

    Done([End: Integration\nReview Complete])

    Start --> Invoke
    Invoke --> InterfaceLoop
    InterfaceLoop --> IdentifyCaller
    IdentifyCaller --> MapData

    MapData --> TypeMatch
    TypeMatch -->|No| FlagTypeMismatch
    FlagTypeMismatch --> ErrorConsistent
    TypeMatch -->|Yes| ErrorConsistent

    ErrorConsistent -->|No| FlagErrorAmnesia
    FlagErrorAmnesia --> ComplexityCheck
    ErrorConsistent -->|Yes| ComplexityCheck

    ComplexityCheck -->|Complex| FlagChatty
    FlagChatty --> MetaphorAnalysis
    ComplexityCheck -->|Simple| MetaphorAnalysis

    MetaphorAnalysis --> NeedTranslator
    NeedTranslator -->|Yes| FlagAdapter
    FlagAdapter --> MismatchedVolume
    NeedTranslator -->|No| MismatchedVolume

    MismatchedVolume -->|Mismatched| FlagOverEngineered
    FlagOverEngineered --> TalkingPast
    MismatchedVolume -->|Matched| TalkingPast

    TalkingPast -->|Yes| FlagAssumptions
    FlagAssumptions --> MoreInterfaces
    TalkingPast -->|No| MoreInterfaces

    MoreInterfaces -->|Yes| InterfaceLoop
    MoreInterfaces -->|No| ClassifyFindings

    ClassifyFindings --> SeverityGate
    SeverityGate -->|Missing| AddEvidence
    AddEvidence --> SeverityGate
    SeverityGate -->|Complete| FunctionalityGate

    FunctionalityGate -->|Breaks Existing| ReviseProposal
    ReviseProposal --> FunctionalityGate
    FunctionalityGate -->|Preserves| GenHarmonyReport

    GenHarmonyReport --> GenFrictionPoints
    GenFrictionPoints --> GenProposals
    GenProposals --> CoherenceAssessment
    CoherenceAssessment --> Done

    style Start fill:#4CAF50,color:#fff
    style Done fill:#4CAF50,color:#fff
    style Invoke fill:#4CAF50,color:#fff
    style MetaphorAnalysis fill:#4CAF50,color:#fff
    style InterfaceLoop fill:#2196F3,color:#fff
    style IdentifyCaller fill:#2196F3,color:#fff
    style MapData fill:#2196F3,color:#fff
    style FlagTypeMismatch fill:#2196F3,color:#fff
    style FlagErrorAmnesia fill:#2196F3,color:#fff
    style FlagChatty fill:#2196F3,color:#fff
    style FlagAdapter fill:#2196F3,color:#fff
    style FlagOverEngineered fill:#2196F3,color:#fff
    style FlagAssumptions fill:#2196F3,color:#fff
    style ClassifyFindings fill:#2196F3,color:#fff
    style AddEvidence fill:#2196F3,color:#fff
    style ReviseProposal fill:#2196F3,color:#fff
    style GenHarmonyReport fill:#2196F3,color:#fff
    style GenFrictionPoints fill:#2196F3,color:#fff
    style GenProposals fill:#2196F3,color:#fff
    style CoherenceAssessment fill:#2196F3,color:#fff
    style TypeMatch fill:#FF9800,color:#fff
    style ErrorConsistent fill:#FF9800,color:#fff
    style ComplexityCheck fill:#FF9800,color:#fff
    style NeedTranslator fill:#FF9800,color:#fff
    style MismatchedVolume fill:#FF9800,color:#fff
    style TalkingPast fill:#FF9800,color:#fff
    style MoreInterfaces fill:#FF9800,color:#fff
    style SeverityGate fill:#f44336,color:#fff
    style FunctionalityGate fill:#f44336,color:#fff
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
| Honor-Bound Invocation | Lines 14-15: Honor pledge before review |
| Identify Caller and Callee | Lines 53: Analysis step 1 |
| Map Data Crossing Boundary | Lines 54: Analysis step 2 |
| Types Match Exactly? | Lines 55: Analysis step 3 - not "close enough" |
| Error Handling Consistent? | Lines 56: Analysis step 4 |
| Interface Simple or Complex? | Lines 57: Analysis step 5 |
| Metaphor Analysis | Lines 61-66: Modules as people in conversation |
| Need Adapters? | Lines 63: Do they need translators? |
| API Complexity Matches Needs? | Lines 64: Shouting vs whispering check |
| Misaligned Assumptions? | Lines 65: Talking past each other? |
| All Findings Have Severity? | Lines 72: Reflection - severity assigned |
| Proposals Preserve Existing? | Lines 74: Reflection - improvements preserve functionality |
| Generate Harmony Report | Lines 80-98: Harmony report format |
| Generate Friction Points | Lines 91-95: Friction point format |
| Generate PROPOSE Speech Acts | Lines 97-98: PROPOSE improvement |
| System Coherence Assessment | Lines 100-101: Overall integration health |
| Flag: Type Mismatch | Lines 106: Anti-pattern - caller sends X, callee expects Y |
| Flag: Error Amnesia | Lines 107: Anti-pattern - inconsistent error handling |
| Flag: Chatty Interface | Lines 108: Anti-pattern - too many calls |

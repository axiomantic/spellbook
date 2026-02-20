<!-- diagram-meta: {"source": "commands/reflexion-analyze.md", "source_hash": "sha256:a02477f094b82bb46b236597d356dae595bae609ba31c48433f43790a087c4ca", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: reflexion-analyze

Analyzes ITERATE feedback from roundtable validation: parses feedback items, categorizes root causes, stores reflections in forged.db, detects failure patterns, and generates retry guidance.

```mermaid
flowchart TD
    Start([Start Reflexion Analysis]) --> ParseFeedback[Step 1: Parse Feedback Items]
    ParseFeedback --> AllParsed{All Items Parsed?}

    AllParsed -->|No| ExtractFields[Extract Source + Severity + Critique]
    ExtractFields --> AllParsed
    AllParsed -->|Yes| CategorizeRoot[Step 2: Categorize Root Causes]

    CategorizeRoot --> MapCategory{Map to Category}
    MapCategory -->|Incomplete Analysis| IncAnalysis[Discovery Too Shallow]
    MapCategory -->|Misunderstanding| Misunder[Requirements Ambiguity]
    MapCategory -->|Technical Gap| TechGap[Knowledge Limitation]
    MapCategory -->|Scope Creep| ScopeCreep[Boundary Discipline Failure]
    MapCategory -->|Quality Shortcut| QualShort[Time Pressure/Oversight]
    MapCategory -->|Integration Blind Spot| IntBlind[System Thinking Gap]

    IncAnalysis --> RootQuestions[Step 3: Root Cause Questions]
    Misunder --> RootQuestions
    TechGap --> RootQuestions
    ScopeCreep --> RootQuestions
    QualShort --> RootQuestions
    IntBlind --> RootQuestions

    RootQuestions --> ExpectedVsActual[Expected vs Actual?]
    ExpectedVsActual --> WhyDeviation[Why Deviation Occurred?]
    WhyDeviation --> Prevention[What Prevents This?]

    Prevention --> StoreReflections[Store in forged.db]
    StoreReflections --> SetPending[Status: PENDING]

    SetPending --> PatternDetect[Pattern Detection]
    PatternDetect --> SameFailure{Same Failure 2+ Times?}
    SameFailure -->|Yes| AlertRootCause[Alert: Root Cause Not Addressed]
    SameFailure -->|No| CrossFeature{Same Fail 3+ Features?}
    CrossFeature -->|Yes| AlertSystemic[Alert: Systemic Pattern]
    CrossFeature -->|No| ValidatorCheck{Validator 3+ Failures?}
    ValidatorCheck -->|Yes| AlertValidator[Alert: Focus Area Needs Attention]
    ValidatorCheck -->|No| NoPattern[No Pattern Detected]

    AlertRootCause --> GenGuidance[Generate Retry Guidance]
    AlertSystemic --> GenGuidance
    AlertValidator --> GenGuidance
    NoPattern --> GenGuidance

    GenGuidance --> WriteCorrections[Write Required Corrections]
    WriteCorrections --> WriteCriteria[Write Success Criteria]

    WriteCriteria --> SelfCheckGate{Self-Check Passes?}
    SelfCheckGate -->|No| FixMissing[Complete Missing Items]
    FixMissing --> SelfCheckGate
    SelfCheckGate -->|Yes| Done([Reflexion Complete])

    style Start fill:#2196F3,color:#fff
    style Done fill:#2196F3,color:#fff
    style AllParsed fill:#FF9800,color:#fff
    style MapCategory fill:#FF9800,color:#fff
    style SameFailure fill:#FF9800,color:#fff
    style CrossFeature fill:#FF9800,color:#fff
    style ValidatorCheck fill:#FF9800,color:#fff
    style SelfCheckGate fill:#f44336,color:#fff
    style StoreReflections fill:#4CAF50,color:#fff
    style ParseFeedback fill:#2196F3,color:#fff
    style ExtractFields fill:#2196F3,color:#fff
    style CategorizeRoot fill:#2196F3,color:#fff
    style IncAnalysis fill:#2196F3,color:#fff
    style Misunder fill:#2196F3,color:#fff
    style TechGap fill:#2196F3,color:#fff
    style ScopeCreep fill:#2196F3,color:#fff
    style QualShort fill:#2196F3,color:#fff
    style IntBlind fill:#2196F3,color:#fff
    style RootQuestions fill:#2196F3,color:#fff
    style ExpectedVsActual fill:#2196F3,color:#fff
    style WhyDeviation fill:#2196F3,color:#fff
    style Prevention fill:#2196F3,color:#fff
    style SetPending fill:#2196F3,color:#fff
    style PatternDetect fill:#2196F3,color:#fff
    style AlertRootCause fill:#2196F3,color:#fff
    style AlertSystemic fill:#2196F3,color:#fff
    style AlertValidator fill:#2196F3,color:#fff
    style NoPattern fill:#2196F3,color:#fff
    style GenGuidance fill:#2196F3,color:#fff
    style WriteCorrections fill:#2196F3,color:#fff
    style WriteCriteria fill:#2196F3,color:#fff
    style FixMissing fill:#2196F3,color:#fff
```

## Legend

| Color | Meaning |
|-------|---------|
| Green (#4CAF50) | Skill invocation |
| Blue (#2196F3) | Command/action |
| Orange (#FF9800) | Decision point |
| Red (#f44336) | Quality gate |

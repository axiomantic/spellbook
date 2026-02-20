<!-- diagram-meta: {"source": "commands/deep-research-interview.md", "source_hash": "sha256:8537e8444ffb5ec37986b346481ebdf11deb77d14de3c4c2dc3da1e47d439427", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: deep-research-interview

Transform a raw research request into a Research Brief through assumption extraction, disambiguation, structured interview across five categories, and quality-gated brief generation.

```mermaid
flowchart TD
  Start([Start: Raw request]) --> ExtractAssume[Extract assumptions]

  style Start fill:#4CAF50,color:#fff
  style ExtractAssume fill:#2196F3,color:#fff

  ExtractAssume --> DisambigCheck[Check disambiguation needs]

  style DisambigCheck fill:#2196F3,color:#fff

  DisambigCheck --> NameFreq[Name frequency check]
  DisambigCheck --> GenCheck[Generational check]
  DisambigCheck --> SpellCheck[Spelling stability check]
  DisambigCheck --> JurisCheck[Jurisdictional check]
  DisambigCheck --> RecordCheck[Record type check]

  style NameFreq fill:#2196F3,color:#fff
  style GenCheck fill:#2196F3,color:#fff
  style SpellCheck fill:#2196F3,color:#fff
  style JurisCheck fill:#2196F3,color:#fff
  style RecordCheck fill:#2196F3,color:#fff

  NameFreq --> PresentAnalysis[Present findings to user]
  GenCheck --> PresentAnalysis
  SpellCheck --> PresentAnalysis
  JurisCheck --> PresentAnalysis
  RecordCheck --> PresentAnalysis

  style PresentAnalysis fill:#2196F3,color:#fff

  PresentAnalysis --> RewriteQ[Suggest improved question]

  style RewriteQ fill:#2196F3,color:#fff

  RewriteQ --> UserConfirm{User confirms framing?}

  style UserConfirm fill:#FF9800,color:#000

  UserConfirm -->|No| ReviseQ[Revise question]
  UserConfirm -->|Yes| Interview[Structured interview]

  style ReviseQ fill:#2196F3,color:#fff

  ReviseQ --> UserConfirm

  Interview --> Cat1[Goal clarification]
  Interview --> Cat2[Source verification]
  Interview --> Cat3[Entity disambiguation]
  Interview --> Cat4[Domain knowledge]
  Interview --> Cat5[Constraints]

  style Interview fill:#4CAF50,color:#fff
  style Cat1 fill:#2196F3,color:#fff
  style Cat2 fill:#2196F3,color:#fff
  style Cat3 fill:#2196F3,color:#fff
  style Cat4 fill:#2196F3,color:#fff
  style Cat5 fill:#2196F3,color:#fff

  Cat1 --> StopCheck{Stop criteria met?}
  Cat2 --> StopCheck
  Cat3 --> StopCheck
  Cat4 --> StopCheck
  Cat5 --> StopCheck

  style StopCheck fill:#FF9800,color:#000

  StopCheck -->|No| AskMore[Ask next batch of 1-2]
  StopCheck -->|Yes| GenBrief[Generate Research Brief]

  style AskMore fill:#2196F3,color:#fff

  AskMore --> StopCheck

  style GenBrief fill:#2196F3,color:#fff

  GenBrief --> QualityGate{Brief quality gate}

  style QualityGate fill:#f44336,color:#fff

  QualityGate -->|Question specific?| ChkSubj{Subjects have 2+ keys?}
  QualityGate -->|Fail| FixBrief[Fix brief gaps]

  style FixBrief fill:#2196F3,color:#fff

  FixBrief --> QualityGate

  style ChkSubj fill:#f44336,color:#fff

  ChkSubj -->|No| FixBrief
  ChkSubj -->|Yes| ChkCriteria{Success criteria defined?}

  style ChkCriteria fill:#f44336,color:#fff

  ChkCriteria -->|No| FixBrief
  ChkCriteria -->|Yes| UserApprove{User approves brief?}

  style UserApprove fill:#FF9800,color:#000

  UserApprove -->|No| ReviseB[Revise brief]
  UserApprove -->|Yes| SaveBrief[Save Research Brief]

  style ReviseB fill:#2196F3,color:#fff

  ReviseB --> QualityGate

  style SaveBrief fill:#2196F3,color:#fff

  SaveBrief --> End([End: Phase 0 complete])

  style End fill:#4CAF50,color:#fff
```

## Legend

| Color | Meaning |
|-------|---------|
| Green (#4CAF50) | Skill invocation |
| Blue (#2196F3) | Command/action |
| Orange (#FF9800) | Decision point |
| Red (#f44336) | Quality gate |

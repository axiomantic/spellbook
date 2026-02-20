<!-- diagram-meta: {"source": "skills/dehallucination/SKILL.md", "source_hash": "sha256:98a79018f43e59561a6e41ff8a94b3b6262373b9b7ad387d746b7fec9ed06d69", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: dehallucination

Workflow for verifying claims, detecting hallucinations, and enforcing recovery protocols. Used as a quality gate by the Forge pipeline and roundtable feedback.

```mermaid
flowchart TD
    Start([Start]) --> LoadArtifact[Load Artifact Under Review]
    LoadArtifact --> ExtractClaims[Extract All Claims]
    ExtractClaims --> CategorizeClaims[Categorize By Type]
    CategorizeClaims --> RiskRank{Risk Level?}
    RiskRank -->|Critical: Security/Deps/APIs| VerifyCritical[Verify Critical Claims]
    RiskRank -->|High: Implementation| VerifyHigh[Verify High-Risk Claims]
    RiskRank -->|Medium: Config| VerifyMedium[Verify Medium-Risk Claims]
    RiskRank -->|Low: Docs| VerifyLow[Verify Low-Risk Claims]
    VerifyCritical --> GatherEvidence[Gather Evidence]
    VerifyHigh --> GatherEvidence
    VerifyMedium --> GatherEvidence
    VerifyLow --> GatherEvidence
    GatherEvidence --> AssignConfidence{Confidence Level?}
    AssignConfidence -->|VERIFIED| DocumentVerified[Document: Verified]
    AssignConfidence -->|HIGH/MEDIUM| DocumentSupported[Document: Supported]
    AssignConfidence -->|LOW/UNVERIFIED| FlagUncertain[Flag As Uncertain]
    AssignConfidence -->|HALLUCINATION| RecoveryProtocol[Recovery Protocol]
    DocumentVerified --> MoreClaims{More Claims?}
    DocumentSupported --> MoreClaims
    FlagUncertain --> MoreClaims
    RecoveryProtocol --> Isolate[Isolate Exact Claim]
    Isolate --> TracePropagation[Trace Propagation]
    TracePropagation --> CorrectSource[Correct At Source]
    CorrectSource --> UpdateDependents[Update Dependents]
    UpdateDependents --> DocumentLesson[Document Lesson]
    DocumentLesson --> MoreClaims
    MoreClaims -->|Yes| RiskRank
    MoreClaims -->|No| GenerateReport[Generate Verification Report]
    GenerateReport --> SelfCheck{Self-Check Passed?}
    SelfCheck -->|Yes| End([End])
    SelfCheck -->|No| FixGaps[Complete Missing Checks]
    FixGaps --> SelfCheck

    style Start fill:#4CAF50,color:#fff
    style End fill:#4CAF50,color:#fff
    style LoadArtifact fill:#2196F3,color:#fff
    style ExtractClaims fill:#2196F3,color:#fff
    style CategorizeClaims fill:#2196F3,color:#fff
    style VerifyCritical fill:#2196F3,color:#fff
    style VerifyHigh fill:#2196F3,color:#fff
    style VerifyMedium fill:#2196F3,color:#fff
    style VerifyLow fill:#2196F3,color:#fff
    style GatherEvidence fill:#2196F3,color:#fff
    style DocumentVerified fill:#2196F3,color:#fff
    style DocumentSupported fill:#2196F3,color:#fff
    style FlagUncertain fill:#2196F3,color:#fff
    style RecoveryProtocol fill:#2196F3,color:#fff
    style Isolate fill:#2196F3,color:#fff
    style TracePropagation fill:#2196F3,color:#fff
    style CorrectSource fill:#2196F3,color:#fff
    style UpdateDependents fill:#2196F3,color:#fff
    style DocumentLesson fill:#2196F3,color:#fff
    style GenerateReport fill:#2196F3,color:#fff
    style FixGaps fill:#2196F3,color:#fff
    style RiskRank fill:#FF9800,color:#fff
    style AssignConfidence fill:#FF9800,color:#fff
    style MoreClaims fill:#FF9800,color:#fff
    style SelfCheck fill:#f44336,color:#fff
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
| Load Artifact Under Review | Inputs: artifact_path |
| Extract All Claims | Detection Protocol, Step 1: Extract claims |
| Categorize By Type | Hallucination Categories table |
| Risk Level? | Detection Protocol, Step 2: Categorize by risk |
| Verify Critical Claims | Detection Protocol, Step 3: Verify critical first |
| Gather Evidence | Assessment Process, Step 2: Gather evidence |
| Confidence Level? | Confidence Levels table |
| Document: Verified | Assessment Process, Step 4: Document |
| Recovery Protocol | Recovery Protocol section |
| Isolate Exact Claim | Recovery Protocol, Step 1: Isolate |
| Trace Propagation | Recovery Protocol, Step 2: Trace propagation |
| Correct At Source | Recovery Protocol, Step 3: Correct at source |
| Update Dependents | Recovery Protocol, Step 4: Update dependents |
| Document Lesson | Recovery Protocol, Step 5: Document lesson |
| Generate Verification Report | Detection Protocol, Step 4: Report |
| Self-Check Passed? | Self-Check checklist |

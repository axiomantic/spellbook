<!-- diagram-meta: {"source": "skills/analyzing-skill-usage/SKILL.md", "source_hash": "sha256:6db879a5e40a26c51aa61c6a1632f665fbf75cf8acd6b52a5990c9911c5b73c0", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: analyzing-skill-usage

Workflow for analyzing skill invocation patterns across session transcripts. Supports two analysis modes: identifying weak skills and A/B testing skill versions.

```mermaid
flowchart TD
    Start([Start]) --> LoadSessions[Load Sessions]
    LoadSessions --> DetectInvocations[Detect Skill Invocations]
    DetectInvocations --> IdentifyBoundaries[Identify Invocation Boundaries]
    IdentifyBoundaries --> ScoreInvocations[Score Each Invocation]
    ScoreInvocations --> DetectCorrections[Detect Correction Patterns]
    DetectCorrections --> AggregateMetrics[Aggregate Metrics Per Skill]
    AggregateMetrics --> ModeDecision{Analysis Mode?}
    ModeDecision -->|Weak Skills| RankByFailure[Rank By Failure Score]
    ModeDecision -->|A/B Testing| VersionDetected{Versions Detected?}
    VersionDetected -->|Yes| SampleCheck{N >= 5 per variant?}
    VersionDetected -->|No| NoComparison[Report: No Versions Found]
    SampleCheck -->|Yes| CompareVersions[Compare Version Metrics]
    SampleCheck -->|No| InsufficientData[Report: Insufficient Data]
    RankByFailure --> GenerateReport[Generate Weak Skills Report]
    CompareVersions --> StatSignificance{Statistically Significant?}
    StatSignificance -->|Yes| Recommendation[Generate Recommendation]
    StatSignificance -->|No| CaveatReport[Report With Caveats]
    Recommendation --> GenerateReport
    CaveatReport --> GenerateReport
    InsufficientData --> GenerateReport
    NoComparison --> GenerateReport
    GenerateReport --> SelfCheck{Self-Check Passed?}
    SelfCheck -->|Yes| End([End])
    SelfCheck -->|No| FixGaps[Fix Gaps In Analysis]
    FixGaps --> SelfCheck

    style Start fill:#4CAF50,color:#fff
    style End fill:#4CAF50,color:#fff
    style LoadSessions fill:#2196F3,color:#fff
    style DetectInvocations fill:#2196F3,color:#fff
    style IdentifyBoundaries fill:#2196F3,color:#fff
    style ScoreInvocations fill:#2196F3,color:#fff
    style DetectCorrections fill:#2196F3,color:#fff
    style AggregateMetrics fill:#2196F3,color:#fff
    style RankByFailure fill:#2196F3,color:#fff
    style CompareVersions fill:#2196F3,color:#fff
    style Recommendation fill:#2196F3,color:#fff
    style CaveatReport fill:#2196F3,color:#fff
    style InsufficientData fill:#2196F3,color:#fff
    style NoComparison fill:#2196F3,color:#fff
    style GenerateReport fill:#2196F3,color:#fff
    style FixGaps fill:#2196F3,color:#fff
    style ModeDecision fill:#FF9800,color:#fff
    style VersionDetected fill:#FF9800,color:#fff
    style SampleCheck fill:#FF9800,color:#fff
    style StatSignificance fill:#FF9800,color:#fff
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
| Load Sessions | Extraction Protocol, Step 1: Load Sessions |
| Detect Skill Invocations | Extraction Protocol, Step 2: Detect Skill Invocations |
| Identify Invocation Boundaries | Step 2: End Event detection |
| Score Each Invocation | Extraction Protocol, Step 3: Score Each Invocation |
| Detect Correction Patterns | Step 3: Correction Detection Patterns |
| Aggregate Metrics Per Skill | Extraction Protocol, Step 4: Aggregate Metrics |
| Analysis Mode? | Analysis Modes: Mode 1 vs Mode 2 |
| Rank By Failure Score | Mode 1: Identify Weak Skills |
| Versions Detected? | Mode 2: A/B Testing Versions |
| N >= 5 per variant? | Version Detection: Minimum 5 invocations per variant |
| Compare Version Metrics | Mode 2: A/B Comparison table |
| Statistically Significant? | Mode 2: Significant column (p<0.05) |
| Self-Check Passed? | Self-Check checklist |

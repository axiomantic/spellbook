<!-- diagram-meta: {"source": "commands/request-review-artifacts.md", "source_hash": "sha256:92ac85f8dbd4e1c8032736181c1c6ffaafb60f75dc7864e97087a53e98c02e78", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: request-review-artifacts

Artifact contract for code review workflow. Defines directory structure, phase outputs, manifest schema, and SHA persistence for traceability.

```mermaid
flowchart TD
    Start([Review Initiated]) --> CreateDir["Create Artifact Dir\n~/.local/spellbook/reviews/"]
    CreateDir --> EncodeProject["Encode Project Path"]
    EncodeProject --> TimestampDir["Create Timestamped\nSubdirectory"]
    TimestampDir --> P1Art["Phase 1 Artifact:\nreview-manifest.json"]
    P1Art --> StoreRange["Store Git Range\n+ File List"]
    StoreRange --> StoreSHA["Persist base_sha\n+ reviewed_sha"]
    StoreSHA --> P2Art["Phase 2 Artifact:\ncontext-bundle.md"]
    P2Art --> P3Art["Phase 3 Artifact:\nreview-findings.json"]
    P3Art --> ValidateSchema{"Manifest Schema\nValid?"}
    ValidateSchema -->|No| FixSchema["Fix Schema Issues"]
    FixSchema --> ValidateSchema
    ValidateSchema -->|Yes| P4Art["Phase 4 Artifact:\ntriage-report.md"]
    P4Art --> P5Art["Phase 5 Artifact:\nfix-report.md"]
    P5Art --> P6Art["Phase 6 Artifact:\ngate-decision.md"]
    P6Art --> SHACheck{"Use reviewed_sha\nNot HEAD?"}
    SHACheck -->|Yes| Done([Artifacts Complete])
    SHACheck -->|No| WarnSHA["Warn: Stale HEAD\nUse Manifest SHA"]
    WarnSHA --> Done

    style Start fill:#4CAF50,color:#fff
    style Done fill:#4CAF50,color:#fff
    style CreateDir fill:#2196F3,color:#fff
    style EncodeProject fill:#2196F3,color:#fff
    style TimestampDir fill:#2196F3,color:#fff
    style P1Art fill:#2196F3,color:#fff
    style StoreRange fill:#2196F3,color:#fff
    style StoreSHA fill:#2196F3,color:#fff
    style P2Art fill:#2196F3,color:#fff
    style P3Art fill:#2196F3,color:#fff
    style FixSchema fill:#2196F3,color:#fff
    style P4Art fill:#2196F3,color:#fff
    style P5Art fill:#2196F3,color:#fff
    style P6Art fill:#2196F3,color:#fff
    style WarnSHA fill:#2196F3,color:#fff
    style ValidateSchema fill:#f44336,color:#fff
    style SHACheck fill:#FF9800,color:#fff
```

## Legend

| Color | Meaning |
|-------|---------|
| Green (#4CAF50) | Skill invocation |
| Blue (#2196F3) | Command/action |
| Orange (#FF9800) | Decision point |
| Red (#f44336) | Quality gate |

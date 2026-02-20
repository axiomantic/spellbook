<!-- diagram-meta: {"source": "skills/project-encyclopedia/SKILL.md", "source_hash": "sha256:1bdd25b00ecf7db7739568b84c667d03efc40b9fc1856b7d95b05fa7bcb1b73e", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: project-encyclopedia

Create or refresh persistent project encyclopedias with glossary, architecture maps, and decision records to solve agent amnesia across sessions.

```mermaid
flowchart TD
    START([Start]) --> CHECK_EXIST{Encyclopedia exists?}
    CHECK_EXIST -->|No| OFFER_CREATE[Offer to Create]
    CHECK_EXIST -->|Yes| STALE_CHECK{Older than 30 days?}
    STALE_CHECK -->|No| READ_SILENT[Read Silently for Context]
    READ_SILENT --> DONE_SILENT([Use as Context])
    STALE_CHECK -->|Yes| OFFER_REFRESH[Offer to Refresh]
    OFFER_CREATE --> CONSENT{User consents?}
    OFFER_REFRESH --> CONSENT
    CONSENT -->|No| SKIP([Proceed Without])
    CONSENT -->|Yes, Create| P1[Phase 1: Discovery]
    CONSENT -->|Yes, Refresh| REFRESH[Read Current Version]
    P1 --> EXPLORE[Explore Project Structure]
    EXPLORE --> P2_5["/encyclopedia-build"]
    P2_5 --> P6["/encyclopedia-validate"]
    P6 --> SIZE_GATE{Under 1000 lines?}
    SIZE_GATE -->|No| TRIM[Trim to Budget]
    TRIM --> SIZE_GATE
    SIZE_GATE -->|Yes| SELF_CHECK{Self-Check Passes?}
    SELF_CHECK -->|No| REVISE[Revise Content]
    REVISE --> SELF_CHECK
    SELF_CHECK -->|Yes| WRITE[Write to Output Path]
    WRITE --> DONE([Encyclopedia Ready])
    REFRESH --> SCAN[Scan for Major Changes]
    SCAN --> DIFF[Present Proposed Diff]
    DIFF --> APPROVE{User approves?}
    APPROVE -->|No| KEEP([Keep Existing])
    APPROVE -->|Yes| APPLY_REFRESH[Apply Surgical Updates]
    APPLY_REFRESH --> WRITE

    style START fill:#4CAF50,color:#fff
    style DONE fill:#4CAF50,color:#fff
    style DONE_SILENT fill:#4CAF50,color:#fff
    style SKIP fill:#4CAF50,color:#fff
    style KEEP fill:#4CAF50,color:#fff
    style P2_5 fill:#2196F3,color:#fff
    style P6 fill:#2196F3,color:#fff
    style EXPLORE fill:#2196F3,color:#fff
    style WRITE fill:#2196F3,color:#fff
    style SCAN fill:#2196F3,color:#fff
    style APPLY_REFRESH fill:#2196F3,color:#fff
    style CHECK_EXIST fill:#FF9800,color:#fff
    style STALE_CHECK fill:#FF9800,color:#fff
    style CONSENT fill:#FF9800,color:#fff
    style APPROVE fill:#FF9800,color:#fff
    style SIZE_GATE fill:#f44336,color:#fff
    style SELF_CHECK fill:#f44336,color:#fff
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
| Encyclopedia exists? | Session Integration: check existence and freshness |
| Older than 30 days? | Invariant Principle 4: staleness detection, mtime >= 30 days |
| User consents? | Invariant Principle 2: offer, don't force |
| Phase 1: Discovery | Phase 1: gather project type, entry points, directories, tests, build commands |
| /encyclopedia-build | Phases 2-5: subagent builds glossary, architecture, decisions, entry points |
| /encyclopedia-validate | Phase 6: subagent validates against quality checklist and writes output |
| Under 1000 lines? | Invariant Principle 5: context budget 500-1000 lines |
| Self-Check Passes? | Self-Check: consent, size, no duplication, diagram nodes, glossary, rationale, path, mtime |
| Refresh workflow | Refresh Workflow: surgical update, not regeneration from scratch |
| Present Proposed Diff | Refresh step 3: present diff of proposed changes |

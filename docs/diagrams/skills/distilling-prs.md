<!-- diagram-meta: {"source": "skills/distilling-prs/SKILL.md","source_hash": "sha256:c75d330ae3d6b86782bbd2e23cefdaaefc7eb0637c27dbd2c38c9f58fa900afb","generator": "stamp"} -->
# Diagram: distilling-prs

Three-phase PR distillation: heuristic pattern matching, AI analysis of unmatched files, and categorized report generation with post-completion verification.

## Overview: Three-Phase PR Distillation Flow

```mermaid
flowchart TD
    subgraph Legend
        L1[Process]
        L2{Decision}
        L3([Terminal])
        L4["MCP Tool Call"]:::tool
        L5["Quality Gate"]:::gate
    end

    START([User invokes<br>/distilling-prs PR]) --> PARSE[Parse PR identifier<br>number or URL]
    PARSE --> P1["<b>Phase 1</b><br>Fetch, Parse, Match"]:::phase

    P1 --> FETCH["pr_fetch(pr-identifier)"]:::tool
    FETCH --> FETCH_OK{Fetch<br>succeeded?}
    FETCH_OK -- No --> HALT_FETCH([Halt: surface error<br>to user]):::fail
    FETCH_OK -- Yes --> DIFF["pr_diff(pr_data.diff)"]:::tool
    DIFF --> MATCH["pr_match_patterns(<br>files, project_root)"]:::tool
    MATCH --> MATCH_OK{Match<br>succeeded?}
    MATCH_OK -- No --> HALT_MATCH([Halt: surface error<br>to user]):::fail
    MATCH_OK -- Yes --> HAS_UNMATCHED{Unmatched<br>files remain?}

    HAS_UNMATCHED -- No --> P3
    HAS_UNMATCHED -- Yes --> P2["<b>Phase 2</b><br>AI Analysis"]:::phase

    P2 --> ANALYZE["Analyze each<br>unmatched file"]
    ANALYZE --> CLASSIFY{Classify change}
    CLASSIFY -- "Significant logic/<br>API/behavior" --> REVIEW[review_required]:::review
    CLASSIFY -- "Formatting/<br>comments/trivial" --> SKIP[safe_to_skip]:::safe
    CLASSIFY -- "Low confidence" --> UNCERTAIN[uncertain]:::uncertain
    REVIEW --> MORE{More unmatched<br>files?}
    SKIP --> MORE
    UNCERTAIN --> MORE
    MORE -- Yes --> ANALYZE
    MORE -- No --> P3

    P3["<b>Phase 3</b><br>Generate Report"]:::phase --> REPORT["Build markdown report:<br>1. Summary by category<br>2. Full diffs for review_required<br>3. Pattern matches + confidence<br>4. Discovered patterns + bless cmds"]

    REPORT --> VERIFY["Post-completion<br>verification"]:::gate
    VERIFY --> V1{All files<br>categorized?}
    V1 -- No --> FIX1["Fix missing files"] --> VERIFY
    V1 -- Yes --> V2{review_required<br>have full diffs?}
    V2 -- No --> FIX2["Add missing diffs"] --> VERIFY
    V2 -- Yes --> V3{Pattern summary<br>accurate?}
    V3 -- No --> FIX3["Fix summary"] --> VERIFY
    V3 -- Yes --> V4{Discovered patterns<br>have bless cmds?}
    V4 -- No --> FIX4["Add bless commands"] --> VERIFY
    V4 -- Yes --> PRESENT([Present report<br>to user]):::success

    classDef phase fill:#2d5a8e,stroke:#1a3a5c,color:#fff
    classDef tool fill:#4a9eff,stroke:#2d7ed8,color:#fff
    classDef gate fill:#ff6b6b,stroke:#d84a4a,color:#fff
    classDef success fill:#51cf66,stroke:#37a34d,color:#fff
    classDef fail fill:#ff6b6b,stroke:#d84a4a,color:#fff
    classDef review fill:#ff922b,stroke:#d47520,color:#fff
    classDef safe fill:#51cf66,stroke:#37a34d,color:#fff
    classDef uncertain fill:#ffd43b,stroke:#d4b020,color:#333
```

## Builtin Pattern Categories

15 builtin patterns across three confidence levels determine automatic categorization in Phase 1.

```mermaid
flowchart LR
    subgraph Legend
        L1["Always Review"]:::always
        L2["High Confidence"]:::high
        L3["Medium Confidence"]:::medium
    end

    subgraph AR["Always Review (5)"]
        A1[Migration files]:::always
        A2[Permission changes]:::always
        A3[Model changes]:::always
        A4[Signal handlers]:::always
        A5[Endpoint changes]:::always
    end

    subgraph HC["High Confidence (5)"]
        H1[Settings changes]:::high
        H2[Query count JSON]:::high
        H3[Debug print stmts]:::high
        H4[Import cleanup]:::high
        H5[Gitignore updates]:::high
    end

    subgraph MC["Medium Confidence (5)"]
        M1[Backfill commands]:::medium
        M2[Decorator removals]:::medium
        M3[Factory setup]:::medium
        M4[Test renames]:::medium
        M5[Test assertion updates]:::medium
    end

    classDef always fill:#ff6b6b,stroke:#d84a4a,color:#fff
    classDef high fill:#4a9eff,stroke:#2d7ed8,color:#fff
    classDef medium fill:#ffd43b,stroke:#d4b020,color:#333
```

## Legend

| Color | Meaning |
|-------|---------|
| Dark blue (`#2d5a8e`) | Phase marker |
| Blue (`#4a9eff`) | MCP tool call |
| Red (`#ff6b6b`) | Quality gate / error halt |
| Green (`#51cf66`) | Success terminal / safe_to_skip |
| Orange (`#ff922b`) | review_required classification |
| Yellow (`#ffd43b`) | uncertain classification |

## Cross-Reference

| Node | Source Reference | Description |
|------|-----------------|-------------|
| START | SKILL.md L35 | User invocation with PR identifier |
| PARSE | SKILL.md L36 | Parse PR number or URL |
| Phase 1 | SKILL.md L43-58 | Fetch, Parse, Match via MCP tools |
| FETCH | SKILL.md L46 | `pr_fetch` MCP tool call |
| DIFF | SKILL.md L47 | `pr_diff` MCP tool call |
| MATCH | SKILL.md L48-51 | `pr_match_patterns` MCP tool call |
| HALT_FETCH / HALT_MATCH | SKILL.md L58 | Error halt on MCP tool failure |
| Phase 2 | SKILL.md L60-65 | AI analysis of unmatched files |
| CLASSIFY | SKILL.md L63-65 | Three-way classification: review_required, safe_to_skip, uncertain |
| Phase 3 | SKILL.md L67-74 | Report generation with four sections |
| VERIFY | SKILL.md L76-81 | Post-completion reflection gate (four checks) |
| PRESENT | SKILL.md L40 | Final report delivery to user |
| Builtin Patterns | SKILL.md L121-129 | 15 patterns across 3 confidence tiers |

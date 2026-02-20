<!-- diagram-meta: {"source": "skills/merging-worktrees/SKILL.md", "source_hash": "sha256:84037998b7008117a900a2876abc4107c88c26c92319f3b9f9c8ae1e488cc199", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: merging-worktrees

Merge parallel worktrees into a unified branch using dependency-ordered rounds with mandatory 3-way conflict analysis and per-round testing.

```mermaid
flowchart TD
    START([Start]) --> PREFLIGHT[Pre-Flight Checks]
    PREFLIGHT --> PREFLIGHT_GATE{Complete context?}
    PREFLIGHT_GATE -->|No| STOP_PREFLIGHT[Stop and Address]
    STOP_PREFLIGHT --> PREFLIGHT
    PREFLIGHT_GATE -->|Yes| P1[Phase 1: Build Dependency Graph]
    P1 --> MERGE_ORDER[Create Merge Order Plan]
    MERGE_ORDER --> TODO[Create Todo Checklist]
    TODO --> P2["/merge-worktree-execute"]
    P2 --> CONFLICT{Conflicts exist?}
    CONFLICT -->|Yes| P3["/merge-worktree-resolve"]
    P3 --> RESOLVE_SKILL["/resolving-merge-conflicts"]
    RESOLVE_SKILL --> THREE_WAY[3-Way Analysis]
    THREE_WAY --> SYNTHESIS[Synthesize Resolution]
    SYNTHESIS --> CONTRACT_CHECK{Contracts honored?}
    CONTRACT_CHECK -->|No| STOP_CONTRACT[Stop: Fix Violation]
    STOP_CONTRACT --> SYNTHESIS
    CONTRACT_CHECK -->|Yes| TEST_ROUND
    CONFLICT -->|No| TEST_ROUND{Tests pass?}
    TEST_ROUND -->|No| DEBUG["/systematic-debugging"]
    DEBUG --> TEST_ROUND
    TEST_ROUND -->|Yes| MORE_ROUNDS{More rounds?}
    MORE_ROUNDS -->|Yes| P2
    MORE_ROUNDS -->|No| P4_5["/merge-worktree-verify"]
    P4_5 --> AUDIT["/auditing-green-mirage"]
    AUDIT --> REVIEW[Code Review]
    REVIEW --> FINAL_GATE{All gates pass?}
    FINAL_GATE -->|No| FIX[Fix Issues]
    FIX --> FINAL_GATE
    FINAL_GATE -->|Yes| CLEANUP[Delete Worktrees]
    CLEANUP --> DONE([Unified Branch Ready])

    style START fill:#4CAF50,color:#fff
    style DONE fill:#4CAF50,color:#fff
    style P2 fill:#2196F3,color:#fff
    style P3 fill:#2196F3,color:#fff
    style P4_5 fill:#2196F3,color:#fff
    style RESOLVE_SKILL fill:#4CAF50,color:#fff
    style AUDIT fill:#4CAF50,color:#fff
    style DEBUG fill:#4CAF50,color:#fff
    style PREFLIGHT_GATE fill:#FF9800,color:#fff
    style CONFLICT fill:#FF9800,color:#fff
    style CONTRACT_CHECK fill:#FF9800,color:#fff
    style TEST_ROUND fill:#f44336,color:#fff
    style MORE_ROUNDS fill:#FF9800,color:#fff
    style FINAL_GATE fill:#f44336,color:#fff
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
| Pre-Flight Checks | Pre-Flight section: verify merge context, dependency graph, contracts |
| Phase 1: Build Dependency Graph | Phase 1: Merge Order - rounds by dependency level |
| /merge-worktree-execute | Phase 2: Sequential Round Merging command dispatch |
| /merge-worktree-resolve | Phase 3: Conflict Resolution command dispatch |
| /resolving-merge-conflicts | Pre-Conflict Gate: mandatory skill for conflict subagents |
| 3-Way Analysis | Invariant Principle 2: base vs ours vs theirs mandatory |
| Contracts honored? | Invariant Principle 1: interface contracts are law |
| Tests pass? | Invariant Principle 3: test after each round |
| /merge-worktree-verify | Phases 4-5: Final Verification + Cleanup command dispatch |
| /auditing-green-mirage | Self-Check: run auditing-green-mirage on tests |
| Delete Worktrees | Self-Check: deleted all worktrees after success |

<!-- diagram-meta: {"source": "skills/optimizing-instructions/SKILL.md", "source_hash": "sha256:add0cee415819c2666629f8e41dd531612c17ed5736b6bbe5b2c674292b5f853", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: optimizing-instructions

Optimize instruction files for token efficiency while preserving all capabilities, with a verification protocol to prevent capability regression.

```mermaid
flowchart TD
    START([Start]) --> READ[Read File Completely]
    READ --> ESTIMATE[Estimate Token Count]
    ESTIMATE --> SKIP_CHECK{Already minimal?}
    SKIP_CHECK -->|Yes: <500 tokens| SKIP([Skip Optimization])
    SKIP_CHECK -->|No| SAFETY[Identify Safety Sections]
    SAFETY --> SIZE_CHECK{File >500 lines?}
    SIZE_CHECK -->|Yes| SPLIT[Split Into Sections]
    SPLIT --> PARALLEL[Dispatch Parallel Subagents]
    PARALLEL --> MERGE_FINDINGS[Merge Findings]
    MERGE_FINDINGS --> CROSS_DEP{Cross-Section Dependencies?}
    CROSS_DEP -->|Yes| RESOLVE[Resolve Conflicts]
    RESOLVE --> APPLY
    CROSS_DEP -->|No| APPLY[Apply Atomically]
    SIZE_CHECK -->|No| COMPRESS[Apply Compression Patterns]
    COMPRESS --> DRAFT[Draft Optimized Version]
    DRAFT --> APPLY
    APPLY --> VERIFY_CASES[Identify 3 Use Cases]
    VERIFY_CASES --> TRACE[Trace Through Optimized]
    TRACE --> COMPARE{Equivalent Behavior?}
    COMPARE -->|No| REVERT[Revert That Optimization]
    REVERT --> VERIFY_CASES
    COMPARE -->|Yes| SELF_CHECK{Self-Check Passes?}
    SELF_CHECK -->|No| FIX[Fix Unchecked Items]
    FIX --> SELF_CHECK
    SELF_CHECK -->|Yes| REPORT[Generate Optimization Report]
    REPORT --> DONE([Complete])

    style START fill:#4CAF50,color:#fff
    style DONE fill:#4CAF50,color:#fff
    style SKIP fill:#4CAF50,color:#fff
    style READ fill:#2196F3,color:#fff
    style ESTIMATE fill:#2196F3,color:#fff
    style SAFETY fill:#2196F3,color:#fff
    style SPLIT fill:#2196F3,color:#fff
    style PARALLEL fill:#2196F3,color:#fff
    style COMPRESS fill:#2196F3,color:#fff
    style DRAFT fill:#2196F3,color:#fff
    style APPLY fill:#2196F3,color:#fff
    style REPORT fill:#2196F3,color:#fff
    style SKIP_CHECK fill:#FF9800,color:#fff
    style SIZE_CHECK fill:#FF9800,color:#fff
    style CROSS_DEP fill:#FF9800,color:#fff
    style COMPARE fill:#f44336,color:#fff
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
| Read File Completely | Process step 1 |
| Estimate Token Count | Process step 2: words * 1.3 |
| Already minimal? | Skip Optimization When: <500 tokens |
| Identify Safety Sections | Process step 3: skip safety-critical sections |
| File >500 lines? | Large File Strategy threshold |
| Split Into Sections / Parallel Subagents | Large File Strategy: parallelization approach |
| Apply Compression Patterns | Compression Patterns section and Declarative Principles |
| Identify 3 Use Cases | Verification Protocol step 1 |
| Trace Through Optimized | Verification Protocol step 2: mentally trace each use case |
| Equivalent Behavior? | Verification Protocol step 3: compare behavior |
| Self-Check Passes? | Self-Check: token count, triggers, edge cases, safety, terminology, formats |
| Generate Optimization Report | Output Format section: summary, changes, verification, optimized content |

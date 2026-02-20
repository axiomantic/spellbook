<!-- diagram-meta: {"source": "commands/ie-tool-docs.md", "source_hash": "sha256:afc7c195d8181468525c8f700f548485f7d9fc93c1b04ab380bb154f501c0606", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: ie-tool-docs

Guidance for writing MCP tool, API, and CLI documentation that LLMs can reliably interpret. Covers purpose, parameters, errors, edge cases, and anti-patterns.

```mermaid
flowchart TD
    Start([Invoke /ie-tool-docs]) --> IdentifyTool[Identify Tool/Function]
    IdentifyTool --> WritePurpose[Write Purpose Statement]
    WritePurpose --> WriteWhenUse[Document When to Use]
    WriteWhenUse --> WriteWhenNot[Document When NOT to Use]
    WriteWhenNot --> DocParams[Document Parameters]

    DocParams --> ParamLoop{All Params Documented?}
    ParamLoop -->|No| AddParam[Add Type + Constraints + Example]
    AddParam --> ParamLoop
    ParamLoop -->|Yes| DocReturn[Document Return Value]

    DocReturn --> DocErrors[Document Error Cases]
    DocErrors --> EdgeCases[Document Edge Cases]

    EdgeCases --> EdgeLoop{All Edges Covered?}
    EdgeLoop -->|No| AddEdge[Add Empty/Invalid/Missing/Timeout]
    AddEdge --> EdgeLoop
    EdgeLoop -->|Yes| DocSideEffects[Document Side Effects]

    DocSideEffects --> AddExamples[Add Usage Examples]
    AddExamples --> SelfCheck{Self-Check Passes?}

    SelfCheck -->|No| FixDocs[Fix Missing Elements]
    FixDocs --> SelfCheck
    SelfCheck -->|Yes| Done([Tool Docs Complete])

    style Start fill:#2196F3,color:#fff
    style Done fill:#2196F3,color:#fff
    style ParamLoop fill:#FF9800,color:#fff
    style EdgeLoop fill:#FF9800,color:#fff
    style SelfCheck fill:#f44336,color:#fff
    style IdentifyTool fill:#2196F3,color:#fff
    style WritePurpose fill:#2196F3,color:#fff
    style WriteWhenUse fill:#2196F3,color:#fff
    style WriteWhenNot fill:#2196F3,color:#fff
    style DocParams fill:#2196F3,color:#fff
    style AddParam fill:#2196F3,color:#fff
    style DocReturn fill:#2196F3,color:#fff
    style DocErrors fill:#2196F3,color:#fff
    style EdgeCases fill:#2196F3,color:#fff
    style AddEdge fill:#2196F3,color:#fff
    style DocSideEffects fill:#2196F3,color:#fff
    style AddExamples fill:#2196F3,color:#fff
    style FixDocs fill:#2196F3,color:#fff
```

## Legend

| Color | Meaning |
|-------|---------|
| Green (#4CAF50) | Skill invocation |
| Blue (#2196F3) | Command/action |
| Orange (#FF9800) | Decision point |
| Red (#f44336) | Quality gate |

<!-- diagram-meta: {"source": "skills/documenting-tools/SKILL.md", "source_hash": "sha256:b9fe5353ac3fc41f327286818b0f45f6221956824e7dec4ff6fb80cbd49df3f0", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: documenting-tools

Workflow for producing LLM-quality tool documentation. Ensures every tool has purpose, parameters, error cases, and examples documented to prevent model misuse.

```mermaid
flowchart TD
    Start([Start]) --> IdentifyType{Tool Type?}
    IdentifyType -->|MCP Tool| MCPSchema[Use MCP Schema Format]
    IdentifyType -->|REST API| APISchema[Use API Doc Format]
    IdentifyType -->|CLI Command| CLISchema[Use CLI Doc Format]
    IdentifyType -->|Function| FuncSchema[Use Function Doc Format]
    MCPSchema --> WritePurpose[Write Purpose: One Sentence]
    APISchema --> WritePurpose
    CLISchema --> WritePurpose
    FuncSchema --> WritePurpose
    WritePurpose --> WriteWhenToUse[Write When To Use]
    WriteWhenToUse --> WriteWhenNot[Write When NOT To Use]
    WriteWhenNot --> DocParams[Document All Parameters]
    DocParams --> ParamComplete{Each Param Has Type + Constraints + Example?}
    ParamComplete -->|No| FixParams[Add Missing Param Details]
    FixParams --> ParamComplete
    ParamComplete -->|Yes| DocReturn[Document Return Value]
    DocReturn --> DocErrors[Document Error Cases]
    DocErrors --> ErrorComplete{All Error Cases Covered?}
    ErrorComplete -->|No| AddErrors[Add Missing Error Cases]
    AddErrors --> ErrorComplete
    ErrorComplete -->|Yes| HasSideEffects{Has Side Effects?}
    HasSideEffects -->|Yes| DocSideEffects[Document Side Effects]
    HasSideEffects -->|No| WriteExamples[Write Usage Examples]
    DocSideEffects --> WriteExamples
    WriteExamples --> ConsistencyCheck{Terminology Consistent?}
    ConsistencyCheck -->|No| FixTerminology[Unify Terminology]
    FixTerminology --> ConsistencyCheck
    ConsistencyCheck -->|Yes| SelfCheck{Self-Check Passed?}
    SelfCheck -->|Yes| End([End])
    SelfCheck -->|No| ImproveDoc[Improve Documentation]
    ImproveDoc --> SelfCheck

    style Start fill:#4CAF50,color:#fff
    style End fill:#4CAF50,color:#fff
    style MCPSchema fill:#2196F3,color:#fff
    style APISchema fill:#2196F3,color:#fff
    style CLISchema fill:#2196F3,color:#fff
    style FuncSchema fill:#2196F3,color:#fff
    style WritePurpose fill:#2196F3,color:#fff
    style WriteWhenToUse fill:#2196F3,color:#fff
    style WriteWhenNot fill:#2196F3,color:#fff
    style DocParams fill:#2196F3,color:#fff
    style FixParams fill:#2196F3,color:#fff
    style DocReturn fill:#2196F3,color:#fff
    style DocErrors fill:#2196F3,color:#fff
    style AddErrors fill:#2196F3,color:#fff
    style DocSideEffects fill:#2196F3,color:#fff
    style WriteExamples fill:#2196F3,color:#fff
    style FixTerminology fill:#2196F3,color:#fff
    style ImproveDoc fill:#2196F3,color:#fff
    style IdentifyType fill:#FF9800,color:#fff
    style ParamComplete fill:#FF9800,color:#fff
    style ErrorComplete fill:#FF9800,color:#fff
    style HasSideEffects fill:#FF9800,color:#fff
    style ConsistencyCheck fill:#FF9800,color:#fff
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
| Tool Type? | Inputs: tool_type (MCP, REST API, CLI, function) |
| Use MCP Schema Format | MCP Tool Schema section |
| Write Purpose: One Sentence | Documentation Checklist: Purpose |
| Write When To Use | Documentation Checklist: When to use |
| Write When NOT To Use | Documentation Checklist: When NOT to use |
| Document All Parameters | Documentation Checklist: Parameters |
| Each Param Has Type + Constraints + Example? | Parameter Documentation Format |
| Document Return Value | Documentation Checklist: Return value |
| Document Error Cases | Error Documentation section |
| All Error Cases Covered? | Error Documentation table (7 error categories) |
| Has Side Effects? | Documentation Checklist: Side effects |
| Write Usage Examples | Documentation Checklist: Examples |
| Terminology Consistent? | Anti-Patterns: Inconsistent terminology |
| Self-Check Passed? | Self-Check checklist |

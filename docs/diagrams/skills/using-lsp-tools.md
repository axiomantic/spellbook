<!-- diagram-meta: {"source": "skills/using-lsp-tools/SKILL.md", "source_hash": "sha256:761e585ed244000f52b4a794a7b8330ee36c45418327906680ae1fb89f8b0bdd", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: using-lsp-tools

Decision protocol for choosing LSP semantic tools versus text-based search, with fallback handling and workflow patterns for exploration, refactoring, and type debugging.

```mermaid
flowchart TD
    Start([Start: Code Query]) --> Analyze{Symbol or Literal?}

    Analyze -->|Symbol| LSPActive{LSP Server Active?}
    Analyze -->|Literal Text| UseGrep[Use Grep/Glob]

    LSPActive -->|Yes| TaskType{Task Type?}
    LSPActive -->|No| FallbackGrep[Fallback: Text Search]

    TaskType -->|Exploration| ExploreFlow
    TaskType -->|Refactoring| RefactorFlow
    TaskType -->|Type Debugging| TypeFlow
    TaskType -->|Call Analysis| CallFlow

    subgraph ExploreFlow[Exploration Workflow]
        E1[document_symbols] --> E2[hover: Types]
        E2 --> E3[definition: Jump]
        E3 --> E4[references: Usage]
    end

    subgraph RefactorFlow[Refactoring Workflow]
        R1[code_actions: Discover] --> R2{Rename Available?}
        R2 -->|Yes| R3[rename_symbol: Execute]
        R2 -->|No| R4[references: Assess Impact]
        R4 --> R5[Manual Multi-File Edit]
    end

    subgraph TypeFlow[Type Debugging Workflow]
        T1[hover: Inferred Type] --> T2[type_hierarchy: Inheritance]
        T2 --> T3[diagnostics: Errors]
    end

    subgraph CallFlow[Call Analysis Workflow]
        C1{Direction?}
        C1 -->|Who Calls This?| C2[call_hierarchy: Incoming]
        C1 -->|What Does It Call?| C3[call_hierarchy: Outgoing]
    end

    ExploreFlow --> ResultCheck
    RefactorFlow --> ResultCheck
    TypeFlow --> ResultCheck
    CallFlow --> ResultCheck

    ResultCheck{Results Empty?}
    ResultCheck -->|No| SelfCheck
    ResultCheck -->|Yes| FileSaved{File Saved to Disk?}

    FileSaved -->|No| SaveRetry[Save File + Retry]
    SaveRetry --> ResultCheck
    FileSaved -->|Yes| UseFallback[Use Table Fallback]

    UseFallback --> FallbackType{Fallback Method?}
    FallbackType -->|Definition| GrepDef[Grep: func/class/def X]
    FallbackType -->|References| GrepRef[Grep: Symbol Name]
    FallbackType -->|Understanding| ReadInfer[Read + Infer]
    FallbackType -->|Rename| ManualEdit[Manual Multi-File Edit]
    FallbackType -->|Outline| GrepDefs[Grep: Definitions]
    FallbackType -->|Persistent Failure| Unsupported[Feature Unsupported]

    GrepDef --> SelfCheck
    GrepRef --> SelfCheck
    ReadInfer --> SelfCheck
    ManualEdit --> SelfCheck
    GrepDefs --> SelfCheck
    UseGrep --> SelfCheck
    FallbackGrep --> SelfCheck

    SelfCheck{Self-Check Passed?}
    SelfCheck -->|Yes| Done([Done])
    SelfCheck -->|No| Reconsider[STOP: Reconsider Approach]

    style Start fill:#4CAF50,color:#fff
    style Done fill:#4CAF50,color:#fff
    style Analyze fill:#FF9800,color:#fff
    style LSPActive fill:#FF9800,color:#fff
    style TaskType fill:#FF9800,color:#fff
    style R2 fill:#FF9800,color:#fff
    style C1 fill:#FF9800,color:#fff
    style ResultCheck fill:#FF9800,color:#fff
    style FileSaved fill:#FF9800,color:#fff
    style FallbackType fill:#FF9800,color:#fff
    style SelfCheck fill:#f44336,color:#fff
    style Reconsider fill:#f44336,color:#fff
    style UseGrep fill:#2196F3,color:#fff
    style FallbackGrep fill:#2196F3,color:#fff
    style E1 fill:#2196F3,color:#fff
    style E2 fill:#2196F3,color:#fff
    style E3 fill:#2196F3,color:#fff
    style E4 fill:#2196F3,color:#fff
    style R1 fill:#2196F3,color:#fff
    style R3 fill:#2196F3,color:#fff
    style R4 fill:#2196F3,color:#fff
    style R5 fill:#2196F3,color:#fff
    style T1 fill:#2196F3,color:#fff
    style T2 fill:#2196F3,color:#fff
    style T3 fill:#2196F3,color:#fff
    style C2 fill:#2196F3,color:#fff
    style C3 fill:#2196F3,color:#fff
    style SaveRetry fill:#2196F3,color:#fff
    style UseFallback fill:#2196F3,color:#fff
    style GrepDef fill:#2196F3,color:#fff
    style GrepRef fill:#2196F3,color:#fff
    style ReadInfer fill:#2196F3,color:#fff
    style ManualEdit fill:#2196F3,color:#fff
    style GrepDefs fill:#2196F3,color:#fff
    style Unsupported fill:#2196F3,color:#fff
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
| Start: Code Query | Inputs: filePath, line, column, symbolName (lines 33-41) |
| Symbol or Literal? | Invariant Principle 2: LSP for Symbols, Grep for Strings (line 16) |
| LSP Server Active? | Analysis block: Is LSP server active for this language? (line 23) |
| Exploration Workflow | Workflows: Exploration sequence (line 92) |
| Refactoring Workflow | Workflows: Refactoring sequence (line 94) |
| Type Debugging Workflow | Workflows: Type debugging sequence (line 96) |
| Call Analysis Workflow | Workflows: Call analysis direction (line 98) |
| document_symbols | Tool Priority Matrix (line 59) |
| hover | Tool Priority Matrix (line 57) |
| definition | Tool Priority Matrix (line 55) |
| references | Tool Priority Matrix (line 56) |
| rename_symbol | Tool Priority Matrix (line 58) |
| call_hierarchy | Tool Priority Matrix (lines 60-61) |
| Results Empty? | Invariant Principle 3: Verify Before Fallback (line 17) |
| File Saved to Disk? | Fallback Protocol step 1: check file saved (line 112) |
| Use Table Fallback | Fallback Protocol step 2: try table fallback (line 113) |
| Feature Unsupported | Fallback Protocol step 3: persistent failure (line 114) |
| Self-Check Passed? | Self-Check checklist (lines 118-124) |

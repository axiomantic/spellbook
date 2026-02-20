<!-- diagram-meta: {"source": "commands/sharpen-improve.md", "source_hash": "sha256:28bb7d26310c6be28f7bbcc5fd0a0873f22158e69c1c6d35313eb740ce8a8d05", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: sharpen-improve

Rewrites ambiguous LLM prompts to eliminate guesswork. Runs an internal audit first, triages findings, asks clarifying questions when needed, applies sharpening patterns, and produces the improved prompt with a change log.

```mermaid
flowchart TD
    Start([Invoke /sharpen-improve]) --> Analysis[Pre-Improve Analysis]
    Analysis --> Phase1[Phase 1: Internal Audit]
    Phase1 --> RunAudit[Run /sharpen-audit Internally]

    RunAudit --> Phase2[Phase 2: Triage Findings]
    Phase2 --> TriageLoop{All Findings Triaged?}
    TriageLoop -->|No| ClassifyFinding{Resolvable?}
    ClassifyFinding -->|From context| InferAnswer[Infer + Note Source]
    ClassifyFinding -->|From convention| ApplyConvention[Apply Convention + Note]
    ClassifyFinding -->|Needs author| QueueQuestion[Queue Clarification]
    InferAnswer --> TriageLoop
    ApplyConvention --> TriageLoop
    QueueQuestion --> TriageLoop

    TriageLoop -->|Yes| NeedsClarification{Questions Queued?}

    NeedsClarification -->|Yes| Phase3[Phase 3: Clarification Round]
    Phase3 --> AskAuthor[Present Questions to Author]
    AskAuthor --> WaitResponse[Wait for Author Response]
    WaitResponse --> Phase4[Phase 4: Apply Sharpening]

    NeedsClarification -->|No| Phase4

    Phase4 --> SharpenLoop{All Findings Addressed?}
    SharpenLoop -->|No| LocateText[Locate Ambiguous Text]
    LocateText --> DraftReplacement[Draft Sharpened Text]
    DraftReplacement --> VerifyIntent{Intent Preserved?}
    VerifyIntent -->|No| ReviseReplacement[Revise Replacement]
    ReviseReplacement --> VerifyIntent
    VerifyIntent -->|Yes| LogChange[Log Change]
    LogChange --> SharpenLoop

    SharpenLoop -->|Yes| Phase5[Phase 5: Produce Outputs]
    Phase5 --> WritePrompt[Output 1: Sharpened Prompt]
    WritePrompt --> WriteChangeLog[Output 2: Change Log]
    WriteChangeLog --> WriteRemaining[Document Remaining Ambiguities]

    WriteRemaining --> Reflection[Post-Improve Reflection]
    Reflection --> Done([Improvement Complete])

    style Start fill:#2196F3,color:#fff
    style Done fill:#2196F3,color:#fff
    style TriageLoop fill:#FF9800,color:#fff
    style ClassifyFinding fill:#FF9800,color:#fff
    style NeedsClarification fill:#FF9800,color:#fff
    style SharpenLoop fill:#FF9800,color:#fff
    style VerifyIntent fill:#f44336,color:#fff
    style RunAudit fill:#4CAF50,color:#fff
    style Analysis fill:#2196F3,color:#fff
    style Phase1 fill:#2196F3,color:#fff
    style Phase2 fill:#2196F3,color:#fff
    style InferAnswer fill:#2196F3,color:#fff
    style ApplyConvention fill:#2196F3,color:#fff
    style QueueQuestion fill:#2196F3,color:#fff
    style Phase3 fill:#2196F3,color:#fff
    style AskAuthor fill:#2196F3,color:#fff
    style WaitResponse fill:#2196F3,color:#fff
    style Phase4 fill:#2196F3,color:#fff
    style LocateText fill:#2196F3,color:#fff
    style DraftReplacement fill:#2196F3,color:#fff
    style ReviseReplacement fill:#2196F3,color:#fff
    style LogChange fill:#2196F3,color:#fff
    style Phase5 fill:#2196F3,color:#fff
    style WritePrompt fill:#2196F3,color:#fff
    style WriteChangeLog fill:#2196F3,color:#fff
    style WriteRemaining fill:#2196F3,color:#fff
    style Reflection fill:#2196F3,color:#fff
```

## Legend

| Color | Meaning |
|-------|---------|
| Green (#4CAF50) | Skill invocation |
| Blue (#2196F3) | Command/action |
| Orange (#FF9800) | Decision point |
| Red (#f44336) | Quality gate |

<!-- diagram-meta: {"source": "skills/async-await-patterns/SKILL.md", "source_hash": "sha256:6804677e5d37765cd12045ece19c1ec90a2c8196c09764cd36375a2b940e6601", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: async-await-patterns

Decision and verification workflow for writing production-grade async/await code in JavaScript and TypeScript. Enforces disciplined async patterns over raw promises.

```mermaid
flowchart TD
    Start([Start]) --> IdentifyAsync{Is Operation Async?}
    IdentifyAsync -->|No| SyncCode[Write Synchronous Code]
    IdentifyAsync -->|Yes| MarkAsync[Mark Function async]
    SyncCode --> End([End])
    MarkAsync --> AddAwait[Add await To All Promises]
    AddAwait --> WrapTryCatch[Wrap In try-catch]
    WrapTryCatch --> CheckDeps{Operations Independent?}
    CheckDeps -->|Yes| UsePromiseAll[Use Promise.all]
    CheckDeps -->|No| SequentialAwait[Sequential await Chain]
    CheckDeps -->|Fault Tolerant| UseAllSettled[Use Promise.allSettled]
    UsePromiseAll --> CheckMixing{Pattern Mixing?}
    SequentialAwait --> CheckMixing
    UseAllSettled --> CheckMixing
    CheckMixing -->|.then/.catch Found| RewriteAwait[Rewrite As async/await]
    CheckMixing -->|Clean| CheckErrors{Error Handling Present?}
    RewriteAwait --> CheckErrors
    CheckErrors -->|No try-catch| AddErrorHandling[Add Typed Error Handling]
    CheckErrors -->|Yes| CheckMissing{Missing await?}
    AddErrorHandling --> CheckMissing
    CheckMissing -->|Promise Not Awaited| FixMissing[Add Missing await]
    CheckMissing -->|All Awaited| SelfCheck{Self-Check Passed?}
    FixMissing --> SelfCheck
    SelfCheck -->|All Items Checked| End
    SelfCheck -->|Items Unchecked| Rewrite[STOP: Rewrite Code]
    Rewrite --> MarkAsync

    style Start fill:#4CAF50,color:#fff
    style End fill:#4CAF50,color:#fff
    style SyncCode fill:#2196F3,color:#fff
    style MarkAsync fill:#2196F3,color:#fff
    style AddAwait fill:#2196F3,color:#fff
    style WrapTryCatch fill:#2196F3,color:#fff
    style UsePromiseAll fill:#2196F3,color:#fff
    style SequentialAwait fill:#2196F3,color:#fff
    style UseAllSettled fill:#2196F3,color:#fff
    style RewriteAwait fill:#2196F3,color:#fff
    style AddErrorHandling fill:#2196F3,color:#fff
    style FixMissing fill:#2196F3,color:#fff
    style Rewrite fill:#2196F3,color:#fff
    style IdentifyAsync fill:#FF9800,color:#fff
    style CheckDeps fill:#FF9800,color:#fff
    style CheckMixing fill:#FF9800,color:#fff
    style CheckErrors fill:#FF9800,color:#fff
    style CheckMissing fill:#FF9800,color:#fff
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
| Is Operation Async? | Required Reasoning: Step 1 |
| Mark Function async | Invariant Principle 1: Explicit async boundary |
| Add await To All Promises | Invariant Principle 2: Await ALL promises |
| Wrap In try-catch | Invariant Principle 3: Structured error handling |
| Operations Independent? | Invariant Principle 5: Parallelism via combinators |
| Use Promise.all | Parallel vs Sequential section |
| Sequential await Chain | Parallel vs Sequential section |
| Use Promise.allSettled | Parallel vs Sequential: Fault-tolerant |
| Pattern Mixing? | Invariant Principle 4: Pattern consistency |
| Rewrite As async/await | Forbidden Pattern 5: Mixing Async/Await with Promise Chains |
| Error Handling Present? | Forbidden Pattern 4: Missing Error Handling |
| Add Typed Error Handling | Complete Real-World Example: catch block |
| Missing await? | Forbidden Pattern 2: Forgetting await Keyword |
| Self-Check Passed? | Self-Check reflection checklist |
| STOP: Rewrite Code | Self-Check: "If NO to ANY item: STOP. Rewrite" |

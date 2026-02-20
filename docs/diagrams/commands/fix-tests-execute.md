<!-- diagram-meta: {"source": "commands/fix-tests-execute.md", "source_hash": "sha256:aa194f2d3ce068e2929357bf1828d6e42dd6d8b35cd46d62b3c2ca1ae8cd454d", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: fix-tests-execute

Execute test fixes by priority: investigate each work item, classify the fix type, apply the fix, verify it catches the original blind spot, and commit independently.

```mermaid
flowchart TD
  Start([Start: Work items parsed]) --> PickItem[Pick next by priority]

  style Start fill:#4CAF50,color:#fff
  style PickItem fill:#2196F3,color:#fff

  PickItem --> ReadTest[Read test file]

  style ReadTest fill:#2196F3,color:#fff

  ReadTest --> ReadProd[Read production code]

  style ReadProd fill:#2196F3,color:#fff

  ReadProd --> Analyze[Analyze what is wrong]

  style Analyze fill:#2196F3,color:#fff

  Analyze --> ClassifyFix{Fix type?}

  style ClassifyFix fill:#FF9800,color:#000

  ClassifyFix -->|Weak assertions| Strengthen[Strengthen assertions]
  ClassifyFix -->|Missing edge case| AddEdge[Add test cases]
  ClassifyFix -->|Wrong expectations| CorrectExp[Correct expectations]
  ClassifyFix -->|Broken setup| FixSetup[Fix setup/teardown]
  ClassifyFix -->|Flaky timing| FixFlaky[Fix isolation]
  ClassifyFix -->|Tests internals| Rewrite[Rewrite for behavior]
  ClassifyFix -->|Production bug| StopReport[STOP and report bug]

  style Strengthen fill:#2196F3,color:#fff
  style AddEdge fill:#2196F3,color:#fff
  style CorrectExp fill:#2196F3,color:#fff
  style FixSetup fill:#2196F3,color:#fff
  style FixFlaky fill:#2196F3,color:#fff
  style Rewrite fill:#2196F3,color:#fff
  style StopReport fill:#f44336,color:#fff

  Strengthen --> RunTest[Run fixed test]
  AddEdge --> RunTest
  CorrectExp --> RunTest
  FixSetup --> RunTest
  FixFlaky --> RunTest
  Rewrite --> RunTest

  style RunTest fill:#2196F3,color:#fff

  RunTest --> TestPass{Test passes?}

  style TestPass fill:#FF9800,color:#000

  TestPass -->|No| Analyze
  TestPass -->|Yes| RunFile[Run entire test file]

  style RunFile fill:#2196F3,color:#fff

  RunFile --> FilePass{File tests pass?}

  style FilePass fill:#FF9800,color:#000

  FilePass -->|No| FixSideEffect[Fix side effects]
  FilePass -->|Yes| CatchGate{Fix catches blind spot?}

  style FixSideEffect fill:#2196F3,color:#fff
  style CatchGate fill:#f44336,color:#fff

  FixSideEffect --> RunFile

  CatchGate -->|No| Analyze
  CatchGate -->|Yes| Commit[Commit fix]

  style Commit fill:#2196F3,color:#fff

  Commit --> MoreItems{More work items?}

  style MoreItems fill:#FF9800,color:#000

  MoreItems -->|Yes| PickItem
  MoreItems -->|No| End([End: All fixes applied])

  StopReport --> End

  style End fill:#4CAF50,color:#fff
```

## Legend

| Color | Meaning |
|-------|---------|
| Green (#4CAF50) | Skill invocation |
| Blue (#2196F3) | Command/action |
| Orange (#FF9800) | Decision point |
| Red (#f44336) | Quality gate |

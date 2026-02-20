# /fix-tests-parse

## Workflow Diagram

# Diagram: fix-tests-parse

Parse audit reports or test failure output into structured work items, honor dependency ordering from remediation plans, and select a commit strategy before execution begins.

```mermaid
flowchart TD
  Start([Start: Audit report input]) --> DetectFormat{YAML block present?}

  style Start fill:#4CAF50,color:#fff
  style DetectFormat fill:#FF9800,color:#000

  DetectFormat -->|Yes| ParseYAML[Parse YAML findings]
  DetectFormat -->|No| FallbackParse[Fallback: split by headers]

  style ParseYAML fill:#2196F3,color:#fff
  style FallbackParse fill:#2196F3,color:#fff

  ParseYAML --> ExtractFields[Extract id, priority, file, pattern]

  style ExtractFields fill:#2196F3,color:#fff

  FallbackParse --> SplitHeaders[Split by Finding headers]

  style SplitHeaders fill:#2196F3,color:#fff

  SplitHeaders --> ExtractFallback[Extract file, line, pattern]

  style ExtractFallback fill:#2196F3,color:#fff

  ExtractFields --> ParseRemPlan{Remediation plan exists?}

  style ParseRemPlan fill:#FF9800,color:#000

  ParseRemPlan -->|Yes| ReadPhases[Read phase ordering]
  ParseRemPlan -->|No| SortPriority[Sort by priority only]

  style ReadPhases fill:#2196F3,color:#fff
  style SortPriority fill:#2196F3,color:#fff

  ExtractFallback --> SortPriority

  ReadPhases --> HonorDeps[Honor depends_on fields]

  style HonorDeps fill:#2196F3,color:#fff

  HonorDeps --> BuildItems[Build work items list]
  SortPriority --> BuildItems

  style BuildItems fill:#2196F3,color:#fff

  BuildItems --> ParseGate{All items parsed?}

  style ParseGate fill:#f44336,color:#fff

  ParseGate -->|No| FixParse[Re-parse failed items]
  ParseGate -->|Yes| OrderItems[Order: critical > important > minor]

  style FixParse fill:#2196F3,color:#fff
  style OrderItems fill:#2196F3,color:#fff

  FixParse --> ParseGate

  OrderItems --> AskCommit{Commit strategy?}

  style AskCommit fill:#FF9800,color:#000

  AskCommit -->|A| PerFix[Per-fix commits]
  AskCommit -->|B| BatchFile[Batch by file]
  AskCommit -->|C| SingleCommit[Single commit]

  style PerFix fill:#2196F3,color:#fff
  style BatchFile fill:#2196F3,color:#fff
  style SingleCommit fill:#2196F3,color:#fff

  PerFix --> End([End: Work items ready])
  BatchFile --> End
  SingleCommit --> End

  style End fill:#4CAF50,color:#fff
```

## Legend

| Color | Meaning |
|-------|---------|
| Green (#4CAF50) | Skill invocation |
| Blue (#2196F3) | Command/action |
| Orange (#FF9800) | Decision point |
| Red (#f44336) | Quality gate |

## Command Content

``````````markdown
# Phase 0: Input Processing

## Invariant Principles

1. **Honor dependency order** - Work items with `depends_on` fields must be resolved in the order specified by the remediation plan
2. **Parse completely before acting** - All YAML findings must be parsed and work items built before any fix execution begins
3. **Priority drives execution order** - Critical findings are processed before important, important before minor; never reorder for convenience

## For audit_report mode

Parse YAML block between `---` markers:

```yaml
findings:
  - id: "finding-1"
    priority: critical
    test_file: "tests/test_auth.py"
    test_function: "test_login_success"
    line_number: 45
    pattern: 2
    pattern_name: "Partial Assertions"
    blind_spot: "Login could return malformed user object"
    depends_on: []

remediation_plan:
  phases:
    - phase: 1
      findings: ["finding-1"]
```

Use `remediation_plan.phases` for execution order. Honor `depends_on` dependencies.

**Fallback parsing** (if no YAML block):
1. Split by `**Finding #N:**` headers
2. Extract priority from section header
3. Parse file/line from `**File:**`
4. Extract pattern from `**Pattern:**`
5. Extract code blocks for current_code, suggested_fix
6. Extract blind_spot from `**Blind Spot:**`

## Commit strategy (optional ask)

A) Per-fix (recommended) - each fix separate commit
B) Batch by file
C) Single commit

Default to (A).
``````````

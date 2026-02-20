# /review-plan-inventory

## Workflow Diagram

# Diagram: review-plan-inventory

Phase 1 of reviewing-impl-plans: establishes context by checking for a parent design document, inventories all work items with parallel/sequential classification, audits setup/skeleton requirements, and flags cross-track interface dependencies.

```mermaid
flowchart TD
    Start([Start Phase 1]) --> CheckDesign{Parent Design Doc?}

    CheckDesign -->|Yes| LogDesign[Log Design Doc Location]
    CheckDesign -->|No| JustifyNo[Require Justification]

    LogDesign --> MoreDetail{Plan Has More Detail?}
    JustifyNo --> RiskUp[Increase Risk Level]

    MoreDetail -->|Yes| Inventory[Inventory Work Items]
    MoreDetail -->|No| FlagGap[Flag Detail Gap]
    RiskUp --> Inventory
    FlagGap --> Inventory

    Inventory --> Classify[Classify Each Item]

    Classify --> IsParallel{Parallel or Sequential?}

    IsParallel -->|Parallel| LogPar[Log Parallel Item]
    IsParallel -->|Sequential| LogSeq[Log Sequential Item]

    LogPar --> RecordDeps[Record Dependencies]
    LogSeq --> RecordBlocks[Record Blocks/Blocked-By]

    RecordDeps --> MoreItems{More Work Items?}
    RecordBlocks --> MoreItems

    MoreItems -->|Yes| Classify
    MoreItems -->|No| Setup[Audit Setup/Skeleton]

    Setup --> GitRepo[Check Git Structure]
    GitRepo --> Config[Check Config Files]
    Config --> Types[Check Shared Types]
    Types --> Stubs[Check Interface Stubs]
    Stubs --> BuildTest[Check Build/Test Infra]

    BuildTest --> CrossTrack[Identify Cross-Track Interfaces]
    CrossTrack --> GateAll{All Items Classified?}

    GateAll -->|Yes| Deliver[Deliver Inventory Report]
    GateAll -->|No| Classify

    Deliver --> Done([Phase 1 Complete])

    style Start fill:#2196F3,color:#fff
    style Done fill:#2196F3,color:#fff
    style CheckDesign fill:#FF9800,color:#fff
    style LogDesign fill:#2196F3,color:#fff
    style JustifyNo fill:#2196F3,color:#fff
    style MoreDetail fill:#FF9800,color:#fff
    style RiskUp fill:#f44336,color:#fff
    style Inventory fill:#2196F3,color:#fff
    style Classify fill:#2196F3,color:#fff
    style IsParallel fill:#FF9800,color:#fff
    style LogPar fill:#2196F3,color:#fff
    style LogSeq fill:#2196F3,color:#fff
    style RecordDeps fill:#2196F3,color:#fff
    style RecordBlocks fill:#2196F3,color:#fff
    style MoreItems fill:#FF9800,color:#fff
    style Setup fill:#2196F3,color:#fff
    style GitRepo fill:#2196F3,color:#fff
    style Config fill:#2196F3,color:#fff
    style Types fill:#2196F3,color:#fff
    style Stubs fill:#2196F3,color:#fff
    style BuildTest fill:#2196F3,color:#fff
    style CrossTrack fill:#f44336,color:#fff
    style FlagGap fill:#2196F3,color:#fff
    style GateAll fill:#f44336,color:#fff
    style Deliver fill:#2196F3,color:#fff
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
# Phase 1: Context and Inventory

You are executing Phase 1 of the implementation plan review. Your job is to establish context and inventory all work items, their classification, and setup requirements.

## Invariant Principles

1. **Design doc anchors confidence** - Plans with a parent design document have higher baseline trust; plans without require justification
2. **Classify before scheduling** - Every work item must be tagged as parallel or sequential before execution ordering begins
3. **Interfaces between parallel tracks are the highest risk** - Identify and flag every cross-track dependency

<analysis>
For each element, trace reasoning:
- Does parent design doc exist? (Higher confidence if yes)
- What work items are parallel vs sequential?
- What setup/skeleton work must complete first?
- What interfaces exist between parallel tracks?
</analysis>

## Parent Design Document

| Element | Status | Notes |
|---------|--------|-------|
| Has parent design doc | YES / NO | |
| Location | [path] or N/A | |
| Impl plan has MORE detail | YES / NO | Each design section must be elaborated |

If NO parent doc: justification required, risk level increases.

## Plan Inventory

| Element | Count | Notes |
|---------|-------|-------|
| Total work items | | |
| Sequential items | | Blocked by dependencies |
| Parallel items | | Can execute concurrently |
| Interfaces between parallel work | | CRITICAL: every one needs complete contract |

## Setup/Skeleton Work

Must complete before parallel execution:

| Item | Specified | Must Complete Before |
|------|-----------|---------------------|
| Git repository structure | Y/N | |
| Config files | Y/N | |
| Shared type definitions | Y/N | |
| Interface stubs | Y/N | |
| Build/test infrastructure | Y/N | |

## Work Item Classification

For EACH parallel work item:
```
Work Item: [name]
Classification: PARALLEL
Can run alongside: [list]
Requires worktree: YES/NO
Interface dependencies: [list]
```

For EACH sequential work item:
```
Work Item: [name]
Classification: SEQUENTIAL
Blocked by: [list]
Blocks: [list]
Reason: [why can't be parallel]
```

## Deliverable

Populate the following sections of the review report:
- Parent design doc status
- Work item counts (total, parallel, sequential)
- Interface count between parallel work
- Setup/skeleton work gaps

Return your completed inventory as structured output for the orchestrator.
``````````

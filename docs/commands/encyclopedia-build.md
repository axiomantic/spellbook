# /encyclopedia-build

## Workflow Diagram

# Diagram: encyclopedia-build

Build encyclopedia content: glossary, architecture skeleton, decision log, and entry points (Phases 2-5).

```mermaid
flowchart TD
    Start([Start]) --> P2[Phase 2: Glossary]
    P2 --> ScanTerms[Scan Project-Specific Terms]
    ScanTerms --> FilterGeneric{Generic Term?}
    FilterGeneric -->|Yes| Skip[Skip Term]
    FilterGeneric -->|No| AddGlossary[Add to Glossary Table]
    Skip --> MoreTerms{More Terms?}
    AddGlossary --> MoreTerms
    MoreTerms -->|Yes| ScanTerms
    MoreTerms -->|No| P3[Phase 3: Architecture]
    P3 --> IdentifyComponents[Identify 3-5 Components]
    IdentifyComponents --> MapFlows[Map Data Flows]
    MapFlows --> NodeCheck{Nodes <= 7?}
    NodeCheck -->|No| Simplify[Simplify Diagram]
    Simplify --> NodeCheck
    NodeCheck -->|Yes| DrawMermaid[Create Mermaid Diagram]
    DrawMermaid --> P4[Phase 4: Decision Log]
    P4 --> FindDecisions[Find Architectural Decisions]
    FindDecisions --> RecordWhy[Record WHY Not WHAT]
    RecordWhy --> Alternatives[Document Alternatives]
    Alternatives --> P5[Phase 5: Entry Points]
    P5 --> MapEntries[Map Entry Points]
    MapEntries --> DocTesting[Document Testing Commands]
    DocTesting --> Done([End])

    style Start fill:#4CAF50,color:#fff
    style Done fill:#4CAF50,color:#fff
    style FilterGeneric fill:#FF9800,color:#fff
    style MoreTerms fill:#FF9800,color:#fff
    style NodeCheck fill:#f44336,color:#fff
    style P2 fill:#2196F3,color:#fff
    style P3 fill:#2196F3,color:#fff
    style P4 fill:#2196F3,color:#fff
    style P5 fill:#2196F3,color:#fff
    style ScanTerms fill:#2196F3,color:#fff
    style AddGlossary fill:#2196F3,color:#fff
    style IdentifyComponents fill:#2196F3,color:#fff
    style MapFlows fill:#2196F3,color:#fff
    style DrawMermaid fill:#2196F3,color:#fff
    style FindDecisions fill:#2196F3,color:#fff
    style RecordWhy fill:#2196F3,color:#fff
    style Alternatives fill:#2196F3,color:#fff
    style MapEntries fill:#2196F3,color:#fff
    style DocTesting fill:#2196F3,color:#fff
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
# Encyclopedia Build (Phases 2-5)

## Invariant Principles

1. **Project-specific terms only** - Generic programming terms do not belong in the glossary; include only terms that would confuse a new contributor to this specific project
2. **Architecture over implementation** - Capture system structure and boundaries, not implementation details that change frequently
3. **Decisions record WHY, not WHAT** - The decision log explains rationale and rejected alternatives, not just the chosen approach

## Phase 2: Glossary Construction

Identify project-specific terms that:
- Appear frequently in code/docs
- Have meanings specific to this project
- Would confuse a new contributor

**Format:**
```markdown
## Glossary

| Term | Definition | Location |
|------|------------|----------|
| worktree | Isolated git working directory for parallel development | `skills/using-git-worktrees/` |
| project-encoded | Path with leading `/` removed, `/` replaced with `-` | CLAUDE.md |
```

<RULE>
Only include terms that aren't obvious from general programming knowledge.
"API" doesn't need definition. "WorkPacket" in this codebase does.
</RULE>

## Phase 3: Architecture Skeleton

Create minimal mermaid diagram showing:
- 3-5 key components (not every file)
- Primary data flows
- External boundaries (APIs, databases, services)

```markdown
## Architecture

```mermaid
graph TD
    CLI[CLI Entry] --> Core[Core Engine]
    Core --> Storage[(Storage Layer)]
    Core --> External[External APIs]
```

**Key boundaries:**
- CLI handles user interaction only
- Core contains all business logic
- Storage is abstracted behind interfaces
```

<FORBIDDEN>
- Diagrams with more than 7 nodes (too detailed)
- Including internal implementation structure
- Showing every file or class
</FORBIDDEN>

## Phase 4: Decision Log

Document WHY decisions were made, not just WHAT exists.

```markdown
## Decisions

| Decision | Alternatives Considered | Rationale | Date |
|----------|------------------------|-----------|------|
| SQLite over PostgreSQL | Postgres, MySQL | Single-file deployment, no server | 2024-01 |
| Monorepo structure | Multi-repo | Shared tooling, atomic commits | 2024-02 |
```

<RULE>
Decisions are stable. Past choices don't change. This section ages well.
Only add decisions that would surprise a newcomer or that you had to discover.
</RULE>

## Phase 5: Entry Points & Testing

```markdown
## Entry Points

| Entry | Path | Purpose |
|-------|------|---------|
| Main CLI | `src/cli.py` | Primary user interface |
| API Server | `src/server.py` | REST API for integrations |
| Worker | `src/worker.py` | Background job processor |

## Testing

- **Command**: `uv run pytest tests/`
- **Framework**: pytest with fixtures in `conftest.py`
- **Coverage**: `uv run pytest --cov=src tests/`
- **Key patterns**: Factory fixtures, mock external APIs
```
``````````

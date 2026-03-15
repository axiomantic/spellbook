# /encyclopedia-build

## Workflow Diagram

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
> **DEPRECATED (v0.23.0):** This command is deprecated. Project knowledge now belongs in `AGENTS.md` files within the project repository. See the "Project Knowledge (AGENTS.md)" section in AGENTS.spellbook.md. This command will be removed in a future version.

<ROLE>
Encyclopedia Architect. Your reputation depends on producing content that is accurate, concise, and durable. Over-detailed encyclopedias become stale and ignored. Vague ones mislead. Your output will be the first document a new contributor reads.
</ROLE>

# Encyclopedia Build (Phases 2-5)

## Invariant Principles

1. **Project-specific terms only** - Include only terms with project-specific meaning that would confuse a new contributor; skip general programming vocabulary.
2. **Architecture over implementation** - Capture system structure and boundaries, not implementation details.
3. **Decisions record WHY, not WHAT** - Record rationale and rejected alternatives, not just the chosen approach.

<FORBIDDEN>
- Glossary terms obvious from general programming knowledge ("API", "function")
- Diagrams with more than 7 nodes, internal implementation structure, or every file/class
- Decision log entries that state only WHAT was chosen without WHY
</FORBIDDEN>

**If a phase yields nothing:** Write the section header and `*[Section name]: nothing identified.*` rather than omitting the section.

## Phase 2: Glossary Construction

Identify project-specific terms used in 3+ files or contexts with project-specific meaning that would confuse a new contributor.

**Format:**
```markdown
## Glossary

| Term | Definition | Location |
|------|------------|----------|
| worktree | Isolated git working directory for parallel development | `skills/using-git-worktrees/` |
| project-encoded | Path with leading `/` removed, `/` replaced with `-` | CLAUDE.md |
```

<RULE>
"API" doesn't need definition. "WorkPacket" in this codebase does.
</RULE>

## Phase 3: Architecture Skeleton

Create a minimal mermaid diagram showing 3-5 key components, primary data flows, and external boundaries (APIs, databases, services).

**Format:**
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

## Phase 4: Decision Log

Document WHY decisions were made. Include only decisions that were non-obvious or that you had to discover by reading the codebase.

**Format:**
```markdown
## Decisions

| Decision | Alternatives Considered | Rationale | Date |
|----------|------------------------|-----------|------|
| SQLite over PostgreSQL | Postgres, MySQL | Single-file deployment, no server | 2024-01 |
| Monorepo structure | Multi-repo | Shared tooling, atomic commits | 2024-02 |
```

<RULE>
Decisions are stable. Record choices that would surprise a newcomer.
</RULE>

## Phase 5: Entry Points & Testing

**Format:**
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

<FINAL_EMPHASIS>
An encyclopedia that is too detailed becomes unmaintainable. An encyclopedia too vague is useless. Every entry earns its place; every omission is deliberate. New contributors depend on what you produce here.
</FINAL_EMPHASIS>
``````````

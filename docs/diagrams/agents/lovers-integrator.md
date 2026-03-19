<!-- diagram-meta: {"source": "agents/lovers-integrator.md","source_hash": "sha256:8385a0a2ef5e95448c7ad96ab4360088b31d6ccca48b4b73c9c20ff5e320d759","generated_at": "2026-03-19T00:00:00Z","generator": "generating-diagrams skill"} -->
# Diagram: lovers-integrator

Integration harmony agent. Reviews connections between modules, ensures API contracts align, flags anti-patterns at boundaries, and produces a harmony report with concrete proposals.

## Overview: Integration Review Workflow

```mermaid
flowchart TD
    subgraph Legend
        direction LR
        L1[Process]
        L2{Decision}
        L3([Terminal]):::success
        L4[Quality Gate]:::gate
        L5[Anti-Pattern Flag]:::antipattern
    end

    Start([Agent Invoked]) --> ValidateInputs{Required inputs<br>provided?}
    ValidateInputs -->|"No: missing modules<br>or interfaces"| Reject([Reject: missing<br>required inputs])
    ValidateInputs -->|Yes| Honor[Honor-Bound<br>Invocation]

    Honor --> EnumInterfaces[Enumerate all<br>interfaces between<br>provided modules]

    EnumInterfaces --> ForEach{More interfaces<br>to review?}

    ForEach -->|Yes| Identify[Step 1: Identify<br>caller and callee]
    Identify --> MapData[Step 2: Map data<br>crossing boundary]
    MapData --> CheckTypes{Step 3: Do types<br>match exactly?}

    CheckTypes -->|No| TypeMismatch[Flag: Type Mismatch<br>CRITICAL]:::antipattern
    CheckTypes -->|Yes| VerifyErrors

    TypeMismatch --> VerifyErrors{Step 4: Error handling<br>consistent both sides?}

    VerifyErrors -->|No| ErrorAmnesia[Flag: Error Amnesia<br>CRITICAL]:::antipattern
    VerifyErrors -->|Yes| AssessComplexity

    ErrorAmnesia --> AssessComplexity{Step 5: Simple<br>or Complex?}

    AssessComplexity -->|"Simple: 1-3 params,<br>no shared state"| Metaphor
    AssessComplexity -->|"Complex: 4+ params,<br>shared state"| AntiPatterns

    subgraph AntiPatterns[Anti-Pattern Detection]
        AP_Chatty{Chatty<br>Interface?}
        AP_God{God Object<br>coupling?}
        AP_Leaky{Leaky<br>Abstraction?}
        AP_Drift{Version<br>Drift?}

        AP_Chatty -->|Yes| Flag_Chatty[Flag: Chatty]:::antipattern
        AP_Chatty -->|No| AP_God
        Flag_Chatty --> AP_God
        AP_God -->|Yes| Flag_God[Flag: God Object]:::antipattern
        AP_God -->|No| AP_Leaky
        Flag_God --> AP_Leaky
        AP_Leaky -->|Yes| Flag_Leaky[Flag: Leaky Abstraction]:::antipattern
        AP_Leaky -->|No| AP_Drift
        Flag_Leaky --> AP_Drift
        AP_Drift -->|Yes| Flag_Drift[Flag: Version Drift]:::antipattern
        AP_Drift -->|No| AP_Done([Done])
        Flag_Drift --> AP_Done
    end

    AntiPatterns --> Metaphor

    subgraph Metaphor[Metaphor Analysis: Modules as Conversation]
        M_Translate{Need adapters<br>/ translators?}
        M_Volume{API complexity<br>matches needs?}
        M_Assumptions{Misaligned<br>assumptions?}

        M_Translate -->|Yes| Flag_Adapter[Flag: Missing<br>Adapter]:::antipattern
        M_Translate -->|No| M_Volume
        Flag_Adapter --> M_Volume
        M_Volume -->|Mismatched| Flag_Over[Flag: Over-Engineered<br>Interface]:::antipattern
        M_Volume -->|Matched| M_Assumptions
        Flag_Over --> M_Assumptions
        M_Assumptions -->|Yes| Flag_Assume[Flag: Assumption<br>Drift]:::antipattern
        M_Assumptions -->|No| M_Done([Done])
        Flag_Assume --> M_Done
    end

    Metaphor --> ScoreInterface[Score interface:<br>Good / Friction / Critical]
    ScoreInterface --> RecordInterface[Record in<br>report table]
    RecordInterface --> ForEach

    ForEach -->|"No: all interfaces<br>reviewed"| ReflectionGate

    subgraph ReflectionGate[Reflection Quality Gate]
        R1{Every interface<br>reviewed?}:::gate
        R2{All friction points<br>have severity?}:::gate
        R3{Proposals concrete<br>with evidence?}:::gate
        R4{Improvements preserve<br>existing functionality?}:::gate

        R1 -->|Yes| R2
        R2 -->|No| FixSeverity[Assign severity:<br>Critical / Important /<br>Suggestion]
        FixSeverity --> R2
        R2 -->|Yes| R3
        R3 -->|No| GatherEvidence[Gather code evidence<br>for both sides]
        GatherEvidence --> R3
        R3 -->|Yes| R4
        R4 -->|No| ReviseProposals[Revise proposals<br>to preserve behavior]
        ReviseProposals --> R4
        R4 -->|Yes| GatePass([Gate Passed]):::success
    end

    ReflectionGate --> GenerateReport

    subgraph GenerateReport[Generate Outputs]
        Report[harmony_report:<br>Integration quality<br>assessment]
        Friction[friction_points:<br>Issues with severity]
        Proposals[proposals:<br>PROPOSE speech acts<br>with evidence]
        Coherence[System Coherence<br>Assessment]

        Report --> Friction --> Proposals --> Coherence
    end

    GenerateReport --> Done([Integration Review<br>Complete]):::success

    classDef gate fill:#ff6b6b,stroke:#333,color:#fff
    classDef antipattern fill:#ff6b6b,stroke:#333,color:#fff
    classDef success fill:#51cf66,stroke:#333,color:#fff
```

## Cross-Reference

| Node | Source Lines | Description |
|------|-------------|-------------|
| Honor-Bound Invocation | 13-15 | Agent recites commitment to rigor and boundary advocacy |
| Step 1: Identify caller/callee | 53 | Analysis protocol step 1 |
| Step 2: Map data crossing boundary | 54 | Analysis protocol step 2 |
| Step 3: Types match exactly? | 55 | Analysis protocol step 3, explicitly "not close enough" |
| Step 4: Error handling consistent? | 56 | Analysis protocol step 4, check both sides |
| Step 5: Simple or Complex? | 57-58 | 1-3 params = simple; 4+ params or shared state = complex |
| Metaphor Analysis | 61-66 | Modules as people in conversation: translators, volume, assumptions |
| Anti-Pattern Detection | 106-118 | 6 FORBIDDEN patterns: Type Mismatch, Error Amnesia, Chatty, God Object, Leaky Abstraction, Version Drift |
| Reflection Quality Gate | 69-75 | 4 checks before proposals: completeness, severity, concreteness, preservation |
| harmony_report | 80-88 | Interfaces Reviewed table with Harmony Scores |
| friction_points | 91-97 | Per-finding: boundary, issue, evidence, proposal |
| proposals | 97-100 | PROPOSE speech acts for key improvements |
| System Coherence Assessment | 100-101 | 2-3 sentences on overall integration health |

## Key Design Notes

- **No subagent dispatches**: Agent uses read-only tools (Read, Grep, Glob) and produces a report directly.
- **Strict ordering**: All interfaces must be reviewed before any proposals (FORBIDDEN: "Proposing improvements before reviewing all interfaces").
- **Evidence requirement**: Every friction point requires code from both sides of the boundary (FORBIDDEN: "Abstract proposals without evidence").
- **Harmony scoring**: Three levels -- Good (aligned types, consistent errors, simple), Friction (minor misalignment or complexity), Critical (type mismatch or missing error handling).
- **Six anti-patterns**: Type Mismatch, Error Amnesia, Chatty Interface, God Object, Leaky Abstraction, Version Drift.

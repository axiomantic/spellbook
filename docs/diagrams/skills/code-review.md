<!-- diagram-meta: {"source": "skills/code-review/SKILL.md", "source_hash": "sha256:f91840caa91900a230dff1fcfe64cc56510bef88d8934391ae7c9ab56a7017e5", "generated_at": "2026-03-10T06:21:33Z", "generator": "generate_diagrams.py"} -->
# Diagram: code-review

## Overview

```mermaid
flowchart TD
    START([Code Review<br/>Invoked]) --> PARSE[Parse Mode Flags]
    PARSE --> ROUTER{Mode Router}

    ROUTER -->|"--self or default"| SELF[Self Mode]
    ROUTER -->|"--feedback, -f"| FEEDBACK[Feedback Mode]
    ROUTER -->|"--give target"| GIVE[Give Mode]
    ROUTER -->|"--audit scope"| AUDIT[Audit Mode]

    SELF --> TAROT_CHECK{--tarot flag?}
    FEEDBACK --> TAROT_CHECK
    GIVE --> TAROT_CHECK
    AUDIT --> TAROT_CHECK

    TAROT_CHECK -->|Yes| TAROT[Tarot Roundtable<br/>Persona Overlay]
    TAROT_CHECK -->|No| OUTPUT
    TAROT --> OUTPUT([Findings + Status])

    subgraph Legend
        L1[Process Step]
        L2{Decision Point}
        L3([Terminal])
    end

    style SELF fill:#4a9eff,color:#fff
    style FEEDBACK fill:#4a9eff,color:#fff
    style GIVE fill:#4a9eff,color:#fff
    style AUDIT fill:#4a9eff,color:#fff
    style TAROT fill:#c084fc,color:#fff
    style OUTPUT fill:#51cf66,color:#fff
    style START fill:#51cf66,color:#fff
```

## Self Mode (`--self`)

```mermaid
flowchart TD
    S_START([Self Mode Entry]) --> S_DIFF["Get diff from<br/>merge-base"]
    S_DIFF --> S_MEMORY["Memory Priming:<br/>memory_recall()"]
    S_MEMORY --> S_PASS1["Pass 1: Logic"]
    S_PASS1 --> S_PASS2["Pass 2: Integration"]
    S_PASS2 --> S_PASS3["Pass 3: Security"]
    S_PASS3 --> S_PASS4["Pass 4: Style"]
    S_PASS4 --> S_FINDINGS["Generate findings<br/>with severity + file:line"]
    S_FINDINGS --> S_PERSIST["Persist significant<br/>findings via memory_store"]
    S_PERSIST --> S_GATE{Severity Gate}
    S_GATE -->|"Critical found"| S_FAIL([FAIL])
    S_GATE -->|"Important found"| S_WARN([WARN])
    S_GATE -->|"Minor only"| S_PASS([PASS])

    style S_START fill:#51cf66,color:#fff
    style S_GATE fill:#ff6b6b,color:#fff
    style S_FAIL fill:#ff6b6b,color:#fff
    style S_WARN fill:#fbbf24,color:#000
    style S_PASS fill:#51cf66,color:#fff
```

## Feedback Mode (`--feedback`)

```mermaid
flowchart TD
    F_START([Feedback Mode Entry]) --> F_GATHER["Gather ALL feedback<br/>across related PRs"]
    F_GATHER --> F_CAT["Categorize each item:<br/>bug/style/question/<br/>suggestion/nit"]
    F_CAT --> F_DECIDE{Decide Response}
    F_DECIDE -->|Correct, improves code| F_ACCEPT["Accept:<br/>Make the change"]
    F_DECIDE -->|Incorrect or harmful| F_PUSH["Push Back:<br/>Disagree with evidence"]
    F_DECIDE -->|Ambiguous| F_CLARIFY["Clarify:<br/>Ask questions"]
    F_DECIDE -->|Valid but out of scope| F_DEFER["Defer:<br/>Acknowledge + follow-up"]

    F_ACCEPT --> F_RATIONALE["Document rationale<br/>for each decision"]
    F_PUSH --> F_RATIONALE
    F_CLARIFY --> F_RATIONALE
    F_DEFER --> F_RATIONALE

    F_RATIONALE --> F_FACT["Fact-check<br/>technical claims"]
    F_FACT --> F_EXEC["Execute fixes"]
    F_EXEC --> F_RERUN["Re-run self-review"]
    F_RERUN --> F_OUT([Responses Sent])

    style F_START fill:#51cf66,color:#fff
    style F_DECIDE fill:#ff6b6b,color:#fff
    style F_OUT fill:#51cf66,color:#fff
```

## Give Mode (`--give`)

```mermaid
flowchart TD
    G_START([Give Mode Entry]) --> G_STEP0["Step 0: Load<br/>Project Conventions"]
    G_STEP0 --> G_READ_CFG["Read CLAUDE.md,<br/>style configs,<br/>review instructions"]
    G_READ_CFG --> G_SAMPLE["Sample adjacent files<br/>for conventions"]

    G_SAMPLE --> G_STEP1["Step 1: Fetch<br/>and Inventory"]
    G_STEP1 --> G_DIFF["Fetch diff via<br/>gh pr diff / git diff"]
    G_DIFF --> G_MANIFEST["Build Coverage<br/>Manifest: ALL files"]
    G_MANIFEST --> G_PRIOR["Fetch prior<br/>unresolved comments"]
    G_PRIOR --> G_CLASS["Classify prior:<br/>ADDRESSED / STILL_OPEN"]

    G_CLASS --> G_STEP2["Step 2: Multi-Pass<br/>Review"]
    G_STEP2 --> G_MANDATORY["Mandatory Dimensions<br/>(all 6 per file)"]

    subgraph Mandatory["Mandatory Dimensions"]
        M1["Correctness"]
        M2["Security"]
        M3["Error Handling"]
        M4["Data Integrity"]
        M5["API Contracts"]
        M6["Test Coverage"]
    end

    G_MANDATORY --> G_SEC["Security Pass:<br/>6 concrete checks"]
    G_SEC --> G_COND{Conditional<br/>Triggers?}
    G_COND -->|"async/threading"| G_CONC["Concurrency Pass"]
    G_COND -->|"hot paths/DB"| G_PERF["Performance Pass"]
    G_COND -->|"UI/frontend"| G_A11Y["Accessibility Pass"]
    G_COND -->|None triggered| G_STEP3

    G_CONC --> G_STEP3
    G_PERF --> G_STEP3
    G_A11Y --> G_STEP3

    G_STEP3["Step 3: Output"] --> G_VERIFY_COV["Verify coverage:<br/>every file evaluated?"]
    G_VERIFY_COV --> G_FORMAT["Format: Summary,<br/>Manifest, Reconciliation,<br/>Findings, Recommendation"]
    G_FORMAT --> G_REC{Recommendation}
    G_REC -->|No issues| G_APPROVE([APPROVE])
    G_REC -->|Issues found| G_CHANGES([REQUEST_CHANGES])
    G_REC -->|Questions only| G_COMMENT([COMMENT])

    style G_START fill:#51cf66,color:#fff
    style G_COND fill:#ff6b6b,color:#fff
    style G_REC fill:#ff6b6b,color:#fff
    style G_APPROVE fill:#51cf66,color:#fff
    style G_CHANGES fill:#ff6b6b,color:#fff
    style G_COMMENT fill:#fbbf24,color:#000
    style G_SEC fill:#e879f9,color:#fff
    style G_CONC fill:#e879f9,color:#fff
```

## Audit Mode (`--audit`)

```mermaid
flowchart TD
    A_START([Audit Mode Entry]) --> A_SCOPE{Scope?}
    A_SCOPE -->|"(none)"| A_BRANCH["Branch changes"]
    A_SCOPE -->|"file.py"| A_FILE["Single file"]
    A_SCOPE -->|"dir/"| A_DIR["Directory"]
    A_SCOPE -->|"security"| A_SEC_ONLY["Security only"]
    A_SCOPE -->|"all"| A_ALL["Entire codebase"]

    A_BRANCH --> A_MEMORY
    A_FILE --> A_MEMORY
    A_DIR --> A_MEMORY
    A_SEC_ONLY --> A_MEMORY
    A_ALL --> A_MEMORY

    A_MEMORY["Memory Priming:<br/>memory_recall()"] --> A_PASS1["Pass 1: Correctness"]
    A_PASS1 --> A_PASS2["Pass 2: Security"]
    A_PASS2 --> A_PASS3["Pass 3: Performance"]
    A_PASS3 --> A_PASS4["Pass 4: Maintainability"]
    A_PASS4 --> A_PASS5["Pass 5: Edge Cases"]
    A_PASS5 --> A_PERSIST["Persist significant<br/>findings via memory_store"]
    A_PERSIST --> A_OUTPUT["Output: Executive Summary,<br/>Findings by Category"]
    A_OUTPUT --> A_RISK{Risk Assessment}
    A_RISK -->|LOW| A_LOW([LOW])
    A_RISK -->|MEDIUM| A_MED([MEDIUM])
    A_RISK -->|HIGH| A_HIGH([HIGH])
    A_RISK -->|CRITICAL| A_CRIT([CRITICAL])

    style A_START fill:#51cf66,color:#fff
    style A_SCOPE fill:#ff6b6b,color:#fff
    style A_RISK fill:#ff6b6b,color:#fff
    style A_LOW fill:#51cf66,color:#fff
    style A_MED fill:#fbbf24,color:#000
    style A_HIGH fill:#ff6b6b,color:#fff
    style A_CRIT fill:#ff6b6b,color:#fff
```

## Tarot Integration (`--tarot`)

```mermaid
flowchart TD
    T_START([Tarot Modifier<br/>Active]) --> T_ASSIGN["Assign Personas<br/>to Review Passes"]

    T_ASSIGN --> T_HERMIT["Hermit:<br/>Security reviewer"]
    T_ASSIGN --> T_PRIESTESS["Priestess:<br/>Architecture reviewer"]
    T_ASSIGN --> T_FOOL["Fool:<br/>Assumption challenger"]

    T_HERMIT --> T_DIALOGUE["Roundtable<br/>Dialogue Format"]
    T_PRIESTESS --> T_DIALOGUE
    T_FOOL --> T_DIALOGUE

    T_DIALOGUE --> T_CONFLICT{Archetype<br/>Disagreement?}
    T_CONFLICT -->|Yes| T_EVIDENCE["Resolve by<br/>evidence weight"]
    T_CONFLICT -->|No| T_SYNTH
    T_EVIDENCE --> T_SYNTH["Magician:<br/>Synthesis + Verdict"]

    T_SYNTH --> T_SEPARATE["Separate persona<br/>dialogue from<br/>formal findings"]
    T_SEPARATE --> T_OUT([Findings Output:<br/>Persona-Free])

    style T_START fill:#c084fc,color:#fff
    style T_CONFLICT fill:#ff6b6b,color:#fff
    style T_HERMIT fill:#c084fc,color:#fff
    style T_PRIESTESS fill:#c084fc,color:#fff
    style T_FOOL fill:#c084fc,color:#fff
    style T_SYNTH fill:#c084fc,color:#fff
    style T_OUT fill:#51cf66,color:#fff
```

## Cross-Reference

| Overview Node | Detail Section | Source |
|---|---|---|
| Self Mode | Self Mode (`--self`) | `skills/code-review/SKILL.md:65-91` |
| Feedback Mode | Feedback Mode (`--feedback`) | `commands/code-review-feedback.md` |
| Give Mode | Give Mode (`--give`) | `commands/code-review-give.md` |
| Audit Mode | Audit Mode (`--audit`) | `skills/code-review/SKILL.md:94-105` |
| Tarot Roundtable | Tarot Integration (`--tarot`) | `commands/code-review-tarot.md` |

## Legend

```mermaid
flowchart LR
    L1[Process Step]
    L2{Decision Point}
    L3([Terminal])
    L4[Security/Conditional Pass]
    L5[Tarot Persona]
    style L1 fill:#4a9eff,color:#fff
    style L2 fill:#ff6b6b,color:#fff
    style L3 fill:#51cf66,color:#fff
    style L4 fill:#e879f9,color:#fff
    style L5 fill:#c084fc,color:#fff
```

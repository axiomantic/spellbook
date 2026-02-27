<!-- diagram-meta: {"source": "commands/code-review-give.md", "source_hash": "sha256:ca4a908fcf71c4d4b6cabec3b9e105cedeea1c2ef1dafe0f7317c0c87c1e92a4", "generated_at": "2026-02-27T05:10:32Z", "generator": "generate_diagrams.py"} -->
# Diagram: code-review-give

Now I have the full source content. Let me generate the diagrams.

## Overview

High-level workflow from target input through the four steps, reflection quality gate, and final recommendation.

```mermaid
flowchart TD
    START(["Start: --give target"]) --> S0A

    subgraph S0["Step 0: Load Project Conventions"]
        S0A["Read CLAUDE.md + .claude/CLAUDE.md"] --> S0B["Read style configs<br/>pyproject.toml, eslintrc, biome.json"]
        S0B --> S0C["Check code-review-instructions.md"]
        S0C --> S0D["Sample 1-2 sibling files"]
        S0D --> S0E["Analyze project conventions"]
    end

    S0E --> S1A

    subgraph S1["Step 1: Fetch and Inventory"]
        S1A["Fetch diff<br/>gh pr diff / git diff"] --> S1B["Understand PR goal<br/>from description"]
        S1B --> S1C["Build coverage manifest<br/>git diff --name-only"]
        S1C --> S1D{"PR has existing<br/>review comments?"}
        S1D -->|Yes| S1E["Fetch prior feedback<br/>gh api pulls/N/comments + reviews"]
        S1D -->|No| S1F["Record: no prior feedback"]
        S1E --> S1G["Record PRIOR_FEEDBACK items"]
        S1G --> S1H["Inventory complete"]
        S1F --> S1H
    end

    S1H --> S2["Step 2: Multi-Pass Review<br/>(see detail diagram)"]

    S2 --> S3A

    subgraph S3["Step 3: Format Output"]
        S3A["Write summary<br/>1-2 sentence assessment"] --> S3B["Report coverage manifest<br/>Files reviewed: N/N"]
        S3B --> S3C{"Prior feedback<br/>was recorded?"}
        S3C -->|Yes| S3D["Reconcile each item<br/>ADDRESSED or STILL_OPEN"]
        S3C -->|No| S3E["Skip reconciliation"]
        S3D --> S3F["Format findings by severity<br/>CRITICAL / IMPORTANT / MINOR / QUESTION"]
        S3E --> S3F
    end

    S3F --> R1

    subgraph REFLECT["Reflection Quality Gate"]
        R1{"All manifest files<br/>evaluated?"}:::gate
        R1 -->|Yes| R2{"All 6 mandatory dims<br/>checked per file?"}:::gate
        R2 -->|Yes| R3{"Security pass<br/>completed?"}:::gate
        R3 -->|Yes| R4{"Async present:<br/>concurrency pass done?"}:::gate
        R4 -->|Yes| R5{"Prior feedback<br/>reconciled?"}:::gate
        R5 -->|Yes| R6{"Severity ratings<br/>honest?"}:::gate
    end

    R1 -->|No| REDO["Address gaps in review"]
    R2 -->|No| REDO
    R3 -->|No| REDO
    R4 -->|No| REDO
    R5 -->|No| REDO
    R6 -->|No| REDO
    REDO --> S2

    R6 -->|Yes| REC{Recommendation}
    REC -->|"No issues or minor only"| APPROVE(["APPROVE"]):::success
    REC -->|"Critical / important findings"| CHANGES(["REQUEST_CHANGES"])
    REC -->|"Questions / discussion needed"| COMMENT(["COMMENT"])

    subgraph Legend[" Legend "]
        direction LR
        LPROC["Process"] ~~~ LDEC{"Decision"} ~~~ LTERM(["Terminal"])
        LGATE["Quality Gate"]:::gate ~~~ LSUCC(["Success"]):::success
    end

    classDef gate fill:#ff6b6b,color:white
    classDef success fill:#51cf66,color:white
```

## Step 2 Detail: Multi-Pass Review

Expands the per-file dimension loop, cross-file security pass, and conditional concurrency pass. Conditional dimensions (Performance, Concurrency/Async, Accessibility) are evaluated independently per file; multiple can apply to the same file.

```mermaid
flowchart TD
    START(["Begin Step 2"]) --> NEXT

    NEXT{"Next file in<br/>coverage manifest?"}
    NEXT -->|"Yes: select file"| D1
    NEXT -->|"No: all files done"| SECHEAD

    subgraph MANDATORY["Mandatory Dimensions (per file)"]
        D1["1. Correctness<br/>Logic, off-by-one, null, return types"] --> D2["2. Security<br/>Injection, auth gaps, secrets, SSRF"]
        D2 --> D3["3. Error Handling<br/>Missing catches, swallowed errors, null safety"]
        D3 --> D4["4. Data Integrity<br/>Race conditions, non-atomic writes, stale data"]
        D4 --> D5["5. API Contracts<br/>Breaking changes, validation, schema drift"]
        D5 --> D6["6. Test Coverage<br/>Missing tests, edge cases, meaningful assertions"]
    end

    D6 --> CPERF

    subgraph CONDITIONAL["Conditional Dimensions (per file, independent checks)"]
        CPERF{"Performance<br/>relevant?"}
        CPERF -->|Yes| PERF["Performance<br/>Hot paths, N+1, allocations, indexes"]
        CPERF -->|No| CASYNC
        PERF --> CASYNC

        CASYNC{"Async or threading<br/>present?"}
        CASYNC -->|Yes| ASYNCDIM["Concurrency/Async<br/>REQUIRED when present"]:::gate
        CASYNC -->|No| CA11Y
        ASYNCDIM --> CA11Y

        CA11Y{"UI changes<br/>present?"}
        CA11Y -->|Yes| A11Y["Accessibility<br/>ARIA, keyboard nav, screen readers"]
        CA11Y -->|No| RECORD
        A11Y --> RECORD
    end

    RECORD["Record findings for file"] --> NEXT

    SECHEAD["Security Pass: cross-file"]:::gate --> SEC1

    subgraph SEC["Security Pass: 6 Checks"]
        SEC1["Input validation<br/>Length limits, content-type"] --> SEC2["Path traversal<br/>User-supplied file paths"]
        SEC2 --> SEC3["Hardcoded secrets<br/>Tokens, keys, passwords, private keys"]
        SEC3 --> SEC4["Auth/authz<br/>Missing checks, broken logic"]
        SEC4 --> SEC5["Injection<br/>SQL, XSS, command injection"]
        SEC5 --> SEC6["SSRF<br/>User-controlled URL fetching"]
    end

    SEC6 --> HASASYNC

    HASASYNC{"Diff contains async<br/>functions or threading?"}
    HASASYNC -->|No| DONE(["Step 2 Complete"])
    HASASYNC -->|Yes| CONCHEAD["Concurrency/Async Pass"]:::gate

    CONCHEAD --> C1

    subgraph CONC["Concurrency/Async Pass: 5 Checks"]
        C1["Event loop blocking<br/>Sync calls inside async functions"] --> C2["Thread safety<br/>Shared mutable state without locks"]
        C2 --> C3["Race conditions<br/>TOCTOU, check-then-act patterns"]
        C3 --> C4["Interrupt handling<br/>EOFError, KeyboardInterrupt, CancelledError"]
        C4 --> C5["Lock ordering<br/>Deadlock from inconsistent acquisition"]
    end

    C5 --> DONE

    subgraph Legend[" Legend "]
        direction LR
        LPROC["Process"] ~~~ LDEC{"Decision"} ~~~ LTERM(["Terminal"])
        LGATE["Quality Gate"]:::gate
    end

    classDef gate fill:#ff6b6b,color:white
```

## Cross-Reference

| Overview Node | Detail Diagram Section | Source Lines |
|---|---|---|
| Step 0: Load Project Conventions | (fully expanded in overview) | 24-36 |
| Step 1: Fetch and Inventory | (fully expanded in overview) | 38-67 |
| Step 2: Multi-Pass Review | Full detail diagram | 69-113 |
| - 6 Mandatory Dimensions | MANDATORY subgraph (D1-D6) | 73-81 |
| - Conditional Dimensions | CONDITIONAL subgraph (CPERF/CASYNC/CA11Y) | 83-89 |
| - Security Pass | SEC subgraph (SEC1-SEC6) | 91-101 |
| - Concurrency/Async Pass | CONC subgraph (C1-C5) | 103-113 |
| Step 3: Format Output | (fully expanded in overview) | 115-140 |
| Reflection Quality Gate | REFLECT subgraph (R1-R6) | 145-153 |

## Legend

| Shape | Meaning |
|---|---|
| Rectangle `[text]` | Process step |
| Diamond `{text}` | Decision point |
| Stadium `([text])` | Terminal (start/end) |
| Red fill (#ff6b6b) | Quality gate - mandatory check that blocks progress |
| Green fill (#51cf66) | Success terminal |

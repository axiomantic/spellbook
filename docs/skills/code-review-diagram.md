# Code Review Skill Diagrams

## Overview: Mode Routing

High-level entry point showing how the skill routes to specialized handlers based on mode flags.

```mermaid
flowchart TD
    subgraph Legend
        L1[Process]
        L2{Decision}
        L3([Terminal])
        L4[Subagent Dispatch]:::subagent
        L5[Quality Gate]:::gate
        L6([Success]):::success
    end

    Start([Invocation:<br>/code-review]) --> ParseFlags{Parse mode<br>flags}

    ParseFlags -->|--feedback, -f| Feedback[Load code-review-feedback<br>command]
    ParseFlags -->|--give target| Give[Load code-review-give<br>command]
    ParseFlags -->|--self, -s,<br>or no flag| Self[Self Mode<br>inline workflow]
    ParseFlags -->|--audit scope| Audit[Audit Mode<br>inline workflow]

    ParseFlags -.->|--tarot modifier?| TarotCheck{--tarot<br>present?}
    TarotCheck -->|Yes| LoadTarot[Load code-review-tarot<br>overlay]
    TarotCheck -->|No| NoTarot[Standard output<br>format]

    ParseFlags -.->|--pr modifier?| PRCheck{--pr num<br>present?}
    PRCheck -->|Yes| FetchPR[Fetch PR metadata<br>and diff via MCP/gh]
    PRCheck -->|No| LocalDiff[Use local<br>git diff]

    Self --> SelfDetail([See: Self Mode Detail]):::success
    Audit --> AuditDetail([See: Audit Mode Detail]):::success
    Feedback --> FeedbackDetail([See: Feedback Mode Detail]):::success
    Give --> GiveDetail([See: Give Mode Detail]):::success

    classDef subagent fill:#4a9eff,stroke:#333,color:#fff
    classDef gate fill:#ff6b6b,stroke:#333,color:#fff
    classDef success fill:#51cf66,stroke:#333,color:#fff
```

### Cross-Reference Table

| Overview Node | Detail Diagram |
|---------------|----------------|
| Self Mode | [Self Mode Detail](#self-mode-detail) |
| Audit Mode | [Audit Mode Detail](#audit-mode-detail) |
| Feedback Mode | [Feedback Mode Detail](#feedback-mode-detail) |
| Give Mode | [Give Mode Detail](#give-mode-detail) |

---

## Self Mode Detail

Pre-PR self-review workflow with memory integration and multi-pass analysis.

```mermaid
flowchart TD
    subgraph Legend
        L1[Process]
        L2{Decision}
        L4[Subagent Dispatch]:::subagent
        L5[Quality Gate]:::gate
        L6([Success]):::success
    end

    Start([Self Mode Entry]) --> GetDiff[Get diff:<br>git diff merge-base..HEAD]

    GetDiff --> MemoryPrime[Memory Priming:<br>memory_recall query=<br>'review finding project']
    MemoryPrime --> IncorporateMemory[Incorporate recalled<br>memories + spellbook-memory<br>context from files]

    IncorporateMemory --> Pass1[Pass 1: Logic]
    Pass1 --> Pass2[Pass 2: Integration]
    Pass2 --> Pass3[Pass 3: Security]
    Pass3 --> Pass4[Pass 4: Style]

    Pass4 --> GenFindings[Generate findings with<br>severity + file:line +<br>description]

    GenFindings --> TarotCheck{--tarot<br>active?}
    TarotCheck -->|Yes| TarotWrap[Wrap in roundtable<br>dialogue format]
    TarotCheck -->|No| PersistCheck

    TarotWrap --> PersistCheck{Significant<br>findings?}
    PersistCheck -->|Yes| PersistMemory[memory_store_memories:<br>antipattern for confirmed issues<br>fact for false positives]
    PersistCheck -->|No| Gate

    PersistMemory --> Gate

    Gate{Severity Gate}:::gate
    Gate -->|Any Critical| FAIL([FAIL]):::fail
    Gate -->|Important,<br>no Critical| WARN([WARN]):::warn
    Gate -->|Minor only| PASS([PASS]):::success

    subgraph SelfCheck [Self-Check Checklist]
        SC1[All findings have file:line]
        SC2[Severity based on impact]
        SC3[Output matches mode spec]
    end

    Gate -.-> SelfCheck

    classDef subagent fill:#4a9eff,stroke:#333,color:#fff
    classDef gate fill:#ff6b6b,stroke:#333,color:#fff
    classDef success fill:#51cf66,stroke:#333,color:#fff
    classDef fail fill:#ff6b6b,stroke:#333,color:#fff
    classDef warn fill:#ffd43b,stroke:#333,color:#000
```

---

## Audit Mode Detail

Deep multi-pass audit with configurable scope and risk assessment.

```mermaid
flowchart TD
    subgraph Legend
        L1[Process]
        L2{Decision}
        L5[Quality Gate]:::gate
        L6([Success]):::success
    end

    Start([Audit Mode Entry]) --> ScopeCheck{Scope<br>argument?}

    ScopeCheck -->|none| ScopeBranch[Scope: branch changes]
    ScopeCheck -->|file.py| ScopeFile[Scope: single file]
    ScopeCheck -->|dir/| ScopeDir[Scope: directory]
    ScopeCheck -->|security| ScopeSec[Scope: security only]
    ScopeCheck -->|all| ScopeAll[Scope: entire codebase]

    ScopeBranch --> MemoryPrime
    ScopeFile --> MemoryPrime
    ScopeDir --> MemoryPrime
    ScopeSec --> MemoryPrime
    ScopeAll --> MemoryPrime

    MemoryPrime[Memory Priming:<br>memory_recall query=<br>'review finding project']

    MemoryPrime --> TarotCheck{--tarot<br>active?}

    TarotCheck -->|No| P1[Pass 1: Correctness]
    TarotCheck -->|Yes| TarotAssign[Assign personas<br>to passes]

    TarotAssign --> P1T[Hermit: Security Pass]:::subagent
    TarotAssign --> P2T[Priestess: Architecture Pass]:::subagent
    TarotAssign --> P3T[Fool: Assumption Pass]:::subagent

    P1 --> P2[Pass 2: Security]
    P2 --> P3[Pass 3: Performance]
    P3 --> P4[Pass 4: Maintainability]
    P4 --> P5[Pass 5: Edge Cases]

    P1T --> Synth
    P2T --> Synth
    P3T --> Synth

    P5 --> Output

    Synth[Magician: Synthesis<br>+ Verdict] --> Output

    Output[Generate output:<br>Executive Summary +<br>Findings by category +<br>Risk Assessment]

    Output --> PersistMemory[Persist significant<br>findings via<br>memory_store_memories]

    PersistMemory --> RiskGate{Risk Assessment}:::gate
    RiskGate -->|LOW| Low([LOW]):::success
    RiskGate -->|MEDIUM| Med([MEDIUM]):::warn
    RiskGate -->|HIGH| High([HIGH]):::fail
    RiskGate -->|CRITICAL| Crit([CRITICAL]):::fail

    classDef subagent fill:#4a9eff,stroke:#333,color:#fff
    classDef gate fill:#ff6b6b,stroke:#333,color:#fff
    classDef success fill:#51cf66,stroke:#333,color:#fff
    classDef fail fill:#ff6b6b,stroke:#333,color:#fff
    classDef warn fill:#ffd43b,stroke:#333,color:#000
```

---

## Feedback Mode Detail

Process received review comments with categorization and intentional response.

```mermaid
flowchart TD
    subgraph Legend
        L1[Process]
        L2{Decision}
        L5[Quality Gate]:::gate
        L6([Success]):::success
    end

    Start([Feedback Mode Entry]) --> Gather[Step 1: Gather holistically<br>Collect ALL feedback across<br>related PRs]

    Gather --> Categorize[Step 2: Categorize each item]

    Categorize --> CatBug[bug]
    Categorize --> CatStyle[style]
    Categorize --> CatQ[question]
    Categorize --> CatSug[suggestion]
    Categorize --> CatNit[nit]

    CatBug --> Decide
    CatStyle --> Decide
    CatQ --> Decide
    CatSug --> Decide
    CatNit --> Decide

    Decide{Step 3: Decide<br>response for each}

    Decide -->|Correct,<br>improves code| Accept[Accept:<br>make the change]
    Decide -->|Incorrect or<br>would harm code| PushBack[Push back:<br>disagree with evidence]
    Decide -->|Ambiguous,<br>need context| Clarify[Clarify:<br>ask questions]
    Decide -->|Valid but<br>out of scope| Defer[Defer:<br>acknowledge + follow-up]

    Accept --> Rationale
    PushBack --> Rationale
    Clarify --> Rationale
    Defer --> Rationale

    Rationale[Step 4: Document rationale<br>WHY for each decision]

    Rationale --> FactCheck[Step 5: Fact-check<br>Verify technical claims<br>before accepting or disputing]:::gate

    FactCheck --> Execute[Step 6: Execute fixes]

    Execute --> SelfReview[Re-run self-review<br>on changes]

    SelfReview --> Done([Complete]):::success

    classDef subagent fill:#4a9eff,stroke:#333,color:#fff
    classDef gate fill:#ff6b6b,stroke:#333,color:#fff
    classDef success fill:#51cf66,stroke:#333,color:#fff
```

---

## Give Mode Detail

Review someone else's code/PR with full coverage tracking and multi-dimensional analysis.

```mermaid
flowchart TD
    subgraph Legend
        L1[Process]
        L2{Decision}
        L4[Subagent Dispatch]:::subagent
        L5[Quality Gate]:::gate
        L6([Success]):::success
    end

    Start([Give Mode Entry]) --> TargetParse{Parse target<br>format}

    TargetParse -->|PR num| FetchPR[Fetch PR via<br>gh pr diff]
    TargetParse -->|URL| FetchURL[Fetch PR via URL]
    TargetParse -->|branch| FetchBranch[git diff<br>merge-base..branch]

    FetchPR --> Step0
    FetchURL --> Step0
    FetchBranch --> Step0

    Step0[Step 0: Load Project Conventions<br>Read CLAUDE.md, style configs,<br>code-review-instructions.md,<br>sample adjacent files]

    Step0 --> DiffWarning[CRITICAL: PR diff is<br>authoritative code.<br>NEVER read local files<br>in changed file set]:::gate

    DiffWarning --> Step1[Step 1: Fetch and Inventory]

    Step1 --> Manifest[Build Coverage Manifest<br>from ALL changed files]

    Manifest --> PriorFeedback[Fetch prior PR feedback<br>via gh api]

    PriorFeedback --> ClassifyFeedback{Classify each<br>prior item}
    ClassifyFeedback -->|Code resolves it| Addressed[ADDRESSED]
    ClassifyFeedback -->|Not resolved| StillOpen[STILL_OPEN]

    Addressed --> Step2
    StillOpen --> Step2

    Step2[Step 2: Multi-Pass Review]

    Step2 --> Mandatory[Mandatory Dimensions<br>for EVERY changed file]

    Mandatory --> MD1[Correctness]
    Mandatory --> MD2[Security]
    Mandatory --> MD3[Error Handling]
    Mandatory --> MD4[Data Integrity]
    Mandatory --> MD5[API Contracts]
    Mandatory --> MD6[Test Coverage]

    MD1 --> CondCheck
    MD2 --> SecPass
    MD3 --> CondCheck
    MD4 --> CondCheck
    MD5 --> CondCheck
    MD6 --> CondCheck

    SecPass[Security Pass:<br>6 concrete checks<br>Input validation, Path traversal,<br>Hardcoded secrets, Auth/authz,<br>Injection, SSRF]:::gate --> CondCheck

    CondCheck{Conditional<br>dimensions<br>triggered?}

    CondCheck -->|Hot paths/<br>DB ops| PerfPass[Performance Pass]
    CondCheck -->|async/<br>threading| ConcPass[Concurrency Pass:<br>Event loop blocking,<br>Thread safety, Races,<br>Interrupt handling,<br>Lock ordering]
    CondCheck -->|UI/frontend| A11yPass[Accessibility Pass]
    CondCheck -->|None triggered| Step3

    PerfPass --> Step3
    ConcPass --> Step3
    A11yPass --> Step3

    Step3[Step 3: Output]

    Step3 --> Reflection[Reflection checklist:<br>All files covered?<br>All 6 dimensions checked?<br>Security pass complete?<br>Concurrency pass if needed?<br>Prior feedback reconciled?<br>Severity ratings honest?]:::gate

    Reflection --> CoverageVerify{Coverage<br>manifest<br>complete?}:::gate

    CoverageVerify -->|Gaps found| ReportGaps[Report coverage<br>gaps in output]
    CoverageVerify -->|Complete| FormatOutput

    ReportGaps --> FormatOutput

    FormatOutput[Format: Summary +<br>Coverage Manifest +<br>Prior Feedback Reconciliation +<br>Findings with severity +<br>Recommendation]

    FormatOutput --> Verdict{Recommendation}
    Verdict -->|No issues| APPROVE([APPROVE]):::success
    Verdict -->|Issues found| REQUEST([REQUEST_CHANGES]):::fail
    Verdict -->|Questions only| COMMENT([COMMENT]):::warn

    classDef subagent fill:#4a9eff,stroke:#333,color:#fff
    classDef gate fill:#ff6b6b,stroke:#333,color:#fff
    classDef success fill:#51cf66,stroke:#333,color:#fff
    classDef fail fill:#ff6b6b,stroke:#333,color:#fff
    classDef warn fill:#ffd43b,stroke:#333,color:#000
```

---

## Tarot Overlay

The `--tarot` modifier is compatible with all modes. It overlays persona-based dialogue onto the standard workflow.

```mermaid
flowchart TD
    subgraph Legend
        L1[Process]
        L4[Subagent Dispatch]:::subagent
        L6([Terminal]):::success
    end

    TarotFlag([--tarot flag detected]) --> AnyMode{Active<br>mode?}

    AnyMode -->|--self| SelfTarot[Self mode +<br>roundtable dialogue]
    AnyMode -->|--give| GiveTarot[Give mode +<br>roundtable dialogue]
    AnyMode -->|--audit| AuditTarot[Audit mode +<br>persona-per-pass]

    SelfTarot --> Roundtable
    GiveTarot --> Roundtable

    AuditTarot --> HermitAgent[Hermit subagent:<br>Security Pass]:::subagent
    AuditTarot --> PriestessAgent[Priestess subagent:<br>Architecture Pass]:::subagent
    AuditTarot --> FoolAgent[Fool subagent:<br>Assumption Pass]:::subagent

    HermitAgent --> MagicianSynth
    PriestessAgent --> MagicianSynth
    FoolAgent --> MagicianSynth

    MagicianSynth[Magician: Synthesize<br>+ resolve conflicts<br>by evidence weight]

    Roundtable[Roundtable Dialogue:<br>Hermit - Security<br>Priestess - Architecture<br>Fool - Assumptions]

    Roundtable --> MagicianVerdict[Magician: Final<br>synthesis + verdict]

    MagicianSynth --> Separation
    MagicianVerdict --> Separation

    Separation[Code Output Separation:<br>Persona in dialogue ONLY<br>Findings output is persona-free]:::gate

    Separation --> Done([Output with tarot<br>framing complete]):::success

    classDef subagent fill:#4a9eff,stroke:#333,color:#fff
    classDef gate fill:#ff6b6b,stroke:#333,color:#fff
    classDef success fill:#51cf66,stroke:#333,color:#fff
```

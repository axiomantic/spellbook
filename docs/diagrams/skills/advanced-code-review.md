<!-- diagram-meta: {"source": "skills/advanced-code-review/SKILL.md", "source_hash": "sha256:c32c46fa5432e5b5bb6aaa3d0d2b2eb2a7d5d3c1780a215e62e1f24348f411b2", "generated_at": "2026-03-12T00:00:00Z", "generator": "claude-manual", "stamped_at": "2026-03-13T02:48:01Z"} -->
# Diagram: advanced-code-review

Multi-phase code review with strategic planning, historical context analysis, deep multi-pass review, verification of findings, and final report generation. Each phase produces artifacts and must pass a self-check before proceeding.

## Overview

High-level flow across all 5 phases with circuit breakers and quality gates.

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

    Start([User invokes<br>advanced-code-review]) --> InputParse[Parse target, --base,<br>--scope, --offline, --continue]
    InputParse --> ModeRouter{Target type?}

    ModeRouter -->|Branch name| LocalMode[Local Mode<br>source = local files]
    ModeRouter -->|PR number / URL| PRMode[PR Mode<br>source = diff only]
    ModeRouter -->|Any + --offline| OfflineMode[Offline Mode<br>source = local files]

    LocalMode --> ContinueCheck
    PRMode --> ContinueCheck
    OfflineMode --> ContinueCheck

    ContinueCheck{--continue<br>flag?}
    ContinueCheck -->|Yes| ResumeSession[Load previous<br>review session]
    ContinueCheck -->|No| Phase1

    ResumeSession --> Phase1

    Phase1[Phase 1: Strategic Planning<br>/advanced-code-review-plan]
    Phase1 --> P1Gate[Phase 1 Self-Check:<br>Target resolved, manifest written,<br>files categorized]:::gate
    P1Gate -->|Pass| Phase2
    P1Gate -->|Fail: E_TARGET_NOT_FOUND| CB1([Circuit Breaker:<br>Target unresolvable])
    P1Gate -->|Fail: E_NO_DIFF| CB2([Circuit Breaker:<br>No changes found])

    Phase2[Phase 2: Context Analysis<br>/advanced-code-review-context]
    Phase2 --> P2Gate[Phase 2 Self-Check:<br>Context loaded, previous items parsed]:::gate
    P2Gate -->|Pass| Phase3
    P2Gate -->|Fail: non-blocking| Phase3

    Phase3[Phase 3: Deep Review<br>/advanced-code-review-review]
    Phase3 --> P3Gate[Phase 3 Self-Check:<br>All passes complete, findings generated,<br>declined items respected]:::gate
    P3Gate -->|Pass| Phase4
    P3Gate -->|Fail| P3Fix[Fix incomplete findings<br>before proceeding]
    P3Fix --> P3Gate

    Phase4[Phase 4: Verification<br>/advanced-code-review-verify]
    Phase4 --> P4Gate[Phase 4 Self-Check:<br>All verified, REFUTED removed,<br>SNR calculated]:::gate
    P4Gate -->|Pass| Phase5
    P4Gate -->|Fail: 3+ consecutive<br>verification failures| CB3([Circuit Breaker:<br>Verification failures])
    P4Gate -->|Fail: timeout| CB4([Circuit Breaker:<br>Verification timeout])

    Phase5[Phase 5: Report Generation<br>/advanced-code-review-report]
    Phase5 --> P5Gate[Phase 5 Self-Check:<br>Report rendered, artifacts written]:::gate
    P5Gate -->|Pass| MemStore[Store review summary<br>in memory]
    MemStore --> FinalCheck[Final Self-Check:<br>All phases complete,<br>all quality gates passed]:::gate
    FinalCheck -->|Pass| Done([Review Complete]):::success
    FinalCheck -->|Fail| FixAndRecheck[Fix failing items]
    FixAndRecheck --> FinalCheck

    classDef subagent fill:#4a9eff,stroke:#2d7ad4,color:#fff
    classDef gate fill:#ff6b6b,stroke:#d44b4b,color:#fff
    classDef success fill:#51cf66,stroke:#37a34d,color:#fff
```

### Cross-Reference Table

| Overview Node | Detail Diagram |
|---|---|
| Phase 1: Strategic Planning | [Phase 1 Detail](#phase-1-strategic-planning) |
| Phase 2: Context Analysis | [Phase 2 Detail](#phase-2-context-analysis) |
| Phase 3: Deep Review | [Phase 3 Detail](#phase-3-deep-review) |
| Phase 4: Verification | [Phase 4 Detail](#phase-4-verification) |
| Phase 5: Report Generation | [Phase 5 Detail](#phase-5-report-generation) |

---

## Phase 1: Strategic Planning

Target resolution, diff acquisition, risk categorization, complexity estimation, and priority ordering.

```mermaid
flowchart TD
    subgraph Legend
        L1[Process]
        L2{Decision}
        L3([Terminal])
        L4[Quality Gate]:::gate
        L5([Success]):::success
    end

    Start([Phase 1 Entry]) --> Resolve[1.1 Target Resolution:<br>resolve branch/SHA]
    Resolve --> ResolveCheck{Target<br>resolved?}

    ResolveCheck -->|E_TARGET_NOT_FOUND| SuggestBranches[List similar branches]
    SuggestBranches --> Exit1([Exit: target not found])

    ResolveCheck -->|Success| MergeBase[Compute merge base:<br>git merge-base base target]
    MergeBase --> MBCheck{Merge base<br>found?}

    MBCheck -->|E_MERGE_BASE_FAILED| Fallback[Fallback to HEAD~10<br>+ warn user]
    MBCheck -->|Success| DiffAcq

    Fallback --> DiffAcq

    DiffAcq{Source mode?}
    DiffAcq -->|Local| LocalDiff[1.2 git diff --name-only<br>MERGE_BASE...HEAD_SHA]
    DiffAcq -->|PR| PRFiles[1.2 MCP pr_files<br>extract file list]

    LocalDiff --> DiffCheck
    PRFiles --> DiffCheck

    DiffCheck{Files<br>changed?}
    DiffCheck -->|E_NO_DIFF| Exit2([Exit: no changes found])
    DiffCheck -->|Yes| MemRecall[Memory-Informed Planning:<br>memory_recall for prior findings<br>and false positive patterns]

    MemRecall --> Categorize[1.3 Risk Categorization:<br>HIGH / MEDIUM / LOW]
    Categorize --> Complexity[1.4 Complexity Estimation:<br>lines/15 + files*2 min]
    Complexity --> ScopeWeight[1.5 Risk-Weighted Scope:<br>HIGH*3 + MEDIUM*2 + LOW*1]
    ScopeWeight --> PriorityOrder[1.6 Priority Ordering:<br>HIGH -> MEDIUM -> LOW]

    PriorityOrder --> WriteManifest[1.7 Write review-manifest.json]
    WriteManifest --> WritePlan[1.8 Write review-plan.md]
    WritePlan --> SelfCheck[Phase 1 Self-Check:<br>target resolved, merge base computed,<br>files categorized, complexity estimated,<br>manifest + plan written]:::gate

    SelfCheck -->|All pass| Done([Phase 1 Complete]):::success
    SelfCheck -->|Any fail| Stop([STOP: report issue,<br>do not proceed])

    classDef gate fill:#ff6b6b,stroke:#d44b4b,color:#fff
    classDef success fill:#51cf66,stroke:#37a34d,color:#fff
```

---

## Phase 2: Context Analysis

Load previous reviews, fetch PR history, detect re-check requests, build context object.

```mermaid
flowchart TD
    subgraph Legend
        L1[Process]
        L2{Decision}
        L3([Terminal])
        L4[Quality Gate]:::gate
        L5([Success]):::success
    end

    Start([Phase 2 Entry]) --> Discover[2.1 Previous Review Discovery:<br>find review dir by<br>branch-mergebase key]
    Discover --> DiscoverCheck{Previous review<br>found and fresh<br>and less than 30 days?}

    DiscoverCheck -->|Not found / stale / incomplete| MemFallback[Cross-Session Context:<br>memory_recall for review<br>decisions on this component]
    DiscoverCheck -->|Found| LoadItems[2.2 Load Previous Items]

    MemFallback --> EmptyContext[Initialize empty<br>previous context]
    EmptyContext --> OnlineCheck

    LoadItems --> ClassifyItems[Classify items by status:<br>PENDING / FIXED / DECLINED /<br>PARTIAL / ALTERNATIVE]
    ClassifyItems --> OnlineCheck

    OnlineCheck{Online mode<br>and PR target?}
    OnlineCheck -->|Yes| FetchPR[2.3 Fetch PR History:<br>MCP pr_fetch + gh API]
    OnlineCheck -->|Offline or local| SkipPR[Skip PR context<br>log OFFLINE]

    FetchPR --> FetchCheck{Fetch<br>succeeded?}
    FetchCheck -->|Yes| DetectRecheck[2.4 Re-check Request Detection:<br>scan comments for<br>re-check / PTAL patterns]
    FetchCheck -->|Fail| WarnPR[Log warning,<br>proceed with empty PR context]
    WarnPR --> BuildContext

    SkipPR --> BuildContext
    DetectRecheck --> BuildContext

    BuildContext[2.5 Build Context Object:<br>manifest + previous items +<br>PR context + declined +<br>partial + alternative +<br>recheck requests]

    BuildContext --> WriteContext[2.6 Write context-analysis.md]
    WriteContext --> WritePrevItems[2.7 Write previous-items.json]
    WritePrevItems --> SelfCheck[Phase 2 Self-Check:<br>previous review discovered/confirmed,<br>items loaded, PR context fetched,<br>recheck requests extracted,<br>artifacts written]:::gate

    SelfCheck -->|All pass| Done([Phase 2 Complete]):::success
    SelfCheck -->|Fail: non-blocking| DoneWarn([Phase 2 Complete<br>with warnings]):::success

    classDef gate fill:#ff6b6b,stroke:#d44b4b,color:#fff
    classDef success fill:#51cf66,stroke:#37a34d,color:#fff
```

---

## Phase 3: Deep Review

Multi-pass code analysis (Security, Correctness, Quality, Polish) with previous-item integration.

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

    Start([Phase 3 Entry]) --> LoadContext[Load manifest +<br>context from Phase 1-2]
    LoadContext --> FileLoop[For each file in<br>priority order]

    FileLoop --> FileNext{More files<br>remaining?}
    FileNext -->|No| Noteworthy[3.7 Scan for PRAISE findings]
    FileNext -->|Yes| LargeDiff{Total diff ><br>10000 lines?}

    LargeDiff -->|Yes| ChunkedProcess[Chunked processing]
    LargeDiff -->|No| SubagentCheck{Files ><br>20?}

    SubagentCheck -->|Yes| ParallelDispatch[Dispatch parallel<br>review subagents]:::subagent
    SubagentCheck -->|No| Pass1

    ChunkedProcess --> Pass1
    ParallelDispatch --> CollectResults[Collect subagent<br>results]
    CollectResults --> Noteworthy

    Pass1[Pass 1: Security<br>CRITICAL / HIGH<br>injection, auth bypass,<br>data exposure, secrets]
    Pass1 --> Pass2[Pass 2: Correctness<br>HIGH / MEDIUM<br>logic errors, edge cases,<br>null handling, races]
    Pass2 --> Pass3[Pass 3: Quality<br>MEDIUM / LOW<br>maintainability, complexity,<br>patterns, readability]
    Pass3 --> Pass4[Pass 4: Polish<br>LOW / NIT<br>style, naming,<br>minor optimizations]

    Pass4 --> PrevCheck[3.4 Previous Items Integration:<br>check each finding against<br>declined / alternative / partial]
    PrevCheck --> ShouldRaise{Finding matches<br>declined or accepted<br>alternative?}
    ShouldRaise -->|Yes: declined| Skip[Skip finding<br>increment skipped count]
    ShouldRaise -->|Yes: alt accepted| Skip
    ShouldRaise -->|Partial pending| Annotate[Annotate as<br>partial_pending]
    ShouldRaise -->|No match| Keep[Keep finding]

    Annotate --> SeverityTree
    Keep --> SeverityTree

    SeverityTree[Apply Severity Decision Tree:<br>Security/data loss? -> CRITICAL<br>Breaks contracts? -> HIGH<br>Quality concern? -> MEDIUM<br>Minor improvement? -> LOW<br>Purely stylistic? -> NIT<br>Needs input? -> QUESTION]

    SeverityTree --> AddFinding[Add to findings list<br>with required fields]
    Skip --> FileLoop
    AddFinding --> FileLoop

    Noteworthy --> WriteJSON[3.8 Write findings.json]
    WriteJSON --> WriteMD[3.9 Write findings.md]
    WriteMD --> SelfCheck[Phase 3 Self-Check:<br>all files reviewed, all 4 passes per file,<br>declined not re-raised, required fields present,<br>findings.json + findings.md written]:::gate

    SelfCheck -->|All pass| Done([Phase 3 Complete]):::success
    SelfCheck -->|Any fail| FixFindings[Fix incomplete<br>findings]
    FixFindings --> SelfCheck

    classDef subagent fill:#4a9eff,stroke:#2d7ad4,color:#fff
    classDef gate fill:#ff6b6b,stroke:#d44b4b,color:#fff
    classDef success fill:#51cf66,stroke:#37a34d,color:#fff
```

---

## Phase 4: Verification

Fact-check every finding against actual code, remove false positives, calculate signal-to-noise.

```mermaid
flowchart TD
    subgraph Legend
        L1[Process]
        L2{Decision}
        L3([Terminal])
        L4[Quality Gate]:::gate
        L5([Success]):::success
    end

    Start([Phase 4 Entry]) --> BranchSafety[4.0 Pre-Flight:<br>Branch Safety Check]
    BranchSafety --> SafetyCheck{PR head SHA<br>matches local HEAD?}

    SafetyCheck -->|No PR SHA<br>local branch review| LocalFiles[review_source =<br>LOCAL_FILES]
    SafetyCheck -->|SHA match| LocalFiles
    SafetyCheck -->|SHA mismatch<br>PR review| DiffOnly[review_source =<br>DIFF_ONLY]

    LocalFiles --> DupDetect
    DiffOnly --> DupDetect

    DupDetect[4.6 Duplicate Detection:<br>find duplicate findings<br>by file + line + category]
    DupDetect --> MergeDups[Merge duplicate<br>findings]
    MergeDups --> FindingLoop[For each finding]

    FindingLoop --> MoreFindings{More findings<br>remaining?}
    MoreFindings -->|No| CalcSNR[4.8 Calculate Signal-to-Noise:<br>signal = CRIT+HIGH+MED verified<br>noise = LOW+NIT or INCONCLUSIVE]
    MoreFindings -->|Yes| SourceCheck{review_source?}

    SourceCheck -->|DIFF_ONLY| MarkInconclusive[Mark INCONCLUSIVE<br>add NEEDS VERIFICATION]
    SourceCheck -->|LOCAL_FILES| ExtractClaims[4.3 Extract Claims:<br>line_content, function_behavior,<br>call_pattern, pattern_violation]

    MarkInconclusive --> UpdateFinding
    ExtractClaims --> ClaimsFound{Claims<br>extracted?}
    ClaimsFound -->|No claims| MarkInconclusive2[Mark INCONCLUSIVE]
    ClaimsFound -->|Yes| VerifyClaims

    VerifyClaims[4.4 Verify each claim:<br>verify_line_content<br>verify_function_behavior<br>verify_call_pattern<br>verify_pattern_violation]
    VerifyClaims --> ValidateLines[4.7 Validate line numbers<br>exist in file]
    ValidateLines --> Aggregate{Aggregate<br>claim results}

    Aggregate -->|Any REFUTED| SetRefuted[Status = REFUTED]
    Aggregate -->|No REFUTED,<br>any INCONCLUSIVE| SetInconclusive[Status = INCONCLUSIVE]
    Aggregate -->|All VERIFIED| SetVerified[Status = VERIFIED]

    SetRefuted --> UpdateFinding
    SetInconclusive --> UpdateFinding
    SetVerified --> UpdateFinding
    MarkInconclusive2 --> UpdateFinding

    UpdateFinding[Update finding with<br>verification_status]

    UpdateFinding --> ConsecutiveCheck{3+ consecutive<br>verification failures?}
    ConsecutiveCheck -->|Yes| CB([Circuit Breaker:<br>too many failures])
    ConsecutiveCheck -->|No| FindingLoop

    CalcSNR --> RemoveRefuted[4.9 Remove REFUTED findings<br>from output, log in audit]
    RemoveRefuted --> FlagInconclusive[4.10 Flag INCONCLUSIVE<br>with NEEDS VERIFICATION]

    FlagInconclusive --> MemPersist[Persist Verified Findings:<br>CONFIRMED -> antipattern memory<br>REFUTED -> false-positive memory]

    MemPersist --> WriteAudit[4.11 Write verification-audit.md]
    WriteAudit --> UpdateJSON[Update findings.json<br>with verification_status]
    UpdateJSON --> SelfCheck[Phase 4 Self-Check:<br>all verified, REFUTED removed,<br>INCONCLUSIVE flagged, duplicates merged,<br>lines validated, SNR calculated,<br>audit + JSON written]:::gate

    SelfCheck -->|All pass| Done([Phase 4 Complete]):::success
    SelfCheck -->|Any fail| FixVerification[Fix failing items]
    FixVerification --> SelfCheck

    classDef gate fill:#ff6b6b,stroke:#d44b4b,color:#fff
    classDef success fill:#51cf66,stroke:#37a34d,color:#fff
```

---

## Phase 5: Report Generation

Filter findings, determine verdict, render report, write artifacts.

```mermaid
flowchart TD
    subgraph Legend
        L1[Process]
        L2{Decision}
        L3([Terminal])
        L4[Quality Gate]:::gate
        L5([Success]):::success
    end

    Start([Phase 5 Entry]) --> Filter[5.1 Filter Findings:<br>remove REFUTED]
    Filter --> Sort[5.2 Sort by Severity:<br>CRITICAL -> HIGH -> MEDIUM<br>-> LOW -> NIT -> PRAISE]
    Sort --> Verdict[5.3 Determine Verdict]

    Verdict --> VerdictLogic{Highest severity<br>in findings?}
    VerdictLogic -->|CRITICAL or HIGH| ReqChanges[Verdict =<br>REQUEST_CHANGES]
    VerdictLogic -->|MEDIUM| Comment[Verdict =<br>COMMENT]
    VerdictLogic -->|LOW / NIT / none| Approve[Verdict =<br>APPROVE]

    ReqChanges --> Rationale[Generate verdict rationale]
    Comment --> Rationale
    Approve --> Rationale

    Rationale --> RenderFindings[5.4 Render each finding<br>with template]
    RenderFindings --> InconclusiveTag{Finding is<br>INCONCLUSIVE?}
    InconclusiveTag -->|Yes| AddFlag[Append<br>NEEDS VERIFICATION tag]
    InconclusiveTag -->|No| NoFlag[Render normally]

    AddFlag --> ActionItems
    NoFlag --> ActionItems

    ActionItems[5.5 Generate Action Items:<br>CRITICAL/HIGH -> Fix<br>MEDIUM -> Consider]
    ActionItems --> PrevContext[5.6 Render Previous Context:<br>declined count, partial fixes,<br>alternatives accepted]

    PrevContext --> RenderReport[Assemble full report<br>from template]
    RenderReport --> WriteReport[5.7 Write review-report.md]
    WriteReport --> WriteSummary[5.8 Write review-summary.json]

    WriteSummary --> MemSummary[Persist Review Summary:<br>store outcome, finding breakdown,<br>risk assessment in memory]

    MemSummary --> SelfCheck[Phase 5 Self-Check:<br>REFUTED filtered, sorted by severity,<br>verdict determined, report rendered,<br>action items generated, previous context included,<br>review-report.md + review-summary.json written]:::gate

    SelfCheck -->|All pass| Done([Review Complete]):::success
    SelfCheck -->|Any fail| FixReport[Fix failing items]
    FixReport --> SelfCheck

    classDef gate fill:#ff6b6b,stroke:#d44b4b,color:#fff
    classDef success fill:#51cf66,stroke:#37a34d,color:#fff
```

---

## Artifact Flow

Data dependencies between phases and their output artifacts.

```mermaid
flowchart LR
    subgraph Phase1[Phase 1: Strategic Planning]
        M[review-manifest.json]
        P[review-plan.md]
    end

    subgraph Phase2[Phase 2: Context Analysis]
        CA[context-analysis.md]
        PI[previous-items.json]
    end

    subgraph Phase3[Phase 3: Deep Review]
        FJ[findings.json]
        FM[findings.md]
    end

    subgraph Phase4[Phase 4: Verification]
        VA[verification-audit.md]
        FJ2[findings.json<br>updated]
    end

    subgraph Phase5[Phase 5: Report Generation]
        RR[review-report.md]
        RS[review-summary.json]
    end

    M --> CA
    M --> FJ
    PI --> FJ
    FJ --> VA
    FJ --> FJ2
    FJ2 --> RR
    FJ2 --> RS
    M --> RR
    CA --> RR
    VA --> RR
```

---

## Legend

| Color | Meaning |
|---|---|
| Blue (`#4a9eff`) | Subagent dispatch |
| Red (`#ff6b6b`) | Quality gate / self-check |
| Green (`#51cf66`) | Success terminal |
| Default | Process / decision / I-O |

## MCP Tool and Git Command Usage

| Tool / Command | Phase(s) | Purpose |
|---|---|---|
| `pr_fetch` | 1, 2 | Fetch PR metadata |
| `pr_files` | 1 | Extract changed file list |
| `pr_diff` | 3 | Parse unified diff |
| `pr_match_patterns` | 1 | Categorize files by risk |
| `memory_recall` | 1, 2 | Load prior findings, false positives, review decisions |
| `memory_store_memories` | 4, 5 | Persist verified findings and review summaries |
| `git merge-base` | 1 | Find common ancestor |
| `git diff --name-only` | 1 | List changed files |
| `git diff` | 3 | Get full diff content |
| `git show` | 4 | Verify file contents at SHA |
| `git rev-parse HEAD` | 4 | Branch safety check for PR mode |

## Source Cross-Reference

| Diagram Node | Source Location |
|---|---|
| Mode Router | `SKILL.md` lines 76-98 (Mode Router table + PR Mode critical section) |
| Phase 1 / `/advanced-code-review-plan` | `SKILL.md` lines 114-127, `advanced-code-review-plan.md` full |
| Target Resolution errors | `advanced-code-review-plan.md` lines 44-50 (Error Handling table) |
| Risk Categorization (HIGH/MEDIUM/LOW) | `advanced-code-review-plan.md` lines 66-92 |
| Complexity Estimation | `advanced-code-review-plan.md` lines 98-126 |
| Phase 2 / `/advanced-code-review-context` | `SKILL.md` lines 130-143, `advanced-code-review-context.md` full |
| Previous Items States | `advanced-code-review-context.md` lines 72-100 |
| Re-check Detection patterns | `advanced-code-review-context.md` lines 118-147 |
| Phase 3 / `/advanced-code-review-review` | `SKILL.md` lines 148-155, `advanced-code-review-review.md` full |
| Multi-pass order (Security/Correctness/Quality/Polish) | `advanced-code-review-review.md` lines 19-27 |
| Severity Decision Tree | `advanced-code-review-review.md` lines 40-66 |
| Previous Items Integration | `advanced-code-review-review.md` lines 106-133 |
| Phase 4 / `/advanced-code-review-verify` | `SKILL.md` lines 159-172, `advanced-code-review-verify.md` full |
| Branch Safety Check (4.0) | `advanced-code-review-verify.md` lines 20-52 |
| Claim Types and Extraction | `advanced-code-review-verify.md` lines 60-156 |
| Verification Functions | `advanced-code-review-verify.md` lines 158-261 |
| Signal-to-Noise Calculation | `advanced-code-review-verify.md` lines 331-359 |
| Duplicate Detection | `advanced-code-review-verify.md` lines 296-313 |
| Circuit Breaker (3+ failures) | `SKILL.md` lines 240-243 |
| Phase 5 / `/advanced-code-review-report` | `SKILL.md` lines 175-187, `advanced-code-review-report.md` full |
| Verdict Determination | `advanced-code-review-report.md` lines 49-87 |
| Action Items Generation | `advanced-code-review-report.md` lines 166-179 |
| Final Self-Check | `SKILL.md` lines 250-273 |

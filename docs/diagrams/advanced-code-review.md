# Advanced Code Review - Workflow Diagrams

## Cross-Reference Table

| Overview Node | Detail Diagram |
|---------------|----------------|
| P1 - Strategic Planning | [Phase 1 Detail](#phase-1-strategic-planning-detail) |
| P2 - Context Analysis | [Phase 2 Detail](#phase-2-context-analysis-detail) |
| P3 - Deep Review | [Phase 3 Detail](#phase-3-deep-review-detail) |
| P4 - Verification | [Phase 4 Detail](#phase-4-verification-detail) |
| P5 - Report Generation | [Phase 5 Detail](#phase-5-report-generation-detail) |

---

## Overview

High-level phase flow with mode routing, circuit breakers, and quality gates.

```mermaid
flowchart TD
    subgraph Legend
        L1[Process]
        L2{Decision}
        L3([Terminal])
        L4[/Input/Output/]
        L5["Subagent dispatch"]
        L6["Quality gate"]
        style L5 fill:#4a9eff,color:#fff
        style L6 fill:#ff6b6b,color:#fff
        style L3 fill:#51cf66,color:#000
    end

    START([User invokes<br>advanced-code-review]) --> INPUT[/Parse inputs:<br>target, --base, --scope,<br>--offline, --continue, --json/]

    INPUT --> RESUME{--continue<br>flag?}
    RESUME -->|Yes| LOAD_SESSION[Load previous<br>review session]
    LOAD_SESSION --> P3
    RESUME -->|No| MODE{Target<br>pattern?}

    MODE -->|Branch name| LOCAL_MODE[Local mode<br>source: local files]
    MODE -->|PR number/URL| PR_MODE[PR mode<br>source: diff only]
    MODE -->|Any + --offline| OFFLINE_MODE[Offline mode<br>source: local files]

    LOCAL_MODE --> P1
    PR_MODE --> P1
    OFFLINE_MODE --> P1

    P1["Phase 1: Strategic Planning<br>/advanced-code-review-plan"]
    P1 --> SC1{"Phase 1<br>self-check?"}
    style SC1 fill:#ff6b6b,color:#fff
    SC1 -->|Fail: target<br>not resolved| CB1([Circuit breaker:<br>target resolution failed])
    SC1 -->|Fail: no diff| CB2([Circuit breaker:<br>no changes found])
    SC1 -->|Pass| P2
    style CB1 fill:#ff6b6b,color:#fff
    style CB2 fill:#ff6b6b,color:#fff

    P2["Phase 2: Context Analysis<br>/advanced-code-review-context"]
    P2 --> SC2{"Phase 2<br>self-check?"}
    style SC2 fill:#ff6b6b,color:#fff
    SC2 -->|Fail| P2_WARN[Log warning,<br>proceed with<br>empty context]
    SC2 -->|Pass| P3
    P2_WARN --> P3

    P3["Phase 3: Deep Review<br>/advanced-code-review-review"]
    P3 --> SC3{"Phase 3<br>self-check?"}
    style SC3 fill:#ff6b6b,color:#fff
    SC3 -->|Fail| SC3_FIX[Fix incomplete<br>findings]
    SC3_FIX --> SC3
    SC3 -->|Pass| P4

    P4["Phase 4: Verification<br>/advanced-code-review-verify"]
    P4 --> SC4{"Phase 4<br>self-check?"}
    style SC4 fill:#ff6b6b,color:#fff
    SC4 -->|Fail: >3 consecutive<br>verification failures| CB3([Circuit breaker:<br>verification failures])
    SC4 -->|Fail: timeout| CB4([Circuit breaker:<br>verification timeout])
    SC4 -->|Fail: other| SC4_FIX[Fix verification<br>issues]
    SC4_FIX --> SC4
    SC4 -->|Pass| P5
    style CB3 fill:#ff6b6b,color:#fff
    style CB4 fill:#ff6b6b,color:#fff

    P5["Phase 5: Report Generation<br>/advanced-code-review-report"]
    P5 --> SC5{"Phase 5<br>self-check?"}
    style SC5 fill:#ff6b6b,color:#fff
    SC5 -->|Fail| SC5_FIX[Fix report<br>issues]
    SC5_FIX --> SC5
    SC5 -->|Pass| FINAL

    FINAL{"Final<br>self-check?"}
    style FINAL fill:#ff6b6b,color:#fff
    FINAL -->|Fail| FINAL_FIX[Fix remaining<br>issues]
    FINAL_FIX --> FINAL
    FINAL -->|Pass| MEMORY[Persist review<br>summary to memory]
    MEMORY --> DONE([Review complete:<br>8 artifacts written])
    style DONE fill:#51cf66,color:#000
```

---

## Phase 1: Strategic Planning Detail

Target resolution, diff acquisition, risk categorization, complexity estimation, and priority ordering.

```mermaid
flowchart TD
    subgraph Legend
        L1[Process]
        L2{Decision}
        L3([Terminal])
        L4["Subagent / MCP tool"]
        L6["Quality gate"]
        style L4 fill:#4a9eff,color:#fff
        style L6 fill:#ff6b6b,color:#fff
        style L3 fill:#51cf66,color:#000
    end

    START([Phase 1 Start]) --> MEMORY_RECALL["memory_recall:<br>prior findings,<br>false positive patterns"]
    style MEMORY_RECALL fill:#4a9eff,color:#fff

    MEMORY_RECALL --> RESOLVE[1.1 Target Resolution]
    RESOLVE --> RES_ERR{Resolution<br>error?}

    RES_ERR -->|E_TARGET_NOT_FOUND| LIST_BRANCHES[List similar branches]
    LIST_BRANCHES --> ABORT1([Abort: target not found])

    RES_ERR -->|E_MERGE_BASE_FAILED| FALLBACK[Fallback to HEAD~10,<br>log warning]
    FALLBACK --> DIFF_ACQ

    RES_ERR -->|E_NO_DIFF| ABORT2([Abort: no changes])

    RES_ERR -->|OK| DIFF_ACQ[1.2 Diff Acquisition]

    DIFF_ACQ --> DIFF_MODE{Review<br>mode?}
    DIFF_MODE -->|Local| GIT_DIFF[git diff --name-only<br>merge_base...HEAD]
    DIFF_MODE -->|PR| PR_FILES["pr_files(pr_result)"]
    style PR_FILES fill:#4a9eff,color:#fff

    GIT_DIFF --> CATEGORIZE
    PR_FILES --> CATEGORIZE

    CATEGORIZE[1.3 Risk Categorization<br>HIGH / MEDIUM / LOW]
    CATEGORIZE --> COMPLEXITY[1.4 Complexity Estimation<br>lines/15 + files*2 min]

    COMPLEXITY --> EFFORT{Effort<br>level?}
    EFFORT -->|"<=15 min"| SMALL[effort: small]
    EFFORT -->|"<=45 min"| MEDIUM_E[effort: medium]
    EFFORT -->|">45 min"| LARGE[effort: large]

    SMALL --> SCOPE
    MEDIUM_E --> SCOPE
    LARGE --> SCOPE

    SCOPE[1.5 Risk-Weighted Scope<br>HIGH*3 + MED*2 + LOW*1]
    SCOPE --> PRIORITY[1.6 Priority Ordering<br>HIGH -> MEDIUM -> LOW]

    PRIORITY --> WRITE_MANIFEST[1.7 Write<br>review-manifest.json]
    PRIORITY --> WRITE_PLAN[1.8 Write<br>review-plan.md]

    WRITE_MANIFEST --> SELF_CHECK
    WRITE_PLAN --> SELF_CHECK

    SELF_CHECK{"Self-Check:<br>target resolved?<br>files categorized?<br>complexity estimated?<br>artifacts written?"}
    style SELF_CHECK fill:#ff6b6b,color:#fff
    SELF_CHECK -->|Pass| DONE([Phase 1 Complete])
    style DONE fill:#51cf66,color:#000
    SELF_CHECK -->|Fail| STOP([STOP: fix before proceeding])
    style STOP fill:#ff6b6b,color:#fff
```

---

## Phase 2: Context Analysis Detail

Previous review discovery, item status loading, PR history fetching, and re-check request detection.

```mermaid
flowchart TD
    subgraph Legend
        L1[Process]
        L2{Decision}
        L3([Terminal])
        L4["Subagent / MCP tool"]
        L6["Quality gate"]
        style L4 fill:#4a9eff,color:#fff
        style L6 fill:#ff6b6b,color:#fff
        style L3 fill:#51cf66,color:#000
    end

    START([Phase 2 Start]) --> DISCOVER[2.1 Previous Review<br>Discovery]
    DISCOVER --> FOUND{Previous<br>review found?}

    FOUND -->|Not found| MEMORY_FALLBACK["memory_recall:<br>review decisions<br>for component"]
    style MEMORY_FALLBACK fill:#4a9eff,color:#fff
    MEMORY_FALLBACK --> BUILD_CTX

    FOUND -->|Found but stale<br>>30 days| MEMORY_FALLBACK
    FOUND -->|Found but<br>incomplete| MEMORY_FALLBACK

    FOUND -->|Found and valid| LOAD_ITEMS[2.2 Load Previous Items]

    LOAD_ITEMS --> CLASSIFY{Item<br>status?}
    CLASSIFY -->|PENDING| PENDING[Include if<br>still present]
    CLASSIFY -->|FIXED| FIXED[Do not re-raise]
    CLASSIFY -->|DECLINED| DECLINED[Do NOT re-raise<br>respect decision]
    CLASSIFY -->|PARTIAL| PARTIAL[Note pending<br>parts only]
    CLASSIFY -->|ALTERNATIVE| ALT_CHECK{Alternative<br>accepted?}
    ALT_CHECK -->|Yes| ALT_ACCEPT[Do not re-raise<br>original issue]
    ALT_CHECK -->|No| ALT_REJECT[Re-evaluate<br>original concern]

    PENDING --> PR_FETCH_CHECK
    FIXED --> PR_FETCH_CHECK
    DECLINED --> PR_FETCH_CHECK
    PARTIAL --> PR_FETCH_CHECK
    ALT_ACCEPT --> PR_FETCH_CHECK
    ALT_REJECT --> PR_FETCH_CHECK

    PR_FETCH_CHECK{Online<br>mode?}
    PR_FETCH_CHECK -->|Yes| PR_FETCH[2.3 PR History Fetching]
    PR_FETCH_CHECK -->|No / Offline| SKIP_PR[Skip PR context<br>log: OFFLINE]

    PR_FETCH --> PR_SUCCESS{Fetch<br>succeeded?}
    PR_SUCCESS -->|Yes| RECHECK[2.4 Re-check Request<br>Detection]
    PR_SUCCESS -->|No| WARN_PR[Log warning,<br>proceed with<br>empty PR context]

    RECHECK --> BUILD_CTX
    WARN_PR --> BUILD_CTX
    SKIP_PR --> BUILD_CTX

    BUILD_CTX[2.5 Build Context Object<br>declined, partial,<br>alternative, recheck]

    BUILD_CTX --> WRITE_CONTEXT[2.6 Write<br>context-analysis.md]
    BUILD_CTX --> WRITE_ITEMS[2.7 Write<br>previous-items.json]

    WRITE_CONTEXT --> SELF_CHECK
    WRITE_ITEMS --> SELF_CHECK

    SELF_CHECK{"Self-Check:<br>previous review checked?<br>items loaded?<br>PR context fetched?<br>rechecks extracted?<br>artifacts written?"}
    style SELF_CHECK fill:#ff6b6b,color:#fff

    SELF_CHECK -->|Pass| DONE([Phase 2 Complete])
    style DONE fill:#51cf66,color:#000
    SELF_CHECK -->|Fail| WARN[Log warning,<br>proceed with<br>empty context<br>Phase 2 non-blocking]
    WARN --> DONE
```

---

## Phase 3: Deep Review Detail

Multi-pass code analysis with previous-items integration, severity classification, and finding generation.

```mermaid
flowchart TD
    subgraph Legend
        L1[Process]
        L2{Decision}
        L3([Terminal])
        L4["Subagent / MCP tool"]
        L6["Quality gate"]
        style L4 fill:#4a9eff,color:#fff
        style L6 fill:#ff6b6b,color:#fff
        style L3 fill:#51cf66,color:#000
    end

    START([Phase 3 Start]) --> FILE_LOOP[For each file in<br>priority order]

    FILE_LOOP --> PASS1[Pass 1: Security<br>CRITICAL / HIGH<br>injection, auth, secrets]

    PASS1 --> PASS2[Pass 2: Correctness<br>HIGH / MEDIUM<br>logic, edge cases, races]

    PASS2 --> PASS3[Pass 3: Quality<br>MEDIUM / LOW<br>maintainability, patterns]

    PASS3 --> PASS4[Pass 4: Polish<br>LOW / NIT<br>style, naming, docs]

    PASS4 --> PRAISE_SCAN[3.7 Noteworthy<br>Collection<br>PRAISE findings]

    PRAISE_SCAN --> PREV_CHECK{Check finding<br>against previous<br>items}

    PREV_CHECK --> PREV_DECLINED{Matches<br>declined<br>item?}
    PREV_DECLINED -->|Yes| SKIP_FINDING[Skip finding<br>status: declined]
    PREV_DECLINED -->|No| PREV_ALT{Matches<br>accepted<br>alternative?}
    PREV_ALT -->|Yes| SKIP_ALT[Skip finding<br>status: alternative_accepted]
    PREV_ALT -->|No| PREV_PARTIAL{Matches<br>partial<br>pending?}
    PREV_PARTIAL -->|Yes| TAG_PARTIAL[Tag finding<br>status: partial_pending]
    PREV_PARTIAL -->|No| NEW_FINDING[New finding<br>status: null]

    TAG_PARTIAL --> SEVERITY
    NEW_FINDING --> SEVERITY

    SEVERITY{Severity<br>Decision Tree}
    SEVERITY -->|Security/data loss| SEV_CRIT[CRITICAL]
    SEVERITY -->|Broken contracts/<br>core functionality| SEV_HIGH[HIGH]
    SEVERITY -->|Quality/maintainability| SEV_MED[MEDIUM]
    SEVERITY -->|Minor improvement| SEV_LOW[LOW]
    SEVERITY -->|Purely stylistic| SEV_NIT[NIT]
    SEVERITY -->|Needs contributor input| SEV_Q[QUESTION]
    SEVERITY -->|Positive pattern| SEV_P[PRAISE]

    SEV_CRIT --> VALIDATE_FIELDS
    SEV_HIGH --> VALIDATE_FIELDS
    SEV_MED --> VALIDATE_FIELDS
    SEV_LOW --> VALIDATE_FIELDS
    SEV_NIT --> VALIDATE_FIELDS
    SEV_Q --> VALIDATE_FIELDS
    SEV_P --> VALIDATE_FIELDS

    VALIDATE_FIELDS{Required fields<br>present?<br>id, severity, category,<br>file, line, evidence}
    style VALIDATE_FIELDS fill:#ff6b6b,color:#fff
    VALIDATE_FIELDS -->|No| FIX_FIELDS[Complete<br>missing fields]
    FIX_FIELDS --> VALIDATE_FIELDS
    VALIDATE_FIELDS -->|Yes| COLLECT[Add to findings list]

    SKIP_FINDING --> MORE_FILES
    SKIP_ALT --> MORE_FILES
    COLLECT --> MORE_FILES

    MORE_FILES{More files<br>to review?}
    MORE_FILES -->|Yes| FILE_LOOP
    MORE_FILES -->|No| WRITE_JSON[3.8 Write<br>findings.json]

    WRITE_JSON --> WRITE_MD[3.9 Write<br>findings.md]

    WRITE_MD --> SELF_CHECK{"Self-Check:<br>all files reviewed?<br>all 4 passes complete?<br>declined not re-raised?<br>all findings have fields?<br>artifacts written?"}
    style SELF_CHECK fill:#ff6b6b,color:#fff
    SELF_CHECK -->|Fail| FIX_REVIEW[Fix incomplete review]
    FIX_REVIEW --> SELF_CHECK
    SELF_CHECK -->|Pass| DONE([Phase 3 Complete])
    style DONE fill:#51cf66,color:#000
```

---

## Phase 4: Verification Detail

Branch safety check, claim extraction, multi-type verification, duplicate detection, and signal-to-noise calculation.

```mermaid
flowchart TD
    subgraph Legend
        L1[Process]
        L2{Decision}
        L3([Terminal])
        L4["Subagent / MCP tool"]
        L6["Quality gate"]
        style L4 fill:#4a9eff,color:#fff
        style L6 fill:#ff6b6b,color:#fff
        style L3 fill:#51cf66,color:#000
    end

    START([Phase 4 Start]) --> BRANCH_CHECK[4.0 Pre-Flight:<br>Branch Safety Check<br>git rev-parse HEAD]

    BRANCH_CHECK --> SOURCE{Review<br>source?}
    SOURCE -->|"LOCAL_FILES<br>(local HEAD == PR HEAD<br>or local branch review)"| DUPES
    SOURCE -->|"DIFF_ONLY<br>(PR review, HEAD mismatch)"| DIFF_ONLY_MODE[All findings marked<br>INCONCLUSIVE<br>with NEEDS VERIFICATION]
    DIFF_ONLY_MODE --> WRITE_AUDIT

    DUPES[4.6 Duplicate Detection<br>same file + line + category]
    DUPES --> MERGE_DUPES[Merge duplicate<br>findings]

    MERGE_DUPES --> LINE_VAL[4.7 Line Number<br>Validation]
    LINE_VAL --> LINE_OK{Lines<br>valid?}
    LINE_OK -->|No| MARK_INCON1[Mark INCONCLUSIVE]
    LINE_OK -->|Yes| FINDING_LOOP

    MARK_INCON1 --> FINDING_LOOP

    FINDING_LOOP[For each finding]
    FINDING_LOOP --> EXTRACT[4.3 Extract Claims<br>from finding]

    EXTRACT --> HAS_CLAIMS{Claims<br>extracted?}
    HAS_CLAIMS -->|No claims| INCON_NO_CLAIMS[Mark INCONCLUSIVE<br>no verifiable claims]
    HAS_CLAIMS -->|Yes| CLAIM_LOOP[For each claim]

    CLAIM_LOOP --> CLAIM_TYPE{Claim<br>type?}
    CLAIM_TYPE -->|line_content| VER_LINE[verify_line_content<br>read line, pattern match]
    CLAIM_TYPE -->|function_behavior| VER_FUNC[verify_function_behavior<br>read function, check behavior]
    CLAIM_TYPE -->|call_pattern| VER_CALL[verify_call_pattern<br>trace callers]
    CLAIM_TYPE -->|pattern_violation| VER_PATTERN[verify_pattern_violation<br>compare two locations]

    VER_LINE --> AGGREGATE
    VER_FUNC --> AGGREGATE
    VER_CALL --> AGGREGATE
    VER_PATTERN --> AGGREGATE

    AGGREGATE{Aggregate<br>claim results}
    AGGREGATE -->|Any REFUTED| VERDICT_REF[REFUTED]
    AGGREGATE -->|Any INCONCLUSIVE<br>no REFUTED| VERDICT_INC[INCONCLUSIVE]
    AGGREGATE -->|All VERIFIED| VERDICT_VER[VERIFIED]

    VERDICT_REF --> HANDLE_REF[4.9 Remove from output<br>log in audit]
    VERDICT_INC --> HANDLE_INC[4.10 Keep with flag<br>NEEDS VERIFICATION]
    VERDICT_VER --> HANDLE_VER[Keep in output]
    INCON_NO_CLAIMS --> HANDLE_INC

    HANDLE_REF --> MORE_FINDINGS
    HANDLE_INC --> MORE_FINDINGS
    HANDLE_VER --> MORE_FINDINGS

    MORE_FINDINGS{More<br>findings?}
    MORE_FINDINGS -->|Yes| FINDING_LOOP
    MORE_FINDINGS -->|No| SNR

    SNR[4.8 Signal-to-Noise<br>Calculation<br>signal / signal+noise]

    SNR --> PERSIST["memory_store_memories:<br>CONFIRMED as antipattern<br>REFUTED as false-positive"]
    style PERSIST fill:#4a9eff,color:#fff

    PERSIST --> WRITE_AUDIT[4.11 Write<br>verification-audit.md]
    WRITE_AUDIT --> UPDATE_JSON[Update findings.json<br>with verification_status]

    UPDATE_JSON --> SELF_CHECK{"Self-Check:<br>all findings verified?<br>REFUTED removed?<br>INCONCLUSIVE flagged?<br>duplicates merged?<br>lines validated?<br>SNR calculated?<br>artifacts written?"}
    style SELF_CHECK fill:#ff6b6b,color:#fff

    SELF_CHECK -->|">3 consecutive<br>verification failures"| CB([Circuit breaker:<br>verification failures])
    style CB fill:#ff6b6b,color:#fff
    SELF_CHECK -->|Timeout exceeded| CB2([Circuit breaker:<br>timeout 60s])
    style CB2 fill:#ff6b6b,color:#fff
    SELF_CHECK -->|Fail: other| FIX[Fix issues]
    FIX --> SELF_CHECK
    SELF_CHECK -->|Pass| DONE([Phase 4 Complete])
    style DONE fill:#51cf66,color:#000
```

---

## Phase 5: Report Generation Detail

Finding filtering, severity sorting, verdict determination, template rendering, and artifact output.

```mermaid
flowchart TD
    subgraph Legend
        L1[Process]
        L2{Decision}
        L3([Terminal])
        L4["Subagent / MCP tool"]
        L6["Quality gate"]
        style L4 fill:#4a9eff,color:#fff
        style L6 fill:#ff6b6b,color:#fff
        style L3 fill:#51cf66,color:#000
    end

    START([Phase 5 Start]) --> FILTER[5.1 Filter Findings<br>remove REFUTED]

    FILTER --> SORT[5.2 Sort by Severity<br>CRITICAL -> HIGH -><br>MEDIUM -> LOW -> NIT -> PRAISE]

    SORT --> VERDICT[5.3 Verdict Determination]
    VERDICT --> V_LOGIC{Highest<br>severity<br>remaining?}

    V_LOGIC -->|CRITICAL or HIGH| REQ_CHANGES[REQUEST_CHANGES<br>N blocking issues]
    V_LOGIC -->|MEDIUM| COMMENT[COMMENT<br>N medium issues<br>worth discussing]
    V_LOGIC -->|LOW / NIT / none| APPROVE[APPROVE<br>no blocking issues]

    REQ_CHANGES --> RENDER
    COMMENT --> RENDER
    APPROVE --> RENDER

    RENDER[5.4 Template Rendering<br>report.md.tpl]
    RENDER --> RENDER_FINDINGS[Render each finding<br>with language detection<br>and INCONCLUSIVE flags]

    RENDER_FINDINGS --> ACTION[5.5 Action Items<br>Generation]
    ACTION --> ACTION_TYPE{Finding<br>severity?}
    ACTION_TYPE -->|CRITICAL / HIGH| FIX_ITEM["Fix [id]: [summary]"]
    ACTION_TYPE -->|MEDIUM| CONSIDER_ITEM["Consider [id]: [summary]"]
    ACTION_TYPE -->|LOW / NIT| NO_ACTION[No action item]

    FIX_ITEM --> PREV_CTX
    CONSIDER_ITEM --> PREV_CTX
    NO_ACTION --> PREV_CTX

    PREV_CTX[5.6 Previous Context<br>Section<br>declined, partial,<br>alternative counts]

    PREV_CTX --> WRITE_REPORT[5.7 Write<br>review-report.md]
    PREV_CTX --> WRITE_SUMMARY[5.8 Write<br>review-summary.json]

    WRITE_REPORT --> WRITE_FILES[5.9 Write all artifacts<br>to review directory]
    WRITE_SUMMARY --> WRITE_FILES

    WRITE_FILES --> PERSIST["memory_store_memories:<br>review summary,<br>severity breakdown,<br>risk assessment"]
    style PERSIST fill:#4a9eff,color:#fff

    PERSIST --> SELF_CHECK{"Self-Check:<br>REFUTED removed?<br>sorted by severity?<br>verdict determined?<br>report rendered?<br>action items generated?<br>previous context included?<br>all artifacts written?"}
    style SELF_CHECK fill:#ff6b6b,color:#fff

    SELF_CHECK -->|Fail| FIX[Fix report issues]
    FIX --> SELF_CHECK
    SELF_CHECK -->|Pass| DONE([Phase 5 Complete])
    style DONE fill:#51cf66,color:#000
```

---

## Artifact Flow

Shows the data flow between phases via their output artifacts.

```mermaid
flowchart LR
    subgraph "Phase 1"
        M[review-manifest.json]
        P[review-plan.md]
    end

    subgraph "Phase 2"
        CA[context-analysis.md]
        PI[previous-items.json]
    end

    subgraph "Phase 3"
        FJ[findings.json]
        FM[findings.md]
    end

    subgraph "Phase 4"
        VA[verification-audit.md]
        FJ2[findings.json<br>updated]
    end

    subgraph "Phase 5"
        RR[review-report.md]
        RS[review-summary.json]
    end

    M -->|manifest| CA
    M -->|manifest| FJ
    PI -->|declined/partial/<br>alternative items| FJ
    FJ -->|raw findings| VA
    FJ -->|raw findings| FJ2
    FJ2 -->|verified findings| RR
    FJ2 -->|verified findings| RS
    M -->|target info| RR
    M -->|target info| RS
    CA -->|previous context| RR
    VA -->|SNR score| RR
    VA -->|SNR score| RS
```

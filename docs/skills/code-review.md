# code-review

Quick code review covering correctness, style, and common issues across four modes: self-review before PRs, processing received feedback, reviewing others' code, and deep audit passes. Catches real issues with file-and-line references and honest severity classification. A core spellbook capability for routine review of changes before committing.

**Auto-invocation:** Your coding assistant will automatically invoke this skill when it detects a matching trigger.

> Use when reviewing code. Triggers: 'review my code', 'check my work', 'look over this', 'review PR #X', 'PR comments to address', 'reviewer said', 'address feedback', 'self-review before PR', 'audit this code'. Modes: --self (pre-PR self-review), --feedback (process received review comments), --give (review someone else's code/PR), --audit (deep single-pass analysis). For heavyweight multi-phase analysis, use advanced-code-review instead.

## Workflow Diagram

# Code Review Skill Diagrams

## Overview: Mode Router and High-Level Flow

```mermaid
flowchart TD
    subgraph Legend
        L1[Process]
        L2{Decision}
        L3([Terminal])
        L4[/"Subagent Dispatch"/]
        L5[[Quality Gate]]
    end

    style L4 fill:#4a9eff,color:#fff
    style L5 fill:#ff6b6b,color:#fff
    style L3 fill:#51cf66,color:#fff

    START([code-review invoked]) --> PARSE[Parse args:<br>mode flags + modifiers]
    PARSE --> TAROT_CHECK{--tarot<br>modifier?}
    TAROT_CHECK -->|Yes| LOAD_TAROT[Load code-review-tarot<br>persona mapping]
    TAROT_CHECK -->|No| MODE
    LOAD_TAROT --> MODE

    MODE{Mode?}
    MODE -->|--self / default| SELF[Self Mode<br>Pre-PR self-review]
    MODE -->|--feedback| FEEDBACK[/"Dispatch:<br>code-review-feedback"/]
    MODE -->|"--give target"| GIVE[/"Dispatch:<br>code-review-give"/]
    MODE -->|"--audit [scope]"| AUDIT[Audit Mode<br>Deep single-pass]

    SELF --> SELF_GATE[[Gate:<br>Critical=FAIL<br>Important=WARN<br>Minor=PASS]]
    FEEDBACK --> FB_OUT([Categorized responses<br>+ re-run self-review])
    GIVE --> GIVE_OUT[[Recommendation:<br>APPROVE /<br>REQUEST_CHANGES /<br>COMMENT]]
    AUDIT --> AUDIT_GATE[[Gate:<br>Risk Assessment<br>LOW/MED/HIGH/CRITICAL]]

    SELF_GATE --> DONE([Review Complete])
    FB_OUT --> DONE
    GIVE_OUT --> DONE
    AUDIT_GATE --> DONE

    style FEEDBACK fill:#4a9eff,color:#fff
    style GIVE fill:#4a9eff,color:#fff
    style SELF_GATE fill:#ff6b6b,color:#fff
    style GIVE_OUT fill:#ff6b6b,color:#fff
    style AUDIT_GATE fill:#ff6b6b,color:#fff
    style DONE fill:#51cf66,color:#fff
    style START fill:#51cf66,color:#fff
```

## Cross-Reference Table

| Overview Node | Detail Diagram |
|---------------|----------------|
| Self Mode | [Self Mode Detail](#self-mode-detail) |
| Feedback (code-review-feedback) | [Feedback Mode Detail](#feedback-mode-detail) |
| Give (code-review-give) | [Give Mode Detail](#give-mode-detail) |
| Audit Mode | [Audit Mode Detail](#audit-mode-detail) |
| Tarot Integration | [Tarot Modifier Detail](#tarot-modifier-detail) |

---

## Self Mode Detail

```mermaid
flowchart TD
    subgraph Legend
        L1[Process]
        L2{Decision}
        L3([Terminal])
        L5[[Quality Gate]]
    end
    style L5 fill:#ff6b6b,color:#fff
    style L3 fill:#51cf66,color:#fff

    S0([Self Mode Start]) --> S1["Get diff:<br>git diff merge-base..HEAD"]
    S1 --> S2["Memory Priming:<br>memory_recall(review findings)"]
    S2 --> S2B{spellbook-memory<br>context from files?}
    S2B -->|Yes| S2C[Incorporate file-specific<br>+ project-wide patterns]
    S2B -->|No| S3
    S2C --> S3

    S3[Multi-Pass Review]
    S3 --> P1[Pass 1: Logic]
    P1 --> P2[Pass 2: Integration]
    P2 --> P3[Pass 3: Security]
    P3 --> P4[Pass 4: Style]

    P4 --> S4[Generate findings:<br>severity + file:line + description]
    S4 --> S5["Persist significant findings:<br>memory_store_memories()"]
    S5 --> S5A{Finding type?}
    S5A -->|Confirmed issue| S5B["Store as antipattern<br>(warns future reviewers)"]
    S5A -->|False positive| S5C["Store as fact<br>tag: false-positive"]
    S5A -->|Minor / one-off| S5D[Do not store]
    S5B --> S6
    S5C --> S6
    S5D --> S6

    S6[[Severity Gate]]
    S6 --> G1{Highest severity?}
    G1 -->|Critical| FAIL([FAIL])
    G1 -->|Important| WARN([WARN])
    G1 -->|Minor only| PASS([PASS])

    style S0 fill:#51cf66,color:#fff
    style S6 fill:#ff6b6b,color:#fff
    style FAIL fill:#ff6b6b,color:#fff
    style WARN fill:#f59f00,color:#fff
    style PASS fill:#51cf66,color:#fff
```

---

## Feedback Mode Detail

Source: `commands/code-review-feedback.md`

```mermaid
flowchart TD
    subgraph Legend
        L1[Process]
        L2{Decision}
        L3([Terminal])
        L4[/"Subagent / Command"/]
    end
    style L4 fill:#4a9eff,color:#fff
    style L3 fill:#51cf66,color:#fff

    F0([Feedback Mode Start]) --> F1[Gather ALL feedback<br>across related PRs]
    F1 --> F2[Categorize each item:<br>bug / style / question<br>/ suggestion / nit]

    F2 --> F3{Decision<br>per item}
    F3 -->|Correct, improves code| ACCEPT[Accept:<br>make the change]
    F3 -->|Incorrect or harmful| PUSH[Push back:<br>disagree with evidence]
    F3 -->|Ambiguous| CLARIFY[Clarify:<br>ask questions]
    F3 -->|Valid but out of scope| DEFER[Defer:<br>acknowledge + follow-up]

    ACCEPT --> F4
    PUSH --> F4
    CLARIFY --> F4
    DEFER --> F4

    F4[Document rationale<br>for each decision]
    F4 --> F5[Fact-check:<br>verify technical claims]
    F5 --> F6[Execute fixes]
    F6 --> F7[/"Re-run self-review<br>(Self Mode)"/]
    F7 --> DONE([Responses sent<br>with templates])

    style F0 fill:#51cf66,color:#fff
    style F7 fill:#4a9eff,color:#fff
    style DONE fill:#51cf66,color:#fff
```

---

## Give Mode Detail

Source: `commands/code-review-give.md`

```mermaid
flowchart TD
    subgraph Legend
        L1[Process]
        L2{Decision}
        L3([Terminal])
        L5[[Quality Gate]]
    end
    style L5 fill:#ff6b6b,color:#fff
    style L3 fill:#51cf66,color:#fff

    G0([Give Mode Start]) --> G0A["Parse target:<br>PR#, URL, branch"]

    G0A --> G0B["Step 0: Load Project Conventions<br>Read CLAUDE.md, style configs,<br>code-review-instructions.md"]
    G0B --> G0C["Sample adjacent files<br>(NOT in changed file set)"]

    G0C --> G1["Step 1: Fetch and Inventory"]
    G1 --> G1A["Get diff via gh pr diff<br>or git diff"]
    G1A --> G1B["Build Coverage Manifest:<br>ALL changed files"]
    G1B --> G1C["Fetch prior PR feedback<br>via gh api"]
    G1C --> G1D{Prior feedback<br>exists?}
    G1D -->|Yes| G1E[Classify each:<br>ADDRESSED / STILL_OPEN]
    G1D -->|No| G2
    G1E --> G2

    G2["Step 2: Multi-Pass Review"]
    G2 --> MAND["Mandatory Dimensions<br>(all 6 per file)"]

    MAND --> D1["Correctness"]
    MAND --> D2["Security"]
    MAND --> D3["Error handling"]
    MAND --> D4["Data integrity"]
    MAND --> D5["API contracts"]
    MAND --> D6["Test coverage"]

    D1 & D2 & D3 & D4 & D5 & D6 --> COND{Conditional<br>triggers?}

    COND -->|Hot paths / DB ops| PERF[Performance pass]
    COND -->|Async / threading| CONC[Concurrency pass]
    COND -->|UI / frontend| A11Y[Accessibility pass]
    COND -->|None triggered| SEC

    PERF --> SEC
    CONC --> SEC
    A11Y --> SEC

    SEC["Security Pass<br>(always required):<br>Input validation, path traversal,<br>secrets, auth, injection, SSRF"]

    SEC --> CONC_CHECK{Async/threading<br>in diff?}
    CONC_CHECK -->|Yes| CONC_PASS["Concurrency Pass:<br>Event loop blocking,<br>thread safety, races,<br>interrupt handling,<br>lock ordering"]
    CONC_CHECK -->|No| G3

    CONC_PASS --> G3

    G3["Step 3: Output"]
    G3 --> MANIFEST[[Coverage Manifest Check:<br>all files evaluated?]]
    MANIFEST --> GAP{Gaps?}
    GAP -->|Yes| REPORT_GAP[Report coverage gaps]
    GAP -->|No| RECONCILE
    REPORT_GAP --> RECONCILE

    RECONCILE[Prior Feedback<br>Reconciliation]
    RECONCILE --> FINDINGS[Format findings:<br>severity + file:line<br>+ dimension + suggestion]

    FINDINGS --> VERDICT[[Recommendation Gate]]
    VERDICT --> V1{Verdict?}
    V1 -->|No issues / minor| APPROVE([APPROVE])
    V1 -->|Significant issues| REQ_CHANGES([REQUEST_CHANGES])
    V1 -->|Needs discussion| COMMENT([COMMENT])

    style G0 fill:#51cf66,color:#fff
    style MANIFEST fill:#ff6b6b,color:#fff
    style VERDICT fill:#ff6b6b,color:#fff
    style APPROVE fill:#51cf66,color:#fff
    style REQ_CHANGES fill:#ff6b6b,color:#fff
    style COMMENT fill:#f59f00,color:#fff
```

---

## Audit Mode Detail

```mermaid
flowchart TD
    subgraph Legend
        L1[Process]
        L2{Decision}
        L3([Terminal])
        L5[[Quality Gate]]
    end
    style L5 fill:#ff6b6b,color:#fff
    style L3 fill:#51cf66,color:#fff

    A0([Audit Mode Start]) --> A0A{Scope?}
    A0A -->|"(none)"| BRANCH[Branch changes]
    A0A -->|file.py| FILE[Single file]
    A0A -->|"dir/"| DIR[Directory]
    A0A -->|security| SECONLY[Security-only audit]
    A0A -->|all| ALL[Full codebase]

    BRANCH & FILE & DIR & SECONLY & ALL --> A1

    A1["Memory Priming:<br>memory_recall(review findings)"]
    A1 --> A1B{spellbook-memory<br>context?}
    A1B -->|Yes| A1C[Incorporate patterns]
    A1B -->|No| A2
    A1C --> A2

    A2[Multi-Pass Audit]
    A2 --> P1[Pass 1: Correctness]
    P1 --> P2[Pass 2: Security]
    P2 --> P3[Pass 3: Performance]
    P3 --> P4[Pass 4: Maintainability]
    P4 --> P5[Pass 5: Edge Cases]

    P5 --> A3[Generate output:<br>Executive Summary +<br>Findings by category]

    A3 --> A4["Persist significant findings:<br>memory_store_memories()"]
    A4 --> A5[[Risk Assessment Gate]]
    A5 --> R{Risk level?}
    R -->|No issues| LOW([LOW])
    R -->|Minor concerns| MED([MEDIUM])
    R -->|Significant issues| HIGH([HIGH])
    R -->|Security / data loss| CRIT([CRITICAL])

    style A0 fill:#51cf66,color:#fff
    style A5 fill:#ff6b6b,color:#fff
    style LOW fill:#51cf66,color:#fff
    style MED fill:#f59f00,color:#fff
    style HIGH fill:#ff6b6b,color:#fff
    style CRIT fill:#ff6b6b,color:#fff
```

---

## Tarot Modifier Detail

Source: `commands/code-review-tarot.md`

Applied as an overlay when `--tarot` flag is present on any mode.

```mermaid
flowchart TD
    subgraph Legend
        L1[Process]
        L2{Decision}
        L3([Terminal])
        L4[/"Subagent Dispatch"/]
    end
    style L4 fill:#4a9eff,color:#fff
    style L3 fill:#51cf66,color:#fff

    T0([--tarot flag detected]) --> T1{Which mode?}

    T1 -->|--self| TS[Self Mode +<br>Tarot dialogue wrapper]
    T1 -->|--give| TG[Give Mode +<br>Tarot dialogue wrapper]
    T1 -->|--audit| TA[Audit Mode +<br>Persona-per-pass]

    TA --> TA1[/"Hermit subagent:<br>Security Pass"/]
    TA --> TA2[/"Priestess subagent:<br>Architecture Pass"/]
    TA --> TA3[/"Fool subagent:<br>Assumption Pass"/]

    TA1 & TA2 & TA3 --> TA4[Magician: Synthesize<br>by evidence weight<br>(not majority vote)]

    TS --> DIALOG
    TG --> DIALOG

    DIALOG[Roundtable Dialogue Format]
    DIALOG --> D1["Magician opens:<br>Review convenes"]
    D1 --> D2["Hermit examines:<br>Security findings"]
    D2 --> D3["Priestess studies:<br>Architecture findings"]
    D3 --> D4["Fool challenges:<br>Hidden assumptions"]
    D4 --> D5["Magician synthesizes:<br>Final verdict"]

    TA4 --> SEP
    D5 --> SEP

    SEP[Code Output Separation:<br>Persona in dialogue ONLY,<br>formal findings persona-free]
    SEP --> DONE([Continue to<br>mode-specific output])

    style T0 fill:#51cf66,color:#fff
    style TA1 fill:#4a9eff,color:#fff
    style TA2 fill:#4a9eff,color:#fff
    style TA3 fill:#4a9eff,color:#fff
    style DONE fill:#51cf66,color:#fff
```

---

## MCP Tool Integration

```mermaid
flowchart LR
    subgraph "MCP Tools - Read/Analyze"
        PR_FETCH["pr_fetch(num_or_url)"]
        PR_DIFF["pr_diff(raw_diff)"]
        PR_MATCH["pr_match_patterns(files, root)"]
        PR_FILES["pr_files(pr_result)"]
    end

    subgraph "CLI - Write Operations"
        GH["gh CLI:<br>post reviews, replies"]
    end

    subgraph "Memory Tools"
        RECALL["memory_recall()"]
        STORE["memory_store_memories()"]
    end

    subgraph "Fallback Chain"
        direction TB
        F1{MCP available?} -->|Yes| F2[Use MCP tools]
        F1 -->|No| F3{gh CLI available?}
        F3 -->|Yes| F4[Use gh CLI]
        F3 -->|No| F5{Local diff available?}
        F5 -->|Yes| F6[Use git diff]
        F5 -->|No| F7[Manual paste]
    end
```

## Skill Content

``````````markdown
# Code Review

<ROLE>
Code Review Specialist. Catch real issues. Respect developer time.
</ROLE>

<analysis>
Unified skill routes to specialized handlers via mode flags.
Self-review catches issues early. Feedback mode processes received comments. Give mode provides helpful reviews. Audit mode does deep security/quality passes.
</analysis>

## Invariant Principles

1. **Evidence Over Assertion** - Every finding needs file:line reference
2. **Severity Honesty** - Critical=security/data loss; Important=correctness; Minor=style
3. **Context Awareness** - Same code may warrant different severity in different contexts
4. **Respect Time** - False positives erode trust; prioritize signal

## Inputs

| Input | Required | Description |
|-------|----------|-------------|
| `args` | Yes | Mode flags and targets |
| `git diff` | Auto | Changed files |
| `PR data` | If --pr | PR metadata via GitHub |

## Outputs

| Output | Type | Description |
|--------|------|-------------|
| `findings` | List | Issues with severity, file:line |
| `status` | Enum | PASS/WARN/FAIL or APPROVE/REQUEST_CHANGES |

## Mode Router

| Flag | Mode | Command File |
|------|------|-------------|
| `--self`, `-s`, (default: no flag given) | Pre-PR self-review | (inline below) |
| `--feedback`, `-f` | Process received feedback | `code-review-feedback` |
| `--give <target>` | Review someone else's code | `code-review-give` |
| `--audit [scope]` | Multi-pass deep-dive | (inline below) |

**Modifiers:** `--tarot` (roundtable dialogue via `code-review-tarot`), `--pr <num>` (PR source)

---

## MCP Tool Integration

| Tool | Purpose |
|------|---------|
| `pr_fetch(num_or_url)` | Fetch PR metadata and diff |
| `pr_diff(raw_diff)` | Parse diff into FileDiff objects |
| `pr_match_patterns(files, root)` | Heuristic pre-filtering |
| `pr_files(pr_result)` | Extract file list |

MCP tools for read/analyze. `gh` CLI for write operations (posting reviews, replies). Fallback: MCP unavailable -> gh CLI -> local diff -> manual paste.

---

## Self Mode (`--self`)

<reflection>
Self-review finds what you missed. Assume bugs exist. Hunt them.
</reflection>

**Workflow:**
1. Get diff: `git diff $(git merge-base origin/main HEAD)..HEAD`
2. **Memory Priming:** Before starting review passes, call `memory_recall(query="review finding [project_or_module]")` to surface:
   - Recurring issues in this codebase (focus review effort here)
   - Known false positives (avoid re-flagging accepted patterns)
   - Prior review decisions (respect precedent unless circumstances changed)
   If you received `<spellbook-memory>` context from reading the files under review, incorporate that as well. The explicit recall supplements auto-injection by surfacing project-wide patterns, not just file-specific ones.
3. Multi-pass: Logic > Integration > Security > Style
4. Generate findings with severity, file:line, description

Example finding: `src/auth/login.py:42 [Critical] Token written to log — data exposure risk`

5. **Persist Review Findings:** After finalizing findings, store significant ones for future reviews:
   ```
   memory_store_memories(memories='{"memories": [{"content": "[Finding description]. Severity: [level]. Status: [confirmed/false_positive/deferred].", "memory_type": "[fact or antipattern]", "tags": ["review", "[finding_category]", "[module]"], "citations": [{"file_path": "[reviewed_file]", "line_range": "[lines]"}]}]}')
   ```
   - Confirmed issues: memory_type = "antipattern" (warns future reviewers)
   - Confirmed false positives: memory_type = "fact" with tag "false-positive" (prevents re-flagging)
   - Do NOT store every minor finding. Store only: recurring patterns, surprising discoveries, and false positive determinations.
6. Gate: Critical=FAIL, Important=WARN, Minor only=PASS

---

## Audit Mode (`--audit [scope]`)

Scopes: (none)=branch changes, file.py, dir/, security, all

**Memory Priming:** Before starting audit passes, call `memory_recall(query="review finding [project_or_module]")` to surface recurring issues, known false positives, and prior review decisions. Incorporate any `<spellbook-memory>` context from files under audit as well.

**Passes:** Correctness > Security > Performance > Maintainability > Edge Cases

Output: Executive Summary, findings by category (same severity thresholds as Self Mode), Risk Assessment (LOW/MEDIUM/HIGH/CRITICAL)

**Persist Review Findings:** After finalizing audit findings, store significant ones using the same protocol as Self Mode (see step 5 above). Audit findings are especially valuable to persist given the depth of analysis.

---

<FORBIDDEN>
- Skip self-review for "small" changes
- Ignore Critical findings
- Dismiss feedback without evidence
- Give vague feedback without file:line
- Approve to avoid conflict
- Rate severity by effort instead of impact
</FORBIDDEN>

## Self-Check

- [ ] Correct mode identified
- [ ] All findings have file:line
- [ ] Severity based on impact, not effort
- [ ] Output matches mode spec

<FINAL_EMPHASIS>
Every finding without file:line is noise. Every severity inflated by effort is a lie. Your credibility as a reviewer depends on signal quality — accurate severity, concrete evidence, zero false positives that waste developer time.
</FINAL_EMPHASIS>
``````````

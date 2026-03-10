# code-review

Use when reviewing code. Triggers: 'review my code', 'check my work', 'look over this', 'review PR #X', 'PR comments to address', 'reviewer said', 'address feedback', 'self-review before PR', 'audit this code'. Modes: --self (pre-PR self-review), --feedback (process received review comments), --give (review someone else's code/PR), --audit (deep single-pass analysis). For heavyweight multi-phase analysis, use advanced-code-review instead.

## Workflow Diagram

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

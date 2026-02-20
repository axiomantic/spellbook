# code-review

Use when reviewing code. Triggers: 'review my code', 'check my work', 'look over this', 'review PR #X', 'PR comments to address', 'reviewer said', 'address feedback', 'self-review before PR', 'audit this code'. Modes: --self (pre-PR self-review), --feedback (process received review comments), --give (review someone else's code/PR), --audit (deep single-pass analysis). For heavyweight multi-phase analysis, use advanced-code-review instead.

## Workflow Diagram

# Diagram: code-review

Unified code review skill with four modes: self-review (pre-PR), feedback processing, giving reviews, and deep audit. Routes via mode flags to specialized handlers with MCP tool integration.

```mermaid
flowchart TD
    Start([Start Code Review])
    ParseArgs[Parse Mode Flags]
    ModeRouter{Which Mode?}

    %% Self Mode
    SelfMode[Self Mode]
    GetDiff[Get Merge-Base Diff]
    LogicPass[Logic Pass]
    IntegrationPass[Integration Pass]
    SecurityPass[Security Pass]
    StylePass[Style Pass]
    SelfFindings[Generate Findings]
    SelfGate{Severity Gate}
    SelfFail([FAIL: Critical Found])
    SelfWarn([WARN: Important Found])
    SelfPass([PASS: Minor Only])

    %% Feedback Mode
    FeedbackMode["/code-review-feedback"]
    ProcessComments[Process PR Comments]
    FeedbackOut([Feedback Addressed])

    %% Give Mode
    GiveMode["/code-review-give"]
    ReviewTarget[Review Target Code]
    GiveOut([Review Delivered])

    %% Audit Mode
    AuditMode[Audit Mode]
    AuditScope{Scope?}
    CorrectnessAudit[Correctness Pass]
    SecurityAudit[Security Pass]
    PerfAudit[Performance Pass]
    MaintAudit[Maintainability Pass]
    EdgeAudit[Edge Cases Pass]
    RiskAssess{Risk Assessment}
    AuditLow([LOW Risk])
    AuditMed([MEDIUM Risk])
    AuditHigh([HIGH Risk])
    AuditCrit([CRITICAL Risk])

    %% Tarot Modifier
    TarotCheck{--tarot flag?}
    TarotMode["/code-review-tarot"]

    %% MCP Integration
    MCPTools[MCP: pr_fetch, pr_diff]
    FallbackCLI[Fallback: gh CLI]
    FallbackLocal[Fallback: Local Diff]

    %% Self-Check
    FinalCheck{Self-Check Gate}
    Done([Review Complete])

    Start --> ParseArgs --> ModeRouter

    ModeRouter -->|"--self / default"| SelfMode
    ModeRouter -->|"--feedback"| FeedbackMode
    ModeRouter -->|"--give target"| GiveMode
    ModeRouter -->|"--audit"| AuditMode

    %% Self flow
    SelfMode --> TarotCheck
    TarotCheck -->|Yes| TarotMode --> GetDiff
    TarotCheck -->|No| GetDiff
    GetDiff --> LogicPass --> IntegrationPass --> SecurityPass --> StylePass
    StylePass --> SelfFindings --> SelfGate
    SelfGate -->|Critical| SelfFail
    SelfGate -->|Important| SelfWarn
    SelfGate -->|Minor only| SelfPass

    %% Feedback flow
    FeedbackMode --> ProcessComments --> FeedbackOut

    %% Give flow
    GiveMode --> MCPTools
    MCPTools -->|Available| ReviewTarget
    MCPTools -->|Unavailable| FallbackCLI --> ReviewTarget
    FallbackCLI -->|Unavailable| FallbackLocal --> ReviewTarget
    ReviewTarget --> GiveOut

    %% Audit flow
    AuditMode --> AuditScope
    AuditScope -->|"branch/file/dir/all"| CorrectnessAudit
    AuditScope -->|"security"| SecurityAudit
    CorrectnessAudit --> SecurityAudit --> PerfAudit --> MaintAudit --> EdgeAudit
    EdgeAudit --> RiskAssess
    RiskAssess -->|LOW| AuditLow
    RiskAssess -->|MEDIUM| AuditMed
    RiskAssess -->|HIGH| AuditHigh
    RiskAssess -->|CRITICAL| AuditCrit

    %% Final check
    SelfFail --> FinalCheck
    SelfWarn --> FinalCheck
    SelfPass --> FinalCheck
    FeedbackOut --> FinalCheck
    GiveOut --> FinalCheck
    AuditLow --> FinalCheck
    AuditMed --> FinalCheck
    AuditHigh --> FinalCheck
    AuditCrit --> FinalCheck
    FinalCheck -->|All checks pass| Done
    FinalCheck -->|"Missing file:line"| ParseArgs

    style Start fill:#4CAF50,color:#fff
    style Done fill:#4CAF50,color:#fff
    style SelfPass fill:#4CAF50,color:#fff
    style AuditLow fill:#4CAF50,color:#fff
    style FeedbackMode fill:#2196F3,color:#fff
    style GiveMode fill:#2196F3,color:#fff
    style TarotMode fill:#2196F3,color:#fff
    style GetDiff fill:#2196F3,color:#fff
    style LogicPass fill:#2196F3,color:#fff
    style IntegrationPass fill:#2196F3,color:#fff
    style SecurityPass fill:#2196F3,color:#fff
    style StylePass fill:#2196F3,color:#fff
    style SelfFindings fill:#2196F3,color:#fff
    style ProcessComments fill:#2196F3,color:#fff
    style ReviewTarget fill:#2196F3,color:#fff
    style CorrectnessAudit fill:#2196F3,color:#fff
    style SecurityAudit fill:#2196F3,color:#fff
    style PerfAudit fill:#2196F3,color:#fff
    style MaintAudit fill:#2196F3,color:#fff
    style EdgeAudit fill:#2196F3,color:#fff
    style MCPTools fill:#2196F3,color:#fff
    style FallbackCLI fill:#2196F3,color:#fff
    style FallbackLocal fill:#2196F3,color:#fff
    style ParseArgs fill:#2196F3,color:#fff
    style ModeRouter fill:#FF9800,color:#fff
    style TarotCheck fill:#FF9800,color:#fff
    style AuditScope fill:#FF9800,color:#fff
    style SelfGate fill:#f44336,color:#fff
    style RiskAssess fill:#f44336,color:#fff
    style FinalCheck fill:#f44336,color:#fff
    style SelfFail fill:#f44336,color:#fff
    style SelfWarn fill:#FF9800,color:#fff
    style AuditMed fill:#FF9800,color:#fff
    style AuditHigh fill:#f44336,color:#fff
    style AuditCrit fill:#f44336,color:#fff
    style FeedbackOut fill:#4CAF50,color:#fff
    style GiveOut fill:#4CAF50,color:#fff
    style SelfMode fill:#4CAF50,color:#fff
    style AuditMode fill:#4CAF50,color:#fff

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
| `--self`, `-s`, (default) | Pre-PR self-review | (inline below) |
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

**Principle:** MCP tools for read/analyze. `gh` CLI for write operations (posting reviews, replies).

**Fallback:** MCP unavailable -> gh CLI -> local diff -> manual paste.

---

## Self Mode (`--self`)

<reflection>
Self-review finds what you missed. Assume bugs exist. Hunt them.
</reflection>

**Workflow:**
1. Get diff: `git diff $(git merge-base origin/main HEAD)..HEAD`
2. Multi-pass: Logic > Integration > Security > Style
3. Generate findings with severity, file:line, description
4. Gate: Critical=FAIL, Important=WARN, Minor only=PASS

---

## Audit Mode (`--audit [scope]`)

Scopes: (none)=branch changes, file.py, dir/, security, all

**Passes:** Correctness > Security > Performance > Maintainability > Edge Cases

Output: Executive Summary, findings by category, Risk Assessment (LOW/MEDIUM/HIGH/CRITICAL)

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
``````````

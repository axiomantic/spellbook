<!-- diagram-meta: {"source": "skills/code-review/SKILL.md", "source_hash": "sha256:e05f8a81fe1f4497cfb0e02432abd70f98ab1c1d565e9a54676f0722ace01f74", "generated_at": "2026-02-20T00:13:41Z", "generator": "generate_diagrams.py"} -->
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

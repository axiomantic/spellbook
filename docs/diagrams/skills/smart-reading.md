<!-- diagram-meta: {"source": "skills/smart-reading/SKILL.md", "source_hash": "sha256:4f6e08e8da1c1a91d27a18907f201a83fb08b1c841f3cb3b61a180afc606dd3c", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: smart-reading

Protocol for reading files and command output without blind truncation or silent data loss. Decides approach based on content size and intent.

```mermaid
flowchart TD
    Start([Start: Read Request]) --> SizeKnown{Size Known?}

    SizeKnown -->|No| CheckSize[wc -l to measure]
    SizeKnown -->|Yes| EvalSize{Lines <= 200?}

    CheckSize --> EvalSize

    EvalSize -->|Yes| ReadDirect[Read Directly]
    EvalSize -->|No| NeedExact{Need Exact Text?}

    NeedExact -->|Yes| ReadOffset[Read with Offset/Limit]
    NeedExact -->|No| Delegate[Delegate to Subagent]

    Delegate --> SpecifyIntent[Specify Intent Statement]
    SpecifyIntent --> IntentType{Intent Type?}

    IntentType -->|Error Extraction| ExtractErrors[Extract Errors + Context]
    IntentType -->|Technical Summary| Summarize[Summarize Structure]
    IntentType -->|Presence Check| PresenceCheck[Check for Concept X]
    IntentType -->|Diff-Aware| DiffAnalysis[Compare Versions]
    IntentType -->|Structure Overview| Outline[Outline Module Structure]

    ExtractErrors --> SubagentReads[Subagent Reads ENTIRE Content]
    Summarize --> SubagentReads
    PresenceCheck --> SubagentReads
    DiffAnalysis --> SubagentReads
    Outline --> SubagentReads

    SubagentReads --> ReturnSummary[Return Targeted Summary]

    ReadDirect --> QG1{No Blind Truncation?}
    ReadOffset --> QG1
    ReturnSummary --> QG1

    QG1 -->|Pass| CmdOutput{Command Output?}
    QG1 -->|Fail| StopFix[STOP: Fix Approach]

    CmdOutput -->|Yes| CaptureDecision{Capture Strategy?}
    CmdOutput -->|No| SelfCheck

    CaptureDecision -->|Need Streaming + Analysis| TeeCapture[Capture with tee]
    CaptureDecision -->|Pure Analysis| DelegateCmd[Delegate Entire Command]
    CaptureDecision -->|Watch for Event| RunDirect[Run Directly]

    TeeCapture --> TempFile[Create Temp File]
    TempFile --> AnalyzeOutput[Analyze Output]
    AnalyzeOutput --> Cleanup[Cleanup Temp Files]
    Cleanup --> SelfCheck

    DelegateCmd --> SelfCheck
    RunDirect --> SelfCheck

    SelfCheck{Self-Check Passed?}
    SelfCheck -->|Yes| Done([Done])
    SelfCheck -->|No| StopFix

    style Start fill:#4CAF50,color:#fff
    style Done fill:#4CAF50,color:#fff
    style SizeKnown fill:#FF9800,color:#fff
    style EvalSize fill:#FF9800,color:#fff
    style NeedExact fill:#FF9800,color:#fff
    style IntentType fill:#FF9800,color:#fff
    style CmdOutput fill:#FF9800,color:#fff
    style CaptureDecision fill:#FF9800,color:#fff
    style SelfCheck fill:#f44336,color:#fff
    style QG1 fill:#f44336,color:#fff
    style StopFix fill:#f44336,color:#fff
    style CheckSize fill:#2196F3,color:#fff
    style ReadDirect fill:#2196F3,color:#fff
    style ReadOffset fill:#2196F3,color:#fff
    style Delegate fill:#4CAF50,color:#fff
    style SpecifyIntent fill:#2196F3,color:#fff
    style ExtractErrors fill:#2196F3,color:#fff
    style Summarize fill:#2196F3,color:#fff
    style PresenceCheck fill:#2196F3,color:#fff
    style DiffAnalysis fill:#2196F3,color:#fff
    style Outline fill:#2196F3,color:#fff
    style SubagentReads fill:#2196F3,color:#fff
    style ReturnSummary fill:#2196F3,color:#fff
    style TeeCapture fill:#2196F3,color:#fff
    style TempFile fill:#2196F3,color:#fff
    style AnalyzeOutput fill:#2196F3,color:#fff
    style Cleanup fill:#2196F3,color:#fff
    style DelegateCmd fill:#4CAF50,color:#fff
    style RunDirect fill:#2196F3,color:#fff
```

## Legend

| Color | Meaning |
|-------|---------|
| Green (#4CAF50) | Skill invocation |
| Blue (#2196F3) | Command/action |
| Orange (#FF9800) | Decision point |
| Red (#f44336) | Quality gate |

## Cross-Reference

| Node | Source Reference |
|------|----------------|
| Start: Read Request | Smart Reading Protocol (line 17) |
| wc -l to measure | "Size Before Strategy" principle (line 22) |
| Lines <= 200? | Decision Matrix (lines 46-52) |
| Read Directly | Decision Matrix: direct read for small files (line 48-49) |
| Read with Offset/Limit | Decision Matrix: targeted section read (line 50) |
| Delegate to Subagent | Decision Matrix: delegate for understanding (line 51) |
| Specify Intent Statement | Delegation Intents table (lines 140-146) |
| Intent Types | Delegation Intents: error extraction, summary, presence, diff, structure (lines 142-146) |
| Subagent Reads ENTIRE Content | Delegation Template (lines 150-158) |
| No Blind Truncation? | Invariant Principle 1: No Silent Data Loss (line 23) |
| Command Output? | Command Output Capture section (lines 59-77) |
| Capture with tee | The Pattern: tee capture (lines 66-77) |
| Cleanup Temp Files | Cleanup Rules (lines 96-110) |
| Self-Check Passed? | Self-Check checklist (lines 232-238) |

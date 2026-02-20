<!-- diagram-meta: {"source": "skills/isolated-testing/SKILL.md", "source_hash": "sha256:d64fd6f3ef90647ae9822eaf74bec360518871f02b0183bd22afe725debf8e62", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: isolated-testing

Disciplined one-theory-one-test protocol for debugging. Enforces strict queue ordering, requires full test design before execution, and halts investigation immediately upon reproduction. Detects and prevents chaos patterns.

```mermaid
flowchart TD
    Start([Theories to Test])
    S0[Step 0: Verify Code State]
    StateKnown{Code State Known?}
    ResetBaseline[Return to Baseline]
    S1[Step 1: Select FIRST Theory]
    S2[Step 2: Design Repro Test]
    DesignComplete{Test Fully Designed?}
    FixDesign[Complete Test Design]
    S3{Approval Gate}
    AutoMode{Autonomous?}
    AskUser[Present Test to User]
    UserApproves{User Approves?}
    AdjustTest[Adjust Test Design]
    SkipTheory[Skip Theory]
    S4[Step 4: Execute ONCE]
    S5{Verdict?}
    Reproduced([BUG REPRODUCED - STOP])
    Disproved[Mark DISPROVED]
    Inconclusive[Note INCONCLUSIVE]
    MoreTheories{More Theories?}
    ChaosCheck{Chaos Detected?}
    AllExhausted([All Theories Exhausted])
    InvokeTDD[/test-driven-development/]
    InvokeHunch[/verifying-hunches/]

    Start --> S0
    S0 --> StateKnown
    StateKnown -- "Yes" --> S1
    StateKnown -- "No" --> ResetBaseline
    ResetBaseline --> S0
    S1 --> S2
    S2 --> DesignComplete
    DesignComplete -- "Yes" --> S3
    DesignComplete -- "No" --> FixDesign
    FixDesign --> S2
    S3 --> AutoMode
    AutoMode -- "Yes" --> S4
    AutoMode -- "No" --> AskUser
    AskUser --> UserApproves
    UserApproves -- "Run" --> S4
    UserApproves -- "Adjust" --> AdjustTest
    UserApproves -- "Skip" --> SkipTheory
    AdjustTest --> S2
    SkipTheory --> MoreTheories
    S4 --> ChaosCheck
    ChaosCheck -- "Yes: mixing theories" --> S0
    ChaosCheck -- "No" --> S5
    S5 -- "Matches correct prediction" --> InvokeHunch
    InvokeHunch --> Reproduced
    Reproduced --> InvokeTDD
    S5 -- "Matches wrong prediction" --> Disproved
    S5 -- "Neither matches" --> Inconclusive
    Disproved --> MoreTheories
    Inconclusive --> MoreTheories
    MoreTheories -- "Yes" --> S1
    MoreTheories -- "No" --> AllExhausted

    style Start fill:#4CAF50,color:#fff
    style StateKnown fill:#FF9800,color:#fff
    style DesignComplete fill:#FF9800,color:#fff
    style AutoMode fill:#FF9800,color:#fff
    style UserApproves fill:#FF9800,color:#fff
    style MoreTheories fill:#FF9800,color:#fff
    style S5 fill:#FF9800,color:#fff
    style S3 fill:#f44336,color:#fff
    style ChaosCheck fill:#f44336,color:#fff
    style InvokeTDD fill:#4CAF50,color:#fff
    style InvokeHunch fill:#4CAF50,color:#fff
    style S0 fill:#2196F3,color:#fff
    style S1 fill:#2196F3,color:#fff
    style S2 fill:#2196F3,color:#fff
    style S4 fill:#2196F3,color:#fff
    style ResetBaseline fill:#2196F3,color:#fff
    style FixDesign fill:#2196F3,color:#fff
    style AskUser fill:#2196F3,color:#fff
    style AdjustTest fill:#2196F3,color:#fff
    style SkipTheory fill:#2196F3,color:#fff
    style Disproved fill:#2196F3,color:#fff
    style Inconclusive fill:#2196F3,color:#fff
    style Reproduced fill:#4CAF50,color:#fff
    style AllExhausted fill:#4CAF50,color:#fff
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
| Step 0: Verify Code State | Lines 41-55: Code state check template |
| Step 1: Select FIRST Theory | Lines 57-71: Queue discipline, FIRST untested theory |
| Step 2: Design Repro Test | Lines 73-107: Complete test design template |
| Approval Gate | Lines 109-115: Non-autonomous vs autonomous |
| Step 4: Execute ONCE | Lines 117-121: Run exactly once |
| Verdict? | Lines 123-129: REPRODUCED / DISPROVED / INCONCLUSIVE |
| BUG REPRODUCED - STOP | Lines 131-155: Full stop on reproduction |
| Chaos Detected? | Lines 159-200: Chaos detection FORBIDDEN list |
| /verifying-hunches/ | Lines 230: Invoked before claiming confirmation |
| /test-driven-development/ | Lines 231: Invoked for fix phase after reproduction |

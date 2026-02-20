<!-- diagram-meta: {"source": "skills/reflexion/SKILL.md", "source_hash": "sha256:b775b3b124cc4d17310230cb6e8029ade4aa4a41bce2e031ccdf747272433b73", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: reflexion

Analyze roundtable ITERATE feedback to extract root causes, store reflections, detect failure patterns, and generate retry guidance for the Forge workflow.

```mermaid
flowchart TD
    START([ITERATE Verdict Received]) --> TRIGGER[forge_iteration_return]
    TRIGGER --> DISPATCH["/reflexion-analyze"]
    DISPATCH --> PARSE[Parse Feedback Items]
    PARSE --> CATEGORIZE[Categorize Root Cause]
    CATEGORIZE --> ROOT_Q[Answer Root Cause Questions]
    ROOT_Q --> STORE[Store Reflections in forged.db]
    STORE --> PATTERN[Pattern Detection]
    PATTERN --> SAME_FEATURE{Same failure x2 same feature?}
    SAME_FEATURE -->|Yes| ALERT_ROOT[Alert: Root Cause Not Addressed]
    SAME_FEATURE -->|No| CROSS_FEATURE{Same failure x3 different features?}
    CROSS_FEATURE -->|Yes| ALERT_SYSTEMIC[Alert: Systemic Pattern]
    CROSS_FEATURE -->|No| VALIDATOR{Same validator x3 failures?}
    VALIDATOR -->|Yes| ALERT_FOCUS[Alert: Validator Focus Area]
    VALIDATOR -->|No| ESCALATION_CHECK
    ALERT_ROOT --> ESCALATION_CHECK
    ALERT_SYSTEMIC --> ESCALATION_CHECK
    ALERT_FOCUS --> ESCALATION_CHECK
    ESCALATION_CHECK{Iteration >= 3 same root cause?}
    ESCALATION_CHECK -->|Yes| ESCALATE[Mark ESCALATED]
    ESCALATE --> HUMAN[Recommend Human Intervention]
    HUMAN --> DONE
    ESCALATION_CHECK -->|No| GENERATE[Generate Retry Guidance]
    GENERATE --> SELF_CHECK{Self-Check Passes?}
    SELF_CHECK -->|No| FIX[Complete Missing Items]
    FIX --> SELF_CHECK
    SELF_CHECK -->|Yes| RETURN[Return to Forge]
    RETURN --> DONE([Re-Select and Re-Invoke Skill])

    style START fill:#4CAF50,color:#fff
    style DONE fill:#4CAF50,color:#fff
    style DISPATCH fill:#2196F3,color:#fff
    style PARSE fill:#2196F3,color:#fff
    style CATEGORIZE fill:#2196F3,color:#fff
    style ROOT_Q fill:#2196F3,color:#fff
    style STORE fill:#2196F3,color:#fff
    style PATTERN fill:#2196F3,color:#fff
    style GENERATE fill:#2196F3,color:#fff
    style RETURN fill:#2196F3,color:#fff
    style TRIGGER fill:#2196F3,color:#fff
    style SAME_FEATURE fill:#FF9800,color:#fff
    style CROSS_FEATURE fill:#FF9800,color:#fff
    style VALIDATOR fill:#FF9800,color:#fff
    style ESCALATION_CHECK fill:#f44336,color:#fff
    style SELF_CHECK fill:#f44336,color:#fff
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
| ITERATE Verdict Received | Integration with Forge: trigger is forge_iteration_return with ITERATE |
| forge_iteration_return | Integration with Forge: MCP tool that triggers reflexion |
| /reflexion-analyze | Phase Sequence: Steps 1-3 dispatched as subagent command |
| Parse Feedback Items | Step 1: extract structured fields from each feedback item |
| Categorize Root Cause | Step 2: map to categories (Incomplete Analysis, Misunderstanding, etc.) |
| Answer Root Cause Questions | Step 3: expected vs actual, why deviation, what prevents |
| Store Reflections | Step 4: write to forged.db with PENDING status |
| Pattern Detection | Pattern Detection table: thresholds for alerts |
| Same failure x2 same feature? | Pattern Detection: "Root cause not addressed" threshold |
| Same failure x3 different features? | Pattern Detection: "Systemic pattern" threshold |
| Same validator x3 failures? | Pattern Detection: "Validator focus area" threshold |
| Iteration >= 3? | Escalation: after 3 iterations on same stage with same root cause |
| Generate Retry Guidance | Step 5: specific correction guidance for re-invoked skill |
| Self-Check Passes? | Self-Check: all items analyzed, categorized, stored, patterns checked, guidance generated |

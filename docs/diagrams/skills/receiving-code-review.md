<!-- diagram-meta: {"source": "skills/receiving-code-review/SKILL.md", "source_hash": "sha256:31a0f417c8c663992f5361569c4e82a4e139fdc2d9b55c46aac136a2a2b3b96c", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: receiving-code-review

Deprecated routing skill that redirects all feedback processing to `code-review --feedback`, with fallback verification chains and trust-level-based processing.

```mermaid
flowchart TD
    START([Start]) --> DEPRECATED[Deprecated Skill Loaded]
    DEPRECATED --> ROUTE["/code-review --feedback"]
    ROUTE --> MANIFEST{review-manifest.json exists?}
    MANIFEST -->|Yes| LOAD_INTERNAL[Load Internal Findings]
    MANIFEST -->|No| DIRECT[Process Feedback Directly]
    LOAD_INTERNAL --> RECONCILE[Reconcile Findings]
    DIRECT --> TRUST[Assess Source Trust Level]
    RECONCILE --> TRUST
    TRUST --> HIGH{High trust?}
    HIGH -->|Yes| SPOT[Spot-Check 1-2 Findings]
    TRUST --> SKEPTICAL{Skeptical trust?}
    SKEPTICAL -->|Yes| FULL_VERIFY[Verify Every Finding]
    TRUST --> LOW{Low trust?}
    LOW -->|Yes| FULL_VERIFY_ESC[Full Verify + Escalate]
    TRUST --> OBJECTIVE{Objective/CI?}
    OBJECTIVE -->|Yes| SYSTEMATIC[Address Systematically]
    SPOT --> VERIFY_TOOL[Verify via MCP Tools]
    FULL_VERIFY --> VERIFY_TOOL
    FULL_VERIFY_ESC --> VERIFY_TOOL
    SYSTEMATIC --> VERIFY_TOOL
    VERIFY_TOOL --> TOOL_FAIL{Tool failed?}
    TOOL_FAIL -->|No| RESPOND[Generate Thread Replies]
    TOOL_FAIL -->|Yes| FALLBACK1[Fallback: Read Tool]
    FALLBACK1 --> FB1_FAIL{Failed?}
    FB1_FAIL -->|No| RESPOND
    FB1_FAIL -->|Yes| FALLBACK2[Fallback: Git Commands]
    FALLBACK2 --> FB2_FAIL{Failed?}
    FB2_FAIL -->|No| RESPOND
    FB2_FAIL -->|Yes| FALLBACK3[Fallback: Ask User]
    FALLBACK3 --> FB3_FAIL{All failed?}
    FB3_FAIL -->|Yes| UNVERIFIED[Mark UNVERIFIED - Do Not Implement]
    FB3_FAIL -->|No| RESPOND
    UNVERIFIED --> RESPOND
    RESPOND --> DONE([Feedback Processed])

    style START fill:#4CAF50,color:#fff
    style DONE fill:#4CAF50,color:#fff
    style ROUTE fill:#4CAF50,color:#fff
    style DEPRECATED fill:#2196F3,color:#fff
    style RECONCILE fill:#2196F3,color:#fff
    style SPOT fill:#2196F3,color:#fff
    style FULL_VERIFY fill:#2196F3,color:#fff
    style FULL_VERIFY_ESC fill:#2196F3,color:#fff
    style SYSTEMATIC fill:#2196F3,color:#fff
    style VERIFY_TOOL fill:#2196F3,color:#fff
    style RESPOND fill:#2196F3,color:#fff
    style MANIFEST fill:#FF9800,color:#fff
    style HIGH fill:#FF9800,color:#fff
    style SKEPTICAL fill:#FF9800,color:#fff
    style LOW fill:#FF9800,color:#fff
    style OBJECTIVE fill:#FF9800,color:#fff
    style TOOL_FAIL fill:#FF9800,color:#fff
    style FB1_FAIL fill:#FF9800,color:#fff
    style FB2_FAIL fill:#FF9800,color:#fff
    style FB3_FAIL fill:#FF9800,color:#fff
    style UNVERIFIED fill:#f44336,color:#fff
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
| Deprecated Skill Loaded | Frontmatter: deprecated: true, replacement: code-review --feedback |
| /code-review --feedback | Automatic Routing: immediately invoke replacement |
| review-manifest.json exists? | Handoff from Requesting Skill: check for existing manifest |
| Reconcile Findings | Finding Reconciliation table: match, new, missing, contradictory |
| Assess Source Trust Level | Feedback Source Trust Levels table: High, Skeptical, Low, Objective |
| Spot-Check 1-2 Findings | Trust Level Actions: High Trust verification |
| Verify Every Finding | Trust Level Actions: Skeptical / Low Trust verification |
| Verify via MCP Tools | MCP Tool Failures: primary tool chain |
| Fallback chain | MCP Tool Failures: Read Tool, Git Commands, Ask User |
| Mark UNVERIFIED | Hard Stop Rule: cannot verify, do not implement |
| Generate Thread Replies | Thread Reply Protocol: FIXED, ACKNOWLEDGED, QUESTION, DISAGREE formats |

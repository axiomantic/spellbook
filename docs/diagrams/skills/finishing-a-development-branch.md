<!-- diagram-meta: {"source": "skills/finishing-a-development-branch/SKILL.md", "source_hash": "sha256:64ccbee8f97f9519b1cd8e86c0ea74640af27f7896b3b2b86e6a1104f6837058", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: finishing-a-development-branch

Workflow for completing a development branch: verifies tests pass, determines base branch, presents 4 structured integration options (merge, PR, keep, discard), executes the chosen option, and performs worktree cleanup where applicable.

```mermaid
flowchart TD
    START([Start]) --> CHECK_AUTO{Autonomous Mode?}

    CHECK_AUTO -->|Yes| AUTO_MODE{post_impl Setting?}
    CHECK_AUTO -->|No| STEP1

    AUTO_MODE -->|auto_pr| OPTION2
    AUTO_MODE -->|stop| REPORT_DONE[Report Completion]
    AUTO_MODE -->|offer_options| STEP1
    AUTO_MODE -->|unset| OPTION2

    STEP1[Step 1: Run Tests]:::cmd --> TESTS_PASS{Tests Pass?}

    TESTS_PASS -->|No| STOP_FAIL[STOP: Fix Tests]:::gate
    TESTS_PASS -->|Yes| STEP2

    STEP2[Step 2: Determine Base]:::cmd --> STEP3

    STEP3[Step 3: Present Options]:::cmd --> USER_CHOICE{User Selects Option}

    USER_CHOICE -->|Option 1| OPTION1[Merge Locally]:::cmd
    USER_CHOICE -->|Option 2| OPTION2[Push and Create PR]:::cmd
    USER_CHOICE -->|Option 3| OPTION3[Keep Branch As-Is]:::cmd
    USER_CHOICE -->|Option 4| OPTION4_CONFIRM{Typed 'discard'?}

    OPTION4_CONFIRM -->|No| STOP_CONFIRM[STOP: Require Confirmation]:::gate
    OPTION4_CONFIRM -->|Yes| OPTION4[Discard Work]:::cmd

    OPTION1 --> EXEC1[/finish-branch-execute/]:::skill
    OPTION2 --> EXEC2[/finish-branch-execute/]:::skill
    OPTION4 --> EXEC4[/finish-branch-execute/]:::skill

    EXEC1 --> POST_MERGE{Post-Merge Tests Pass?}
    POST_MERGE -->|No| STOP_MERGE[STOP: Merge Broke Tests]:::gate
    POST_MERGE -->|Yes| CLEANUP1[/finish-branch-cleanup/]:::skill

    EXEC2 --> PR_URL[Return PR URL]:::cmd
    PR_URL --> DONE

    OPTION3 --> DONE

    EXEC4 --> CLEANUP4[/finish-branch-cleanup/]:::skill

    CLEANUP1 --> SELF_CHECK[Self-Check Checklist]:::gate
    CLEANUP4 --> SELF_CHECK

    SELF_CHECK --> DONE([Done])

    REPORT_DONE --> DONE

    style START fill:#333,color:#fff
    style DONE fill:#333,color:#fff
    style STEP1 fill:#2196F3,color:#fff
    style STEP2 fill:#2196F3,color:#fff
    style STEP3 fill:#2196F3,color:#fff
    style OPTION1 fill:#2196F3,color:#fff
    style OPTION2 fill:#2196F3,color:#fff
    style OPTION3 fill:#2196F3,color:#fff
    style OPTION4 fill:#2196F3,color:#fff
    style PR_URL fill:#2196F3,color:#fff
    style REPORT_DONE fill:#2196F3,color:#fff
    style EXEC1 fill:#4CAF50,color:#fff
    style EXEC2 fill:#4CAF50,color:#fff
    style EXEC4 fill:#4CAF50,color:#fff
    style CLEANUP1 fill:#4CAF50,color:#fff
    style CLEANUP4 fill:#4CAF50,color:#fff
    style CHECK_AUTO fill:#FF9800,color:#fff
    style AUTO_MODE fill:#FF9800,color:#fff
    style TESTS_PASS fill:#FF9800,color:#fff
    style USER_CHOICE fill:#FF9800,color:#fff
    style OPTION4_CONFIRM fill:#FF9800,color:#fff
    style POST_MERGE fill:#FF9800,color:#fff
    style STOP_FAIL fill:#f44336,color:#fff
    style STOP_CONFIRM fill:#f44336,color:#fff
    style STOP_MERGE fill:#f44336,color:#fff
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
| Step 1: Run Tests | Step 1: Verify Tests (line 90) |
| Tests Pass? | If tests fail / If tests pass (lines 104-115) |
| Step 2: Determine Base | Step 2: Determine Base Branch (line 117) |
| Step 3: Present Options | Step 3: Present Options (line 126) |
| User Selects Option | Options 1-4 (lines 131-138) |
| Typed 'discard'? | Destruction Requires Proof, Invariant 3 (line 18) |
| /finish-branch-execute/ | Step 4: Execute Choice (line 144) |
| Post-Merge Tests Pass? | Tests Gate Everything, Invariant 1 (line 16) |
| /finish-branch-cleanup/ | Step 5: Cleanup Worktree (line 149) |
| Autonomous Mode? | Autonomous Mode section (lines 42-59) |
| post_impl Setting? | post_impl preference table (lines 48-53) |
| Self-Check Checklist | Self-Check section (lines 182-193) |

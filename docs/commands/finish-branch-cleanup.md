# /finish-branch-cleanup

## Workflow Diagram

# Diagram: finish-branch-cleanup

Worktree cleanup after branch integration. Applies to merge, PR, and discard options. Keeps worktree intact for keep-as-is option.

```mermaid
flowchart TD
    Start([Integration Complete]) --> CheckOption{"Which Integration\nOption?"}
    CheckOption -->|Option 1: Merge| Cleanup["Proceed to Cleanup"]
    CheckOption -->|Option 2: PR| Cleanup
    CheckOption -->|Option 3: Keep| NoCleanup([Keep Worktree Intact])
    CheckOption -->|Option 4: Discard| Cleanup
    Cleanup --> DetectWorktree["Detect if in\nWorktree"]
    DetectWorktree --> IsWorktree{"Currently in\nWorktree?"}
    IsWorktree -->|No| AlreadyClean([No Cleanup Needed])
    IsWorktree -->|Yes| RemoveWorktree["Remove Worktree"]
    RemoveWorktree --> RemoveResult{"Removal\nSucceeded?"}
    RemoveResult -->|Yes| Done([Worktree Removed\nIntegration Complete])
    RemoveResult -->|No| CheckChanges{"Uncommitted\nChanges?"}
    CheckChanges -->|Yes| WarnUser["Warn: Uncommitted\nChanges Detected"]
    CheckChanges -->|No| ReportError["Report Removal\nError"]
    WarnUser --> AskConfirm{"Force Remove?"}
    AskConfirm -->|Yes| ForceRemove["Force Remove\nWorktree"]
    AskConfirm -->|No| KeepForNow([Keep Worktree\nFor User])
    ForceRemove --> Done
    ReportError --> KeepForNow

    style Start fill:#4CAF50,color:#fff
    style Done fill:#4CAF50,color:#fff
    style NoCleanup fill:#4CAF50,color:#fff
    style AlreadyClean fill:#4CAF50,color:#fff
    style KeepForNow fill:#4CAF50,color:#fff
    style Cleanup fill:#2196F3,color:#fff
    style DetectWorktree fill:#2196F3,color:#fff
    style RemoveWorktree fill:#2196F3,color:#fff
    style WarnUser fill:#2196F3,color:#fff
    style ForceRemove fill:#2196F3,color:#fff
    style ReportError fill:#2196F3,color:#fff
    style CheckOption fill:#FF9800,color:#fff
    style IsWorktree fill:#FF9800,color:#fff
    style CheckChanges fill:#FF9800,color:#fff
    style AskConfirm fill:#FF9800,color:#fff
    style RemoveResult fill:#f44336,color:#fff
```

## Legend

| Color | Meaning |
|-------|---------|
| Green (#4CAF50) | Skill invocation |
| Blue (#2196F3) | Command/action |
| Orange (#FF9800) | Decision point |
| Red (#f44336) | Quality gate |

## Command Content

``````````markdown
# Step 5: Cleanup Worktree

## Invariant Principles

1. **Option 3 means hands off** - "Keep as-is" means no cleanup whatsoever; the worktree stays intact for the user
2. **Detect before deleting** - Verify whether you are inside a worktree before running removal commands; deleting the wrong directory is catastrophic
3. **Uncommitted changes are a red flag** - A worktree with uncommitted changes at cleanup time indicates something went wrong upstream; warn before removing

<ROLE>
Release Engineer. Your reputation depends on clean integrations that never break main or lose work.
</ROLE>

You are cleaning up the worktree after executing an integration option. This step applies ONLY to Options 1, 2, and 4.

---

## Applicability

| Option | Cleanup Worktree? |
|--------|-------------------|
| 1. Merge locally | Yes |
| 2. Create PR | Yes |
| 3. Keep as-is | **NO - Keep worktree intact** |
| 4. Discard | Yes |

**For Option 3:** Do nothing. The worktree stays as-is for the user to handle later.

---

## Cleanup Procedure (Options 1, 2, 4)

Detect if currently in a worktree:

```bash
git worktree list | grep $(git branch --show-current)
```

If in a worktree, remove it:

```bash
git worktree remove <worktree-path>
```

If the worktree removal fails (e.g., uncommitted changes), report the error. Do NOT force-remove without user confirmation.

Report final state: "Worktree at <path> removed. Integration complete."
``````````

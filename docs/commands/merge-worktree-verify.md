# /merge-worktree-verify

## Workflow Diagram

# Diagram: merge-worktree-verify

Phases 4-5 of merging-worktrees: runs the full test suite, audits test quality with green-mirage detection, verifies all interface contracts survive merging, performs code review against the implementation plan, then cleans up worktrees and branches.

```mermaid
flowchart TD
    Start([Start Phase 4-5]) --> FullTests[Run Full Test Suite]

    FullTests --> TestsPass{All Tests Pass?}

    TestsPass -->|Yes| GreenMirage[Invoke auditing-green-mirage]
    TestsPass -->|No| FixTests[Fix Failures First]

    FixTests --> FullTests

    GreenMirage --> CodeReview[Invoke code-review]

    CodeReview --> PickContract[Pick Interface Contract]
    PickContract --> BothExist{Both Sides Exist?}

    BothExist -->|Yes| SigsMatch{Type Signatures Match?}
    BothExist -->|No| FlagMissing[Flag Missing Interface]

    FlagMissing --> MoreContracts{More Contracts?}

    SigsMatch -->|Yes| BehaviorMatch{Behavior Matches Spec?}
    SigsMatch -->|No| FlagSigMismatch[Flag Signature Mismatch]

    FlagSigMismatch --> MoreContracts
    BehaviorMatch -->|Yes| ContractOK[Contract Verified]
    BehaviorMatch -->|No| FlagBehavior[Flag Behavior Mismatch]

    FlagBehavior --> MoreContracts
    ContractOK --> MoreContracts

    MoreContracts -->|Yes| PickContract
    MoreContracts -->|No| AllVerified{All Contracts Verified?}

    AllVerified -->|Yes| Cleanup[Cleanup Phase]
    AllVerified -->|No| FixIssues[Fix Contract Issues]

    FixIssues --> FullTests

    Cleanup --> RemoveWT[Remove Worktrees]
    RemoveWT --> Prune[Git Worktree Prune]
    Prune --> DeleteBranch[Delete Merged Branches]
    DeleteBranch --> Report[Generate Merge Report]
    Report --> Done([Phase 4-5 Complete])

    style Start fill:#2196F3,color:#fff
    style Done fill:#2196F3,color:#fff
    style FullTests fill:#2196F3,color:#fff
    style FixTests fill:#2196F3,color:#fff
    style GreenMirage fill:#4CAF50,color:#fff
    style CodeReview fill:#4CAF50,color:#fff
    style PickContract fill:#2196F3,color:#fff
    style ContractOK fill:#2196F3,color:#fff
    style FlagMissing fill:#f44336,color:#fff
    style FlagSigMismatch fill:#2196F3,color:#fff
    style FlagBehavior fill:#2196F3,color:#fff
    style Cleanup fill:#2196F3,color:#fff
    style RemoveWT fill:#2196F3,color:#fff
    style Prune fill:#2196F3,color:#fff
    style DeleteBranch fill:#2196F3,color:#fff
    style Report fill:#2196F3,color:#fff
    style FixIssues fill:#2196F3,color:#fff
    style TestsPass fill:#f44336,color:#fff
    style BothExist fill:#FF9800,color:#fff
    style SigsMatch fill:#FF9800,color:#fff
    style BehaviorMatch fill:#FF9800,color:#fff
    style MoreContracts fill:#FF9800,color:#fff
    style AllVerified fill:#f44336,color:#fff
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
# Phase 4: Final Verification

## Invariant Principles

1. **Full suite, no shortcuts** - Final verification runs the complete test suite, not a subset; partial verification misses cross-worktree regressions
2. **Contracts survive merging** - Both sides of every interface must exist with matching type signatures and behavior after the final merge
3. **Cleanup only after verification passes** - Worktree deletion is irreversible; never clean up before the full test suite and contract checks pass

After all worktrees merged:

1. **Full test suite** - All tests must pass
2. **auditing-green-mirage** - Invoke on all modified test files
3. **Code review** - Invoke `code-reviewer` against implementation plan, verify all contracts honored
4. **Interface contract check** - For each contract:
   - Both sides of interface exist
   - Type signatures match
   - Behavior matches specification

# Phase 5: Cleanup

```bash
# Delete worktrees
git worktree remove [worktree-path] --force

# If worktree has uncommitted changes (shouldn't happen)
rm -rf [worktree-path]
git worktree prune

# Delete branches if no longer needed
git branch -d [worktree-branch]
```

**Report template:**
```
Worktree merge complete

Merged worktrees:
- setup-worktree -> deleted
- api-worktree -> deleted
- ui-worktree -> deleted

Final branch: [base-branch]
All tests passing: yes
All interface contracts verified: yes
```
``````````

# /finish-branch-execute

## Workflow Diagram

```mermaid
flowchart TD
    Start([User Choice Received]) --> OptionSwitch{"Which Option?"}
    OptionSwitch -->|Option 1: Merge| CheckoutBase["Checkout Base Branch"]
    OptionSwitch -->|Option 2: PR| PushBranch["Push Branch\nto Origin"]
    OptionSwitch -->|Option 3: PR+Dance| PushBranch2["Push Branch\nto Origin"]
    OptionSwitch -->|Option 4: Keep| ReportKeep([Report: Keeping\nBranch As-Is])
    OptionSwitch -->|Option 5: Discard| ShowWarning["Show Discard\nWarning"]
    CheckoutBase --> PullLatest["Pull Latest\nBase Branch"]
    PullLatest --> MergeBranch["Merge Feature\nBranch"]
    MergeBranch --> PostMergeTest["Run Post-Merge\nTests"]
    PostMergeTest --> MergeTestGate{"Tests Pass?"}
    MergeTestGate -->|No| MergeFail([Report Failure\nKeep Branch])
    MergeTestGate -->|Yes| DeleteBranch["Delete Feature\nBranch"]
    DeleteBranch --> ToCleanup1["Invoke\nfinish-branch-cleanup"]
    PushBranch --> CreatePR["Create PR\nvia gh"]
    CreatePR --> ReportURL["Report PR URL"]
    ReportURL --> ToCleanup2["Invoke\nfinish-branch-cleanup"]
    PushBranch2 --> CreatePR2["Create PR\nvia gh"]
    CreatePR2 --> ReportURL2["Report PR URL"]
    ReportURL2 --> ExecutePRDance["Dispatch Subagent\nto Execute pr-dance"]
    ExecutePRDance --> ToCleanup4["Invoke\nfinish-branch-cleanup"]
    ShowWarning --> TypeConfirm{"User Types\n'discard'?"}
    TypeConfirm -->|No / Partial| RejectDiscard([Discard Cancelled])
    TypeConfirm -->|Yes| CheckoutDiscard["Checkout Base\nBranch"]
    CheckoutDiscard --> ForceDelete["Force Delete\nFeature Branch"]
    ForceDelete --> ToCleanup3["Invoke\nfinish-branch-cleanup"]
    ToCleanup1 --> Done([Integration Complete])
    ToCleanup2 --> Done
    ToCleanup3 --> Done
    ToCleanup4 --> Done

    style Start fill:#4CAF50,color:#fff
    style Done fill:#4CAF50,color:#fff
    style ReportKeep fill:#4CAF50,color:#fff
    style MergeFail fill:#f44336,color:#fff
    style RejectDiscard fill:#f44336,color:#fff
    style CheckoutBase fill:#2196F3,color:#fff
    style PullLatest fill:#2196F3,color:#fff
    style MergeBranch fill:#2196F3,color:#fff
    style PostMergeTest fill:#2196F3,color:#fff
    style DeleteBranch fill:#2196F3,color:#fff
    style PushBranch fill:#2196F3,color:#fff
    style CreatePR fill:#2196F3,color:#fff
    style ReportURL fill:#2196F3,color:#fff
    style PushBranch2 fill:#2196F3,color:#fff
    style CreatePR2 fill:#2196F3,color:#fff
    style ReportURL2 fill:#2196F3,color:#fff
    style ExecutePRDance fill:#4CAF50,color:#fff
    style ShowWarning fill:#2196F3,color:#fff
    style CheckoutDiscard fill:#2196F3,color:#fff
    style ForceDelete fill:#2196F3,color:#fff
    style ToCleanup1 fill:#4CAF50,color:#fff
    style ToCleanup2 fill:#4CAF50,color:#fff
    style ToCleanup3 fill:#4CAF50,color:#fff
    style ToCleanup4 fill:#4CAF50,color:#fff
    style OptionSwitch fill:#FF9800,color:#fff
    style TypeConfirm fill:#FF9800,color:#fff
    style MergeTestGate fill:#f44336,color:#fff
```

**Changes made:**
- Added Option 3 branch (PR+Dance): `OptionSwitch -->|Option 3: PR+Dance| PushBranch2`
- Created separate PR+Dance path: PushBranch2 → CreatePR2 → ReportURL2 → ExecutePRDance → ToCleanup4
- Renumbered Option 3 (Keep) → Option 4, Option 4 (Discard) → Option 5
- Styled ExecutePRDance as green (skill invocation) with ToCleanup4 convergence to Done

## Command Content

``````````markdown
# Step 4: Execute Choice

<ROLE>
Release Engineer. Your reputation depends on clean integrations that never break main or lose work. A merge that breaks the build is a public failure. A discard without confirmation is unforgivable.
</ROLE>

## Invariant Principles

1. **Execute exactly the chosen strategy** — never silently switch options
2. **Discard requires explicit confirmation** — Option 4 is irreversible; re-confirm before executing
3. **Pull before merge** — always pull the latest base branch to avoid stale-base conflicts

<FORBIDDEN>
- Silently switching to a different integration option than the user selected
- Auto-executing Option 4 (discard) in autonomous mode without typed confirmation
</FORBIDDEN>

Context: Steps 1-3 complete. You have: chosen option number (1-5), feature branch name, base branch name, worktree path (if applicable).

---

## Option 1: Merge Locally

```bash
git checkout <base-branch>
git pull
git merge <feature-branch>
<test-command>          # use test command from Step 1 context; ask if unknown
git branch -d <feature-branch>   # only on test pass
```

<CRITICAL>
**If post-merge tests fail:** STOP. Report the failure. Do NOT delete the branch. User decides next steps.
</CRITICAL>

After success: invoke `finish-branch-cleanup`.

---

## Option 2: Push and Create PR

```bash
git push -u origin <feature-branch>
gh pr create --title "<title>" --body "$(cat <<'EOF'
## Summary
<2-3 bullets of what changed>

## Test Plan
- [ ] <verification steps>
EOF
)"
```

**If push or PR creation fails:** STOP. Report the error. Do NOT proceed to cleanup.

Report the PR URL to the user. After PR creation: invoke `finish-branch-cleanup`.

---

## Option 3: Push, Create PR, and Do the PR Dance

Execute Option 2 steps first (push + create PR). Then dispatch a subagent with command: `pr-dance`

Provide context: PR number/URL from the PR just created, repo owner, feature branch name.

The subagent drives the PR through iterative CI + bot review cycles until merge-ready. See `pr-dance` command for the full protocol.

After the subagent completes: invoke `finish-branch-cleanup`.

---

## Option 4: Keep As-Is

Report: "Keeping branch `<name>`. Worktree preserved at `<path>`."

**Do NOT cleanup worktree. Do NOT invoke finish-branch-cleanup.**

---

## Option 5: Discard

<CRITICAL>
**Confirm first with explicit typed confirmation:**
```
This will permanently delete:
- Branch <name>
- All commits: <commit-list>
- Worktree at <path>

Type 'discard' to confirm.
```

Wait for exact string `discard`. Do NOT proceed on partial match.
Do NOT auto-execute in autonomous mode. This is a circuit breaker.
</CRITICAL>

If confirmed:
```bash
git checkout <base-branch>
git branch -D <feature-branch>
```

After confirmed discard: invoke `finish-branch-cleanup`.

<FINAL_EMPHASIS>
Execute the strategy the user chose — nothing more, nothing less. Clean integrations protect the team. When in doubt on discard: stop and ask again.
</FINAL_EMPHASIS>
``````````

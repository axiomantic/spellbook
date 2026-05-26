<!-- diagram-meta: {"source": "agents/git-committer.md", "source_hash": "sha256:ffc88f75b5dfea74c4485cc48ce5e65d04ff458ee7991134097c54505a7bd893", "generated_at": "2026-05-25T01:40:43Z", "generator": "generate_diagrams.py"} -->
# Diagram: git-committer

```mermaid
flowchart TD
    START(["`**git-committer dispatched**`"]):::terminal

    %% Entry verification
    START --> VERIFY["Verify working directory\n& current branch\nmatch parent's dispatch"]
    VERIFY --> BRANCH_MATCH{Match?}
    BRANCH_MATCH -- No --> REJECT(["`**Reject dispatch**\nreport mismatch to parent`"]):::gate
    BRANCH_MATCH -- Yes --> INSPECT["git status / git diff\nInspect named files\nin scope"]

    %% Analysis phase
    INSPECT --> FILES_CHANGED{Named files\nactually changed?}
    FILES_CHANGED -- No --> NO_COMMIT(["`**No commit made**\ncommit_sha = null\nreport in notes`"]):::success
    FILES_CHANGED -- Yes --> CONV_CHECK["Validate commit message\nconvention before staging"]

    %% Convention check
    CONV_CHECK --> CONV_OK{Conventions\nclear?}
    CONV_OK -- No:\nAI trailers / issue numbers\n/ --amend without auth --> STOP_CONV(["`**Stop**\nSurface violation to parent`"]):::gate
    CONV_OK -- Yes --> STAGE["git add\n(only parent-named files)"]

    %% Staging guardrail
    STAGE --> BLANKET{Blanket-add\nattempted?}
    BLANKET -- Yes:\ngit add -A or git add . --> FORBIDDEN(["`**Forbidden**\nNever use blanket-add`"]):::gate
    BLANKET -- No --> BASH_GATE["Bash invocation →\nspellbook PreToolUse\nbash gate"]

    %% Gate decision
    BASH_GATE --> GATE_RESULT{Gate\nverdict}
    GATE_RESULT -- Denied --> SURFACE_DENIAL["Surface denial verbatim\nto operator\nAsk how to proceed"]
    SURFACE_DENIAL --> OPERATOR_RESP{Operator\nresponse}
    OPERATOR_RESP -- Abort --> ABORTED(["`**Aborted**\ncommit_sha = null\ndenial logged in notes`"]):::success
    OPERATOR_RESP -- Restructured cmd --> BASH_GATE
    GATE_RESULT -- Allowed --> COMMIT["git commit\n(no --no-verify,\nno AI trailers,\nno issue refs)"]

    %% Destructive verb check
    COMMIT --> DEST_CHECK{Destructive or\nremote verb?}
    DEST_CHECK -- Yes:\npush / reset --hard\n/ rebase / stash drop --> FORBIDDEN2(["`**Forbidden**\nOut of scope for this agent`"]):::gate
    DEST_CHECK -- No --> HOOK_RUN["Pre-commit hook runs"]

    HOOK_RUN --> HOOK_RESULT{Hook\nresult}
    HOOK_RESULT -- Fails --> HOOK_FAIL["Report hook failure\nFix underlying issue\n(never --no-verify)"]
    HOOK_FAIL --> STAGE
    HOOK_RESULT -- Passes --> SHA["Capture commit SHA\n& branch name"]

    SHA --> REFLECTION["Reflection:\n- Staged only in-scope files?\n- Local-only op?\n- Gate denials surfaced?"]

    REFLECTION --> RETURN(["`**Return GitCommitterResult**\ncommit_sha, branch,\nfiles_committed, notes`"]):::success

    %% Subgraphs
    subgraph TOOLS["Tools (narrowed surface)"]
        direction LR
        T1[Bash\ngit operations]
        T2[Read\nfiles / templates]
    end

    subgraph FORBIDDEN_OPS["Forbidden Operations"]
        direction LR
        F1["git push"]
        F2["git reset --hard"]
        F3["git checkout --"]
        F4["git rebase"]
        F5["git stash drop"]
        F6["--amend\n(without auth)"]
        F7["git add -A / ."]
        F8["--no-verify"]
    end

    subgraph LEGEND["Legend"]
        direction LR
        L1["Process"]:::process
        L2{Decision}
        L3(["Terminal / Result"]):::success
        L4["Quality Gate / Stop"]:::gate
    end

    classDef terminal fill:#2a2a3e,stroke:#888,color:#e8e8ea
    classDef gate fill:#ff6b6b,stroke:#c0392b,color:#1a1a1d
    classDef success fill:#51cf66,stroke:#2f9e44,color:#1a1a1d
    classDef process fill:#2a2a3e,stroke:#555,color:#e8e8ea
```

## Overview

The `git-committer` agent performs local-only git work dispatched by a parent. The flow has four stages:

1. **Entry verification** — confirms working directory and branch match the dispatch before any git operation.
2. **Analysis** — inspects changed files, validates commit message conventions.
3. **Staging + Gate** — stages only named files, passes each Bash invocation through the spellbook PreToolUse bash gate; denials are surfaced verbatim to the operator.
4. **Commit + Reflection** — commits (no `--no-verify`, no AI trailers, no issue refs), captures SHA, runs a structured reflection check, returns `GitCommitterResult`.

Destructive verbs (`push`, `reset --hard`, `rebase`, `stash drop`, `--amend` without auth) and blanket-adds (`git add -A`/`.`) are unconditionally forbidden.

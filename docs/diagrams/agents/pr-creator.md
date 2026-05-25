<!-- diagram-meta: {"source": "agents/pr-creator.md", "source_hash": "sha256:ffc88f75b5dfea74c4485cc48ce5e65d04ff458ee7991134097c54505a7bd893", "generated_at": "2026-05-25T01:42:41Z", "generator": "generate_diagrams.py"} -->
# Diagram: pr-creator

```mermaid
flowchart TD
    START(["`**pr-creator** agent invoked`"]):::terminal

    START --> ANALYZE

    subgraph ANALYZE["Phase 1 · Analysis"]
        A1["Confirm head branch\n& base branch"]
        A2{"Head branch\npushed to remote?"}
        A3["Surface to operator:\nbranch not pushed\n(push = git-pusher scope)"]
        A4["Locate PR template\n(.github/pull_request_template.md\nor equivalents)"]
        A5{"Template\nfound?"}
        A6["Apply real template\nto body"]
        A7["No template — use plain\ndescription; do NOT\ninvent Summary/Test-plan"]

        A1 --> A2
        A2 -->|No| A3
        A3 --> DONE_BLOCKED(["`**Halted** — operator\nmust push first`"]):::terminal
        A2 -->|Yes| A4
        A4 --> A5
        A5 -->|Yes| A6
        A5 -->|No| A7
        A6 --> SANITIZE
        A7 --> SANITIZE
    end

    subgraph SANITIZE["Phase 2 · Body Sanitisation"]
        S1["Strip AI-attribution trailers\n(Co-Authored-By, 'Generated with Claude')"]
        S2["Strip GitHub issue refs\n(fixes #123, closes #456)"]
        S3["Strip ## Summary / ## Test plan\nif not from real template"]

        S1 --> S2 --> S3
    end

    subgraph EXECUTE["Phase 3 · Execute gh PR Verb"]
        E1{"Which action?"}
        E2["gh pr create"]
        E3["gh pr edit"]
        E4["gh pr view\ngh pr diff\ngh pr list"]
        E5{"Bash gate\ndenied?"}
        E6["Surface denial verbatim\nto operator; ask how to proceed"]
        E7["Action completed"]

        E1 -->|create| E2
        E1 -->|edit| E3
        E1 -->|view/diff/list| E4
        E2 --> E5
        E3 --> E5
        E4 --> E5
        E5 -->|Yes| E6
        E6 --> DONE_DENIED(["`**Halted** — operator\ndecides next step`"]):::terminal
        E5 -->|No| E7
    end

    subgraph REFLECT["Phase 4 · Reflection"]
        R1{"Did I stay within\nauthoring verbs only?"}
        R2["STOP — do not proceed;\nout-of-scope action logged\nin notes field"]
        R3{"Applied real template\n(not fabricated)?"}
        R4["Note discrepancy in notes;\ncorrect before returning"]
        R5["Assemble output schema\n(pr_url, pr_number, branch,\nbase, action, notes)"]

        R1 -->|No| R2
        R1 -->|Yes| R3
        R3 -->|No| R4
        R3 -->|Yes| R5
    end

    SANITIZE --> EXECUTE
    E7 --> REFLECT
    R2 --> DONE_BLOCKED2(["`**Halted** — scope\nviolation`"]):::terminal
    R4 --> R5
    R5 --> DONE_OK(["`**Success**\nReturn PrCreatorResult JSON`"]):::success

    subgraph LEGEND["Legend"]
        direction LR
        L1["Process step"]
        L2{Decision}
        L3([Terminal]):::terminal
        L4([Success terminal]):::success
        L5["GUARDRAIL gate"]:::gate
    end

    classDef terminal fill:#ff6b6b,color:#fff,stroke:#cc4444
    classDef success fill:#51cf66,color:#fff,stroke:#3aab4d
    classDef gate fill:#ff6b6b,color:#fff,stroke:#cc4444
```

**Agent scope** (hard boundaries enforced by guardrails):

| Allowed verbs | Forbidden verbs |
|---|---|
| `gh pr create`, `gh pr edit`, `gh pr view`, `gh pr diff`, `gh pr list` | `gh pr merge`, `gh pr ready`, `git push`, any working-tree mutation |
| `git log`, `git diff`, `git rev-parse`, `git branch` (read-only) | `Edit`, `Write`, `Grep`, `Glob` (not in toolset) |

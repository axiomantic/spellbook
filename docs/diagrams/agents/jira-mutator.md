<!-- diagram-meta: {"source": "agents/jira-mutator.md", "source_hash": "sha256:ffc88f75b5dfea74c4485cc48ce5e65d04ff458ee7991134097c54505a7bd893", "generated_at": "2026-05-25T01:41:56Z", "generator": "generate_diagrams.py"} -->
# Diagram: jira-mutator

```mermaid
flowchart TD
    A([START: jira-mutator dispatched]) --> B[Read dispatch prompt\nfrom parent]
    B --> C{Prompt-injection scan:\nany untrusted Jira content\nembedded in dispatch?}
    C -->|Injection detected| D([ABORT: report in notes,\nreturn result=aborted])
    C -->|Clean| E[Identify issue key\n+ mutation verb\ncreate / transition / comment / edit]
    E --> F[Fetch current issue state\nvia Atlassian MCP read tool]
    F --> G[Compose confirmation prompt:\nissue key · current status\ntarget status · transition name]

    G --> H{Operator confirmation\nrequired}
    H -->|Declined| I([RETURN: result=declined\nnew_state=null])
    H -->|Approved| J{Which mutation?}

    J -->|create| K[createJiraIssue via MCP]
    J -->|transition| L[transitionJiraIssue via MCP]
    J -->|comment| M[addCommentToJiraIssue via MCP]
    J -->|edit| N[editJiraIssue via MCP]

    K --> O{Mutation succeeded?}
    L --> O
    M --> O
    N --> O

    O -->|Error / denied| P([RETURN: result=denied\nnew_state=null\nerror in notes])
    O -->|Success| Q[Capture new_state\nvia MCP read tool]
    Q --> R{More mutations\nin dispatch?}
    R -->|Yes — each requires\nindividual confirmation| G
    R -->|No| S([RETURN: result=success\nprevious_state · new_state · notes])

    subgraph LEGEND["Legend"]
        direction LR
        L1[Process]
        L2{Decision}
        L3([Terminal])
        L4[/Confirmation gate/]
        style L1 fill:#1e3a5f,stroke:#4a9eff,color:#e8e8ea
        style L2 fill:#1e3a5f,stroke:#ffcc44,color:#e8e8ea
        style L3 fill:#1a3a1a,stroke:#51cf66,color:#e8e8ea
        style L4 fill:#3a1a1a,stroke:#ff6b6b,color:#e8e8ea
    end

    style A fill:#1a3a1a,stroke:#51cf66,color:#e8e8ea
    style D fill:#3a1a1a,stroke:#ff6b6b,color:#e8e8ea
    style I fill:#3a1a1a,stroke:#ff6b6b,color:#e8e8ea
    style P fill:#3a1a1a,stroke:#ff6b6b,color:#e8e8ea
    style S fill:#1a3a1a,stroke:#51cf66,color:#e8e8ea
    style H fill:#3a1a1a,stroke:#ff6b6b,color:#e8e8ea
    style C fill:#1e3a5f,stroke:#4a9eff,color:#e8e8ea
    style K fill:#1e3a5f,stroke:#4a9eff,color:#e8e8ea
    style L fill:#1e3a5f,stroke:#4a9eff,color:#e8e8ea
    style M fill:#1e3a5f,stroke:#4a9eff,color:#e8e8ea
    style N fill:#1e3a5f,stroke:#4a9eff,color:#e8e8ea
```

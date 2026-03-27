<!-- diagram-meta: {"source": "skills/generating-diagrams/SKILL.md", "source_hash": "sha256:8ad5d86bde9ca9a7689e62cba5315d0bb801db80b2701fe31b54b0353a698260", "generated_at": "2026-03-25T10:43:42Z", "generator": "generate_diagrams.py"} -->
# Diagram: generating-diagrams

```mermaid
graph TD
    %% Legend
    subgraph Legend
        L_start([Start])
        L_process[Process Step]
        L_decision{Decision Point}
        L_subagent_dispatch[Subagent Dispatch / Skill Invocation]
        L_quality_gate{Quality Gate}
        L_terminal([Terminal State])
        style L_subagent_dispatch fill:#4a9eff,color:#fff
        style L_quality_gate fill:#ff6b6b,color:#fff
        style L_terminal fill:#51cf66,color:#fff
    end

    Start([Start]) --> Phase1[Phase 1: Analysis]

    subgraph Phase 1: Analysis
        Phase1 --> P1_1{Identify Diagram Subject?}
        P1_1 -->|Subject spans multiple types?| P1_1_separate[Produce separate diagrams]
        P1_1 -->|No| P1_2[Scope the Traversal]
        P1_1_separate --> P1_2

        P1_2 --> P1_3{Select Format?}
        P1_3 -->|Complexity (nodes > 50, styling, etc.)| P1_3_G[Graphviz DOT]
        P1_3 -->|Default: Mermaid| P1_3_M[Mermaid]
        P1_3_G --> P1_4{Plan Decomposition (if needed)?}
        P1_3_M --> P1_4

        P1_4 -->|Estimated node count exceeds limits?| P1_4_decompose[Decompose into levels (0, 1, 2)]
        P1_4 -->|No decomposition| P2_start
        P1_4_decompose --> P2_start
    end

    Phase2[Phase 2: Content Extraction]

    subgraph Phase 2: Content Extraction
        P2_start[Start Traversal Protocol] --> P2_1_algorithm[Systematic Traversal Algorithm]
        P2_1_algorithm --> P2_1_extract[Extract content: Decision points, Subagent dispatches, Data transformations, Quality gates, Loop logic, Terminal conditions, Conditional branches]
        P2_1_extract --> P2_2{Verify Completeness?}
        P2_2 -->|Not Complete (e.g., orphan nodes, missing branches, placeholders)?| P2_2_return[Return to Phase 2, re-traverse]
        P2_2 -->|Complete| P3_start
        P2_2_return --> P2_1_algorithm
    end

    Phase3[Phase 3: Diagram Generation]

    subgraph Phase 3: Diagram Generation
        P3_start[Start Diagram Generation] --> P3_1[Generate Diagram Code (Mermaid/Graphviz rules)]
        P3_1 --> P3_1_rules[Apply node/edge styling, labels, multiplicity]
        P3_1_rules --> P3_2[Generate Legend]
        P3_2 --> P3_3{Generate Cross-Reference Table?}
        P3_3 -->|Decomposed diagrams?| P3_3_yes[Yes]
        P3_3 -->|No| P4_start
        P3_3_yes --> P4_start
    end

    Phase4[Phase 4: Verification]

    subgraph Phase 4: Verification
        P4_start[Start Verification] --> P4_1{Syntax Check?}
        P4_1 -->|Syntax errors?| P4_return_P3[Return to Phase 3]
        P4_1 -->|OK| P4_2{Renderability Check?}
        P4_2 -->|Render issues (e.g., too many nodes, overlapping labels)?| P4_return_P1_4[Return to Phase 1.4: Decomposition]
        P4_2 -->|OK| P4_3{Completeness Check?}
        P4_3 -->|Not Complete (e.g., missing nodes/edges, unrepresented conditions)?| P4_return_P2[Return to Phase 2: Re-traverse]
        P4_3 -->|Complete| End([End: Diagram Generated])
        P4_return_P3 --> P3_1
        P4_return_P1_4 --> P1_4
        P4_return_P2 --> P2_1_algorithm
    end

    Start --> Phase1
    Phase1 --> Phase2
    Phase2 --> Phase3
    Phase3 --> Phase4
    Phase4 --> End

    style Phase1 fill:#f0f8ff,stroke:#333,stroke-width:2px
    style Phase2 fill:#f0f8ff,stroke:#333,stroke-width:2px
    style Phase3 fill:#f0f8ff,stroke:#333,stroke-width:2px
    style Phase4 fill:#f0f8ff,stroke:#333,stroke-width:2px
    style P2_1_algorithm fill:#4a9eff,color:#fff
    style P2_1_extract fill:#4a9eff,color:#fff
    style P2_2 fill:#ff6b6b,color:#fff
    style P4_1 fill:#ff6b6b,color:#fff
    style P4_2 fill:#ff6b6b,color:#fff
    style P4_3 fill:#ff6b6b,color:#fff
```

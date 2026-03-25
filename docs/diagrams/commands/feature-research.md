<!-- diagram-meta: {"source": "commands/feature-research.md", "source_hash": "sha256:26b944ed9044b4500b7aa4af6b3b60d9604582fc7f4ad9ec22227dc97c189f4f", "generated_at": "2026-03-25T15:32:37Z", "generator": "generate_diagrams.py"} -->
# Diagram: feature-research

I will generate a Mermaid diagram to visualize the `feature-research` command by following these steps:

1. **Analyze `commands/feature-research.md`**: I'll read the markdown file to understand the process, its steps, decision points, and any referenced commands or skills. This will help determine the overall structure and complexity, and confirm that Mermaid is the appropriate diagramming tool.
2. **Extract Content**: I will systematically go through the markdown file, identifying all key actions, decisions, inputs, outputs, and any conditional logic. I will look for calls to other agents, skills, or commands, and note success/failure conditions.
3. **Generate Diagram**: Based on the extracted information, I will construct a Mermaid diagram. I'll use standard flow chart elements:
    * Rectangles for processes/steps.
    * Diamonds for decision points.
    * Stadium shapes for start/end points.
    * Blue for subagent dispatches (`#4a9eff`).
    * Red for quality gates/critical checks (`#ff6b6b`).
    * Green for successful terminal conditions (`#51cf66`).
    I will also include a legend within the diagram.
4. **Verify Diagram**: I will check the Mermaid code for syntax errors and ensure that the diagram accurately reflects the `feature-research` command as described in the markdown file, covering all branches and outcomes.
```mermaid
graph TD
    %% Node Definitions
    start((Start))
    stop((Stop))
    prereq_check{Prerequisite Verification}
    prereq_fail_stop[Stop: Prerequisite Failed]:::red_stop
    strategy_plan[1.1 Research Strategy Planning]
    dispatch_subagent[1.2 Execute Research (Subagent)]:::blue_subagent
    subagent_retry_check{Subagent First Failure?}
    subagent_fail_2nd_stop[Subagent Failed Twice: Return UNKNOWN Findings]
    extract_ambiguities[1.3 Ambiguity Extraction]
    calc_quality_score[1.4 Research Quality Score Calculation]
    quality_gate{Research Quality Score >= 100%?}
    user_choice[User Chooses Action]
    phase1_complete_check{Phase 1 Complete Verification}
    phase1_fail_stop[Stop: Phase 1 Incomplete]:::red_stop
    proceed_to_1_5[/Proceed to Phase 1.5 (feature-discover)/]:::green_success

    %% Graph Connections
    start --> prereq_check
    prereq_check -- Any Check Fails --> prereq_fail_stop
    prereq_check -- All Checks Pass --> strategy_plan
    strategy_plan --> dispatch_subagent
    dispatch_subagent -- 1st Failure --> subagent_retry_check
    subagent_retry_check -- Yes --> dispatch_subagent
    subagent_retry_check -- No (2nd Failure) --> subagent_fail_2nd_stop
    subagent_fail_2nd_stop --> extract_ambiguities
    dispatch_subagent -- Success --> extract_ambiguities
    extract_ambiguities --> calc_quality_score
    calc_quality_score --> quality_gate
    quality_gate -- No (<100%) --> user_choice
    user_choice -- Continue Anyway / Iterate / Skip --> phase1_complete_check
    quality_gate -- Yes (100%) --> phase1_complete_check
    phase1_complete_check -- Any Unchecked --> phase1_fail_stop
    phase1_complete_check -- All Checked --> proceed_to_1_5

    proceed_to_1_5 --> stop
    prereq_fail_stop --> stop
    phase1_fail_stop --> stop


    %% Styling
    classDef red_stop fill:#ff6b6b,stroke:#333,stroke-width:2px,color:#fff;
    classDef green_success fill:#51cf66,stroke:#333,stroke-width:2px,color:#fff;
    classDef blue_subagent fill:#4a9eff,stroke:#333,stroke-width:2px,color:#fff;

    %% Legend
    subgraph Legend
        direction LR
        A[Process] --> B{Decision}
        C[Stop/Failure]:::red_stop
        D[Subagent Dispatch]:::blue_subagent
        E[Success]:::green_success
    end
```

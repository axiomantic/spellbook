# Fractal Thinking: MCP Tools and Node State Machine

Canonical reference for the `fractal_*` MCP tool surface, the metadata keys that
auto-create edges, the valid saturation reasons, and the node state machine.
`skills/fractal-thinking/SKILL.md` and all three phase commands
(`/fractal-think-seed`, `/fractal-think-work`, `/fractal-think-harvest`) resolve
tool names, parameter values, and status semantics here rather than restating them.

## Valid Parameter Values

- `intensity`: `pulse` | `explore` | `deep`
- `checkpoint_mode`: `autonomous` | `convergence` | `interactive` | `depth:N` (where N is a positive integer)

## Tool Surface

Graph lifecycle:
- `fractal_create_graph(seed, intensity, checkpoint_mode, metadata?)` -> `{graph_id, root_node_id, intensity, checkpoint_mode, budget, status}`
- `fractal_resume_graph(graph_id)` -> full graph snapshot
- `fractal_update_graph_status(graph_id, status, reason?)` -> status transition
- `fractal_delete_graph(graph_id)` -> cleanup

Node operations:
- `fractal_add_node(graph_id, parent_id, node_type, text, owner?, metadata?)` -> `{node_id, graph_id, parent_id, depth, node_type, status}`
- `fractal_update_node(graph_id, node_id, metadata)` -> merge metadata, auto-create edges
- `fractal_mark_saturated(graph_id, node_id, reason)` -> mark branch done
- `fractal_claim_work(graph_id, worker_id, session_id?)` -> atomically claim next open node with branch affinity; session_id links the node to the worker's chat log for replay
- `fractal_synthesize_node(graph_id, node_id, synthesis_text)` -> mark node synthesized with local synthesis

Query operations:
- `fractal_get_snapshot(graph_id)` -> full graph with all nodes/edges
- `fractal_get_branch(graph_id, node_id)` -> subtree from node
- `fractal_get_open_questions(graph_id)` -> unanswered questions
- `fractal_query_convergence(graph_id)` -> convergence clusters
- `fractal_query_contradictions(graph_id)` -> contradiction pairs with tension
- `fractal_get_saturation_status(graph_id)` -> branch saturation report
- `fractal_get_claimable_work(graph_id, worker_id?)` -> open nodes ordered by branch affinity
- `fractal_get_ready_to_synthesize(graph_id)` -> answered nodes whose children are all done

## Edge Creation via Metadata

`fractal_update_node` auto-creates edges when metadata contains:
- `"convergence_with": ["node_id_1", ...]` -> creates convergence edges
- `"contradiction_with": ["node_id_1", ...]` -> creates contradiction edges
- `"convergence_insight": "text"` -> stored for synthesis
- `"contradiction_tension": "text"` -> stored for synthesis

## Saturation Reasons

Valid reasons for `fractal_mark_saturated`:
`semantic_overlap` | `derivable` | `actionable` | `hollow_questions` | `budget_exhausted` | `error`

## Node State Machine

```
question:open -> question:claimed -> question:answered -> question:synthesized
                                                       -> question:saturated
                                  -> question:open        (recovery)
                                  -> question:error
                                  -> question:saturated   (budget exhaustion)
```

| Status | Meaning |
|--------|---------|
| `open` | Available for claiming. No worker owns this node. |
| `claimed` | A worker owns this node and is actively processing it. |
| `answered` | Node has been answered and may have child questions still in progress. |
| `synthesized` | All children done. Local synthesis complete. Synthesis text in metadata. |
| `saturated` | Branch needs no further exploration. |
| `error` | Processing failed. |
| `budget_exhausted` | Budget ceiling prevented further exploration. Note: in the standard worker flow, budget exhaustion at the node level is handled via `fractal_mark_saturated(reason="budget_exhausted")` which sets status to `saturated`, not `budget_exhausted`. The `budget_exhausted` node status exists for direct status management outside the worker flow. |

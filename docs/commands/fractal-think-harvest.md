# /fractal-think-harvest
## Command Content

``````````markdown
# Phase 3: Fractal Think Harvest

<ROLE>
Synthesis Analyst. Your reputation depends on accuracy and completeness: every finding traced to actual graph data, no fabricated insights, no missed contradictions. You read a completed fractal graph where bottom-up synthesis already occurred during the work phase. Verify the root is synthesized, extract the synthesis chain, format convergence and contradiction findings, and produce the final FractalResult deliverable. You verify and format. You do not re-synthesize.
</ROLE>

## Invariant Principles

1. **Evidence over narrative** - Every finding must trace to specific graph nodes; no unsupported claims.
2. **Contradictions are findings** - Unresolved tensions are reported as open questions, not hidden.
3. **Preserve synthesis fidelity** - Read bottom-up syntheses as composed by workers. Do not reconstruct, reinterpret, or replace them.

<analysis>Before harvest, assess: root synthesis status, any nodes still awaiting synthesis, graph completeness, convergence cluster count, unresolved contradictions, open questions.</analysis>
<reflection>After harvest, verify: every claim traces to nodes, no convergence overlooked, synthesis chain is complete from root to leaves, FractalResult complete.</reflection>

## Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `graph_id` | Yes | ID of the fractal graph to harvest |
| `seed` | Yes | The original seed for context |

## Step 1: Read Final Graph State

Query the complete graph:

```
snapshot = fractal_get_snapshot(graph_id: <graph_id>)
convergence = fractal_query_convergence(graph_id: <graph_id>)
contradictions = fractal_query_contradictions(graph_id: <graph_id>)
saturation = fractal_get_saturation_status(graph_id: <graph_id>)
open_questions = fractal_get_open_questions(graph_id: <graph_id>)
ready_to_synthesize = fractal_get_ready_to_synthesize(graph_id: <graph_id>)
```

Record metrics from the snapshot:
- `node_count`: total nodes
- `edge_count`: total edges (from snapshot.edges.length)
- `max_depth`: highest depth value among all nodes
- `answer_count`: nodes where node_type == "answer"
- `synthesized_count`: nodes where status == "synthesized"
- `saturated_count`: nodes where status == "saturated"
- `open_count`: open_questions.count
- `missed_synthesis_count`: ready_to_synthesize.count (should be 0)

## Step 2: Verify Root Synthesis

Find the root node (depth == 0) in the snapshot.

**If root status is "synthesized":**
- Extract root synthesis text from `metadata.synthesis`. This is the primary answer.
- Proceed to Step 3.

**If root status is "answered" and all children are done:**
- The work phase missed the final root synthesis. This is recoverable.
- Read the syntheses of all immediate children of the root (from their `metadata.synthesis` fields).
- Compose a root synthesis from the children's syntheses, just as a worker would have:
  - Summarize the children's syntheses into a coherent answer to the root question.
  - Store the synthesis via `fractal_synthesize_node(graph_id: <graph_id>, node_id: <root_node_id>, synthesis_text: <composed synthesis>)`.
- Log a warning: "Root synthesis was missing; composed from child syntheses during harvest."
- Proceed to Step 3.

**If root has no answer (status is "open" or "claimed"):**
- Exploration did not complete. Report error.
- Set `status` to "error" in the FractalResult.
- Provide whatever partial findings are available from answered branches.

**If `ready_to_synthesize` returned nodes:**
- Some non-leaf nodes were missed by the bottom-up synthesis cascade. Log warnings for each.
- If count ≤ 5: synthesize them now starting from the deepest. For each, read its children's syntheses and compose. This repairs the synthesis chain.
- If count > 5: report the gap in the FractalResult findings. Do not attempt bulk repair.

## Step 3: Extract Findings

<CRITICAL>
API key names matter. Convergence query returns `insight` (not `convergence_insight`). Contradiction query returns `tension` (not `contradiction_tension`). Using the wrong key silently produces empty findings. Verify key names before constructing each finding block.
</CRITICAL>

### 3.1 Convergence Points (High-Confidence Findings)

For each convergence cluster from `fractal_query_convergence`:

1. Read the `insight` from the cluster. **Key name is `insight`, not `convergence_insight`.**
2. Identify all nodes in the cluster.
3. For each node, read its text (the answer).
4. Construct finding:

```
Finding: <insight>
Confidence: HIGH (converged from <N> independent branches)
Supporting nodes: <list of node texts, summarized>
```

Convergence points are the strongest findings — multiple independent branches arriving at the same conclusion is strong evidence.

### 3.2 Unresolved Contradictions (Open Tensions)

For each contradiction from `fractal_query_contradictions`:

1. Read the `tension` from the contradiction dict. **Key name is `tension`, not `contradiction_tension`.**
2. Check if either node has `contradiction_resolved: true` in metadata.
3. If resolved: skip (it is a resolved finding, not an open tension).
4. If unresolved: flag as open tension.

```
Tension: <tension>
Side A: <node_a text, summarized>
Side B: <node_b text, summarized>
Status: UNRESOLVED
```

### 3.3 Resolved Contradictions

For contradictions where `contradiction_resolved: true`:

1. Find the resolution node (from `resolution_node` in metadata).
2. Read the resolution text.

```
Resolved tension: <tension>
Resolution: <resolution_node text>
```

### 3.4 Boundary Questions

Scan all nodes in the snapshot for `metadata.boundary == true`. These are cross-branch convergence questions created during the work phase when a worker detected convergence between branches.

For each boundary question:

1. Read the question text and its answer (if answered/synthesized).
2. Read the `converging_nodes` from its metadata to identify the original convergent nodes.
3. Construct finding:

```
Boundary exploration: <question text>
Converging nodes: <converging_node_a>, <converging_node_b>
Finding: <answer or synthesis text, if available>
Status: <answered | synthesized | open>
```

Answered boundary questions yield the deepest cross-branch insights; open ones represent unexplored connections.

### 3.5 Synthesis Chain

Walk from the root node downward, extracting the synthesis text at each level. This produces a layered view where readers can stop at any depth they choose.

1. Start with the root node. Record `{node_id, depth: 0, question: <text>, synthesis: <metadata.synthesis>}`.
2. For each child question of the root that has status "synthesized", record the same structure at depth 1.
3. Continue recursively for children of children, stopping when nodes have no synthesized children or when depth exceeds `max_depth`.

The result is an array of `{node_id, depth, question, synthesis}` ordered depth-first:
- Depth 0: Root synthesis (the complete answer)
- Depth 1: Branch syntheses (major themes)
- Depth 2+: Sub-branch syntheses (specific findings)

### 3.6 Saturated Branches (Explored to Completion)

For each saturated branch from `fractal_get_saturation_status`:

1. Read the branch root text.
2. Read the saturation reason.
3. Summarize what was learned in this branch.

```
Branch: <branch_text>
Saturation reason: <reason>
Key finding: <summary of answers in this branch>
```

### 3.7 Unexplored Questions (Known Gaps)

For each open question from `fractal_get_open_questions`:

1. Check if it has `budget_exhausted: true` in metadata.
2. Read the question text.

```
Gap: <question_text>
Reason: <budget_exhausted | not_reached>
```

Additionally, scan for nodes with status "claimed" in the snapshot. These represent stuck workers that never completed their work. Report them separately:

```
Stuck: <question_text> (claimed by <owner>, never completed)
```

### 3.8 Depth-Limited Answers

Scan all answer nodes for `depth_limited: true` in metadata. These are answers that could have generated more sub-questions but were stopped by the depth budget.

```
Depth-limited: <answer_text> (at depth <depth>)
Implication: Further exploration in this direction was cut short
```

## Step 4: Generate Summary

Compose a natural language summary structured as follows. **Lead with the root synthesis** — it is the primary answer composed bottom-up from all branch syntheses.

### Summary Template

```markdown
## Fractal Thinking: <seed (truncated to 80 chars)>

### Answer

<The root synthesis text. This is the primary deliverable. Present it as a
direct, clear answer to the seed question. If the root synthesis is long,
this section may span several paragraphs.>

### Supporting Branch Syntheses

<For each depth-1 synthesized child of the root, write 1-3 sentences
summarizing its synthesis. These are the major themes that composed into
the root answer. Order by depth-1 node creation order (preserves the
natural decomposition structure). If there is only one branch, omit this
section and let the root synthesis stand alone.>

### Key Findings

<For each convergence point, write 1-2 sentences summarizing the finding
and its confidence level. Order by number of converging branches (most
convergence first). Include boundary question findings here if they
produced answered results.>

### Open Tensions

<For each unresolved contradiction, write 1-2 sentences describing the
tension and what would resolve it. If no contradictions, state "No
unresolved contradictions.">

### Resolved Tensions

<For each resolved contradiction, write 1 sentence. If none, omit section.>

### Known Gaps

<For each unexplored question, write 1 bullet. Group by reason
(budget vs not reached vs stuck). If no gaps, state "All branches fully explored.">

### Exploration Metrics

- Nodes: <node_count> (<answer_count> answers, <synthesized_count> synthesized, <open_count> open questions)
- Depth: <max_depth> levels
- Branches: <saturated_count> saturated, <open branch count> open
- Convergence points: <convergence.count>
- Contradictions: <contradictions.count> (<resolved_count> resolved)
- Boundary questions: <boundary_count> (<boundary_answered_count> answered)
```

### Summary Quality Rules

1. **Lead with the root synthesis.** The answer section is the most important part. Convergence points support it.
2. **Quantify confidence.** "3 branches converged" is better than "high confidence".
3. **Name tensions explicitly.** "X says A but Y says B" not "some disagreement exists".
4. **Acknowledge gaps honestly.** Never imply completeness if open questions remain.
5. **Show the synthesis depth.** The supporting branch syntheses section demonstrates that the answer was composed bottom-up, not fabricated top-down.
6. **Scale summary length with intensity:** 200-500 words (pulse), 500-1000 words (explore), 1000-2000 words (deep). The intensity was set by the orchestrator; if unknown, default to pulse.

## Step 5: Mark Graph Completed

<CRITICAL>
Only transition if the graph is currently in "active" or "budget_exhausted" status. Terminal states (`completed`, `error`) cannot transition — skip the status update and note the current status in the FractalResult. Do not attempt to force a transition.
</CRITICAL>

```
fractal_update_graph_status(
  graph_id: <graph_id>,
  status: "completed",
  reason: "Harvest complete"
)
```

Valid transitions:
- `active` -> `completed`, `paused`, `error`, `budget_exhausted`
- `budget_exhausted` -> `active`, `completed`
- `paused` -> `active`

## Step 6: Return FractalResult

Return the structured result to the orchestrator:

```json
{
  "graph_id": "<graph_id>",
  "seed": "<seed>",
  "status": "<final graph status>",
  "summary": "<the natural language summary from Step 4>",
  "node_count": "<total nodes>",
  "edge_count": "<total edges>",
  "max_depth": "<max depth reached>",
  "convergence_count": "<number of convergence clusters>",
  "contradiction_count": "<number of contradictions>",
  "unresolved_contradiction_count": "<number unresolved>",
  "open_question_count": "<remaining open questions>",
  "synthesis_chain": [
    {
      "node_id": "<node_id>",
      "depth": 0,
      "question": "<question text>",
      "synthesis": "<synthesis text from metadata>"
    },
    {
      "node_id": "<node_id>",
      "depth": 1,
      "question": "<question text>",
      "synthesis": "<synthesis text from metadata>"
    }
  ],
  "boundary_questions": [
    {
      "node_id": "<node_id>",
      "question": "<boundary question text>",
      "converging_nodes": ["<node_a_id>", "<node_b_id>"],
      "status": "<answered | synthesized | open>",
      "finding": "<answer or synthesis text, if available>"
    }
  ],
  "findings": [
    {
      "type": "convergence",
      "insight": "<convergence insight>",
      "confidence": "HIGH",
      "supporting_nodes": "<count>"
    },
    {
      "type": "tension",
      "description": "<contradiction tension>",
      "status": "UNRESOLVED | RESOLVED",
      "resolution": "<resolution text if resolved>"
    },
    {
      "type": "gap",
      "question": "<unexplored question>",
      "reason": "budget_exhausted | not_reached | stuck"
    },
    {
      "type": "depth_limited",
      "answer": "<answer text>",
      "depth": "<depth>"
    }
  ]
}
```

## Edge Cases

### Empty Graph

If the graph has only the root node and no children (seeding failed or was skipped), return:

```json
{
  "graph_id": "<graph_id>",
  "seed": "<seed>",
  "status": "error",
  "summary": "No exploration occurred. Graph contains only the seed question.",
  "node_count": 1,
  "edge_count": 0,
  "max_depth": 0,
  "synthesis_chain": [],
  "boundary_questions": []
}
```

### All Questions Still Open

If no questions were answered (workers failed entirely):

```json
{
  "summary": "Exploration was attempted but no questions were answered. <open_count> questions remain open.",
  "status": "error",
  "synthesis_chain": [],
  "boundary_questions": []
}
```

### Graph Not Found

If `fractal_get_snapshot` returns `{"error": ...}`:

Return the error directly. Do not fabricate a summary.

### Root Not Synthesized but Children Are

If the root is "answered" and all children are "synthesized" or "saturated", the work phase missed the final root synthesis. Step 2 handles this by composing the root synthesis from children. This is the most common partial-completion scenario.

### Claimed Nodes Remain

If nodes are still in "claimed" status, workers exited without completing their work. Report these as stuck nodes in the Known Gaps section. The orchestrator should have cleaned these up, but harvest handles the case gracefully.

## Error Handling

| Error | Action |
|-------|--------|
| `fractal_get_snapshot` returns error | Return error as FractalResult with status "error" |
| `fractal_update_graph_status` rejects transition | Skip status update, note in result |
| Convergence/contradiction queries fail | Proceed with partial data, note gaps |
| `fractal_get_ready_to_synthesize` fails | Proceed without synthesis gap detection |
| `fractal_synthesize_node` fails during root repair | Report root synthesis as missing in summary |
| Summary generation fails | Return structured findings without prose summary |

<FORBIDDEN>
- Fabricating findings not present in the graph
- Claiming completeness when open questions remain
- Omitting contradictions from the summary
- Marking graph as "completed" when it is in a terminal error state
- Generating a summary without reading the actual graph (using cached/stale data)
- Inventing convergence or contradiction that is not recorded as edges in the graph
- Re-synthesizing the entire graph top-down instead of reading the existing bottom-up syntheses
- Ignoring the synthesis chain in favor of raw graph traversal
- Using `convergence_insight` as the convergence key (correct key: `insight`)
- Using `contradiction_tension` as the contradiction key (correct key: `tension`)
</FORBIDDEN>

<FINAL_EMPHASIS>
You are a Synthesis Analyst. The quality of this harvest is the quality of the entire fractal exploration — every finding must trace to actual graph data, every contradiction must surface, every gap must be named. A summary that omits contradictions or fabricates convergence is worse than no summary. Verify before you deliver.
</FINAL_EMPHASIS>
``````````

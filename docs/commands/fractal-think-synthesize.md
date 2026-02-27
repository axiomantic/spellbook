# /fractal-think-synthesize
## Command Content

``````````markdown
# Phase 3: Fractal Think Synthesize

<ROLE>
Synthesis Analyst. You read a completed exploration graph and distill it into
a clear, actionable summary. You surface convergence points as high-confidence
findings, flag unresolved contradictions as open tensions, and note unexplored
branches as known gaps. Your output is the final deliverable to the caller.
</ROLE>

## Invariant Principles

1. **Evidence over narrative** - Every finding must trace to specific graph nodes; no unsupported claims.
2. **Contradictions are findings** - Unresolved tensions are reported as open questions, not hidden.
3. **Completeness is explicit** - Report explored branches, saturated branches, and unexplored gaps separately.

<analysis>Before synthesis, assess: graph completeness, convergence cluster count, unresolved contradictions, open questions.</analysis>
<reflection>After synthesis, verify: every claim traces to nodes, no convergence overlooked, FractalResult complete.</reflection>

## Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `graph_id` | Yes | ID of the fractal graph to synthesize |
| `seed` | Yes | The original seed for context |

## Step 1: Read Final Graph State

Query the complete graph:

```
snapshot = fractal_get_snapshot(graph_id: <graph_id>)
convergence = fractal_query_convergence(graph_id: <graph_id>)
contradictions = fractal_query_contradictions(graph_id: <graph_id>)
saturation = fractal_get_saturation_status(graph_id: <graph_id>)
open_questions = fractal_get_open_questions(graph_id: <graph_id>)
```

Record metrics from the snapshot:
- `node_count`: total nodes
- `edge_count`: total edges (from snapshot.edges.length)
- `max_depth`: highest depth value among all nodes
- `answer_count`: nodes where node_type == "answer"
- `saturated_count`: nodes where status == "saturated"
- `open_count`: open_questions.count

## Step 2: Extract Findings

### 2.1 Convergence Points (High-Confidence Findings)

For each convergence cluster from `fractal_query_convergence`:

1. Read the `convergence_insight` from the cluster
2. Identify all nodes in the cluster
3. For each node, read its text (the answer)
4. Construct finding:

```
Finding: <convergence_insight>
Confidence: HIGH (converged from <N> independent branches)
Supporting nodes: <list of node texts, summarized>
```

Convergence points are the strongest findings. Multiple independent branches
arriving at the same conclusion is strong evidence.

### 2.2 Unresolved Contradictions (Open Tensions)

For each contradiction from `fractal_query_contradictions`:

1. Read the `contradiction_tension` from the edge metadata
2. Check if either node has `contradiction_resolved: true` in metadata
3. If resolved: skip (it is a resolved finding, not an open tension)
4. If unresolved: flag as open tension

```
Tension: <contradiction_tension>
Side A: <node_a text, summarized>
Side B: <node_b text, summarized>
Status: UNRESOLVED
```

### 2.3 Resolved Contradictions

For contradictions where `contradiction_resolved: true`:

1. Find the resolution node (from `resolution_node` in metadata)
2. Read the resolution text

```
Resolved tension: <contradiction_tension>
Resolution: <resolution_node text>
```

### 2.4 Saturated Branches (Explored to Completion)

For each saturated branch from `fractal_get_saturation_status`:

1. Read the branch root text
2. Read the saturation reason
3. Summarize what was learned in this branch

```
Branch: <branch_text>
Saturation reason: <reason>
Key finding: <summary of answers in this branch>
```

### 2.5 Unexplored Questions (Known Gaps)

For each open question from `fractal_get_open_questions`:

1. Check if it has `budget_exhausted: true` in metadata
2. Read the question text

```
Gap: <question_text>
Reason: <budget_exhausted | not_reached>
```

### 2.6 Depth-Limited Answers

Scan all answer nodes for `depth_limited: true` in metadata. These are
answers that could have generated more sub-questions but were stopped by
the depth budget.

```
Depth-limited: <answer_text> (at depth <depth>)
Implication: Further exploration in this direction was cut short
```

## Step 3: Generate Summary

Compose a natural language summary structured as follows:

### Summary Template

```markdown
## Fractal Thinking: <seed (truncated to 80 chars)>

### Key Findings

<For each convergence point, write 1-2 sentences summarizing the finding
and its confidence level. Order by number of converging branches (most
convergence first).>

### Open Tensions

<For each unresolved contradiction, write 1-2 sentences describing the
tension and what would resolve it. If no contradictions, state "No
unresolved contradictions.">

### Resolved Tensions

<For each resolved contradiction, write 1 sentence. If none, omit section.>

### Known Gaps

<For each unexplored question, write 1 bullet. Group by reason
(budget vs not reached). If no gaps, state "All branches fully explored.">

### Exploration Metrics

- Nodes: <node_count> (<answer_count> answers, <open_count> open questions)
- Depth: <max_depth> levels
- Branches: <saturated_count> saturated, <open branch count> open
- Convergence points: <convergence.count>
- Contradictions: <contradictions.count> (<resolved_count> resolved)
```

### Summary Quality Rules

1. **Lead with strongest findings.** Convergence points first, always.
2. **Quantify confidence.** "3 branches converged" is better than "high confidence".
3. **Name tensions explicitly.** "X says A but Y says B" not "some disagreement exists".
4. **Acknowledge gaps honestly.** Never imply completeness if open questions remain.
5. **Be concise.** The summary should be 200-500 words for pulse, 500-1000 for
   explore, 1000-2000 for deep. Scale with intensity.

## Step 4: Mark Graph Completed

Only transition if the graph is currently in "active" status:

```
fractal_update_graph_status(
  graph_id: <graph_id>,
  status: "completed",
  reason: "Synthesis complete"
)
```

**Terminal states cannot transition.** The following are terminal:
`completed`, `error`, `budget_exhausted`. If the graph is already in any
of these states, skip the status update. Note the current status in the
FractalResult; do not attempt to force a transition.

Valid transitions:
- `active` -> `completed`, `paused`, `error`, `budget_exhausted`
- `paused` -> `active`

## Step 5: Return FractalResult

Return the structured result to the orchestrator:

```json
{
  "graph_id": "<graph_id>",
  "seed": "<seed>",
  "status": "<final graph status>",
  "summary": "<the natural language summary from Step 3>",
  "node_count": <total nodes>,
  "edge_count": <total edges>,
  "max_depth": <max depth reached>,
  "convergence_count": <number of convergence clusters>,
  "contradiction_count": <number of contradictions>,
  "unresolved_contradiction_count": <number unresolved>,
  "open_question_count": <remaining open questions>,
  "findings": [
    {
      "type": "convergence",
      "insight": "<convergence insight>",
      "confidence": "HIGH",
      "supporting_nodes": <count>
    },
    {
      "type": "tension",
      "description": "<contradiction tension>",
      "status": "UNRESOLVED" | "RESOLVED",
      "resolution": "<resolution text if resolved>"
    },
    {
      "type": "gap",
      "question": "<unexplored question>",
      "reason": "budget_exhausted" | "not_reached"
    }
  ]
}
```

## Edge Cases

### Empty Graph

If the graph has only the root node and no children (Phase 1 failed or
was skipped), return:

```json
{
  "graph_id": "<graph_id>",
  "seed": "<seed>",
  "status": "error",
  "summary": "No exploration occurred. Graph contains only the seed question.",
  "node_count": 1,
  "edge_count": 0,
  "max_depth": 0
}
```

### All Questions Still Open

If no questions were answered (Phase 2 failed entirely):

```json
{
  "summary": "Exploration was attempted but no questions were answered. <open_count> questions remain open.",
  "status": "error"
}
```

### Graph Not Found

If `fractal_get_snapshot` returns `{"error": ...}`:

Return the error directly. Do not fabricate a summary.

## Error Handling

| Error | Action |
|-------|--------|
| `fractal_get_snapshot` returns error | Return error as FractalResult with status "error" |
| `fractal_update_graph_status` rejects transition | Skip status update, note in result |
| Convergence/contradiction queries fail | Proceed with partial data, note gaps |
| Summary generation fails | Return structured findings without prose summary |

<FORBIDDEN>
- Fabricating findings not present in the graph
- Claiming completeness when open questions remain
- Omitting contradictions from the summary
- Marking graph as "completed" when it is in a terminal error state
- Generating a summary without reading the actual graph (using cached/stale data)
- Inventing convergence or contradiction that is not recorded as edges in the graph
</FORBIDDEN>
``````````

---
description: "Phase 2 of fractal-thinking: Recursive exploration with subagent dispatch, convergence detection, contradiction handling"
---

# Phase 2: Fractal Think Explore

<ROLE>
Exploration Coordinator. You dispatch subagents per cluster, monitor graph
state via MCP query tools, detect convergence and contradiction, manage budget,
and decide when exploration is complete. You read the graph; subagents write it.
</ROLE>

<CRITICAL>
You are a coordinator, NOT an explorer. You dispatch subagents to explore
clusters. You query the graph to monitor progress. You NEVER answer questions
or write answer nodes yourself.
</CRITICAL>

## Invariant Principles

1. **Coordinator reads, subagents write** - Never create answer nodes directly; dispatch subagents for all exploration.
2. **Convergence halts branches** - When multiple paths reach the same conclusion, mark branches saturated.
3. **Contradictions spawn resolution** - Flag contradictions AND create resolution branches to investigate.

<analysis>Before each round, assess: open questions count, budget remaining, convergence clusters, contradiction pairs.</analysis>
<reflection>After each round, verify: no budget overrun, new convergence/contradictions detected, saturation propagated.</reflection>

## Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `exploration_state` | Yes | JSON from Phase 1 with graph_id, clusters, budget, etc. |

## Exploration Loop

The exploration runs in rounds. Each round:
1. Dispatch subagents for active clusters
2. Wait for subagent completion
3. Query graph for convergence and contradictions
4. Check saturation status
5. Apply checkpoint logic
6. Decide: continue, pause, or complete

```
[Dispatch Cluster Agents] -> [Monitor Completion]
         ^                          |
         |                    [Query Graph State]
         |                          |
         |                    [Check Convergence]
         |                    [Check Contradictions]
         |                    [Check Saturation]
         |                          |
         |                    [Checkpoint Decision]
         |                          |
         |         CONTINUE         |
         +--------------------------+
                       |
                  DONE/PAUSE
                       |
                  [Return State]
```

## Step 1: Parse Exploration State

Extract from the provided `exploration_state`:

```
graph_id = state.graph_id
root_node_id = state.root_node_id
intensity = state.intensity
checkpoint = state.checkpoint
budget = state.budget
agents_spawned = state.agents_spawned
current_depth = state.current_depth
clusters = state.clusters
```

Verify the graph is still active:

```
fractal_get_snapshot(graph_id: <graph_id>)
```

If graph status is not "active", return immediately with explanation.

## Step 2: Dispatch Cluster Agents

For each cluster that has open questions, dispatch a subagent. Each subagent
is responsible for one cluster and operates independently.

### Budget Check Before Dispatch

```
remaining_agents = budget.max_agents - agents_spawned
clusters_needing_exploration = clusters with open questions
agents_to_dispatch = min(remaining_agents, len(clusters_needing_exploration))
```

If `remaining_agents <= 0`, skip to Step 5 (budget exhausted path).

### Subagent Prompt Template

For each cluster being dispatched:

```
Task(
  description: "Fractal Explore cluster: <cluster.domain>",
  prompt: """
You are a fractal exploration agent for cluster "<cluster.domain>".

## Your Mission

Answer the open questions assigned to you and generate follow-up questions
where uncertainty remains. Write all your work to the graph via MCP tools.

## Graph Context

Graph ID: <graph_id>
Your cluster: <cluster.domain>
Your agent ID: "agent-<cluster.cluster_id>"

## Your Questions

<for each question_id in cluster.question_ids>
- Node <question_id>: "<question_text>"
</for>

## Step 1: Read Graph Snapshot

Call fractal_get_snapshot(graph_id: "<graph_id>") to understand current
graph state. Read ALL existing nodes to avoid duplicating work.

## Step 2: Answer Each Open Question

For each open question assigned to you:

1. Think carefully about the answer
2. Write the answer as a child node:
   fractal_add_node(
     graph_id: "<graph_id>",
     parent_id: "<question_node_id>",
     node_type: "answer",
     text: "<your_answer>",
     owner: "agent-<cluster.cluster_id>"
   )
   Note: adding an answer node auto-transitions the parent to "answered" if the parent is an open question

3. After answering, apply the Adaptive Primitive:
   "Given everything in this graph, and given this answer I just wrote,
   what questions would move me toward certainty? Generate only questions
   NOT already answered or derivable from existing answers."

4. For each generated sub-question, apply Structural Proxy Judgment:

### Structural Proxy Judgment

Evaluate your answer against these signals to decide whether each
sub-question warrants a new branch (new question node) or is trivially
answerable inline (answer it immediately without a new question node):

| Signal | How to Detect | Verdict |
|--------|--------------|---------|
| Qualifiers in your answer | "maybe", "probably", "it depends", "could be" | BRANCH |
| Listed alternatives | "Option A... Option B..." or "either X or Y" | BRANCH |
| Unverifiable assumptions | "assuming that...", "if X is true..." | BRANCH |
| Short confident answer | <=2 sentences, no qualifiers, high confidence | INLINE |
| New domain not in graph | Topic not covered by any existing node | BRANCH |
| Factual lookup needed | Answer is a specific verifiable fact | INLINE |
| High blast radius | Answer affects multiple other branches | BRANCH |

**BRANCH verdict:** Create a new question node as child of your answer:
  fractal_add_node(
    graph_id: "<graph_id>",
    parent_id: "<answer_node_id>",
    node_type: "question",
    text: "<sub_question>",
    owner: "agent-<cluster.cluster_id>",
    metadata: '{"cluster": "<cluster.domain>", "proxy_signal": "<signal_name>"}'
  )

**INLINE verdict:** The sub-question is trivially answerable. Skip it.
  Do NOT create a node for it.

5. Depth check: Before creating sub-question nodes, verify:
   current_depth_of_parent + 1 <= <budget.max_depth>
   If at max depth, do NOT create sub-questions. Instead, mark the answer
   with metadata noting depth limit reached:
   fractal_update_node(
     graph_id: "<graph_id>",
     node_id: "<answer_node_id>",
     metadata: '{"depth_limited": true}'
   )

## Step 3: Detect Convergence

After answering all your questions, scan the graph snapshot for convergence:

1. Re-read the snapshot: fractal_get_snapshot(graph_id: "<graph_id>")
2. Compare your answers with answers from other agents (different owners)
3. If two answers reach the same conclusion from different angles:
   fractal_update_node(
     graph_id: "<graph_id>",
     node_id: "<your_answer_node_id>",
     metadata: '{"convergence_with": ["<other_node_id>"], "convergence_insight": "<what converged>"}'
   )

## Step 4: Detect Contradictions

1. Scan for answers that directly contradict your answers
2. Two answers contradict if they cannot both be true simultaneously
3. If contradiction found:
   fractal_update_node(
     graph_id: "<graph_id>",
     node_id: "<your_answer_node_id>",
     metadata: '{"contradiction_with": ["<other_node_id>"], "contradiction_tension": "<describe the tension>"}'
   )

## Step 5: Check Saturation

For each branch you explored, evaluate saturation:

| Reason | When to Apply |
|--------|--------------|
| semantic_overlap | New questions rephrase existing ones |
| derivable | Answers can be derived from existing graph nodes |
| actionable | Answer is concrete enough to act on, no more questions needed |
| hollow_questions | Sub-questions are vague or rhetorical, not productive |

If a branch is saturated:
  fractal_mark_saturated(
    graph_id: "<graph_id>",
    node_id: "<branch_root_node_id>",
    reason: "<reason>"
  )

## Step 6: Report

Return a summary of your work:
- Questions answered (count)
- Sub-questions generated (count)
- Convergences detected (list)
- Contradictions detected (list)
- Branches saturated (list with reasons)
"""
)
```

Increment `agents_spawned` by the number dispatched.

## Step 3: Monitor Subagent Completion

Wait for all dispatched subagents to complete. Collect their reports.

After all subagents finish, query the graph for the global view:

```
snapshot = fractal_get_snapshot(graph_id: <graph_id>)
convergence = fractal_query_convergence(graph_id: <graph_id>)
contradictions = fractal_query_contradictions(graph_id: <graph_id>)
saturation = fractal_get_saturation_status(graph_id: <graph_id>)
open_questions = fractal_get_open_questions(graph_id: <graph_id>)
```

## Step 4: Handle Contradictions

If `contradictions.count > 0`, spawn a resolution agent for each contradiction:

```
Task(
  description: "Fractal: resolve contradiction",
  prompt: """
You are a contradiction resolver for fractal graph <graph_id>.

Contradiction detected between nodes:
- Node <node_a>: "<text_a>"
- Node <node_b>: "<text_b>"
Tension: "<tension_description>"

## Instructions

1. Read both branches: fractal_get_branch for each node
2. Determine which answer is more supported by evidence in the graph
3. If both have merit, create a synthesis answer that reconciles them
4. Write your resolution as a new answer node:
   fractal_add_node(
     graph_id: "<graph_id>",
     parent_id: "<root_node_id>",
     node_type: "answer",
     text: "Resolution: <your_resolution>",
     owner: "resolver"
   )
5. Mark resolution in metadata of both contradicting nodes:
   fractal_update_node(
     graph_id: "<graph_id>",
     node_id: "<node_a>",
     metadata: '{"contradiction_resolved": true, "resolution_node": "<resolution_node_id>"}'
   )
"""
)
```

Increment `agents_spawned` for each resolution agent.

## Step 5: Apply Checkpoint Logic

### Completion Conditions

Check these in order:

1. **All saturated:** `saturation.all_saturated == true` -> DONE
2. **No open questions:** `open_questions.count == 0` -> DONE
3. **Budget exhausted (agents):** `agents_spawned >= budget.max_agents` -> BUDGET_EXHAUSTED
4. **Budget exhausted (depth):** `max node depth >= budget.max_depth` -> BUDGET_EXHAUSTED

### Checkpoint Mode Handling

**autonomous:** If not DONE or BUDGET_EXHAUSTED, loop back to Step 2 with
remaining open questions re-clustered.

**convergence:** If `convergence.count > 0`, PAUSE. Return state with
convergence findings for the orchestrator to present to the caller.

**interactive:** PAUSE after every round. Return state with current
graph summary for user review.

**depth:N:** Parse N from checkpoint mode. If any node's depth is a
multiple of N and new since last check, PAUSE. Return state for review.

### Re-clustering for Next Round

If continuing (not DONE, not PAUSED, not BUDGET_EXHAUSTED):

1. Get remaining open questions: `fractal_get_open_questions(graph_id)`
2. Group by cluster metadata (same domain)
3. If open questions span new domains, create new clusters
4. Update `exploration_state.clusters` with new cluster list
5. Update `current_depth` to max depth in graph
6. Loop back to Step 2

## Step 6: Return Updated State

Return the updated exploration state:

```json
{
  "graph_id": "<graph_id>",
  "root_node_id": "<root_node_id>",
  "intensity": "<intensity>",
  "checkpoint": "<checkpoint>",
  "budget": { "max_agents": 8, "max_depth": 4 },
  "agents_spawned": <updated_count>,
  "current_depth": <updated_depth>,
  "clusters": <updated_clusters>,
  "status": "all_saturated" | "budget_exhausted" | "convergence_detected" | "paused" | "active",
  "convergence_points": <from fractal_query_convergence>,
  "contradictions": <from fractal_query_contradictions>,
  "open_questions_remaining": <count>
}
```

## Budget Exhaustion Protocol

When budget is exhausted before all branches are saturated:

1. Freeze the graph:
   ```
   fractal_update_graph_status(
     graph_id: <graph_id>,
     status: "budget_exhausted",
     reason: "Reached max_agents=<N> or max_depth=<N>"
   )
   ```

2. For each open question remaining, note it was not explored:
   ```
   fractal_update_node(
     graph_id: <graph_id>,
     node_id: <open_question_id>,
     metadata: '{"budget_exhausted": true, "unexplored_reason": "budget limit reached"}'
   )
   ```

3. Set status to "budget_exhausted" in return state

## Error Handling

| Error | Action |
|-------|--------|
| Subagent fails entirely | Mark affected cluster questions as status "error", continue with other clusters |
| MCP query tool returns error | Retry once, then proceed with stale data and note in metadata |
| Graph transitions to non-active state unexpectedly | Return immediately with current state |
| Contradiction resolution agent fails | Log failure, leave contradiction unresolved for synthesis phase |

<FORBIDDEN>
- Answering questions in coordinator context instead of dispatching subagents
- Dispatching more agents than budget.max_agents
- Creating nodes deeper than budget.max_depth
- Ignoring contradictions (must attempt resolution)
- Skipping convergence/saturation checks between rounds
- Continuing after all branches saturated (wasted budget)
- Modifying graph status to "completed" (that is Phase 3's job)
</FORBIDDEN>

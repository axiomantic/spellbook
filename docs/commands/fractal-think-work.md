# /fractal-think-work
## Command Content

``````````markdown
# Phase 2: Fractal Think Work

<ROLE>
Worker Dispatcher. You dispatch parallel worker subagents that claim and process
nodes from the fractal graph. Each worker executes the same recursive primitive
(decompose, synthesize, connect) on whatever node it claims. You monitor graph
state and handle termination.
</ROLE>

<CRITICAL>
Workers claim, workers explore, workers synthesize. The dispatcher only monitors.
You NEVER answer questions, create answer nodes, or write synthesis text yourself.
You dispatch workers and wait for them to finish.
</CRITICAL>

## Invariant Principles

1. **Workers claim, workers explore, workers synthesize** - The dispatcher only monitors. All graph mutations happen inside worker subagents.
2. **The graph IS the work queue** - All state is in MCP tools. There is no separate task queue, no round counter, no cluster registry. Workers pull work dynamically via `fractal_claim_work`.
3. **Branch affinity is a preference, not a guarantee** - Workers prefer nodes in branches they have already touched, but work stealing ensures progress when affinity-matching work is exhausted.

<analysis>Before dispatching, assess: open question count, budget limits, graph active status.</analysis>
<reflection>After workers finish, verify: no orphaned claimed nodes, synthesis cascade complete, all work accounted for.</reflection>

## Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `exploration_state` | Yes | JSON from Phase 1 (seed command) with graph_id, budget, intensity, checkpoint |

The `exploration_state` has this shape:

```json
{
  "graph_id": "<graph_id>",
  "root_node_id": "<root_node_id>",
  "intensity": "<intensity>",
  "checkpoint": "<checkpoint>",
  "budget": { "max_agents": 8, "max_depth": 4 },
  "seed_count": 6
}
```

## Step 1: Parse State and Compute Worker Count

Extract from the provided `exploration_state`:

```
graph_id = state.graph_id
root_node_id = state.root_node_id
intensity = state.intensity
checkpoint = state.checkpoint
budget = state.budget
seed_count = state.seed_count
```

### Verify Graph is Active

```
snapshot = fractal_get_snapshot(graph_id: <graph_id>)
```

If graph status is not "active", return immediately with explanation.

### Compute Worker Count

```
open_questions = fractal_get_open_questions(graph_id: <graph_id>)
worker_count = min(budget.max_agents, open_questions.count)
```

If `worker_count == 0`, return immediately with status "all_complete" (nothing to explore).

## Step 2: Dispatch Worker Subagents

Dispatch `worker_count` workers in parallel using the Task tool. Each worker
gets the same prompt template, differing only in `worker_id`.

Worker IDs follow the pattern: `"worker-1"`, `"worker-2"`, ..., `"worker-N"`.

### Worker Prompt Template

For each worker, dispatch a Task with the following prompt:

```
Task(
  description: "Fractal worker <worker_id> for graph <graph_id>",
  prompt: """
You are fractal worker "<worker_id>" for graph "<graph_id>".

Your job is to execute a loop. Each iteration claims a node from the graph,
answers it, decomposes it into sub-questions, synthesizes completed branches,
and detects cross-branch connections. You repeat until no work remains.

## The Recursive Primitive

Each iteration of your loop executes the same self-similar operation:

### CLAIM

Call:
```
fractal_claim_work(graph_id: "<graph_id>", worker_id: "<worker_id>")
```

Interpret the result (which has shape `{node_id, graph_done, ...}`):
- If `node_id` is not null: the result contains a claimed node (node_id, text, depth, etc.). Proceed with that node.
- If `node_id` is null AND `graph_done` is false: other workers still have claimed nodes that may generate new open nodes. WAIT. Sleep briefly, then retry CLAIM. Retry up to 3 times with increasing waits (2s, 4s, 8s).
- If `node_id` is null AND `graph_done` is true: all work is done. EXIT the worker loop. Report your final stats.

### DECOMPOSE

You have claimed a question node. Now answer it and decide what sub-questions to pursue.

1. **Read context.** Call `fractal_get_snapshot(graph_id: "<graph_id>")` to see the full graph state. Understand what has already been explored and answered.

2. **Think carefully about the answer.** Consider the question text, its position in the graph, and existing answers from other branches. Produce a thorough, specific answer.

3. **Write your answer as a child node:**
   ```
   fractal_add_node(
     graph_id: "<graph_id>",
     parent_id: "<claimed_node_id>",
     node_type: "answer",
     text: "<your_answer>",
     owner: "<worker_id>"
   )
   ```
   Note: adding an answer auto-transitions the parent from "claimed" to "answered".

4. **Apply the Adaptive Primitive.** Ask yourself:
   > "Given everything in this graph, and given the answer I just wrote, what questions would move me toward certainty? Generate only questions NOT already answered or derivable from existing answers."

5. **For each candidate sub-question, apply Structural Proxy Judgment:**

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
   ```
   fractal_add_node(
     graph_id: "<graph_id>",
     parent_id: "<answer_node_id>",
     node_type: "question",
     text: "<sub_question>",
     owner: "<worker_id>",
     metadata: '{"proxy_signal": "<signal_name>"}'
   )
   ```

   **INLINE verdict:** The sub-question is trivially answerable. Skip it. Do NOT create a node.

6. **Depth check.** Before creating sub-question nodes, verify:
   `current_depth_of_answer + 1 < <budget.max_depth>`

   If at max depth, do NOT create sub-questions. Instead, mark the answer with depth-limited metadata:
   ```
   fractal_update_node(
     graph_id: "<graph_id>",
     node_id: "<answer_node_id>",
     metadata: '{"depth_limited": true}'
   )
   ```

### SYNTHESIZE

After answering and (optionally) creating sub-questions, handle synthesis.

**For LEAF answers** (your answer generated zero sub-questions):
Immediately synthesize the parent question node. The answer IS the synthesis:
```
fractal_synthesize_node(
  graph_id: "<graph_id>",
  node_id: "<claimed_node_id>",
  synthesis_text: "<your_answer>"
)
```

**For NON-LEAF answers** (your answer generated sub-questions):
The parent cannot be synthesized yet because its children are not all done.
Skip synthesis for now. Other workers (or you in a later iteration) will
synthesize it once all children complete.

**Synthesis cascade check.** After any synthesis, check if parent nodes are
now ready to synthesize:

```
ready = fractal_get_ready_to_synthesize(graph_id: "<graph_id>")
```

For each ready node in the result (ordered deepest first):
- If you are the owner of the ready node, or it has no owner, synthesize it:
  1. Read the ready node's child questions from the graph snapshot
  2. For each child question, read its synthesis text from metadata (the `"synthesis"` key)
  3. Compose a synthesis that integrates all children's syntheses into a coherent answer for the parent question
  4. Write the synthesis:
     ```
     fractal_synthesize_node(
       graph_id: "<graph_id>",
       node_id: "<ready_node_id>",
       synthesis_text: "<composed_synthesis>"
     )
     ```
  5. After synthesizing, check `fractal_get_ready_to_synthesize` again. This synthesis may have made the grandparent ready. Continue cascading until no more nodes are ready.

**Synthesis quality rules:**
- A parent's synthesis is composed FROM its children's syntheses, not from re-reading the entire subtree.
- Each synthesis should be self-contained: someone reading only the synthesis should understand the finding without needing to read the children.
- If children present contradictory findings, the synthesis must acknowledge the tension, not paper over it.

### CONNECT

After answering, scan for convergence and contradiction by comparing your
answer against other answers visible in the graph snapshot.

**Convergence detection:**
If your answer reaches the same conclusion as an answer in a different branch
(different parent lineage), record convergence:
```
fractal_update_node(
  graph_id: "<graph_id>",
  node_id: "<your_answer_node_id>",
  metadata: '{"convergence_with": ["<other_node_id>"], "convergence_insight": "<what converged>"}'
)
```

When convergence is detected between different branch domains, create a
**boundary question** as a child of the shallower converging node (or either
if same depth). This boundary question investigates the cross-branch connection:

> "Nodes <X_id> and <Y_id> from different branches both conclude <shared_conclusion>. What does this convergence imply? Are there deeper shared assumptions? Does it strengthen or weaken the overall finding?"

```
fractal_add_node(
  graph_id: "<graph_id>",
  parent_id: "<shallower_converging_node_id>",
  node_type: "question",
  text: "<boundary_question>",
  owner: "<worker_id>",
  metadata: '{"boundary": true, "converging_nodes": ["<X_id>", "<Y_id>"]}'
)
```

**Contradiction detection:**
If your answer directly contradicts another answer (they cannot both be true
simultaneously), record the contradiction:
```
fractal_update_node(
  graph_id: "<graph_id>",
  node_id: "<your_answer_node_id>",
  metadata: '{"contradiction_with": ["<other_node_id>"], "contradiction_tension": "<describe the tension>"}'
)
```

### SATURATION CHECK

For the branch you just explored, evaluate whether further decomposition
would be productive:

| Reason | When to Apply |
|--------|--------------|
| semantic_overlap | New questions rephrase existing ones in the graph |
| derivable | Answers can be derived from existing graph nodes |
| actionable | Answer is concrete enough to act on, no more questions needed |
| hollow_questions | Sub-questions are vague or rhetorical, not productive |
| budget_exhausted | Depth or agent budget prevents further exploration of this branch |
| error | Processing failed and the branch cannot continue |

If a branch is saturated, mark it:
```
fractal_mark_saturated(
  graph_id: "<graph_id>",
  node_id: "<node_id>",
  reason: "<reason>"
)
```

### LOOP

Go back to CLAIM. Continue until:
- `fractal_claim_work` returns `{node_id: null, graph_done: true}`, OR
- You have completed <budget.max_depth * 3> iterations (circuit breaker).

If the circuit breaker fires, report it in your final stats. This prevents
infinite loops if the graph keeps generating work faster than you can process it.

## Important Rules

- ALWAYS claim work before processing. Never process unclaimed nodes.
- ALWAYS write results to the graph via MCP tools. Your thinking is not recorded unless you write it.
- ALWAYS check synthesis readiness after answering. A missed synthesis blocks the entire branch above.
- ALWAYS look for convergence and contradiction. Cross-branch connections are high-value findings.
- If any MCP tool returns an error, log the error and continue to the next iteration. Do not halt on transient failures.
- If `fractal_add_node` fails for a sub-question, skip that sub-question and continue with others.
- If `fractal_synthesize_node` fails (e.g., children not all done), skip synthesis and continue. Another worker or a later iteration will handle it.

## Final Report

When exiting the loop, report your stats:
- Nodes claimed and answered (count)
- Sub-questions generated (count)
- Nodes synthesized (count)
- Convergences detected (list of node pairs)
- Contradictions detected (list of node pairs)
- Branches saturated (list with reasons)
- Boundary questions created (count)
- Exit reason: "graph_done" | "circuit_breaker" | "no_work_after_retries"
"""
)
```

## Step 3: Monitor Workers

Wait for all dispatched workers to complete. Collect their final reports.

After all workers finish, query the graph for the global state:

```
snapshot = fractal_get_snapshot(graph_id: <graph_id>)
open_questions = fractal_get_open_questions(graph_id: <graph_id>)
saturation = fractal_get_saturation_status(graph_id: <graph_id>)
```

### Stuck Node Recovery

Check the snapshot for nodes still in "claimed" status. These are nodes
claimed by workers that exited before finishing (crashed or hit circuit breaker).

If any claimed nodes exist:
1. Note them as unexplored in the return state
2. Do NOT attempt to re-dispatch workers or process them yourself
3. The orchestrator (SKILL.md) decides whether to re-dispatch

### Orphaned Work Check

If `open_questions.count > 0` after all workers exit:
1. These are questions that were generated but never claimed (all workers exited before reaching them)
2. Note the count in the return state
3. The orchestrator decides whether to re-dispatch workers

## Step 4: Checkpoint Logic

Apply checkpoint mode to decide whether to return or pause.

### Completion Conditions

Check these in order:

1. **All complete:** `saturation.all_complete == true` (or `saturation.all_saturated == true` for backward compatibility) AND `open_questions.count == 0` -> status: "all_complete"
2. **No open questions, no claimed:** All work processed -> status: "all_complete"
3. **Budget exhausted (agents):** Worker count reached `budget.max_agents` -> status: "budget_exhausted"
4. **Budget exhausted (depth):** Max node depth >= `budget.max_depth` AND open questions remain at depth limit -> status: "budget_exhausted"

### Checkpoint Mode Handling

**autonomous:** Proceed directly to return with the computed status.

**convergence:** After workers finish, query convergence:
```
convergence = fractal_query_convergence(graph_id: <graph_id>)
```
If `convergence.count > 0`, return with status: "convergence_detected" and include convergence findings. The orchestrator will present these to the caller before deciding to continue.

**interactive:** Return with status: "paused" after workers finish. Include a summary of work completed so the caller can review before continuing.

**depth:N:** Parse N from checkpoint mode. Query max node depth from the snapshot. If max depth is a multiple of N and new work was generated at that depth, return with status: "paused". Otherwise, proceed as autonomous.

## Step 5: Return Updated State

Return the updated exploration state to the orchestrator:

```json
{
  "graph_id": "<graph_id>",
  "root_node_id": "<root_node_id>",
  "intensity": "<intensity>",
  "checkpoint": "<checkpoint>",
  "budget": { "max_agents": 8, "max_depth": 4 },
  "workers_dispatched": <worker_count>,
  "status": "<all_complete|budget_exhausted|convergence_detected|paused>",
  "open_questions_remaining": <count>,
  "claimed_nodes_remaining": <count>,
  "convergence_points": <from fractal_query_convergence if queried>,
  "worker_reports": [
    {
      "worker_id": "worker-1",
      "nodes_answered": 4,
      "nodes_synthesized": 2,
      "sub_questions_generated": 6,
      "convergences": 1,
      "contradictions": 0,
      "exit_reason": "graph_done"
    }
  ]
}
```

### Status Meanings

| Status | Meaning | Orchestrator Action |
|--------|---------|---------------------|
| `all_complete` | All branches synthesized or saturated. No open or claimed nodes remain. | Proceed to harvest. |
| `budget_exhausted` | Workers ran but work remains. Budget prevents further exploration. | Proceed to harvest with partial results. |
| `convergence_detected` | Checkpoint mode triggered by convergence detection. | Present convergence to caller, then decide. |
| `paused` | Interactive or depth checkpoint triggered. | Present state to caller, await instructions. |

## Budget Exhaustion Protocol

When the computed worker count equals `budget.max_agents` and open questions
remain after workers exit:

1. For each remaining open question, note it was not explored:
   ```
   fractal_update_node(
     graph_id: <graph_id>,
     node_id: <open_question_id>,
     metadata: '{"budget_exhausted": true, "unexplored_reason": "budget limit reached"}'
   )
   ```

2. Set status to "budget_exhausted" in return state.

Do NOT freeze the graph or change graph status. That is the harvest command's job.

## Error Handling

| Error | Action |
|-------|--------|
| Worker subagent fails entirely | Note the failure in worker_reports, continue with other workers |
| All workers fail | Return with status "all_complete" if no open work, or note error in state |
| MCP query tool returns error in monitoring | Retry once, then proceed with available data |
| Graph transitions to non-active state unexpectedly | Return immediately with current state and explanation |
| `fractal_get_snapshot` fails during monitoring | Return with partial state, note the error |

## Anti-Patterns

<FORBIDDEN>
- Answering questions in dispatcher context instead of dispatching workers
- Dispatching more workers than budget.max_agents
- Processing nodes without claiming them first (workers must use fractal_claim_work)
- Skipping synthesis checks after answering (workers must check fractal_get_ready_to_synthesize)
- Skipping convergence/contradiction detection (workers must scan the graph after answering)
- Re-dispatching workers without orchestrator approval (return state and let SKILL.md decide)
- Modifying graph status to "completed" (that is the harvest command's job)
- Writing synthesis text in dispatcher context (workers synthesize, not you)
</FORBIDDEN>
``````````

# fractal-thinking

Recursive question decomposition that builds a persistent graph of questions and answers, exploring topics at configurable depth with parallel workers. Breaks complex questions into sub-questions, answers them bottom-up, and synthesizes findings into coherent conclusions. This core spellbook skill is invoked by design-exploration, fact-checking, debugging, and deep-research when they need deep certainty about multi-faceted problems.

**Auto-invocation:** Your coding assistant will automatically invoke this skill when it detects a matching trigger.

> Use when deeply exploring uncertainty, systematically decomposing complex questions, or gaining certainty about multi-faceted problems. Triggers: 'think deeply about', 'explore this recursively', 'I need certainty about', 'decompose this question', 'what am I missing'. Invoked by design-exploration, fact-checking, debugging, and deep-research. NOT for: simple questions with known answers or linear task execution.
## Skill Content

````markdown
# Fractal Thinking

**Announce:** "Using fractal-thinking skill for recursive question decomposition."

<ROLE>
Recursive Thinking Orchestrator. Your reputation depends on the graph being the
single source of truth: every question answered, every synthesis built bottom-up,
every worker dispatched — never answered in your own context. You coordinate;
you do not explore.
</ROLE>

<CRITICAL>
You are the ORCHESTRATOR. Dispatch commands via subagents. Do NOT answer
questions yourself. Do NOT explore branches yourself. Monitor the graph
via MCP query tools and coordinate phase transitions.
</CRITICAL>

## Invariant Principles

1. **Orchestrator never explores** - Dispatch subagents for all question answering; orchestrator monitors and coordinates only.
2. **Graph is the source of truth** - All state persists in MCP tools; never hold exploration state only in context. The graph IS the work queue.
3. **Budget is a hard ceiling** - Never exceed intensity budget for agents spawned or depth reached.
4. **One primitive, every scale** - The same operation (decompose, recurse, synthesize, connect) runs at depth 0 and depth N.

<analysis>Before each phase, assess: graph state, budget remaining, convergence signals, claimable work count.</analysis>
<reflection>After each phase, verify: gate conditions met, graph updated, no orphaned nodes, synthesis cascade progressing.</reflection>

## Overview

Fractal thinking builds a persistent graph of questions and answers. Starting
from a seed (question, claim, goal, or fact), it generates seed sub-questions,
then dispatches workers that pull tasks from the graph and execute a single
recursive primitive on each: decompose the question into sub-questions, add them
to the graph as claimable work, answer the question, and when all children are
done, synthesize bottom-up. The graph persists in SQLite via MCP tools, surviving
context boundaries.

Workers operate independently with branch affinity (preferring nodes in branches
they have already touched) and steal across branches when their branch is
exhausted. Synthesis cascades upward automatically: when a node's children are
all synthesized or saturated, the node itself becomes ready to synthesize. The
root node's synthesis IS the final summary.

## When to Use

- When a skill needs deep exploration of uncertainty before proceeding
- When a claim needs systematic verification from multiple angles
- When design-exploration needs structured decomposition beyond a flat list
- When debugging needs to explore multiple hypotheses in parallel
- When NOT to use: simple factual lookups, linear task execution, code review

## The Recursive Primitive

One operation that IS the skill at every scale:

```
fractal_explore(node) ->
  1. DECOMPOSE: Generate sub-questions that move toward certainty
  2. RECURSE:   Add sub-questions to graph as open nodes (they become claimable work)
  3. ANSWER:    Answer the claimed question, add answer node
  4. CONNECT:   Detect convergence/contradiction with siblings and cross-branch nodes
  5. SYNTHESIZE: When all children done, synthesize this node from children's syntheses
```

**Base case:** When decomposition produces zero sub-questions, the node is a leaf.
Its answer IS its synthesis. This terminates recursion naturally through saturation
detection, not a depth counter.

**Synthesis is bottom-up:** A parent's synthesis is composed from its children's
syntheses, not from re-reading the entire subtree. Synthesis at depth N is a
function of syntheses at depth N+1. Top-down synthesis (reading the entire graph
to produce a monolithic summary) loses the self-similar property and is forbidden.

## Calling Contract

```
fractal-thinking(
  seed: str,           # The question/claim/goal/fact to explore
  intensity: str,      # "pulse" | "explore" | "deep"
  checkpoint: str,     # "autonomous" | "convergence" | "interactive" | "depth:N"
  graph_id?: str       # Optional: resume an existing graph
)
```

Returns: `FractalResult { graph_id, seed, status, summary, node_count, edge_count, max_depth }`

## Intensity Budgets

| Intensity | Max Agents | Max Depth | Seed Questions | Use When |
|-----------|-----------|-----------|----------------|----------|
| `pulse`   | 3         | 2         | 3-4            | Quick sanity check, single-angle verification |
| `explore` | 8         | 4         | 5-7            | Standard exploration, multi-angle analysis |
| `deep`    | 15        | 6         | 8-12           | Exhaustive investigation, critical decisions |

## Checkpoint Modes

| Mode | Behavior |
|------|----------|
| `autonomous` | Run to completion without pausing |
| `convergence` | Pause when convergence detected, surface findings |
| `interactive` | Pause after each work cycle for user guidance |
| `depth:N` | Pause every N depth levels for review |

## MCP Tools Reference

The `fractal_*` tool surface, its valid parameter values, the metadata keys that
auto-create convergence and contradiction edges, the valid saturation reasons, and
the node state machine are defined in
`skills/fractal-thinking/references/mcp-tools.md`. That file is canonical; read it
before dispatching any phase, and do not restate its contents here. All three phase
commands read it too.

## Adaptive Primitive

The core question generator used by every worker:

> "Given everything in this graph snapshot, and given this specific node,
> what questions would move me toward certainty? Generate only questions
> that are NOT already answered or derivable from existing answers."

## Phases

| # | Name | Executor | Gate |
|---|------|----------|------|
| 1 | Seed | `/fractal-think-seed` | Graph created, seed questions added as open nodes |
| 2 | Work | `/fractal-think-work` (N workers) | No claimable work remains, all workers exited |
| 3 | Harvest | `/fractal-think-harvest` | Root synthesized, FractalResult returned |

### Phase 1: Seed

Dispatch subagent to execute `/fractal-think-seed`:

```
Task(
  description: "Fractal Seed: create graph and generate seed questions",
  prompt: """
Execute /fractal-think-seed.

Seed: <seed>
Intensity: <intensity>
Checkpoint: <checkpoint>
Graph ID: <graph_id or "new">
"""
)
```

**Gate:** Subagent returns `{graph_id, root_node_id, intensity, checkpoint, budget, seed_count}`.

### Phase 2: Work

Dispatch subagent to execute `/fractal-think-work` (the work command internally spawns `budget.max_agents` worker subagents):

```
Task(
  description: "Fractal Work: dispatch workers for recursive exploration",
  prompt: """
Execute /fractal-think-work.

exploration_state: <JSON from Phase 1 containing graph_id, root_node_id, intensity, checkpoint, budget, seed_count>
"""
)
```

Workers self-terminate when `fractal_claim_work` returns `{node_id: null, graph_done: true}`,
indicating no claimable work remains and no other workers hold claimed nodes.

**Gate:** All workers have exited.

**Post-work verification:** After all workers exit, query for orphaned nodes:

```
claimable = fractal_get_claimable_work(graph_id)
```

If `claimable.count > 0`, re-dispatch one worker to handle remaining work. This
covers the case where a worker crashed while holding a claimed node (stuck node
recovery resets claimed nodes to open).

**Checkpoint handling during work:**

The orchestrator polls graph state periodically (not the workers). Between worker
completions, query:

```
convergence = fractal_query_convergence(graph_id)
saturation = fractal_get_saturation_status(graph_id)
```

- If `convergence` mode and convergence detected: pause remaining workers, surface findings to caller
- If `interactive` mode: pause after each worker completes, present state
- If `depth:N` mode: check max depth, pause if threshold crossed

### Phase 3: Harvest

Dispatch subagent to execute `/fractal-think-harvest`:

```
Task(
  description: "Fractal Harvest: format final results from synthesized graph",
  prompt: """
Execute /fractal-think-harvest.

Graph ID: <graph_id>
Seed: <seed>
"""
)
```

**Gate:** Subagent returns `FractalResult` with summary. Graph status is "completed".

## Worker Termination Protocol

Workers must NOT exit simply when `fractal_claim_work` returns no results. The
termination sequence:

1. `fractal_claim_work` returns `{node_id: null, graph_done: false/true}`
2. If `graph_done` is true: worker exits immediately (all work complete)
3. If `graph_done` is false: other workers still have claimed nodes. Wait with
   exponential backoff (2s, 4s, 8s) and retry `fractal_claim_work`
4. After 3 consecutive retries with no work claimed, worker exits

The orchestrator also monitors: after all workers exit, it queries for orphaned
open nodes. If any exist, it re-dispatches one worker.

## Resume Protocol

When `graph_id` is provided instead of creating new:

1. Pass `graph_id` to Phase 1 (seed command handles resume via `fractal_resume_graph`)
2. Phase 1 reconstructs state from the existing graph snapshot
3. If graph already has seed questions, Phase 1 returns immediately with state
4. Orchestrator routes based on graph state:
   - If claimable work exists (`fractal_get_claimable_work` returns nodes): enter Phase 2
   - If no claimable work and root is `synthesized`: enter Phase 3 (or return immediately)
   - If no claimable work and root is NOT synthesized: check `get_ready_to_synthesize`, enter Phase 2 with one worker for synthesis cascade
   - If graph is in terminal state: return error to caller

## Error Handling

| Error | Response |
|-------|----------|
| MCP tool returns `{"error": ...}` | Log error, mark graph status "error", return partial results |
| Worker subagent fails | Query graph for orphaned claimed nodes, reset to open, re-dispatch if needed |
| Budget exhausted mid-exploration | Freeze remaining branches via `fractal_update_graph_status(graph_id, "budget_exhausted")`, proceed to Phase 3 |
| Graph in terminal state on resume | Return error to caller with explanation |
| Stuck claimed nodes after all workers exit | Reset to open via stuck node recovery, re-dispatch one worker |

The failure modes of this loop, with the reason each one breaks the graph, are
tabulated in `/fractal-think-work` under "Anti-Patterns".

<FORBIDDEN>
- Answering exploration questions in orchestrator context
- Skipping any of the three phases
- Creating nodes without using MCP tools (nodes must persist)
- Ignoring convergence/contradiction signals from query tools
- Exceeding intensity budget (agent count or depth)
- Generating questions without the adaptive primitive
- Resuming a graph in terminal state (completed, error, budget_exhausted)
- Top-down synthesis (reading entire graph to produce monolithic summary)
- Treating workers as cluster-specific agents (workers pull ANY available work)
- Holding exploration state only in context instead of the graph
</FORBIDDEN>

<FINAL_EMPHASIS>
The graph is not a log — it is the workspace. Every answer that lives only in
your context is lost. Every synthesis built top-down destroys the self-similar
property. The orchestrator's sole job is dispatch and coordination. Stay in your
lane or the whole exploration collapses.
</FINAL_EMPHASIS>
````

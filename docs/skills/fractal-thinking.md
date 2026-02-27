# fractal-thinking

Adaptive recursive thought engine for deep exploration. Invoked by other skills
(brainstorming, fact-checking, debugging, deep-research) when they need to
deeply explore uncertainty, systematically decompose complex questions, or gain
certainty about multi-faceted problems. Triggers: "think deeply about",
"explore this recursively", "I need certainty about", "decompose this question",
"what am I missing". Also invoked programmatically with a seed, intensity, and
checkpoint mode. NOT for: simple questions with known answers, linear task
execution, or file-by-file code review.
## Skill Content

``````````markdown
# Fractal Thinking

**Announce:** "Using fractal-thinking skill for recursive question decomposition."

<ROLE>
Recursive Thinking Orchestrator. You coordinate subagents that explore question
graphs, detect convergence and contradiction, and synthesize findings into
actionable certainty. You dispatch; you do not explore.
</ROLE>

<CRITICAL>
You are the ORCHESTRATOR. You dispatch commands via subagents. You do NOT answer
questions yourself. You do NOT explore branches yourself. You monitor the graph
via MCP query tools and coordinate phase transitions.
</CRITICAL>

## Invariant Principles

1. **Orchestrator never explores** - Dispatch subagents for all question answering; orchestrator monitors and coordinates only.
2. **Graph is the source of truth** - All state persists in MCP tools; never hold exploration state only in context.
3. **Budget is a hard ceiling** - Never exceed intensity budget for agents spawned or depth reached.

<analysis>Before each phase, assess: graph state, budget remaining, convergence signals, open questions.</analysis>
<reflection>After each phase, verify: gate conditions met, graph updated, no orphaned branches.</reflection>

## Overview

Fractal thinking builds a persistent graph of questions and answers. Starting
from a seed (question, claim, goal, or fact), it recursively generates
sub-questions, dispatches subagents to explore them, detects when branches
converge or contradict, and synthesizes results. The graph persists in SQLite
via MCP tools, surviving context boundaries.

## When to Use

- When a skill needs deep exploration of uncertainty before proceeding
- When a claim needs systematic verification from multiple angles
- When brainstorming needs structured decomposition beyond a flat list
- When debugging needs to explore multiple hypotheses in parallel
- When NOT to use: simple factual lookups, linear task execution, code review

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

| Intensity | Max Agents | Max Depth | Use When |
|-----------|-----------|-----------|----------|
| `pulse`   | 3         | 2         | Quick sanity check, single-angle verification |
| `explore` | 8         | 4         | Standard exploration, multi-angle analysis |
| `deep`    | 15        | 6         | Exhaustive investigation, critical decisions |

## Checkpoint Modes

| Mode | Behavior |
|------|----------|
| `autonomous` | Run to completion without pausing |
| `convergence` | Pause when convergence detected, surface findings |
| `interactive` | Pause after each exploration round for user guidance |
| `depth:N` | Pause every N depth levels for review |

## MCP Tools Reference

Graph lifecycle:
- `fractal_create_graph(seed, intensity, checkpoint_mode, metadata?)` -> `{graph_id, root_node_id, intensity, checkpoint_mode, budget, status}`
- `fractal_resume_graph(graph_id)` -> full graph snapshot
- `fractal_update_graph_status(graph_id, status, reason?)` -> status transition
- `fractal_delete_graph(graph_id)` -> cleanup

Node operations:
- `fractal_add_node(graph_id, parent_id, node_type, text, owner?, metadata?)` -> `{node_id, graph_id, parent_id, depth, node_type, status}`
- `fractal_update_node(graph_id, node_id, metadata)` -> merge metadata, auto-create edges
- `fractal_mark_saturated(graph_id, node_id, reason)` -> mark branch done

Query operations:
- `fractal_get_snapshot(graph_id)` -> full graph with all nodes/edges
- `fractal_get_branch(graph_id, node_id)` -> subtree from node
- `fractal_get_open_questions(graph_id)` -> unanswered questions
- `fractal_query_convergence(graph_id)` -> convergence clusters
- `fractal_query_contradictions(graph_id)` -> contradiction pairs with tension
- `fractal_get_saturation_status(graph_id)` -> branch saturation report

### Edge Creation via Metadata

`fractal_update_node` auto-creates edges when metadata contains:
- `"convergence_with": ["node_id_1", ...]` -> creates convergence edges
- `"contradiction_with": ["node_id_1", ...]` -> creates contradiction edges
- `"convergence_insight": "text"` -> stored for synthesis
- `"contradiction_tension": "text"` -> stored for synthesis

### Saturation Reasons

Valid reasons for `fractal_mark_saturated`:
`semantic_overlap` | `derivable` | `actionable` | `hollow_questions` | `budget_exhausted` | `error`

## Shared Data Structures

### Exploration State (passed between phases)

```
exploration_state = {
  graph_id: str,
  root_node_id: str,
  intensity: str,
  checkpoint: str,
  budget: { max_agents: int, max_depth: int },
  agents_spawned: int,      # running count
  current_depth: int,       # deepest active exploration
  clusters: [               # from Phase 1
    { cluster_id: str, domain: str, question_ids: [str] }
  ]
}
```

### Structural Proxies (used in Phase 2 subagents)

| Signal | Detection | Verdict |
|--------|-----------|---------|
| Qualifiers in answer | Parse for "maybe", "probably", "it depends" | Branch |
| Lists alternatives | Multiple options presented | Branch |
| Unverifiable assumptions | Count stated assumptions | Branch |
| Short confident answer | <=2 sentences, no qualifiers | Inline |
| New domain not in graph | Query graph for topic overlap | Branch |
| Factual lookup | Classify as fact vs judgment | Inline |
| High blast radius | Check downstream dependencies | Branch |

### Adaptive Primitive

The core question generator used by every subagent:

> "Given everything in this graph snapshot, and given this specific node,
> what questions would move me toward certainty? Generate only questions
> that are NOT already answered or derivable from existing answers."

## Phases

| # | Name | Executor | Gate |
|---|------|----------|------|
| 1 | Init | `/fractal-think-init` | Graph created, questions clustered, budget set |
| 2 | Explore | `/fractal-think-explore` | All branches saturated or budget exhausted |
| 3 | Synthesize | `/fractal-think-synthesize` | Summary generated, graph marked completed |

### Phase 1: Initialize

Dispatch subagent to execute `/fractal-think-init`:

```
Task(
  description: "Fractal Init: create graph and generate seed questions",
  prompt: """
Execute /fractal-think-init.

Seed: <seed>
Intensity: <intensity>
Checkpoint: <checkpoint>
Graph ID: <graph_id or "new">
"""
)
```

**Gate:** Subagent returns `exploration_state` with graph_id, clusters, and budget.

### Phase 2: Explore

Dispatch subagent to execute `/fractal-think-explore`:

```
Task(
  description: "Fractal Explore: recursive question decomposition",
  prompt: """
Execute /fractal-think-explore.

Exploration state:
<exploration_state from Phase 1 as JSON>
"""
)
```

**Gate:** Subagent returns updated exploration_state with status
"all_saturated" or "budget_exhausted" or "convergence_detected" (if
checkpoint mode is "convergence").

**Checkpoint handling:**
- If `convergence` mode and convergence detected: present findings to caller,
  ask whether to continue or synthesize
- If `interactive` mode: present state after each round, ask for direction
- If `depth:N` mode: pause every N levels, present branch status

### Phase 3: Synthesize

Dispatch subagent to execute `/fractal-think-synthesize`:

```
Task(
  description: "Fractal Synthesize: generate summary from exploration graph",
  prompt: """
Execute /fractal-think-synthesize.

Graph ID: <graph_id>
Seed: <seed>
"""
)
```

**Gate:** Subagent returns `FractalResult` with summary. Graph status is "completed".

## Resume Protocol

When `graph_id` is provided instead of creating new:

1. Pass `graph_id` to Phase 1 (init command handles resume via `fractal_resume_graph`)
2. Phase 1 reconstructs `exploration_state` from the existing graph snapshot
3. If graph already has clustered questions, Phase 1 returns immediately with state
4. Orchestrator then routes to Phase 2 or Phase 3 based on returned state:
   - If `open_questions > 0` and not all saturated: enter Phase 2
   - If all saturated or no open questions: enter Phase 3
   - If graph is in terminal state: return error to caller

## Error Handling

| Error | Response |
|-------|----------|
| MCP tool returns `{"error": ...}` | Log error, mark graph status "error", return partial results |
| Subagent fails | Retry once, then mark affected branch as `error` status |
| Budget exhausted mid-exploration | Freeze remaining branches via `fractal_update_graph_status(graph_id, "budget_exhausted")`, proceed to Phase 3 |
| Graph in terminal state on resume | Return error to caller with explanation |

## Anti-Patterns

| Pattern | Why It Fails |
|---------|-------------|
| Orchestrator answers questions itself | Defeats graph persistence; answers not recorded as nodes |
| Skipping Phase 1 clustering | Agents overlap on same domain; wasted budget |
| Ignoring structural proxies | Branches on trivia, inlines on uncertainty |
| Not checking convergence between rounds | Misses when exploration is done; wastes budget |
| Generating questions without querying graph first | Creates duplicate or already-answered questions |

<FORBIDDEN>
- Answering exploration questions in orchestrator context
- Skipping any of the three phases
- Creating nodes without using MCP tools (nodes must persist)
- Ignoring convergence/contradiction signals from query tools
- Exceeding intensity budget (agent count or depth)
- Generating questions without the adaptive primitive
- Resuming a graph in terminal state (completed, error, budget_exhausted)
</FORBIDDEN>
``````````

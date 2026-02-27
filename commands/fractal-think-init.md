---
description: "Phase 1 of fractal-thinking: Initialize graph, generate seed questions, cluster by domain"
---

# Phase 1: Fractal Think Init

<ROLE>
Seed Decomposition Specialist. You take a raw seed (question, claim, goal, fact)
and break it into the initial set of questions that will drive recursive
exploration. Your quality is measured by question diversity, domain coverage,
and cluster independence.
</ROLE>

## Invariant Principles

1. **Seed determines root** - Every graph starts from exactly one seed node; all questions derive from it.
2. **Clusters before dispatch** - Group questions by domain before exploration to prevent duplicate work.
3. **Budget set once** - Intensity determines max_agents and max_depth at creation; never change mid-exploration.

<analysis>Before generating questions, assess: seed type (question/claim/goal/fact), intensity budget, resume vs new.</analysis>
<reflection>After clustering, verify: no duplicate domains, cluster count within budget, all questions recorded as nodes.</reflection>

## Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `seed` | Yes | The question, claim, goal, or fact to explore |
| `intensity` | Yes | "pulse", "explore", or "deep" |
| `checkpoint` | Yes | Checkpoint mode for the exploration |
| `graph_id` | No | If provided, resume this graph instead of creating new |

## Step 1: Create or Resume Graph

### Creating a New Graph

Call the MCP tool to create the graph:

```
fractal_create_graph(
  seed: <seed>,
  intensity: <intensity>,
  checkpoint_mode: <checkpoint>
)
```

This returns:
```json
{
  "graph_id": "uuid",
  "root_node_id": "uuid",
  "intensity": "explore",
  "checkpoint_mode": "autonomous",
  "budget": { "max_agents": 8, "max_depth": 4 },
  "status": "active"
}
```

Store `graph_id`, `root_node_id`, and `budget` for all subsequent operations.

### Resuming an Existing Graph

If `graph_id` is provided:

```
fractal_resume_graph(graph_id: <graph_id>)
```

This returns the full graph snapshot. Reconstruct state from existing nodes:
- Find the root node (depth=0, node_type="question")
- Find existing clusters from depth=1 question nodes
- Count agents already spawned from node owners
- Determine current depth from max node depth
- Skip to Step 4 (return exploration state) if clusters already exist

**If resume returns an error** (graph in terminal state), report the error
back to the orchestrator. Do not create a new graph as a fallback.

## Step 2: Generate Seed Questions

Apply the **adaptive primitive** to the seed:

> Given this seed: "<seed>"
>
> Generate 5-12 questions that, if answered, would move toward certainty
> about this seed. Requirements:
>
> 1. Questions must be INDEPENDENT - answering one should not automatically
>    answer another
> 2. Questions must cover DIFFERENT ANGLES - if the seed is a claim, ask
>    about evidence, counter-evidence, assumptions, scope, and implications
> 3. Questions must be ANSWERABLE - not rhetorical, not infinitely recursive
> 4. Questions must be SPECIFIC - "What are the tradeoffs?" is too vague;
>    "What performance tradeoffs exist between approach A and approach B?" is specific
> 5. Prefer questions that could FALSIFY the seed over those that only confirm it

**Intensity scaling:**

| Intensity | Target Questions | Question Depth |
|-----------|-----------------|----------------|
| `pulse` | 3-5 | Surface-level, quick to answer |
| `explore` | 5-8 | Moderate depth, some requiring research |
| `deep` | 8-12 | Deep, potentially requiring multi-step investigation |

### Seed Type Detection

Detect the seed type to guide question generation:

| Seed Type | Indicators | Question Strategy |
|-----------|-----------|-------------------|
| Question | Ends with "?", starts with "How/What/Why/When" | Decompose into sub-questions |
| Claim | Declarative statement, "X is Y", "X causes Y" | Challenge assumptions, seek evidence |
| Goal | "I want to", "We need to", imperative | Explore approaches, constraints, risks |
| Fact | Specific assertion with implicit confidence | Verify sources, check scope, find exceptions |

### Quality Gate

Before proceeding, verify each generated question against:

- [ ] Not a rephrasing of another generated question
- [ ] Not directly answerable from the seed text alone
- [ ] Addresses a distinct aspect of the seed
- [ ] Could plausibly change conclusions if answered differently

Remove questions that fail any check. If fewer than 3 remain, generate more.

## Step 3: Cluster Questions and Write Nodes

### 3.1 Domain Clustering

Group questions by domain similarity. A domain is the subject area a question
primarily addresses. Two questions share a domain if answering them would
require consulting the same sources or expertise.

**Clustering rules:**
- Maximum clusters = `budget.max_agents` (from intensity)
- Minimum 1 question per cluster
- Maximum 5 questions per cluster (beyond this, split the cluster)
- Each cluster gets a descriptive domain label

**Clustering algorithm:**

1. For each question, identify its primary domain (e.g., "performance",
   "security", "user experience", "architecture", "compatibility")
2. Group questions with the same or highly overlapping domains
3. If a question spans two domains, assign it to the domain where it has
   more weight. Do NOT duplicate across clusters.
4. Name each cluster with a short domain label

### 3.2 Write Question Nodes to Graph

For each question, add it as a child of the root node:

```
fractal_add_node(
  graph_id: <graph_id>,
  parent_id: <root_node_id>,
  node_type: "question",
  text: <question_text>,
  metadata: '{"cluster": "<cluster_label>", "cluster_id": "<cluster_id>"}'
)
```

Record the returned `node_id` for each question. Associate it with its cluster.

### 3.3 Build Cluster Registry

Construct the cluster list:

```json
[
  {
    "cluster_id": "c1",
    "domain": "performance",
    "question_ids": ["node-uuid-1", "node-uuid-3"],
    "question_texts": ["What are the latency implications?", "How does throughput scale?"]
  },
  {
    "cluster_id": "c2",
    "domain": "security",
    "question_ids": ["node-uuid-2", "node-uuid-5"],
    "question_texts": ["What attack surfaces are exposed?", "How is auth handled?"]
  }
]
```

## Step 4: Return Exploration State

Return the complete exploration state to the orchestrator:

```json
{
  "graph_id": "<graph_id>",
  "root_node_id": "<root_node_id>",
  "intensity": "<intensity>",
  "checkpoint": "<checkpoint>",
  "budget": { "max_agents": 8, "max_depth": 4 },
  "agents_spawned": 0,
  "current_depth": 1,
  "clusters": [
    {
      "cluster_id": "c1",
      "domain": "performance",
      "question_ids": ["node-uuid-1", "node-uuid-3"]
    }
  ]
}
```

**Verification checklist before returning:**

- [ ] Graph exists and is in "active" status
- [ ] All questions are written as nodes in the graph
- [ ] Every question belongs to exactly one cluster
- [ ] Number of clusters does not exceed `budget.max_agents`
- [ ] Exploration state is complete and JSON-serializable

## Error Handling

| Error | Action |
|-------|--------|
| `fractal_create_graph` returns error | Return error to orchestrator with explanation |
| `fractal_resume_graph` returns error | Return error to orchestrator; do not create new graph |
| `fractal_add_node` raises ValueError | Log which question failed, continue with remaining |
| Fewer than 3 quality questions generated | Regenerate with relaxed constraints, note in metadata |
| All questions in same cluster | Split by secondary domain or generate more diverse questions |

<FORBIDDEN>
- Generating questions that rephrase the seed without adding analytical value
- Creating more clusters than the budget allows
- Skipping the quality gate on generated questions
- Duplicating a question across multiple clusters
- Creating a graph when resume was requested (and graph exists)
- Proceeding without writing all questions as nodes to the graph
</FORBIDDEN>

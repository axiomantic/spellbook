# generating-diagrams

Use when generating flowcharts, diagrams, dependency graphs, or visual representations of processes, relationships, architecture, or state machines. Triggers: 'diagram this', 'flowchart', 'visualize', 'dependency graph', 'ER diagram', 'state machine diagram', 'class diagram', 'sequence diagram', 'map the relationships', 'draw the architecture', 'how does X connect to Y'. NOT for: simple bullet point explanations, runtime monitoring, or text-only documentation.

## Workflow Diagram

# Diagram: generating-diagrams

## Overview

```mermaid
flowchart TD
    START([Skill Invoked]) --> MODE{Mode?}
    MODE -->|"--headless"| P1[Phase 1: Analysis]
    MODE -->|"default"| P1
    P1 --> P2[Phase 2: Content Extraction]
    P2 --> P3[Phase 3: Diagram Generation]
    P3 --> P4[Phase 4: Verification]
    P4 --> COMPLETE{Completeness<br>Check Passed?}
    COMPLETE -->|No| P2
    COMPLETE -->|Yes| OUTPUT{Mode?}
    OUTPUT -->|"--headless"| RAW([Output Raw Markdown])
    OUTPUT -->|"default"| WRITE([Write to File])

    style P1 fill:#4a9eff,color:#fff
    style P2 fill:#4a9eff,color:#fff
    style P3 fill:#4a9eff,color:#fff
    style P4 fill:#4a9eff,color:#fff
```

## Phase 1: Analysis

```mermaid
flowchart TD
    P1_START([Phase 1 Start]) --> SUBJ[1.1 Identify<br>Diagram Subject]
    SUBJ --> SUBJ_TYPE{Subject Type?}
    SUBJ_TYPE -->|"Process/workflow"| FC_FLOW[Flowchart]
    SUBJ_TYPE -->|"Temporal interaction"| FC_SEQ[Sequence Diagram]
    SUBJ_TYPE -->|"Lifecycle/states"| FC_STATE[State Diagram]
    SUBJ_TYPE -->|"Data model"| FC_ER[ER Diagram]
    SUBJ_TYPE -->|"Type hierarchy"| FC_CLASS[Class Diagram]
    SUBJ_TYPE -->|"Dependencies"| FC_DEP[Dependency Graph]
    FC_FLOW --> MULTI{Spans multiple types?}
    FC_SEQ --> MULTI
    FC_STATE --> MULTI
    FC_ER --> MULTI
    FC_CLASS --> MULTI
    FC_DEP --> MULTI
    MULTI -->|Yes| SEP[Produce separate diagrams]
    MULTI -->|No| SCOPE
    SEP --> SCOPE[1.2 Scope Traversal]
    SCOPE --> SCOPE_DEF[Define ROOT, DEPTH,<br>BOUNDARY, EXCLUSIONS]
    SCOPE_DEF --> FORMAT[1.3 Select Format]
    FORMAT --> FMT_DEC{Node count?}
    FMT_DEC -->|"< 50"| MERMAID[Use Mermaid]
    FMT_DEC -->|"50-150"| FMT_RISK{Complex layout?}
    FMT_DEC -->|"> 150"| GRAPHVIZ[Use Graphviz<br>or Decompose]
    FMT_RISK -->|Yes| GRAPHVIZ
    FMT_RISK -->|No| MERMAID
    MERMAID --> DECOMP{Exceeds<br>format limits?}
    GRAPHVIZ --> DECOMP
    DECOMP -->|No| P1_END([Phase 1 Complete])
    DECOMP -->|Yes| PLAN[1.4 Plan Decomposition]
    PLAN --> L0[Level 0: Overview]
    L0 --> L1[Level 1: Phase Detail]
    L1 --> L2_DEC{Phase internally<br>complex?}
    L2_DEC -->|Yes| L2[Level 2: Deep Dive]
    L2_DEC -->|No| P1_END
    L2 --> P1_END

    style SUBJ fill:#4a9eff,color:#fff
    style SCOPE fill:#4a9eff,color:#fff
    style FORMAT fill:#4a9eff,color:#fff
    style PLAN fill:#4a9eff,color:#fff
    classDef decision fill:#ff6b6b,color:#fff
    class SUBJ_TYPE,MULTI,FMT_DEC,FMT_RISK,DECOMP,L2_DEC decision
```

## Phase 2: Content Extraction

```mermaid
flowchart TD
    P2_START([Phase 2 Start]) --> INIT[Initialize QUEUE,<br>VISITED, NODES, EDGES]
    INIT --> LOOP{QUEUE empty?}
    LOOP -->|Yes| VERIFY[2.2 Verify Completeness]
    LOOP -->|No| POP[Pop current from QUEUE]
    POP --> VISITED_CHK{Already visited?}
    VISITED_CHK -->|Yes| LOOP
    VISITED_CHK -->|No| READ[Read source location]
    READ --> EXTRACT[Extract: decisions,<br>dispatches, transforms]
    EXTRACT --> EXTRACT2[Extract: quality gates,<br>loops, terminals]
    EXTRACT2 --> EXTRACT3[Extract: conditional<br>branches]
    EXTRACT3 --> ADD_NODE[Append to NODES]
    ADD_NODE --> ADD_EDGES[Append edges<br>for references]
    ADD_EDGES --> ENQUEUE[Enqueue unvisited<br>targets]
    ENQUEUE --> LOOP
    VERIFY --> CHK1{Orphan nodes?}
    CHK1 -->|Yes| FAIL([Return to fix])
    CHK1 -->|No| CHK2{All terminals<br>marked?}
    CHK2 -->|No| FAIL
    CHK2 -->|Yes| CHK3{All branches<br>represented?}
    CHK3 -->|No| FAIL
    CHK3 -->|Yes| CHK4{Loop conditions<br>complete?}
    CHK4 -->|No| FAIL
    CHK4 -->|Yes| CHK5{Placeholders<br>exist?}
    CHK5 -->|Yes| FAIL
    CHK5 -->|No| P2_END([Phase 2 Complete])

    style INIT fill:#4a9eff,color:#fff
    style READ fill:#4a9eff,color:#fff
    style EXTRACT fill:#4a9eff,color:#fff
    style VERIFY fill:#4a9eff,color:#fff
    classDef decision fill:#ff6b6b,color:#fff
    class LOOP,VISITED_CHK,CHK1,CHK2,CHK3,CHK4,CHK5 decision
```

## Phase 3: Diagram Generation

```mermaid
flowchart TD
    P3_START([Phase 3 Start]) --> GEN[3.1 Generate<br>Diagram Code]
    GEN --> APPLY_DIR[Set flow direction<br>TD or LR]
    APPLY_DIR --> GROUP[Group nodes into<br>subgraphs by phase]
    GROUP --> SHAPES[Apply node shapes:<br>decision, process, terminal]
    SHAPES --> STYLES[Apply styles:<br>blue=dispatch, red=gate]
    STYLES --> LABELS[Apply label guidelines:<br>max 5 words per line]
    LABELS --> MULT{Multiple edges<br>same source-target?}
    MULT -->|Yes| ANNOT[Use multiplicity<br>annotation]
    MULT -->|No| LEGEND
    ANNOT --> LEGEND[3.2 Generate Legend]
    LEGEND --> LEG_SUB[Add disconnected<br>legend subgraph]
    LEG_SUB --> LEG_COLOR[Include color meanings<br>if using classDef]
    LEG_COLOR --> XREF{Decomposed<br>diagram?}
    XREF -->|Yes| TABLE[3.3 Generate<br>Cross-Reference Table]
    XREF -->|No| P3_END([Phase 3 Complete])
    TABLE --> P3_END

    style GEN fill:#4a9eff,color:#fff
    style LEGEND fill:#4a9eff,color:#fff
    style TABLE fill:#4a9eff,color:#fff
    classDef decision fill:#ff6b6b,color:#fff
    class MULT,XREF decision
```

## Phase 4: Verification

```mermaid
flowchart TD
    P4_START([Phase 4 Start]) --> SYNTAX[4.1 Syntax Check]
    SYNTAX --> RENDER_AVAIL{Renderer<br>available?}
    RENDER_AVAIL -->|"Mermaid"| MERM_LIVE[Test in mermaid.live]
    RENDER_AVAIL -->|"Graphviz"| DOT_RUN[Run dot command]
    RENDER_AVAIL -->|"None"| MANUAL[Manual syntax audit]
    MANUAL --> BRACE[Count braces/brackets]
    BRACE --> SUB_END[Verify subgraph/end pairs]
    SUB_END --> NODE_ID[Check node ID format]
    NODE_ID --> EDGE_Q[Check edge label quoting]
    EDGE_Q --> CLASS_REF[Verify classDef matches]
    CLASS_REF --> RESERVED[Check reserved words]
    MERM_LIVE --> RENDER[4.2 Renderability Check]
    DOT_RUN --> RENDER
    RESERVED --> RENDER
    RENDER --> R_NODES{Too many nodes?}
    R_NODES -->|Yes| FIX_DECOMP[Decompose into levels]
    R_NODES -->|No| R_LABELS{Overlapping labels?}
    FIX_DECOMP --> RENDER
    R_LABELS -->|Yes| FIX_LABELS[Shorten labels]
    R_LABELS -->|No| R_EDGES{Edge spaghetti?}
    FIX_LABELS --> RENDER
    R_EDGES -->|Yes| FIX_EDGES[Reorder nodes,<br>change direction]
    R_EDGES -->|No| COMPLETE[4.3 Completeness Check]
    FIX_EDGES --> RENDER
    COMPLETE --> C1{All source sections<br>have nodes?}
    C1 -->|No| RETRAVERSE([Return to Phase 2])
    C1 -->|Yes| C2{All branches<br>as edges?}
    C2 -->|No| RETRAVERSE
    C2 -->|Yes| C3{All invocations<br>represented?}
    C3 -->|No| RETRAVERSE
    C3 -->|Yes| C4{All gates show<br>pass and fail?}
    C4 -->|No| RETRAVERSE
    C4 -->|Yes| P4_END([Phase 4 Complete])

    style SYNTAX fill:#4a9eff,color:#fff
    style RENDER fill:#4a9eff,color:#fff
    style COMPLETE fill:#4a9eff,color:#fff
    classDef decision fill:#ff6b6b,color:#fff
    class RENDER_AVAIL,R_NODES,R_LABELS,R_EDGES,C1,C2,C3,C4 decision
```

## Cross-Reference

| Overview Node | Detail Section | Source |
|---|---|---|
| P1 | Phase 1: Analysis | `skills/generating-diagrams/SKILL.md:47-99` |
| P2 | Phase 2: Content Extraction | `skills/generating-diagrams/SKILL.md:101-156` |
| P3 | Phase 3: Diagram Generation | `skills/generating-diagrams/SKILL.md:158-203` |
| P4 | Phase 4: Verification | `skills/generating-diagrams/SKILL.md:205-237` |

## Legend

```mermaid
flowchart LR
    L1[Process Step]
    L2{Decision Point}
    L3([Terminal])
    L4[Loop Back]
    style L1 fill:#4a9eff,color:#fff
    style L2 fill:#ff6b6b,color:#fff
    style L3 fill:#51cf66,color:#fff
    style L4 fill:#f0f0f0,color:#333
```

## Skill Content

``````````markdown
# Generating Diagrams

<ROLE>
Diagram Architect. Your reputation depends on diagrams that are accurate, renderable, and exhaustively sourced from real material -- never invented.
</ROLE>

## Overview

Generate accurate, renderable, exhaustive diagrams from code, processes, instructions, or architecture. Every node justified by source material. Every reference traced to its deepest level. Mermaid for inline markdown; Graphviz DOT for complex or heavily styled output.

## When to Use

- Visualizing process flows, decision trees, or multi-phase workflows
- Mapping dependency/invocation relationships between components
- Documenting state machines or lifecycle transitions
- Creating entity-relationship or class hierarchy diagrams
- Analyzing skill, command, or instruction structure visually
- Generating sequence diagrams for temporal interactions

**When NOT to use:** Structure is flat (no branches, decisions, or relationships) AND content is 10 items or fewer -- a list or table suffices. Runtime observability. Text-only documentation.

## Invariant Principles

1. **Source-Grounded Nodes**: Every node traces to a specific source location (file:line, section heading, or code symbol). No invented nodes.
2. **Exhaustive Traversal**: Follow every reference, invocation, and branch to its terminal point. "..." and "etc." are forbidden. If too complex for one diagram, decompose into linked diagrams.
3. **One Entity, One Node**: Each entity appears exactly once in relationship/dependency diagrams. Multiple connections use multiple edges, not duplicate nodes.
4. **Renderability Over Completeness**: A diagram that cannot render is worthless. Always verify. When too complex for one diagram, decompose.

## Quick Reference

| Diagram Type | Best For | Mermaid Syntax | Graphviz Alternative |
|-------------|---------|----------------|---------------------|
| **Flowchart** | Processes, decisions, workflows | `flowchart TD` | `digraph { }` with shapes |
| **Sequence** | Temporal interactions, request/response | `sequenceDiagram` | Not recommended |
| **State** | Lifecycles, state machines | `stateDiagram-v2` | `digraph { }` with edge labels |
| **ER** | Data models, entity relationships | `erDiagram` | `graph { }` undirected |
| **Class** | Type hierarchies, composition | `classDiagram` | `digraph { }` with record shapes |
| **Dependency** | Import/invocation graphs | `flowchart LR` | `digraph { }` with clusters |

## Workflow

### Phase 1: Analysis

<analysis>Before generating any diagram, identify: subject type, traversal scope, source material locations, and rendering format.</analysis>

**1.1 Identify Diagram Subject**

| Subject Type | Examples | Primary Diagram Type |
|-------------|---------|---------------------|
| Process/workflow | CI pipeline, feature workflow, approval flow | Flowchart |
| Temporal interaction | API call sequence, auth handshake | Sequence |
| Lifecycle/states | Order states, connection lifecycle | State |
| Data model | Database schema, domain entities | ER |
| Type hierarchy | Class inheritance, interface impl | Class |
| Dependencies | Module imports, skill invocations, package deps | Dependency graph |

If the subject spans multiple types, produce separate diagrams for each concern rather than a hybrid.

**1.2 Scope the Traversal**

Define boundaries BEFORE reading source material. Confirm with user; in autonomous mode, use default depth.

```
ROOT: [starting entity/file/process]
DEPTH: [how many levels of references to follow]
BOUNDARY: [what counts as "outside" - stop traversing here]
EXCLUSIONS: [known irrelevant branches to skip]
```

Default DEPTH: follow all references until reaching external dependencies or leaf nodes.

**1.3 Select Format**

| Criterion | Mermaid | Graphviz DOT |
|-----------|---------|--------------|
| Node count < 50 | Yes | Overkill |
| Node count 50-150 | Risky (test render) | Yes |
| Node count > 150 | No (decompose) | Yes (with clusters) |
| Needs GitHub inline rendering | Yes | No (render to SVG) |
| Complex layout (overlapping edges) | Limited control | Full control |
| Custom styling (colors, fonts, shapes) | Basic | Full |
| Subgraph nesting > 3 levels | Fragile | Solid |

**Default: Mermaid** unless complexity indicators from the table above suggest otherwise.

**1.4 Plan Decomposition (if needed)**

When estimated node count exceeds format limits:

1. **Level 0 (Overview)**: High-level boxes with phase/component names. No internal detail. Include "see Diagram N" references.
2. **Level 1 (Phase Detail)**: One diagram per major phase/component. Shows all internal steps and decision points.
3. **Level 2 (Deep Dive)**: Optional. For phases that are themselves complex (e.g., a sub-skill with its own multi-phase workflow).

Each level's diagrams must use consistent node IDs so cross-references are unambiguous.

### Phase 2: Content Extraction

<CRITICAL>
Phase 2 traversal is mandatory. Skipping it to go directly to generation produces invented nodes and missing edges. There are no shortcuts here.
</CRITICAL>

**2.1 Systematic Traversal Protocol**

```
QUEUE = [ROOT]
VISITED = {}
NODES = []
EDGES = []

while QUEUE not empty:
    current = QUEUE.pop()
    if current in VISITED: continue
    VISITED.add(current)

    content = read(current.source_location)

    NODES.append({
        id: sanitize(current.name),
        label: current.display_name,
        source: current.source_location,
        type: classify(current)  # decision/process/subgraph/terminal/etc
    })

    for each reference in content:
        target = resolve(reference)
        EDGES.append({
            from: current.id,
            to: target.id,
            label: reference.context,
            condition: reference.condition or null
        })
        if target not in VISITED:
            QUEUE.append(target)
```

Extract from each source file/section:
- Decision points (if/else, switch, routing logic)
- Subagent dispatches or skill invocations
- Data transformations (input -> output)
- Quality gates (pass/fail with consequences)
- Loop/retry logic
- Terminal conditions (exit, error, completion)
- Conditional branches (with the condition on the edge label)

**2.2 Verify Completeness**

- [ ] Every item in VISITED has at least one edge (no orphan nodes)
- [ ] Every terminal node is explicitly marked (success, error, exit)
- [ ] Every decision has all branches represented (not just the happy path)
- [ ] Every loop has both continue and break conditions
- [ ] No "..." or placeholder nodes exist

### Phase 3: Diagram Generation

**3.1 Generate Diagram Code**

| Rule | Mermaid | Graphviz |
|------|---------|----------|
| Flow direction | `TD` for processes, `LR` for dependencies | `rankdir=TB` or `rankdir=LR` |
| Subgraphs | Group by phase/component | `subgraph cluster_name { }` |
| Decision nodes | `{Diamond text}` | `shape=diamond` |
| Process nodes | `[Rectangle text]` | `shape=box` |
| Terminal nodes | `([Stadium text])` | `shape=doubleoctagon` |
| Subagent dispatch | Blue fill | `fillcolor="#4a9eff"` |
| Quality gate | Red fill | `fillcolor="#ff6b6b"` |
| Conditional edge | Dashed line + label | `style=dashed, label="condition"` |

**Node label guidelines:**
- Max 5 words per line
- Use `<br/>` for line breaks in Mermaid, `\n` in Graphviz
- Put detail in edge labels or annotations, not node labels
- Reference skill/command names inline: `Invoke: skill-name`

**Multiplicity annotation:** When the same target is invoked multiple times from the same source, use a single edge with multiplicity in the label: `-->|"x3: per-task, comprehensive, pre-PR"| FC`. Create separate edges only when the edge source, target, or conditional label differs between invocations.

**3.2 Generate Legend**

Every diagram MUST include a legend. For Mermaid, add a disconnected subgraph:

```mermaid
subgraph Legend
    L1[Process Step]
    L2{Decision Point}
    L3([Terminal])
    L4[/Input-Output/]
end
```

Include color meanings if using `classDef` or fill colors. For Graphviz, add `subgraph cluster_legend`.

**3.3 Generate Cross-Reference Table**

For decomposed diagrams, produce a table mapping node IDs to their detail diagram:

| Node in Overview | Detail Diagram | Source File |
|-----------------|----------------|-------------|
| `phase_1` | Diagram 2: Research | `commands/feature-research.md` |
| `phase_2` | Diagram 3: Design | `commands/feature-design.md` |

### Phase 4: Verification

**4.1 Syntax Check**

- Mermaid: Paste into [mermaid.live](https://mermaid.live) or a local renderer
- Graphviz: Run `dot -Tsvg input.dot -o output.svg`
- If no renderer available, manual syntax audit:
  1. Count opening/closing braces and brackets (must match)
  2. Verify every `subgraph` has a matching `end`
  3. Verify all node IDs are alphanumeric (no spaces or unquoted special chars)
  4. Verify all edge labels use correct quoting (`|"label"|` for Mermaid)
  5. Verify `classDef` names match `class` references
  6. Check for Mermaid reserved words used as node IDs (`end`, `graph`, `subgraph`)

**4.2 Renderability Check**

| Issue | Symptom | Fix |
|-------|---------|-----|
| Too many nodes | Render timeout or blank output | Decompose into levels |
| Overlapping labels | Text collision in rendered output | Shorten labels, use edge labels |
| Subgraph overflow | Nodes escape their container | Reduce nesting depth, use clusters |
| Mermaid max nodes (~100) | Render fails silently | Switch to Graphviz or decompose |
| Edge spaghetti | Unreadable crossing lines | Reorder nodes, use `LR` vs `TD`, add invisible edges for spacing |

**4.3 Completeness Check**

- Every file/section in scope has corresponding nodes
- Every conditional branch from source appears as a labeled edge
- Every skill/subagent invocation is represented
- Every quality gate shows both pass and fail paths
- Terminal conditions match source (exit, error, completion, loop-back)

If anything is missing, return to Phase 2 and re-traverse.

<reflection>After generating any diagram, verify: every node traces to source, no placeholders remain, legend is present, syntax renders cleanly, and completeness check passes.</reflection>

## Mermaid Syntax Reference

```mermaid
flowchart TD
    A[Process] --> B{Decision}
    B -->|Yes| C[Action]
    B -->|No| D[Other Action]
    C --> E([Terminal])

    subgraph Group Name
        F[Step 1] --> G[Step 2]
    end

    style A fill:#4a9eff,color:#fff
    classDef gate fill:#ff6b6b,color:#fff
    class B gate
```

```mermaid
sequenceDiagram
    participant A as Client
    participant B as Server
    A->>B: Request
    B-->>A: Response
    alt Success
        A->>B: Confirm
    else Failure
        A->>B: Retry
    end
```

```mermaid
stateDiagram-v2
    [*] --> Idle
    Idle --> Processing: start
    Processing --> Complete: success
    Processing --> Failed: error
    Failed --> Idle: retry
    Complete --> [*]
```

```mermaid
erDiagram
    SKILL ||--o{ COMMAND : "invokes"
    SKILL {
        string name
        string description
    }
    COMMAND {
        string name
        string phase
    }
```

## Graphviz DOT Reference

```dot
digraph G {
    rankdir=TD;
    node [shape=box, style=filled, fillcolor="#f0f0f0"];

    start [label="Start", shape=oval];
    decision [label="Decision?", shape=diamond, fillcolor="#ff6b6b"];
    process [label="Process Step", fillcolor="#4a9eff", fontcolor=white];
    end_node [label="End", shape=doubleoctagon, fillcolor="#51cf66"];

    start -> decision;
    decision -> process [label="Yes"];
    decision -> end_node [label="No", style=dashed];
    process -> end_node;

    subgraph cluster_phase1 {
        label="Phase 1";
        style=filled;
        fillcolor="#f8f9fa";
        a1 -> a2 -> a3;
    }
}
```

## Common Mistakes

| Mistake | Why It Fails | Fix |
|---------|-------------|-----|
| Dumping everything into one diagram | Exceeds render limits, unreadable | Decompose into levels with cross-references |
| Duplicate nodes for same entity | Obscures that edges point to same thing | One node, multiple edges |
| "..." or "etc." placeholders | Defeats exhaustive purpose | Trace every reference or mark as out-of-scope |
| No legend | Reader cannot decode color/shape meaning | Always include legend subgraph |
| Verbose node labels (10+ words) | Nodes become unreadable blobs | Max 5 words, detail on edges or in table |
| Skipping error/failure paths | Happy-path-only diagram lies about complexity | Every decision needs all branches |
| No source traceability | Cannot verify diagram accuracy | Keep node-to-source mapping |
| Choosing Mermaid for 100+ node graphs | Silent render failure | Use Graphviz or decompose |
| Flowchart for relationship data | Wrong tool for the job | Use ER, class, or dependency diagram |
| No rendering verification | Broken syntax ships as "done" | Always validate syntax before delivery |

## Rationalization Counters

| Excuse | Reality |
|--------|---------|
| "This diagram is simple, skip the traversal" | Simple diagrams are fast to traverse. Skipping risks missing edges. Always traverse. |
| "I'll add the legend later" | Later never comes. Generate it with the diagram. |
| "Decomposition is overkill for this" | If unsure whether to decompose, count nodes. Numbers decide, not feelings. |
| "The completeness check takes too long" | Completeness check catches missing edges every time. 2 minutes to check vs. delivering wrong diagram. |
| "I know this domain well enough to skip reading" | Source-grounded means reading, not remembering. Read or mark out-of-scope. |

## Modes

### `--headless`

Invoked as: `/generating-diagrams --headless`

<CRITICAL>
When `--headless` is specified, the calling script captures your raw text output and saves it directly as a file. Your output IS the file content.

Rules:
1. Do ALL analysis, extraction, and verification work SILENTLY. Do not output your Phase 1/2/4 work.
2. Do NOT read, compare against, or reference any existing diagram files. Always generate fresh from the source.
3. Do NOT output "no changes needed" or "the diagram is accurate". Always output the full diagram.
4. Do NOT output any prose, preamble, summary, or description of what you did.
5. ONLY output markdown headings, mermaid code blocks, and cross-reference tables.

Your output must match this template exactly:
</CRITICAL>

```
## Overview

\`\`\`mermaid
flowchart TD
    A[Phase 1] --> B[Phase 2]
\`\`\`

## Phase 1: Name

\`\`\`mermaid
flowchart TD
    A[Step 1] --> B{Decision}
    B -->|Yes| C[Action]
    B -->|No| D[Other]
\`\`\`

## Cross-Reference

| Overview Node | Detail Section | Source |
|---|---|---|
| A | Phase 1: Name | `path/to/source` |

## Legend

\`\`\`mermaid
flowchart LR
    L1[Process Step]
    L2{Decision Point}
    L3([Terminal])
    style L1 fill:#4a9eff,color:#fff
    style L2 fill:#ff6b6b,color:#fff
    style L3 fill:#51cf66,color:#fff
\`\`\`
```

If the very first characters of your output are not `## Overview`, you are doing it wrong.

### Default (interactive)

When `--headless` is NOT specified, write the diagram to the appropriate file path using Write or Edit tools. Confirm the output path with the user if not obvious from context.

<FORBIDDEN>
- Placeholder nodes ("...", "etc.", "and more")
- Duplicate nodes for the same entity in relationship diagrams
- Diagrams without legends
- Skipping the traversal protocol (Phase 2) and going straight to generation
- Delivering unverified diagram syntax
- Node labels exceeding 5 words per line
- Hybrid diagrams mixing process flow with relationship data (use separate diagrams)
- Handwaving over nested references ("see X for details" without tracing X)
- Rationalizing that "this is simple enough" to skip any phase
- In headless mode: any text output that is not a markdown heading, mermaid code block, or cross-reference table
</FORBIDDEN>

<FINAL_EMPHASIS>
Every node traces to source. Every diagram renders. Every phase executes. Shortcuts produce wrong diagrams that mislead -- and a wrong diagram is worse than no diagram at all.
</FINAL_EMPHASIS>
``````````

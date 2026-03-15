# generating-diagrams

**Auto-invocation:** Your coding assistant will automatically invoke this skill when it detects a matching trigger.

> Use when generating flowcharts, diagrams, dependency graphs, or visual representations of processes, relationships, architecture, or state machines. Triggers: 'diagram this', 'flowchart', 'visualize', 'dependency graph', 'ER diagram', 'state machine diagram', 'class diagram', 'sequence diagram', 'map the relationships', 'draw the architecture', 'how does X connect to Y'. NOT for: simple bullet point explanations, runtime monitoring, or text-only documentation.

## Workflow Diagram

# Generating Diagrams - Skill Workflow Diagrams

## Overview Diagram

High-level flow showing the two entry paths (new generation vs update mode) and the four core phases.

```mermaid
flowchart TD
    START([Skill Invoked]) --> MODE{New or Update?}

    MODE -->|"New diagram"| P1[Phase 1:<br>Analysis]
    MODE -->|"Existing diagram"| UM[Update Mode:<br>Classify Changes]

    UM --> T1{Tier?}
    T1 -->|"Tier 1: STAMP"| STAMP([Stamp as Fresh<br>No Regen])
    T1 -->|"Tier 2: PATCH"| PATCH[Surgical Edit<br>to Existing Diagram]
    T1 -->|"Tier 3: REGENERATE"| P1
    T1 -->|"Classification error"| P1

    PATCH --> P4
    P1 --> P2[Phase 2:<br>Content Extraction]
    P2 --> P3[Phase 3:<br>Diagram Generation]
    P3 --> P4[Phase 4:<br>Verification]

    P4 --> VPASS{All Checks Pass?}
    VPASS -->|"Yes"| DONE([Deliver Diagram])
    VPASS -->|"Missing content"| P2

    subgraph Legend
        L1[Process Step]
        L2{Decision Point}
        L3([Terminal])
    end

    classDef gate fill:#ff6b6b,color:#fff
    classDef success fill:#51cf66,color:#fff

    class MODE,T1,VPASS gate
    class DONE,STAMP success
```

## Cross-Reference Table

| Node in Overview | Detail Diagram | Source Lines |
|-----------------|----------------|--------------|
| `P1` Phase 1 | Diagram 2: Analysis | SKILL.md:47-99 |
| `P2` Phase 2 | Diagram 3: Content Extraction | SKILL.md:101-156 |
| `P3` Phase 3 | Diagram 4: Diagram Generation | SKILL.md:158-203 |
| `P4` Phase 4 | Diagram 5: Verification | SKILL.md:205-237 |
| `UM` Update Mode | Diagram 6: Update Mode | SKILL.md:346-378 |

---

## Diagram 2: Phase 1 - Analysis

Steps 1.1 through 1.4: subject identification, scope definition, format selection, and optional decomposition planning.

```mermaid
flowchart TD
    P1_START([Phase 1 Start]) --> IDENT["1.1 Identify<br>Diagram Subject"]

    IDENT --> STYPE{Subject Type?}
    STYPE -->|"Process/workflow"| FMT_FC["Flowchart"]
    STYPE -->|"Temporal interaction"| FMT_SEQ["Sequence"]
    STYPE -->|"Lifecycle/states"| FMT_ST["State"]
    STYPE -->|"Data model"| FMT_ER["ER"]
    STYPE -->|"Type hierarchy"| FMT_CL["Class"]
    STYPE -->|"Dependencies"| FMT_DEP["Dependency Graph"]

    FMT_FC & FMT_SEQ & FMT_ST & FMT_ER & FMT_CL & FMT_DEP --> MULTI{Spans multiple<br>types?}
    MULTI -->|"Yes"| SEP["Produce separate<br>diagrams per concern"]
    MULTI -->|"No"| SCOPE

    SEP --> SCOPE["1.2 Scope Traversal<br>ROOT / DEPTH /<br>BOUNDARY / EXCLUSIONS"]

    SCOPE --> CONFIRM{Autonomous<br>mode?}
    CONFIRM -->|"Yes"| DEFAULT["Use default depth:<br>follow all refs to<br>leaf/external"]
    CONFIRM -->|"No"| ASK["Confirm scope<br>with user"]

    DEFAULT & ASK --> FORMAT["1.3 Select Format"]

    FORMAT --> NODES{Estimated<br>node count?}
    NODES -->|"< 50"| MERMAID["Use Mermaid"]
    NODES -->|"50-150"| TEST["Test Mermaid render;<br>fallback to Graphviz"]
    NODES -->|"> 150"| GRAPHVIZ["Use Graphviz<br>with clusters"]

    MERMAID & TEST & GRAPHVIZ --> DECOMP{Exceeds format<br>limits?}
    DECOMP -->|"No"| P1_END([Phase 1 Complete])
    DECOMP -->|"Yes"| PLAN["1.4 Plan Decomposition"]

    PLAN --> L0["Level 0: Overview<br>High-level boxes"]
    L0 --> L1D["Level 1: Phase Detail<br>One per component"]
    L1D --> L2{Complex<br>sub-phases?}
    L2 -->|"Yes"| L2D["Level 2: Deep Dive<br>Sub-skill detail"]
    L2 -->|"No"| P1_END

    L2D --> P1_END

    subgraph Legend
        LL1[Process Step]
        LL2{Decision Point}
        LL3([Terminal])
    end

    classDef gate fill:#ff6b6b,color:#fff
    classDef success fill:#51cf66,color:#fff

    class STYPE,MULTI,CONFIRM,NODES,DECOMP,L2 gate
    class P1_END success
```

---

## Diagram 3: Phase 2 - Content Extraction

The systematic traversal protocol (BFS queue) and completeness verification.

```mermaid
flowchart TD
    P2_START([Phase 2 Start]) --> INIT["Initialize QUEUE,<br>VISITED, NODES, EDGES"]

    INIT --> LOOP{QUEUE<br>empty?}
    LOOP -->|"Yes"| VERIFY["2.2 Verify<br>Completeness"]
    LOOP -->|"No"| POP["Pop current<br>from QUEUE"]

    POP --> SKIP{Already<br>visited?}
    SKIP -->|"Yes"| LOOP
    SKIP -->|"No"| READ["Read source at<br>current.source_location"]

    READ --> ADD_NODE["Add to NODES:<br>id, label, source, type"]

    ADD_NODE --> EXTRACT["Extract from content:<br>decisions, dispatches,<br>transforms, gates,<br>loops, terminals,<br>conditional branches"]

    EXTRACT --> ADD_EDGES["Add to EDGES:<br>from, to, label,<br>condition"]

    ADD_EDGES --> ENQUEUE["Enqueue unvisited<br>targets"]

    ENQUEUE --> LOOP

    VERIFY --> CHK_ORPHAN{Orphan nodes?<br>All have edges?}
    CHK_ORPHAN -->|"Fail"| FIX["Re-traverse<br>missing sections"]
    CHK_ORPHAN -->|"Pass"| CHK_TERM{All terminals<br>marked?}

    CHK_TERM -->|"Fail"| FIX
    CHK_TERM -->|"Pass"| CHK_BRANCH{All decision<br>branches present?}

    CHK_BRANCH -->|"Fail"| FIX
    CHK_BRANCH -->|"Pass"| CHK_LOOP{All loops have<br>continue + break?}

    CHK_LOOP -->|"Fail"| FIX
    CHK_LOOP -->|"Pass"| CHK_PLACEHOLDER{Any placeholders<br>remain?}

    CHK_PLACEHOLDER -->|"Fail"| FIX
    CHK_PLACEHOLDER -->|"Pass"| P2_END([Phase 2 Complete])

    FIX --> LOOP

    subgraph Legend
        LL1[Process Step]
        LL2{Decision Point}
        LL3([Terminal])
    end

    classDef gate fill:#ff6b6b,color:#fff
    classDef success fill:#51cf66,color:#fff

    class LOOP,SKIP,CHK_ORPHAN,CHK_TERM,CHK_BRANCH,CHK_LOOP,CHK_PLACEHOLDER gate
    class P2_END success
```

---

## Diagram 4: Phase 3 - Diagram Generation

Code generation, legend, and optional cross-reference table.

```mermaid
flowchart TD
    P3_START([Phase 3 Start]) --> GEN["3.1 Generate<br>Diagram Code"]

    GEN --> DIR{Diagram type?}
    DIR -->|"Process flow"| TD_DIR["Use TD direction"]
    DIR -->|"Dependencies"| LR_DIR["Use LR direction"]

    TD_DIR & LR_DIR --> GROUP["Group nodes into<br>subgraphs by<br>phase/component"]

    GROUP --> SHAPES["Apply node shapes:<br>rectangles=process<br>diamonds=decision<br>stadiums=terminal"]

    SHAPES --> STYLE["Apply styling:<br>blue=#4a9eff subagents<br>red=#ff6b6b gates<br>green=#51cf66 success"]

    STYLE --> LABELS{Labels<br>compliant?}
    LABELS -->|"No: >5 words"| SHORTEN["Shorten labels;<br>move detail to edges"]
    LABELS -->|"Yes"| EDGES

    SHORTEN --> EDGES["Generate edges<br>with labels and<br>conditions"]

    EDGES --> MULT{Same target<br>invoked multiple<br>times?}
    MULT -->|"Yes"| SINGLE_EDGE["Single edge with<br>multiplicity label"]
    MULT -->|"No"| LEGEND

    SINGLE_EDGE --> LEGEND["3.2 Generate Legend<br>Disconnected subgraph"]

    LEGEND --> DECOMPOSED{Decomposed<br>diagram set?}
    DECOMPOSED -->|"Yes"| XREF["3.3 Generate<br>Cross-Reference Table"]
    DECOMPOSED -->|"No"| P3_END([Phase 3 Complete])

    XREF --> P3_END

    subgraph Legend
        LL1[Process Step]
        LL2{Decision Point}
        LL3([Terminal])
    end

    classDef gate fill:#ff6b6b,color:#fff
    classDef success fill:#51cf66,color:#fff

    class DIR,LABELS,MULT,DECOMPOSED gate
    class P3_END success
```

---

## Diagram 5: Phase 4 - Verification

Syntax, renderability, and completeness verification with return-to-Phase-2 on failure.

```mermaid
flowchart TD
    P4_START([Phase 4 Start]) --> SYNTAX["4.1 Syntax Check"]

    SYNTAX --> RENDERER{Renderer<br>available?}
    RENDERER -->|"Mermaid"| MLIVE["Test in<br>mermaid.live"]
    RENDERER -->|"Graphviz"| DOT["Run dot -Tsvg"]
    RENDERER -->|"None"| MANUAL["Manual audit:<br>matched braces,<br>subgraph/end pairs,<br>valid node IDs,<br>edge label quoting,<br>classDef matches,<br>reserved words"]

    MLIVE & DOT & MANUAL --> SYN_PASS{Syntax<br>valid?}
    SYN_PASS -->|"No"| SYN_FIX["Fix syntax errors"]
    SYN_FIX --> SYNTAX
    SYN_PASS -->|"Yes"| RENDER["4.2 Renderability<br>Check"]

    RENDER --> R_ISSUES{Render<br>issues?}
    R_ISSUES -->|"Too many nodes"| DECOMPOSE["Decompose into<br>levels"]
    R_ISSUES -->|"Overlapping labels"| SHORTEN["Shorten labels"]
    R_ISSUES -->|"Edge spaghetti"| REORDER["Reorder nodes,<br>change direction"]
    R_ISSUES -->|"None"| COMPLETE

    DECOMPOSE & SHORTEN & REORDER --> RENDER

    COMPLETE["4.3 Completeness<br>Check"] --> C1{All scoped files<br>have nodes?}
    C1 -->|"No"| RETRACE([Return to Phase 2])
    C1 -->|"Yes"| C2{All conditional<br>branches present?}

    C2 -->|"No"| RETRACE
    C2 -->|"Yes"| C3{All invocations<br>represented?}

    C3 -->|"No"| RETRACE
    C3 -->|"Yes"| C4{All gates show<br>pass + fail?}

    C4 -->|"No"| RETRACE
    C4 -->|"Yes"| C5{Terminals match<br>source?}

    C5 -->|"No"| RETRACE
    C5 -->|"Yes"| P4_END([Deliver Diagram])

    subgraph Legend
        LL1[Process Step]
        LL2{Decision Point}
        LL3([Terminal])
    end

    classDef gate fill:#ff6b6b,color:#fff
    classDef success fill:#51cf66,color:#fff
    classDef warn fill:#ffa94d,color:#fff

    class RENDERER,SYN_PASS,R_ISSUES,C1,C2,C3,C4,C5 gate
    class P4_END success
    class RETRACE warn
```

---

## Diagram 6: Update Mode

Change classification and tier routing. Default path when updating existing diagrams.

```mermaid
flowchart TD
    UM_START([Update Mode<br>Invoked]) --> CLASSIFY["Classify source<br>changes vs existing<br>diagram"]

    CLASSIFY --> CERR{Classification<br>error?}
    CERR -->|"Yes"| FALLBACK["Fallback to<br>full regeneration"]
    CERR -->|"No"| TIER{Change Tier?}

    TIER -->|"Tier 1: STAMP"| STAMP_CHK["Non-structural change:<br>XML tags, prose,<br>typos, FORBIDDEN items,<br>code examples"]
    TIER -->|"Tier 2: PATCH"| PATCH_CHK["Small structural change:<br>add/remove 1 step,<br>rename phase,<br>add gate, reorder 1-2"]
    TIER -->|"Tier 3: REGENERATE"| REGEN_CHK["Major structural change:<br>add/remove phases,<br>reorg ordering,<br>change branching,<br>new parallel tracks"]

    STAMP_CHK --> STAMP_DO["Mark diagram<br>as fresh"]
    STAMP_DO --> UM_END([Done:<br>No Diagram Change])

    PATCH_CHK --> PATCH_DO["Surgical edit:<br>preserve ALL existing<br>structure/styling"]
    PATCH_DO --> PATCH_ERR{Patch<br>error?}
    PATCH_ERR -->|"Yes"| FALLBACK
    PATCH_ERR -->|"No"| VERIFY["Run Phase 4:<br>Verification"]
    VERIFY --> UM_DONE([Done:<br>Patched Diagram])

    REGEN_CHK --> FALLBACK
    FALLBACK --> FULL["Execute full workflow:<br>Phase 1 through 4"]
    FULL --> UM_REGEN([Done:<br>Regenerated Diagram])

    subgraph "Invocation Options"
        INV1["--interactive<br>Smart classification"]
        INV2["--force-regen<br>Skip to full regen"]
    end

    subgraph Legend
        LL1[Process Step]
        LL2{Decision Point}
        LL3([Terminal])
    end

    classDef gate fill:#ff6b6b,color:#fff
    classDef success fill:#51cf66,color:#fff

    class CERR,TIER,PATCH_ERR gate
    class UM_END,UM_DONE,UM_REGEN success
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

## Update Mode (Default)

When updating existing diagrams (the default path), the system classifies source changes before deciding how to proceed:

### Tier 1: STAMP (Non-Structural)
Changes that don't affect the workflow diagram are stamped as fresh without regeneration.
- Adding/modifying XML tags (e.g., `<BEHAVIORAL_MODE>`, `<ROLE>`, `<CRITICAL>`)
- Changing prose, descriptions, or explanations within existing steps
- Fixing typos, rewording instructions
- Adding/removing FORBIDDEN or REQUIRED items
- Changing code examples within steps

### Tier 2: PATCH (Surgical Update)
Small structural changes trigger targeted edits to the existing diagram rather than full regeneration.
- Adding or removing a single step within an existing phase
- Renaming a phase or step
- Adding a new quality gate
- Reordering 1-2 steps

When patching, preserve ALL existing diagram structure, styling, and layout. Only modify the specific nodes, edges, or subgraphs affected by the change.

### Tier 3: REGENERATE (Full)
Major structural changes fall through to the full 4-phase generation workflow above.
- Adding or removing entire phases
- Major reorganization of step ordering
- Changing flow/branching logic
- Adding new parallel tracks or decision points

### Invocation
- `generate_diagrams.py --interactive` uses smart classification by default
- `generate_diagrams.py --force-regen` bypasses classification for full regeneration
- On any classification or patching error, falls back to full regeneration automatically

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
</FORBIDDEN>

<FINAL_EMPHASIS>
Every node traces to source. Every diagram renders. Every phase executes. Shortcuts produce wrong diagrams that mislead -- and a wrong diagram is worse than no diagram at all.
</FINAL_EMPHASIS>
``````````

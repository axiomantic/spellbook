<!-- diagram-meta: {"source": "commands/fact-check-verify.md", "source_hash": "sha256:69bd9dd391d25f57505a8cd405285372bb3c3b0ae01d9bc1e09bff99c8a6c49e", "generated_at": "2026-03-09T10:30:36Z", "generator": "generate_diagrams.py"} -->
# Diagram: fact-check-verify

Now I have the full picture. Here are the diagrams:

---

# fact-check-verify Command Diagrams

## Overview: High-Level Flow

```mermaid
graph TD
    subgraph legend["Legend"]
        L1["Process"]
        L2{"Decision"}
        L3([Terminal])
        L4["Subagent Dispatch"]:::subagent
        L5{"Quality Gate"}:::gate
        L6([Success]):::success
    end

    START([Phase 4-5 Entry]) --> CACHE_CHECK{"AgentDB<br>available?"}

    CACHE_CHECK -->|Yes| RETRIEVE["Retrieve cached findings<br>similarity threshold 0.92"]
    CACHE_CHECK -->|No| SKIP_CACHE["Skip cache, proceed<br>store locally for later sync"]

    RETRIEVE --> CACHE_HIT{"Cached finding<br>similarity > 0.92?"}
    CACHE_HIT -->|Yes| FILE_CHANGED{"Referenced file<br>changed since storage?"}
    CACHE_HIT -->|No| SPAWN

    FILE_CHANGED -->|Yes| INVALIDATE["Invalidate cache entry"] --> SPAWN
    FILE_CHANGED -->|No| RETURN_CACHED["Return cached finding"] --> VERDICT_ASSEMBLY

    SKIP_CACHE --> SPAWN

    SPAWN["Spawn category agents<br>via swarm-orchestration"]:::subagent --> SPAWN_OK{"Swarm spawn<br>successful?"}:::gate

    SPAWN_OK -->|No| ESCALATE_FAIL([Escalate to orchestrator<br>NO partial verdicts])
    SPAWN_OK -->|Yes| PARALLEL["Parallel agent verification<br>See: Detail Diagram A"]

    PARALLEL --> SCOPE_CHECK{"System-wide<br>claim keywords?"}
    SCOPE_CHECK -->|Yes| SCOPE_EXPAND["Scope Expansion<br>See: Detail Diagram B"]
    SCOPE_CHECK -->|No| CONFLICT_CHECK

    SCOPE_EXPAND --> CONFLICT_CHECK{"Cross-agent<br>conflict detected?"}

    CONFLICT_CHECK -->|Yes| CONTESTED["Mark Contested<br>present BOTH verdicts<br>See: Detail Diagram C"]
    CONFLICT_CHECK -->|No| DEPTH_CHECK

    CONTESTED --> DEPTH_CHECK{"Depth escalation<br>required?"}

    DEPTH_CHECK -->|Yes| ESCALATION["Depth Escalation<br>See: Detail Diagram D"]
    DEPTH_CHECK -->|No| FRACTAL_CHECK

    ESCALATION --> FRACTAL_CHECK{"Verdict is<br>Inconclusive or<br>Ambiguous?"}

    FRACTAL_CHECK -->|Yes| FRACTAL["Invoke fractal-thinking<br>intensity: pulse"]
    FRACTAL_CHECK -->|No| VERDICT_ASSEMBLY

    FRACTAL --> FRACTAL_UPGRADE{"Verdict<br>upgraded?"}
    FRACTAL_UPGRADE -->|Yes| UPDATE_VERDICT["Update verdict<br>category + evidence"]
    FRACTAL_UPGRADE -->|No| VERDICT_ASSEMBLY

    UPDATE_VERDICT --> VERDICT_ASSEMBLY

    VERDICT_ASSEMBLY{"Every verdict has<br>concrete evidence?"}:::gate
    VERDICT_ASSEMBLY -->|No| REJECT_VERDICT([FORBIDDEN:<br>No verdict without citation])
    VERDICT_ASSEMBLY -->|Yes| STORE_FINDING["Store finding in AgentDB<br>with file hash"]

    STORE_FINDING --> OUTPUT([Emit verdicts<br>to fact-check-report]):::success

    classDef subagent fill:#4a9eff,stroke:#333,color:#fff
    classDef gate fill:#ff6b6b,stroke:#333,color:#fff
    classDef success fill:#51cf66,stroke:#333,color:#fff
```

### Cross-Reference Table

| Overview Node | Detail Diagram |
|---|---|
| Parallel agent verification | Detail Diagram A: Category Agent Dispatch |
| Scope Expansion | Detail Diagram B: System-Wide Claim Expansion |
| Mark Contested | Detail Diagram C: Cross-Agent Conflict Resolution |
| Depth Escalation | Detail Diagram D: Depth Escalation Protocol |

---

## Detail Diagram A: Category Agent Dispatch (Phase 4)

```mermaid
graph TD
    subgraph legend["Legend"]
        L1["Process"]
        L2{"Decision"}
        L4["Subagent"]:::subagent
        L5{"Quality Gate"}:::gate
    end

    ENTRY([Swarm spawn]) --> AGENTS

    subgraph AGENTS["Category Agents (Parallel)"]
        SEC["SecurityAgent"]:::subagent
        COR["CorrectnessAgent"]:::subagent
        PERF["PerformanceAgent"]:::subagent
        CONC["ConcurrencyAgent"]:::subagent
        DOC["DocumentationAgent"]:::subagent
        HIST["HistoricalAgent"]:::subagent
        CONF["ConfigurationAgent"]:::subagent
    end

    AGENTS --> CUSTOM_CHECK{"Claims require<br>non-standard domain?"}
    CUSTOM_CHECK -->|Yes| CUSTOM["Spawn additional<br>domain-specific agents"]:::subagent
    CUSTOM_CHECK -->|No| COLLECT

    CUSTOM --> COLLECT["Collect all agent results"]

    COLLECT --> EVIDENCE_CHECK{"Each verdict cites<br>Tier 1-5 evidence?"}:::gate
    EVIDENCE_CHECK -->|No| REJECT([FORBIDDEN:<br>Tier 6 alone is not evidence])
    EVIDENCE_CHECK -->|Yes| TIER_CHECK{"Evidence tier<br>classification"}

    TIER_CHECK --> T1["Tier 1: Code trace<br>Standalone: Yes"]
    TIER_CHECK --> T2["Tier 2: Test output<br>Standalone: Yes"]
    TIER_CHECK --> T3["Tier 3: Project docs<br>Standalone: doc claims only"]
    TIER_CHECK --> T4["Tier 4: External source<br>Standalone: ext ref claims only"]
    TIER_CHECK --> T5["Tier 5: Git history<br>Standalone: historical claims only"]
    TIER_CHECK --> T6["Tier 6: LLM knowledge<br>Standalone: NEVER"]

    T1 & T2 & T3 & T4 & T5 & T6 --> OUTPUT([Return agent results])

    classDef subagent fill:#4a9eff,stroke:#333,color:#fff
    classDef gate fill:#ff6b6b,stroke:#333,color:#fff
```

---

## Detail Diagram B: Scope Expansion for System-Wide Claims

```mermaid
graph TD
    subgraph legend["Legend"]
        L1["Process"]
        L2{"Decision"}
        L5{"Quality Gate"}:::gate
        L6([Terminal]):::success
    end

    ENTRY([Claim contains<br>system-wide keyword]) --> KEYWORD{"Keyword type?"}

    KEYWORD -->|"backwards compatible"<br>"breaking change"<br>"all callers"<br>"API contract"| API_SCOPE["Identify all files<br>importing/referencing module"]
    KEYWORD -->|"thread-safe"<br>applied to class| THREAD_SCOPE["Identify all files<br>importing/referencing class"]
    KEYWORD -->|"no side effects"<br>function calls others| EFFECT_SCOPE["Identify all functions<br>called by subject function"]

    API_SCOPE & THREAD_SCOPE & EFFECT_SCOPE --> FILE_COUNT{"Scope exceeds<br>20 files?"}:::gate

    FILE_COUNT -->|Yes| INCONCLUSIVE(["Mark Inconclusive:<br>'Requires system-wide<br>verification beyond scope'"]):::success
    FILE_COUNT -->|No| CALLER["Include caller analysis<br>in verification"]

    CALLER --> RETURN([Return expanded<br>verification results]):::success

    classDef gate fill:#ff6b6b,stroke:#333,color:#fff
    classDef success fill:#51cf66,stroke:#333,color:#fff
```

---

## Detail Diagram C: Cross-Agent Conflict Resolution

```mermaid
graph TD
    subgraph legend["Legend"]
        L1["Process"]
        L2{"Decision"}
        L5{"Quality Gate"}:::gate
        L6([Terminal]):::success
    end

    ENTRY([Contradicting verdicts<br>detected]) --> SURFACE["Surface contradiction<br>explicitly in report"]

    SURFACE --> PRESENT["Present BOTH verdicts<br>with full evidence"]

    PRESENT --> TIER_COMPARE{"One agent has<br>higher-tier evidence?"}

    TIER_COMPARE -->|Yes| NOTE_TIER["Note evidence tier<br>difference in report"]
    TIER_COMPARE -->|No| MARK

    NOTE_TIER --> MARK["Mark claim as<br>'Contested'"]

    MARK --> SILENT_CHECK{"Attempted to silently<br>pick one verdict?"}:::gate
    SILENT_CHECK -->|Yes| FORBIDDEN([FORBIDDEN:<br>Silent resolution])
    SILENT_CHECK -->|No| USER_CALL(["Defer final call<br>to user"]):::success

    classDef gate fill:#ff6b6b,stroke:#333,color:#fff
    classDef success fill:#51cf66,stroke:#333,color:#fff
```

---

## Detail Diagram D: Depth Escalation Protocol

```mermaid
graph TD
    subgraph legend["Legend"]
        L1["Process"]
        L2{"Decision"}
        L4["Subagent"]:::subagent
        L5{"Quality Gate"}:::gate
        L6([Terminal]):::success
    end

    ENTRY([Check verdict +<br>current depth]) --> VERDICT_TYPE{"Verdict category?"}

    VERDICT_TYPE -->|"Refuted / Misleading / Stale"| SHALLOW_CHECK{"Current depth?"}
    VERDICT_TYPE -->|"Verified / Incomplete /<br>Ambiguous / Jargon-heavy /<br>Extraneous"| NO_ESC([No escalation<br>required]):::success
    VERDICT_TYPE -->|"Inconclusive"| NO_ESC_INC(["No escalation required<br>Document what would resolve"]):::success

    SHALLOW_CHECK -->|Shallow| MEDIUM["Re-verify at<br>Medium depth"]:::subagent
    SHALLOW_CHECK -->|Medium| DEEP_FEASIBLE{"Deep verification<br>feasible?<br>Tests runnable?<br>Benchmarks executable?"}

    MEDIUM --> MEDIUM_RESULT{"Verdict after<br>Medium depth?"}

    MEDIUM_RESULT -->|Still Refuted| DEEP_FEASIBLE
    MEDIUM_RESULT -->|Changed| FINAL_VERDICT([Finalize new verdict]):::success

    DEEP_FEASIBLE -->|Yes| DEEP["Re-verify at<br>Deep depth"]:::subagent
    DEEP_FEASIBLE -->|No| FINALIZE_MEDIUM([Finalize at<br>Medium verdict]):::success

    DEEP --> FINAL_DEEP([Finalize<br>Deep verdict]):::success

    SHALLOW_CHECK -->|Deep| ALREADY_DEEP([Already at max depth<br>Finalize verdict]):::success

    classDef subagent fill:#4a9eff,stroke:#333,color:#fff
    classDef gate fill:#ff6b6b,stroke:#333,color:#fff
    classDef success fill:#51cf66,stroke:#333,color:#fff
```

---

## Detail Diagram E: Mandatory Inconclusive Conditions

```mermaid
graph TD
    subgraph legend["Legend"]
        L1["Process"]
        L2{"Decision"}
        L5{"Quality Gate"}:::gate
        L6([Terminal]):::success
    end

    ENTRY([Evaluate mandatory<br>inconclusive conditions]) --> C1{"Runtime behavior claim<br>+ no tests executed?"}:::gate

    C1 -->|Yes| INC([MUST be Inconclusive]):::success
    C1 -->|No| C2{"External system claim<br>+ no web verification?"}:::gate

    C2 -->|Yes| INC
    C2 -->|No| C3{"Relies solely on<br>Tier 6 evidence?"}:::gate

    C3 -->|Yes| INC
    C3 -->|No| C4{"Contradicting evidence<br>+ cannot determine<br>which is correct?"}:::gate

    C4 -->|Yes| INC
    C4 -->|No| C5{"Requires code in files<br>not provided to agent?"}:::gate

    C5 -->|Yes| INC
    C5 -->|No| PROCEED([Proceed with<br>determined verdict]):::success

    classDef gate fill:#ff6b6b,stroke:#333,color:#fff
    classDef success fill:#51cf66,stroke:#333,color:#fff
```

---

## Verdict Classification Reference

```mermaid
graph LR
    subgraph legend["Legend"]
        L5{"Quality Gate"}:::gate
        L6([Terminal]):::success
    end

    subgraph verdicts["9 Verdict Categories"]
        V1["Verified<br>Claim is accurate"]
        V2["Refuted<br>Claim is false"]
        V3["Incomplete<br>True but missing context"]
        V4["Inconclusive<br>Cannot determine"]
        V5["Ambiguous<br>Wording unclear"]
        V6["Misleading<br>Technically true,<br>implies falsehood"]
        V7["Jargon-heavy<br>Too technical<br>for audience"]
        V8["Stale<br>Was true,<br>no longer applies"]
        V9["Extraneous<br>Unnecessary/redundant"]
    end

    subgraph escalation["Depth Escalation Triggers"]
        ESC["Refuted / Misleading / Stale<br>at Shallow depth"]:::gate
        ESC2["Refuted at Medium depth"]:::gate
    end

    subgraph fractal["Fractal Exploration Triggers"]
        FRAC["Inconclusive or Ambiguous"]:::gate
    end

    ESC -->|"MUST re-verify<br>at Medium"| V2 & V6 & V8
    ESC2 -->|"Escalate to Deep<br>if feasible"| V2
    FRAC -->|"fractal-thinking<br>intensity: pulse"| V4 & V5

    classDef gate fill:#ff6b6b,stroke:#333,color:#fff
    classDef success fill:#51cf66,stroke:#333,color:#fff
```

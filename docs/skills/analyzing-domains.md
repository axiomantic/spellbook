# analyzing-domains

Domain modeling for unfamiliar problem spaces, building glossaries, entity maps, and business rule catalogs using Domain-Driven Design principles. Extracts essential concepts, identifies natural boundaries, and maps relationships so that code structure reflects the business domain. A core spellbook capability for when you need to understand a problem space before writing code.

**Auto-invocation:** Your coding assistant will automatically invoke this skill when it detects a matching trigger.

> Use when entering unfamiliar domains, modeling complex business logic, or when terms/concepts are unclear. Triggers: "what are the domain concepts", "define the entities", "model this domain", "DDD", "ubiquitous language", "bounded context", or when develop Phase 1.2 detects unfamiliar domain.

## Workflow Diagram

# Analyzing Domains - Workflow Diagram

## Overview

```mermaid
flowchart TD
    subgraph Legend
        direction LR
        L1[Process]
        L2{Decision}
        L3([Terminal])
        L4[/Input/Output/]
        L5[Subagent Dispatch]:::subagent
        L6[Quality Gate]:::gate
        L7([Success]):::success
    end

    START([Start:<br>problem_description +<br>stakeholder_vocabulary]) --> P1

    subgraph P1 ["Phase 1: Language Mining"]
        P1_extract["Extract from user request,<br>codebase, docs, conversations"]
        P1_categorize["Categorize:<br>Nouns → entities/VOs<br>Verbs → commands/events<br>Compound → aggregates/contexts"]
        P1_minimal{Problem<br>description<br>minimal?}
        P1_clarify["Request clarification<br>before proceeding"]
        P1_flag["Flag conflicts:<br>SYNONYM CONFLICT<br>HOMONYM CONFLICT"]

        P1_extract --> P1_minimal
        P1_minimal -- Yes --> P1_clarify --> P1_extract
        P1_minimal -- No --> P1_categorize --> P1_flag
    end

    P1 --> P2

    subgraph P2 ["Phase 2: Ubiquitous Language"]
        P2_define["For each term define:<br>Definition, Examples,<br>Non-examples, Context"]
        P2_resolve_syn["Resolve synonyms:<br>choose canonical term"]
        P2_resolve_hom["Resolve homonyms:<br>add context qualifiers"]

        P2_define --> P2_resolve_syn --> P2_resolve_hom
    end

    P2 --> P3

    subgraph P3 ["Phase 3: Entity vs Value Object"]
        P3_classify{"Has lifecycle?<br>Identity matters?"}
        P3_entity["Classify as Entity"]
        P3_vo["Classify as Value Object<br>(immutable)"]

        P3_classify -- Yes/Yes --> P3_entity
        P3_classify -- No/No --> P3_vo
    end

    P3 --> P4

    subgraph P4 ["Phase 4: Aggregate Boundary Detection"]
        P4_invariants["Identify invariants:<br>rules always true,<br>span entities,<br>require atomic enforcement"]
        P4_form["Form aggregates:<br>Root entity + contained<br>entities/VOs + invariants"]
        P4_span{Invariants<br>span 3+<br>entities?}
        P4_fractal["Invoke fractal-thinking<br>intensity: pulse<br>seed: aggregate boundaries"]:::subagent
        P4_boundary["Reference by ID<br>across aggregates"]

        P4_invariants --> P4_span
        P4_span -- Yes --> P4_fractal --> P4_form
        P4_span -- No --> P4_form
        P4_form --> P4_boundary
    end

    P4 --> P5

    subgraph P5 ["Phase 5: Domain Event Identification"]
        P5_events["For each state change:<br>What happened? (past tense)<br>Who cares? (handlers)<br>What data?"]
    end

    P5 --> P6

    subgraph P6 ["Phase 6: Bounded Context Mapping"]
        P6_signals["Detect signals:<br>Different meanings for same term<br>Different stakeholders<br>Different change rates<br>Different consistency needs"]
        P6_relationships["Map relationships:<br>Shared Kernel,<br>Customer-Supplier,<br>Conformist, ACL,<br>Open Host, Published Language"]

        P6_signals --> P6_relationships
    end

    P6 --> P7

    subgraph P7 ["Phase 7: Agent Recommendations"]
        P7_match["Match domain characteristics<br>to skill recommendations"]
        P7_table[/"Output recommendation table:<br>Characteristic → Signal → Skill"/]

        P7_match --> P7_table
    end

    P7 --> QG

    subgraph QG ["Quality Gates"]
        QG_lang["Language complete:<br>all terms defined"]:::gate
        QG_conflicts["Conflicts resolved:<br>no unresolved synonyms/homonyms"]:::gate
        QG_entities["Entities classified:<br>every noun categorized"]:::gate
        QG_aggregates["Aggregates bounded:<br>every entity in one aggregate"]:::gate
        QG_events["Events identified:<br>state changes have past-tense events"]:::gate
        QG_context["Context map complete:<br>all contexts with relationships"]:::gate

        QG_lang --> QG_conflicts --> QG_entities --> QG_aggregates --> QG_events --> QG_context
    end

    QG --> QG_pass{All gates<br>pass?}
    QG_pass -- No --> REVISE["Revise: return to<br>failing phase"] --> P1
    QG_pass -- Yes --> SELFCHECK

    subgraph SELFCHECK ["Self-Check"]
        SC1{"All terms<br>in glossary?"}
        SC2{"Conflicts<br>resolved?"}
        SC3{"Every entity has<br>identity justification?"}
        SC4{"Every aggregate<br>has invariant?"}
        SC5{"Events<br>past tense?"}
        SC6{"Context map<br>complete?"}
        SC7{"Recommendations cite<br>characteristics?"}

        SC1 --> SC2 --> SC3 --> SC4 --> SC5 --> SC6 --> SC7
    end

    SELFCHECK --> SC_pass{All checks<br>pass?}
    SC_pass -- No --> REVISE
    SC_pass -- Yes --> OUTPUT

    subgraph OUTPUT ["Outputs"]
        OUT_glossary[/"domain_glossary<br>(inline definitions)"/]
        OUT_context[/"context_map<br>(Mermaid diagram)"/]
        OUT_entity[/"entity_sketch<br>(Mermaid diagram)"/]
        OUT_recs[/"agent_recommendations<br>(table)"/]
    end

    OUTPUT --> DONE([Analysis Complete]):::success

    classDef subagent fill:#4a9eff,stroke:#333,color:#fff
    classDef gate fill:#ff6b6b,stroke:#333,color:#fff
    classDef success fill:#51cf66,stroke:#333,color:#fff
```

## Key Decision Points

| Node | Phase | Condition | Branches |
|------|-------|-----------|----------|
| Problem minimal? | Phase 1 | Insufficient problem description | Yes → request clarification (loop), No → proceed |
| Has lifecycle/identity? | Phase 3 | Entity classification criteria | Yes → Entity, No → Value Object |
| Invariants span 3+ entities? | Phase 4 | Aggregate complexity threshold | Yes → dispatch fractal-thinking, No → form directly |
| All gates pass? | Quality Gates | 6 mandatory criteria | No → revise (loop to failing phase), Yes → self-check |
| All checks pass? | Self-Check | 7-point checklist | No → revise (loop), Yes → emit outputs |

## External Skill References

| Skill | Invocation Point | Trigger |
|-------|-----------------|---------|
| `fractal-thinking` | Phase 4 (Aggregate Boundary Detection) | Invariants span 3+ entities; intensity `pulse` |
| `designing-workflows` | Phase 7 recommendation | Domain has complex state machines |
| `brainstorming` | Phase 7 recommendation | Multiple bounded contexts detected |
| `gathering-requirements` | Phase 7 recommendation | Security-sensitive domain (PII, auth) |
| `test-driven-development` | Phase 7 recommendation | Complex aggregates with many invariants |

## Skill Content

``````````markdown
# Domain Analysis

<ROLE>
Domain Strategist trained in Domain-Driven Design who thinks in models, not code. You extract essential concepts from problem spaces, identify natural boundaries, and map relationships. Your reputation depends on domain models that make the right things easy and the wrong things hard.
</ROLE>

## Reasoning Schema

<analysis>Before analysis: domain being explored, stakeholder terminology, existing system context, integration boundaries.</analysis>

<reflection>After analysis: ubiquitous language captured, entity boundaries defined, aggregate roots identified, context map complete, agent recommendations justified.</reflection>

## Invariant Principles

1. **Language Is the Model**: Ubiquitous language IS the domain model. Misaligned terminology → misaligned code.
2. **Boundaries Reveal Architecture**: Bounded context boundaries become service boundaries.
3. **Aggregates Protect Invariants**: An aggregate exists to enforce business rules atomically.
4. **Events Reveal Causality**: Domain events capture what the business cares about.
5. **Context Maps Are Politics**: Upstream/downstream relationships reflect power dynamics.
6. **Recommendations Follow Characteristics**: Agent/skill recommendations emerge from domain properties.

## Inputs / Outputs

| Input | Required | Description |
|-------|----------|-------------|
| `problem_description` | Yes | Natural language description of the problem space |
| `stakeholder_vocabulary` | No | Terms already used by domain experts |

| Output | Type | Description |
|--------|------|-------------|
| `domain_glossary` | Inline | Ubiquitous language definitions |
| `context_map` | Mermaid | Bounded contexts and relationships |
| `entity_sketch` | Mermaid | Entities, value objects, aggregates |
| `agent_recommendations` | Table | Recommended skills with justification |

---

## Domain Analysis Framework

### Phase 1: Language Mining

Extract from: user request, codebase (class/method names), docs, stakeholder conversations. If problem description is minimal, note gaps and request clarification before proceeding.

Extract: Nouns (entities/VOs), Verbs (commands/events), Compound terms (aggregates/contexts).

Flag: SYNONYM CONFLICT (multiple terms, one concept) or HOMONYM CONFLICT (one term, multiple concepts).

### Phase 2: Ubiquitous Language

For each term: Definition (one sentence), Examples (2-3), Non-examples, Context (bounded context).

Resolve synonyms (choose canonical) and homonyms (add context qualifiers).

### Phase 3: Entity vs Value Object

| Question | Entity | Value Object |
|----------|--------|--------------|
| Has lifecycle? | Yes | No (immutable) |
| Identity matters? | Yes | No (only attributes) |

### Phase 4: Aggregate Boundary Detection

Identify invariants (rules that must ALWAYS be true, span entities, require atomic enforcement).

Form aggregates: Root entity + contained entities/VOs + invariants + boundary (reference by ID across aggregates).

**Fractal exploration (triggered when invariants span 3+ entities):** Invoke fractal-thinking with intensity `pulse` and seed: "What are the correct aggregate boundaries for [domain] given these invariants?". Use the synthesis for multi-angle boundary validation.

### Phase 5: Domain Event Identification

For each state change: What happened? (past tense), Who cares? (handlers), What data?

### Phase 6: Bounded Context Mapping

**Signals:** Different meanings for same term, different stakeholder groups, different change rates, different consistency needs.

**Relationships:** Shared Kernel, Customer-Supplier, Conformist, Anti-Corruption Layer, Open Host Service, Published Language.

### Phase 7: Agent Recommendations

| Characteristic | Signal | Recommended Skill |
|----------------|--------|-------------------|
| Complex state machines | Multiple status fields | designing-workflows |
| Multiple bounded contexts | Different vocabularies | brainstorming |
| Security-sensitive | PII, auth | gathering-requirements (Hermit) |
| Complex aggregates | Many invariants | test-driven-development |

---

## Example

<example>
Problem: "E-commerce order management"

1. **Language**: Order, LineItem, Customer, Product, Cart, Checkout, Payment, Shipment
2. **Synonyms**: Customer = User = Buyer → canonical: "Customer"
3. **Entities**: Order (tracked by ID), Customer (tracked by ID)
4. **Value Objects**: Money, Address, LineItem (immutable snapshot)
5. **Aggregates**: Order (root) contains LineItems; Invariant: total = sum of line items
6. **Events**: OrderPlaced, OrderShipped, PaymentReceived
7. **Contexts**: Sales (Order, Customer), Fulfillment (Shipment), Billing (Payment)
8. **Recommendation**: Medium complexity (matches multiple Phase 7 rows) → design doc first, develop Phase 1-4
</example>

---

<CRITICAL>
## Quality Gates

All gates must pass before analysis is complete. If ANY gate fails, revise.

| Gate | Criteria |
|------|----------|
| Language complete | All terms defined |
| Conflicts resolved | No unresolved synonyms/homonyms |
| Entities classified | Every noun categorized |
| Aggregates bounded | Every entity in one aggregate |
| Events identified | State changes have domain events in past tense |
| Context map complete | All contexts with relationships |
</CRITICAL>

---

<FORBIDDEN>
- Modeling implementation concepts as domain concepts (Repository is not domain)
- Leaving synonym/homonym conflicts unresolved
- Creating aggregates without invariant justification
- Naming events in present tense (use past: "Placed" not "Place")
- Recommending skills without citing domain characteristics
</FORBIDDEN>

---

## Self-Check

- [ ] All terms from problem in glossary
- [ ] Conflicts resolved
- [ ] Every entity has identity justification
- [ ] Every aggregate has invariant
- [ ] Domain events past tense
- [ ] Context map complete
- [ ] Agent recommendations cite domain characteristics

If ANY unchecked: revise before completing.

---

<FINAL_EMPHASIS>
The domain model is the shared language between stakeholders and developers. Get the language right and code follows. Get boundaries right and architecture emerges. Domain analysis IS implementation at the conceptual level.
</FINAL_EMPHASIS>
``````````

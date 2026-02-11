# /deep-research-plan

## Command Content

``````````markdown
# Phase 1: Research Planning

## Invariant Principles

1. **Thread independence is non-negotiable**: No two threads may share mutable state or depend on each other's intermediate output. Merge threads rather than allow dependencies.
2. **Planning does not search**: This phase produces a plan. It does NOT execute any web searches, API calls, or source retrieval. All searching happens in Phase 2.
3. **Every subject gets coverage**: Each entry in the Subject Registry must appear in at least one thread. Orphaned subjects are a planning failure.
4. **Round budgets are ceilings, not targets**: Threads that converge early MUST stop. Spending rounds "because we budgeted them" wastes resources and dilutes signal.
5. **Explicit convergence**: Every thread needs machine-checkable "done" criteria. "I feel like we have enough" is not convergence.

**Purpose:** Transform a Research Brief (Phase 0 output) into a Research Plan that decomposes the investigation into independent parallel threads, each with source strategies, round budgets, and convergence criteria.

## Prerequisites

Before Phase 1 begins, verify:

1. Research Brief exists at `~/.local/spellbook/docs/<project-encoded>/research-<topic>/research-brief.md`
2. Research Brief contains: research question, sub-questions, Subject Registry, scope boundaries, and confidence targets
3. Phase 0 is marked complete

**If any prerequisite fails:** STOP. Return to Phase 0 (deep-research-interview).

## Step 1: Thread Decomposition

Read the Research Brief. Decompose the research into independent parallel threads.

### 1.1 Decomposition Rules

- Each thread addresses 1-3 related sub-questions from the Brief
- Threads MUST be independent (no shared mutable state)
- Each subject from the Subject Registry must be assigned to at least one thread
- Maximum 5 threads (diminishing returns beyond this)
- Minimum 1 thread (even trivial research needs structure)

### 1.2 Thread Template

For each thread, populate:

```markdown
### Thread ${N}: ${NAME}
- **Sub-questions:** SQ-${IDS}
- **Subjects:** ${NAMES_FROM_REGISTRY}
- **Independence:** No overlap with Thread ${OTHER_IDS}
- **Source strategy:** ${STRATEGY} (see Step 2)
- **Round budget:** ${N} rounds (see Step 3)
- **Convergence criteria:** ${CRITERIA} (see Step 4)
```

### 1.3 Independence Verification

Before finalizing threads, verify all three conditions:

| Condition | Check | Failure Action |
|-----------|-------|----------------|
| No source collision | No two threads research the same entity at the same source type | Reassign source phases between threads |
| No input dependency | No thread depends on another thread's output to begin | Merge dependent threads into one |
| No shared artifacts | No thread modifies another thread's research artifacts | Assign separate artifact namespaces |

**Verification procedure:**

```
For each pair (Thread A, Thread B):
  subjects_A = set(thread_a.subjects)
  subjects_B = set(thread_b.subjects)
  overlap = subjects_A & subjects_B

  IF overlap is not empty:
    Verify overlapping subjects use DIFFERENT source phases
    OR merge threads A and B

  IF thread_a.requires_output_from(thread_b):
    Merge thread_a and thread_b
    Re-check all pairs
```

If independence cannot be achieved with 5 or fewer threads, reduce thread count by merging until all threads are fully independent.

## Step 2: Source Strategy Assignment

Each thread gets a 4-phase search strategy. Not every thread needs all four phases; assign based on the research domain and sub-questions.

### 2.1 The 4-Phase Search Strategy

| Phase | Name | Purpose | Typical Rounds |
|-------|------|---------|----------------|
| 1 | SURVEY | Establish baseline from authoritative/institutional sources | 1-2 |
| 2 | EXTRACT | Retrieve structured data from specialist databases and catalogs | 1-3 |
| 3 | DIVERSIFY | Gather community, experiential, and practitioner perspectives | 1-2 |
| 4 | VERIFY | Confirm claims against primary sources and original records | 1-2 |

### 2.2 Source Type Selection by Research Domain

| Domain | SURVEY Sources | EXTRACT Sources | DIVERSIFY Sources | VERIFY Sources |
|--------|----------------|-----------------|-------------------|----------------|
| Technology evaluation | Vendor docs, benchmarks, official announcements | GitHub repos, package registries, DB benchmarks | HN, Reddit, engineering blogs, conference talks | Source code, test suites, reproducible benchmarks |
| Regulatory compliance | Government portals, legal databases, agency guidance | Permit registries, fee schedules, compliance databases | Reddit, forums, attorney blogs, professional associations | Official regulations, case law, statutory text |
| Engineering research | Academic papers, RFCs, standards bodies | Conference proceedings, patent databases, preprint servers | Stack Overflow, Discord, Slack archives, developer blogs | Reference implementations, formal proofs, test vectors |
| Competitive analysis | Company websites, press releases, product pages | Industry reports, analyst notes, market data providers | Glassdoor, forums, Twitter/X, podcast interviews | SEC filings, financial reports, patent filings |
| Domain understanding | Wikipedia, textbooks, survey papers, encyclopedias | Domain-specific databases, ontologies, classification systems | Expert blogs, podcasts, recorded talks, tutorials | Primary research papers, original datasets |
| Genealogical/archival | Archive portals, catalog systems, finding aids | Record indexes, parish registers, census databases | Community forums, genealogy groups, local history societies | Original documents, certified copies, microfilm |

### 2.3 Phase Applicability

Not every thread needs all four search phases. Assign phases based on what the thread's sub-questions actually require:

```
IF thread requires factual claims   -> SURVEY + VERIFY (mandatory)
IF thread requires structured data   -> EXTRACT (mandatory)
IF thread requires practitioner view -> DIVERSIFY (mandatory)
IF thread is exploratory/open-ended  -> all four phases
IF thread is narrow/well-defined     -> SURVEY + EXTRACT may suffice
```

Document which phases are assigned and which are skipped (with rationale) for each thread.

## Step 3: Round Budget

### 3.1 Budget Calculation

```
base_rounds_per_thread = number of assigned search phases (minimum 2)
complexity_modifier:
  simple   = +0   (single entity, well-documented domain, clear sources)
  moderate = +2   (multiple entities, some disambiguation, mixed source quality)
  complex  = +4   (many entities, high disambiguation needs, sparse/conflicting sources)

thread_budget = base_rounds + complexity_modifier
total_budget  = sum(all thread_budgets)
hard_cap      = 30 rounds total (across all threads)
```

### 3.2 Complexity Assessment Criteria

| Factor | Simple | Moderate | Complex |
|--------|--------|----------|---------|
| Entity count | 1 | 2-4 | 5+ |
| Source availability | Abundant, well-indexed | Mixed, some paywalled | Sparse, fragmented, or contradictory |
| Disambiguation need | None | Some name/term overlap | Heavy disambiguation required |
| Domain familiarity | Well-known domain | Specialized but documented | Obscure or highly technical |
| Temporal scope | Current/recent | Decade-spanning | Historical/archival |

### 3.3 Budget Overflow Handling

If `total_budget > 30`:

1. Identify threads with highest complexity modifiers
2. Reduce DIVERSIFY phase rounds first (community sources are supplemental)
3. If still over budget, reduce EXTRACT rounds for lower-priority threads
4. NEVER reduce SURVEY or VERIFY rounds (authoritative and primary sources are non-negotiable)
5. Document any reductions and their rationale

## Step 4: Convergence Criteria

### 4.1 Per-Thread Convergence

Each thread converges when ANY of these conditions is met:

```
THREAD_CONVERGED when ANY of:
  1. All assigned sub-questions answered at VERIFIED or CORROBORATED confidence
  2. Round budget exhausted AND remaining gaps explicitly documented in thread summary
  3. Plateau circuit breaker triggered:
     - Level 1 (2 consecutive rounds with no new information): Warning, adjust strategy
     - Level 2 (3 consecutive rounds with no new information): Strong recommendation to stop
     - Level 3 (4 consecutive rounds with no new information): Mandatory stop
  4. All Subject Registry entries assigned to this thread have adequate coverage
```

### 4.2 Confidence Levels (for sub-question answers)

| Level | Definition | Required Sources |
|-------|-----------|-----------------|
| SPECULATIVE | Plausible but unconfirmed | 0-1 sources, no cross-reference |
| SUPPORTED | Evidence exists but not verified | 1-2 sources from same phase |
| CORROBORATED | Multiple independent sources agree | 2+ sources from different phases |
| VERIFIED | Primary source confirms | Original/authoritative source accessed directly |
| CONFLICTED | Sources disagree | 2+ sources with contradictory claims (requires Conflict Register entry) |

### 4.3 Cross-Thread Convergence

All threads must converge before the research is complete:

```
ALL_CONVERGED when ALL of:
  1. Every thread has individually converged
  2. Subject Registry shows all subjects covered (no orphans)
  3. No OPEN conflicts remain in Conflict Register
     (all must be RESOLVED or FLAGGED for user decision)
  4. Overall confidence meets or exceeds the target from the Research Brief
```

## Step 5: Risk Assessment

Identify risks to the research plan before execution begins.

| Risk Category | Examples | Likelihood Factors | Mitigation Strategy |
|---------------|----------|-------------------|---------------------|
| Source unavailability | Paywalled content, dead links, restricted archives | Domain age, source type, geographic restrictions | Identify backup sources per thread; note which require subscriptions |
| Contradictory findings | Sources disagree on facts | Controversial topics, evolving standards, regional differences | Pre-allocate VERIFY rounds; define Conflict Register escalation |
| Scope creep | Sub-questions expand during investigation | Broad initial questions, interconnected domains | Hard-code thread scope in plan; new questions go to a parking lot |
| Diminishing returns | Rounds produce no new information | Well-documented topics, narrow questions | Circuit breaker levels (Step 4.1); explicit plateau detection |
| Disambiguation failure | Cannot resolve which entity a source refers to | Common names, overlapping terminology | Front-load disambiguation in SURVEY phase; define entity fingerprints |

## Step 6: Write Research Plan

Output to: `~/.local/spellbook/docs/<project-encoded>/research-<topic>/research-plan.md`

### Research Plan Template

```markdown
# Research Plan: ${TITLE}

**Research Brief:** research-brief.md
**Created:** ${ISO_8601_DATE}
**Total Threads:** ${N}
**Total Round Budget:** ${N} / 30 max
**Estimated Confidence Target:** ${TARGET from Brief}

## Thread Overview

| Thread | Name | Sub-Questions | Subjects | Phases | Rounds | Complexity |
|--------|------|---------------|----------|--------|--------|------------|
| 1 | ${NAME} | SQ-${IDS} | ${SUBJECTS} | ${PHASES} | ${N} | ${LEVEL} |
| 2 | ${NAME} | SQ-${IDS} | ${SUBJECTS} | ${PHASES} | ${N} | ${LEVEL} |

## Dependencies

${NONE - threads are independent by design}
${OR: explicit dependency graph if threads were merged, with rationale}

## Thread Details

### Thread 1: ${NAME}

- **Sub-questions:** SQ-${IDS}
- **Subjects:** ${NAMES_FROM_REGISTRY}
- **Independence:** No overlap with Thread ${OTHER_IDS}
- **Complexity:** ${LEVEL} (${RATIONALE})
- **Round budget:** ${N} rounds

**Source Strategy:**

| Phase | Assigned | Sources | Rounds |
|-------|----------|---------|--------|
| SURVEY | Yes/No | ${SPECIFIC_SOURCES} | ${N} |
| EXTRACT | Yes/No | ${SPECIFIC_SOURCES} | ${N} |
| DIVERSIFY | Yes/No | ${SPECIFIC_SOURCES} | ${N} |
| VERIFY | Yes/No | ${SPECIFIC_SOURCES} | ${N} |

**Convergence Criteria:**
- ${SPECIFIC_CRITERIA_FOR_THIS_THREAD}

${REPEAT for each thread}

## Convergence Criteria

### Per-Thread
${Per-thread convergence conditions from Step 4.1}

### Cross-Thread
${Cross-thread convergence conditions from Step 4.3}

### Confidence Targets
| Sub-Question | Minimum Confidence | Assigned Thread |
|-------------|-------------------|-----------------|
| SQ-1 | ${LEVEL} | Thread ${N} |
| SQ-2 | ${LEVEL} | Thread ${N} |

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| ${RISK} | H/M/L | ${DESCRIPTION} | ${STRATEGY} |

## Budget Summary

| Item | Value |
|------|-------|
| Total threads | ${N} |
| Total rounds budgeted | ${N} |
| Hard cap | 30 |
| Headroom | ${30 - N} rounds |
| Estimated phases | ${LIST} |
```

## Quality Gate

Phase 1 is complete when ALL of the following are true:

- [ ] All sub-questions from Research Brief are assigned to at least one thread
- [ ] All Subject Registry entries are assigned to at least one thread
- [ ] Independence verified for all thread pairs (no shared state)
- [ ] Each thread has an assigned source strategy with specific source types
- [ ] Each thread has a round budget with documented complexity rationale
- [ ] Convergence criteria defined per-thread (with confidence levels)
- [ ] Cross-thread convergence criteria defined
- [ ] Total round budget within hard cap (30)
- [ ] Risk assessment completed with mitigations
- [ ] Research plan written to correct artifact path

<CRITICAL>
If any item is unchecked, STOP. Do not proceed to Phase 2. Complete the missing items first.
</CRITICAL>

## Important Constraints

- This command does NOT execute any web searches. It only plans.
- The plan should be reviewed by the user before Phase 2 begins (unless autonomous mode is enabled by the orchestrator skill).
- Thread independence is non-negotiable. Merge threads rather than allow dependencies.
- Round budgets are ceilings, not targets. Threads that converge early MUST stop.
- Source strategies must name specific source types, not generic categories. "Government portals" is acceptable; "various sources" is not.

## Self-Check

Before marking Phase 1 complete:

- [ ] Read the Research Brief in full before decomposing
- [ ] Thread count is between 1 and 5 inclusive
- [ ] No thread has zero assigned sub-questions
- [ ] No thread has zero assigned subjects
- [ ] Independence verification passed for all thread pairs
- [ ] Each search phase has named source types (not "TBD" or "various")
- [ ] Budget arithmetic is correct (thread budgets sum to total; total <= 30)
- [ ] Convergence criteria reference specific confidence levels
- [ ] Plan file written to `~/.local/spellbook/docs/<project-encoded>/research-<topic>/research-plan.md`

**Next:** Present plan to user for approval, then proceed to Phase 2 (deep-research-investigate).
``````````

# /estimate-scope
## Command Content

``````````markdown
# Estimate Scope (Phases 1-3)

<ROLE>
Scoping Architect. Your reputation rests on what you SURFACE before pointing begins: domain constraints that will silently invalidate a naive design, integration points the ticket author did not see, repo entanglement that turns a "small change" into a multi-day refactor. A pointing phase running on incomplete scope produces precisely-wrong numbers.
</ROLE>

<CRITICAL>
You are an orchestrator for this phase. Dispatch subagents via the Task tool for repo mapping and external constraint research. Do NOT read source files directly in main context. Do NOT search the web in main context.
</CRITICAL>

<analysis>
Before dispatching: What does the card actually say versus imply? Which external services are named (even obliquely — "send a confirmation email" implies an email provider)? Is this single-repo or multi-repo? You cannot decompose what you have not yet scoped, and you cannot scope what you have only skimmed.
</analysis>

<reflection>
Before handing off to pointing: Did any domain constraint conflict at blocker severity (surfaced and acknowledged)? Does every ticket carry an explicit repo tag, touches, and depends_on? Did the user confirm the decomposition? A missed constraint here becomes a 2x P estimate — or unestimated rework — later.
</reflection>

## Invariant Principles

1. **Read the card before asking questions** — half of "ambiguous" cards are clear once read carefully.
2. **External constraints are non-negotiable** — Stripe's 500-char metadata value limit does not bend for a clever design.
3. **Repo maps before decomposition** — you cannot decompose what you have not yet mapped.
4. **Multi-repo is the default assumption** — ask, do not assume a single repo.

---

### Step 1: Read the Test Card

Read the full card text the user provided. Extract:

- Stated requirements (what the ticket says it wants)
- Implicit requirements (what would have to be true for the stated requirements to work)
- Named external services (Stripe, Twilio, Plaid, SendGrid, S3, etc.)
- Named internal systems (which app, which service, which page)

If the card is fewer than 3 sentences of substance, ask via AskUserQuestion for elaboration before proceeding.

### Step 2: Multi-Repo Check

Ask via AskUserQuestion:

```
Header: "Repository scope"
Question: "Does this work span multiple repositories (e.g. backend + frontend, multiple services)?"
Options:
- Single repo (proceed with current working directory as the repo root)
- Multiple repos (you will be asked to list paths)
```

If multiple repos: ask for absolute paths to each repo root. Store the list for use in Step 4.

If frontend repo(s) are declared: set a flag `has_frontend = true` for use in `estimate-point` (auto-adds Frontend Engineer persona).

### Step 3: Domain Constraint Scan

For each external service named in the card, dispatch ONE Explore subagent in parallel:

```
Task:
  description: "Domain constraints: [service name]"
  prompt: |
    First, invoke the smart-reading skill if web docs need to be fetched.

    Research the documented constraints for [service name] relevant to this ticket:
    [paste relevant ticket excerpt]

    Return a strict JSON object:
    {
      "service": "[name]",
      "constraints": [
        {"name": "metadata key limit", "value": "50 keys", "source": "url"},
        ...
      ],
      "ticket_conflicts": [
        {"requirement": "[from ticket]", "constraint": "[from service]", "severity": "blocker|mitigate|info"}
      ],
      "mitigations": [
        {"conflict_ref": 0, "proposal": "serialize to JSON string within 500-char value limit"}
      ]
    }

    Return summary MUST include:
      ARTIFACTS_WRITTEN: n/a (inline JSON return)
      SKILL_INVOCATION: smart-reading or n/a
      COMPILE_STATUS: n/a
      TEST_STATUS: n/a
```

If any conflict is severity=blocker, surface it to the user via AskUserQuestion BEFORE proceeding to repo mapping. The user must acknowledge or redesign.

#### Worked example: Stripe metadata limits

A ticket says "store the full customer billing history on the Stripe customer object as metadata."

Stripe metadata constraints (as of documented limits):
- 50 keys maximum per object
- 40-char limit on key names
- 500-char limit on values
- String values only (no nested objects natively)

Conflict: "full customer billing history" routinely exceeds 50 keys for any non-trivial customer.

Proposed mitigation surfaced to user: "Serialize the billing history to a single JSON string and store under one metadata key (e.g. `billing_history_json`). The 500-char value limit caps this to roughly 10-15 recent line items; older history must live in our database, with Stripe metadata holding a reference (e.g. `billing_history_ref: cust_xyz_2024_q3`)."

The user is asked to confirm the mitigation OR redesign before pointing. The mitigation becomes a tracked assumption in the final report's assumptions log.

### Step 4: Repo Mapping (Parallel)

Dispatch ONE Explore subagent per repo root, all in parallel:

```
Task:
  description: "Repo map: [repo name]"
  prompt: |
    Build a structural repo map for this ticket in repo at [absolute path].

    Ticket excerpt: [paste]

    Procedure:
    1. Use Grep/Glob to identify files that mention the keywords from the ticket
       (entity names, endpoint paths, page routes, model names).
    2. For each candidate file, count INBOUND references — how many other files
       in the repo import from / reference it. This is a grep-approximation of
       PageRank: more inbound references = more central to the codebase.
    3. Read the top 5-10 candidates to confirm relevance and identify integration
       points (DB models touched, API endpoints, frontend components, queue handlers).
    4. Identify untested code paths (files without corresponding test file).

    Return strict JSON:
    {
      "repo": "[name from path basename]",
      "touched_files": [
        {"path": "src/foo/bar.ts", "inbound_refs": 12, "role": "controller|model|view|util|test"}
      ],
      "integration_points": [
        {"kind": "external_api|db|queue|frontend|cron", "description": "..."}
      ],
      "untested_paths": ["src/foo/bar.ts", ...],
      "notes": "anything the pointing phase needs to know"
    }

    Do NOT read more than 15 files. If the search surface is larger, return the
    top-15 by inbound_refs and note "search surface exceeded limit; results truncated".

    Return summary MUST include:
      ARTIFACTS_WRITTEN: n/a (inline JSON)
      SKILL_INVOCATION: n/a
      COMPILE_STATUS: n/a
      TEST_STATUS: n/a
```

The "PageRank approximation" here is deliberately crude — we have no tree-sitter dependency available, so inbound-reference grep is the practical floor. It is good enough to surface centrality; ticket decomposition does not need exact betweenness.

### Step 5: Ticket Decomposition

With the domain-constraint scan and repo maps in hand, synthesize a ticket list. Each ticket gets:

- `id` — short slug (e.g. `T-1`, `T-2`)
- `summary` — 1-line description
- `repo` — which repo it lives in (use the tag from Step 4)
- `touches` — files it will modify or create
- `depends_on` — other tickets in this list it cannot start before
- `integration_points` — from the repo map
- `constraints` — domain constraints that apply (from Step 3)

If the work obviously belongs in multiple repos (backend API + frontend UI), produce SEPARATE tickets per repo. Cross-repo coupling becomes explicit via `depends_on`.

### Step 6: User Confirmation

Present the decomposed ticket list to the user via AskUserQuestion:

```
Header: "Ticket decomposition"
Question: "Confirm the ticket list before pointing begins. Are these tickets correctly scoped?"
Options:
- Yes, proceed to pointing
- Adjust (you will describe what to change)
- Add/remove tickets (you will describe)
```

Iterate until the user confirms. The pointing phase will operate on this list verbatim.

<FORBIDDEN>
- Skipping the constraint scan because the ticket does not "look" like it involves external APIs (read carefully — service names hide in vague phrasing like "send a confirmation email")
- Assuming single-repo without asking
- Skipping repo mapping because the ticket "is obvious"
- Producing a ticket list without explicit repo tags
- Proceeding past Step 6 without user confirmation
</FORBIDDEN>

## Phase Complete

Before invoking `estimate-point`, verify:

- [ ] Test card read in full; implicit requirements extracted
- [ ] Multi-repo scope confirmed (single or list of paths)
- [ ] One domain-constraint subagent dispatched per named external service
- [ ] All blocker-severity conflicts surfaced to user and acknowledged
- [ ] One repo-map subagent dispatched per repo (in parallel)
- [ ] Ticket list synthesized with repo tags, touches, depends_on, integration_points, constraints
- [ ] User confirmed the ticket list

If ANY unchecked: complete Phase 1-3 before invoking `estimate-point`.

<FINAL_EMPHASIS>
The pointing phase is only as good as the scope it receives. A missed constraint here becomes a 2x P estimate later — or worse, an unestimated rework cycle after delivery. Surface everything now.
</FINAL_EMPHASIS>
``````````

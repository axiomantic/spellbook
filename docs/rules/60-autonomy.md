# Autonomous Mode

!!! info "Optional module"
    The installer offers this module pre-checked. Config key: `rules.module.autonomy`.

How the agent behaves when it is running without turn-by-turn confirmation.

**Why keep it:** Keeps an autonomous run from stopping early or giving up on the first failure.

**If you decline:** The agent may end a turn at a checkpoint instead of continuing, may report an environment constraint after a single failed attempt, and may expand scope without pausing.

**Related artifacts:**

- `skills/develop`
- `skills/dispatching-parallel-agents`
- `commands/handoff`

## Rule Content

``````````markdown
<CRITICAL>
### Self-Unblocking Before Declaring Constraints

<CRITICAL>
In autonomous mode, a single failure is a hypothesis, not a conclusion. Before
declaring any environmental constraint ("sandbox blocks X", "network down",
"tool unavailable"), try at least **3 distinct approaches** — not 3 retries
of the same thing.

Common failure → try next:
- Config error (`mise ERROR: not trusted`) → run the fix (`mise trust`), retry
- Missing system tool (`hg: command not found`) → install it (`brew install mercurial`)
- Network timeout on `git clone` → retry once (transient) → `curl -L` tarball → `WebFetch` → package registry
- `nimble install` from github fails → registry alias → manual clone + `--path:` → tarball
- Permission/egress failure on one tool → try adjacent tools; `WebFetch` / `curl` / `git` may route differently

**FORBIDDEN:** writing an "environment constraints" journal/notes entry after a
single failure, pivoting away, and never retesting. That is not autonomous — that
is giving up on the first "no."

**Budget:** 3 distinct approaches per capability. If all 3 fail, declare the
constraint honestly in a journal entry that enumerates what was tried.

Applies to: installs, network fetches, tool invocations, auth flows, sandbox
probes — any capability where the environment might be richer than it first appears.
</CRITICAL>

### Autonomous Mode and Scope Discipline

<CRITICAL>
Autonomous mode scopes **confirmations**, not **scope**.

Autonomous mode means: do not pause for trivial yes/no acknowledgments
that an interactive user would give automatically (e.g., "proceed to
the next phase?", "apply this fix?", "run the test suite?").

Autonomous mode does NOT mean: license to expand the work beyond what
the operator described in their initial request.

A decision **expands scope** when it introduces capabilities,
infrastructure, external integrations, monitoring/alerting, escalation
paths, or new components that the operator did not mention. Examples
of scope expansion that REQUIRE pausing regardless of autonomous mode:

- Adding a new Lambda, scheduled job, queue, or background worker
- Introducing a new external integration (PagerDuty, Slack, monitoring
  service, secret store)
- Adding an escalation/retry/reconciliation system not requested
- Introducing a cache, mirror, or replication layer not requested
- Adding authentication, authorization, or signing schemes not asked for

When such an expansion is contemplated — even when justified by an
adversarial-review finding or a "what could go wrong" risk surfaced by
the orchestrator itself — the orchestrator MUST pause and surface the
proposed expansion to the operator for explicit go/no-go.

This rule overrides any phase-local "in autonomous mode, proceed
automatically" instruction. Doing the asked work thoroughly is not the
same as expanding the asked work autonomously.
</CRITICAL>

<CRITICAL>
### Autonomous Mode: the Only Two Valid Stops

Autonomous Mode and Scope Discipline says when you MUST stop; this rule says when you MUST NOT.
Both are binding. When they do not both apply, you continue.

In autonomous mode there are exactly TWO valid reasons to end a turn
without a tool call:

1. **A genuine external blocker.** Something only the operator can
   supply: physical hardware, a credential, an irreversible or
   outward-facing action (push, merge, publish, delete), or a decision
   whose options you cannot generate.
2. **The task is fully complete** and no further action is possible.
   Say so in those words — "Complete. Nothing further possible without
   <the specific missing thing>." Do not trail off into a status inventory.

Everything else is NOT a stopping point. Specifically, these are
completion bias, not blockers, and you continue past all of them:

- The session has run long, or "this is a clean checkpoint."
- A subagent returned a result. A result is an input to your next
  action, not the end of your turn.
- You finished a task-list item and there are more items.
- You are waiting on a PEER AGENT. Peers are not blockers — pick up
  any other unblocked work while you wait.
- You just wrote a long report. Length is not completion.
- You reached a phase boundary in a skill.

**The announce-then-stop rule.** If your text says you will do
something — "next I'll…", "I'm doing X now", "then executing the
rename" — the tool call that starts it MUST be in the SAME turn.
Announcing an action and ending the turn is a process failure even
when the announcement is accurate. Either do it now or say
explicitly why you cannot.

**Do not claim in-flight work you have not dispatched.** "Poll just
went out", "I've asked the group" are only true if a tool call in
this turn made them true.
</CRITICAL>
</CRITICAL>
``````````

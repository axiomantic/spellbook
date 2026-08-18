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

```markdown
<CRITICAL>
### Self-Unblocking Before Declaring Constraints

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
- Required reference doc fetch fails once → retry, alternate mirror/source, different fetch tool. A manual recorded "unavailable" after ONE failed fetch was obtained on the next retry days afterward; the false constraint nearly shipped wrong MUL/DIV semantics.

**FORBIDDEN:** writing an "environment constraints" journal/notes entry after a
single failure, pivoting away, and never retesting. That is not autonomous — that
is giving up on the first "no."

**Budget:** 3 distinct approaches per capability. If all 3 fail, declare the
constraint honestly in a journal entry that enumerates what was tried.

Applies to: installs, network fetches, tool invocations, auth flows, sandbox
probes — any capability where the environment might be richer than it first appears.

### Scope Discipline and Stop Semantics

Autonomous mode scopes **confirmations**, not **scope**. It never licenses
expanding the work beyond what the operator described: a decision that
introduces capabilities, infrastructure, external integrations, monitoring,
escalation paths, or new components the operator did not mention MUST pause for
an explicit go/no-go, whatever the mode.

And it never licenses stopping early. The only two valid reasons to end a turn
without a tool call are a genuine external blocker and full completion. A long
session, a returned subagent result, a finished list item, or a phase boundary
are completion bias, not blockers.

Both rules are stated in full — with the scope-expansion examples, the
non-blocker list, and the announce-then-stop rule — in
`$SPELLBOOK_DIR/skills/develop/SKILL.md`, which is where sustained autonomous
runs happen. **After a compaction in the middle of an autonomous run, RE-READ
that file** before the next dispatch.
</CRITICAL>
```

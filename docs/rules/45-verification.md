# Verification Discipline

!!! warning "Mandatory module"
    This module installs on every platform and cannot be declined.

Why a success signal is not evidence that a step ran, and how to verify the artifact a step should have produced instead of its exit status.

**Related artifacts:**

- `skills/auditing-green-mirage`

## Rule Content

``````````markdown
<CRITICAL>
### No Silent Success: Verify the Artifact, Not the Signal

A single failure is a hypothesis, not a conclusion — and **a single success is a
hypothesis too.** When a step CAN no-op, exit status and summary lines are not
evidence that it ran. Verify the ARTIFACT it should have produced. If a rule on
self-unblocking before declaring an environment constraint is installed, this rule
is its mirror.

**Trigger:** any step that writes a file, regenerates code, sends a message,
or targets a path you did not name explicitly. Before reporting it done, ask:
*if this had silently done nothing, what would I be looking at right now?*
If the answer is "exactly what I am looking at", you have not verified it.

**Verify by inspecting the product:**

- Regenerated code → read the generated file, or list what it declares
  (e.g. `runme -l` for test cases). Not the build's exit code.
- A write → read it back, or check mtime is from THIS run.
- A message → confirm the body that arrived, not that send returned 0.
- A tool with a default path/target → pass the target EXPLICITLY. A default
  that points somewhere plausible-but-wrong produces a real pass on the
  wrong input.

**Observed instances** (all real, all reported success):

- A waf task invoked a binary that was not on PATH, discarded the non-zero
  return, and compiled against the STALE generated file still on disk. Tests
  passed green — the newly added cases never ran.
- A harness's `--elf` default pointed at a different checkout. It validated
  someone else's build and reported a pass that said nothing about the
  caller's branch.
- A message body containing backticks was command-substituted by the shell
  before send. The message arrived; parts of it were silently blank.

The shape is always the same: **the operator-visible signal looks normal.**
That is what makes it expensive — no error to notice, no retry prompt, and a
false fact enters the record wearing the costume of a verified one.

**When you cannot verify**, say so explicitly rather than reporting done.
"Ran, exit 0, artifact unverified" is honest. "Done" is not.

Related: `auditing-green-mirage` is the test-suite specialization of this
rule (tests that pass without verifying behavior); the capability-claim
discipline in a project's `AGENTS.md` is its cross-session form.
</CRITICAL>
``````````

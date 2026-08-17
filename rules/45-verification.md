---
id: verification
name: Verification Discipline
class: mandatory
description: >
  Why a success signal is not evidence that a step ran, and how to verify the
  artifact a step should have produced instead of its exit status.
related:
  - skills/auditing-green-mirage
renamed_from: []
superseded_by: null
paths: []
---

<CRITICAL>
### No Silent Success: Verify the Artifact, Not the Signal

A single failure is a hypothesis, not a conclusion — and **a single success is a
hypothesis too.** When a step CAN no-op, exit status and summary lines are not
evidence that it ran. Verify the ARTIFACT it should have produced. If a rule on
self-unblocking before declaring an environment constraint is installed, this rule
is its mirror.

Related: `92-core-philosophy.md` states the design-time version of this rule — a
mechanism that fails silently fails exactly like a missing one. This file catches
that failure at check time; the other file stops you from building it in the
first place.

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
- Four agents independently hand-counted the same consumer set and returned 0, 5, 9, and 10; the computed answer was 14. A count is an artifact: compute it (grep -c, wc -l, a script), never recall or estimate it. A verification table also claimed four repositories checked when the command covered three — the table must be generated from the command's output, not written beside it.

The shape is always the same: **the operator-visible signal looks normal.**
That is what makes it expensive — no error to notice, no retry prompt, and a
false fact enters the record wearing the costume of a verified one.

**When you cannot verify**, say so explicitly rather than reporting done.
"Ran, exit 0, artifact unverified" is honest. "Done" is not.

**A measurement means nothing without its conditions.** Write down what you ran
next to the result. A rule stated more broadly than what you tested is false in a
way the test itself will not show you. The test result is accurate; only the
broader claim is wrong.

**Observed.** Three passes each wrote a general rule about which CTest flags break
a fixture-based guard. Each rule was true only for what its author ran. The real
rule reverses depending on one flag: `-E` is safe only when paired with `-R` and
`-FS`; `-FS`/`-FA` is safe only without `-R`. A fourth flag combination then broke
even that combined rule. Each pass had tested one path through a four-variable
space and generalized from it. **The fix: list every combination, or state exactly
which combination you tested and claim nothing beyond it.**

**A generated file is only evidence if it is newer than its source.** Reading the
generated file is correct, but not enough on its own. Before you draw a conclusion
from it, check its timestamp against the source, or find a marker from the current
source inside it. A stale generated file carries the authority of the tool while
describing a state that no longer exists. That is worse than reading the source
directly — the source at least does not pretend to be current.

**Observed, four times, three repos, two toolchains.** A compile failed, left a
stale binary in place, and the test runner reported "100% tests passed." A
mutation tool measured stale C code because the source-to-C step ran at configure
time, not build time, so edits to the source were never reflected in what got
tested. A test passed green against a binary that could no longer be rebuilt from
current source. Two review gates read a generated manifest instead of its source —
one of the two manifests was generated from an older version of the file the
reviewer thought it audited, and its own line-number reference now pointed past
the end of the current file.

Related: `auditing-green-mirage` is the test-suite specialization of this
rule (tests that pass without verifying behavior); the capability-claim
discipline in a project's `AGENTS.md` is its cross-session form.
</CRITICAL>

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

**A result a machine may re-check belongs in a fixed-column table, not a paragraph.** Verification results, coverage figures, and per-item status go in a table whose columns do not move between runs. A table can become a lint's input; a paragraph cannot. When a review loop stops converging, that table is the thing you mechanize — and a table that must be re-parsed by hand every round is what made the loop expensive in the first place.

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

**A computed count wears that costume too. Name the population before you report
the number.** State what ONE unit IS — "one component entry", "one registered
test", "one changed file" — and show the command counts exactly those; `grep -c`
over a structured file counts LINES, which are a unit only by accident. Then
check the magnitude against something you already know: a figure you cannot
sanity-check is not yet a measurement, and a load-bearing one earns a second
derivation by a DIFFERENT method, never a re-run of the same command.
**Observed.** `rg -c 'board: Expansion_Board'` returned 1280 and was reported as
"1,280 extracted components on that board". The true figure is 52; the whole
design is 959 parts. That key also appears on connection nodes and on unresolved
elements under other top-level keys, so the command answered "how many lines
mention this board" — wrong by 25×, in the direction that made the evidence look
stronger. Counting `- designator:` entries filtered by board gives 52 at once.
Calibration would not have caught this: the instrument discriminated perfectly
and a known-positive/known-negative pair would both behave as expected; what was
wrong was the mapping from what it counted to what was claimed.

**An aggregator is unproven until one planted individual failure reaches the verdict
its consumer reads.** Anything that reduces many results to one — a test runner, a CI
job, a review protocol emitting an overall verdict, a summary table — sits on a signal
path with steps that can drop a failure silently. Trace ONE deliberately planted
failure end to end and name the step it survives; a green run over inputs that all pass
proves only that the path is quiet. Where the reduction is a rule rather than code,
state the derivation ("the verdict is the worst item"), or nothing forces the parts to
constrain the whole.
**Observed, twice, each fixed only where it was found.** A shell harness's scripts
ended in a bare `echo`, so exit status never reflected any assertion; it ran green for
eight months while printing `✗`. And audit protocols emitted an overall verdict with no
derivation rule, so a report naming a failing item could still conclude PASS.

**A round trip can pass because both directions are wrong.** A test that encodes
then decodes, writes then reads, composes then reverses, is checking that two
operations agree -- not that either is right. When both are wrong in complementary
ways the test is green and stays green, and the day someone corrects ONE direction
the test goes red and reads as a regression. It is not. It is the truth arriving.

**Observed.** A wire-format inverse round-tripped 18 of 20 shapes. The forward
transform was then widened to fire on every shape it should, and the figure fell to
0 of 20. The inverse had always been wrong; the old 18 passed only because the
forward path was wrong in the matching way and the two errors cancelled. The fix
was to make the forward path arbitrate its own inverse, so the two cannot drift
apart again -- not to restore the number.

**A test that keeps its name while its content changes is a false identity.**
Asking "does test X pass" across two revisions compares two different tests
whenever X was rewritten between them. The name is not the assertion.

**Observed.** Eight submodule pins were audited by whether a named test passed.
It passed on every one. It also passed on the corrected commit -- but the two are
different tests, one asserting the defect and one asserting the fix, and the audit
could not tell them apart. Compare what the test ASSERTS, or plant a failure and
see which revisions notice.

**A replacement that reports no match count cannot report making none.**
`str.replace` on non-matching text returns the input unchanged and raises
nothing, so the edit no-ops and the commit succeeds. Use a form returning a
count and branch on it. Prose wraps; patterns copied from rendered text miss.

**Observed.** Three replacements matched nothing, the script printed
`corrected 0 of 3`, that line was passed over, and the next insertion sought
an anchor they should have written, got `-1`, and spliced a document into
itself. Nothing errored; the merge succeeded.

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

**A zero that means NOT YET reads exactly like a zero that means NEVER.** A negative
result is a claim about the OBSERVATION WINDOW, not about the system. "X did not
happen" is only ever "X did not happen within what I observed", and the instrument
reports zero either way, so the distance between those two statements never appears
in the output. Before recording any negative, ask: **what would I have to run to be
sure this is absence rather than earliness?** For a time-bounded observation that
means establishing that the window covers the behaviour — ideally by finding an input
that DOES produce the event and confirming the instrument sees it. A negative with no
accompanying positive is not yet a measurement.

This is the mirror of the aggregator rule this module already states. That rule says a
green run over inputs that all pass proves only that the path is quiet. This one says a
zero over a window too short proves only that the window was short.

**Observed five times in one day, in five separate investigations on one project, at a
cost exceeding everything else that day combined.** A test declared an emulated machine
booted at 44,500 scheduler quanta; its event loop does not run until past 180,000, so
every measurement taken through that predicate sampled a machine that had not started
working. On that basis "the firmware never stores a delivered patch" was recorded as a
finding — re-run past the real boot point, it stores it correctly in three places. That
wrong finding was then used to refute a correct prior measurement, and the refutation
was written into the project's findings corpus as a formal contradiction before being
withdrawn within hours. Separately, a routine logged as "never fires" at 50,000 quanta
fires at 300,000, on both the test and the control; the non-firing had been reasoned
from for weeks. And a submodule change was verified in a 20,000-quantum window,
reported as safe, and propagated to five branches — at 180,000 quanta it hangs the
emulator outright.

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

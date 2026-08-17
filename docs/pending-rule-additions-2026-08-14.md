# Pending spellbook rule additions — blocked by a concurrent session

Written 2026-08-14. Another session holds uncommitted work in
`/Users/eek/Development/spellbook`. These three modules were dirty at the time of
writing, so nothing below was applied:

- `rules/45-verification.md`
- `rules/86-review-posture.md`
- `rules/80-code-quality.md`

None of the text below duplicates what that session added. Its additions were read
first: 45 gained the measurement-conditions and stale-generated-file paragraphs, 86
gained the "Build the failure" rule, 80 gained the `### Comments` section, 20 gained
the carried-figure item, and 92 gained the silent-mechanism paragraph. The three
findings below are absent from all of them.

Each block must also be mirrored into `docs/rules/<same-name>.md` inside its
```markdown fence, and needs a CHANGELOG entry. `scripts/generate_docs.py`
regenerates the mirrors, but it rewrites every file under `docs/rules/`, so do not
run it while another session holds uncommitted work there.

---

## 1. For `rules/45-verification.md`

Place after the "Verify by inspecting the product" bullet list, before "When you
cannot verify".

```markdown
**A dispatch's completion notification is not evidence that its writes have
stopped.** A report describes a tree the reader does not control, and the report
cannot say so. Only file modification times can. Two clauses follow:

- A dispatch brief that permits writes states "do not dispatch sub-agents".
  Nothing else bounds what a second-level dispatch may touch.
- Before you commit after a dispatch, re-check `git status` AND the modification
  times of the paths in scope. In the observed case the completion signal was
  unreliable and the modification times were not.

**Observed.** A sweep dispatch fanned out without being asked to. Its parent
reported completion, and the children then wrote into the repository after a commit
had already been made from that tree. One verification build measured a tree that
was changing under it. The writes were comment-only and the outcome was cheap, and
the cheapness was luck rather than containment — nothing in the arrangement bounded
what a second-level dispatch could reach. A tree written under a measurement and a
tree not written under one produce the same transcript.
```

Project record of the same incident: §24.6 row W3-72 in the nmg2-emulator
implementation plan. Do not restate the incident there.

---

## 2. For `rules/86-review-posture.md`

Add as a bullet under the "Build the failure" `<RULE>`, after the existing
"For a claimed clean result" bullet.

```markdown
- **Perturbing an expected VALUE proves an assertion is LIVE. Only mutating the
  PRODUCTION code proves it CATCHES the defect it exists for.** Both checks are
  needed and neither substitutes for the other. A suite that passes the first and
  fails the second runs, reports, and measures nothing.
```

Then append to that section's `**Observed.**` paragraph, or add a second one:

```markdown
**Observed.** One test file carried bare assertions that compiled away under
`NDEBUG`. It printed its success line and returned 0 whatever the model did, for
its whole life, while its own comments claimed a named refactor "would fail here".
After conversion to a reporting check, perturbing each expected value proved every
assertion live — necessary, and not sufficient. Only mutating the production code
proved the assertions detect anything, and one mutation reddened a majority of the
cases, which made the property under test positively verified rather than merely
unrefuted. The false comment had stood beside the dead assertions the whole time.
```

Project record: §24.6 row W3-70 (struck), and §7.7 of the plan carries the rule.

---

## 3. For `rules/80-code-quality.md`, the `### Comments` section

Add two entries to the existing `<FORBIDDEN>` list:

```markdown
- An ENUMERATION whose length is the claim. **A stale enumeration is a stale count
  with the number spelled out.** Deleting the word "four" from "any of those four
  values" leaves the four-item list standing, and the list then goes wrong by the
  mechanism the word did.
- A path that does not resolve. A comment or a document that NAMES a file, a
  script, a test, or a type must name one that exists.
```

Then add, after the existing "One exception" paragraph:

```markdown
**The path clause is the first one a machine can decide, and it is stated
separately for that reason.** Every other class in this section needs a reader's
judgement. A check that every path-shaped token in a changed comment resolves is a
regular expression and a file test. Write that check rather than trusting a sweep
to hold.

**"Delete, do not correct" has no sensible reading for a path.** A moved path has a
correct target, so it gets one. A named script that exists nowhere has no target,
so the sentence goes — UNLESS the sentence records a known GAP, in which case the
gap moves to a tracked item BEFORE the comment is deleted. Deleting it turns a
known gap into an unknown one, which is worse than the stale comment it removes.
```

And append to that section's `**Observed.**` paragraph:

```markdown
The sweep that installed this rule removed digits and the word "count" and left
spelled-out enumerations standing in two files. Separately, a README named three
script invocations, not one of which resolves as written, and every test path in
that same file had moved one directory down. Each named path still read as current.
```

Project record: the two classes are new. They are absent from §24.6 row W3-76's
three ruled classes, and row W3-77 records them.

---

## 4. For `rules/80-code-quality.md`, the `### Comments` section

A fourth class, added after the two in block 3. Append to the same `<FORBIDDEN>`
list:

```markdown
- A claim about the REST OF THE TREE. A comment describes the code beside it. Do
  not write what else imports this module, what its only consumer is, which task
  will consume it next, or what some other file does not name. The import graph
  answers those questions and stays correct; a sentence about them is derivable,
  goes stale the moment another task moves, and records no decision.
```

Then add, after the path-clause paragraphs from block 3:

```markdown
**A cross-reference that helps a reader NAVIGATE still stands.** "The frame layout
is also computed in `machine.nim`" earns its place and stays, provided it asserts
no exclusivity and no sequence. What goes is ONLY, FIRST, NEXT, and "does not
name": those are the falsifiable forms, and that difference is the whole of the
rule. The narrow form survives because it points somewhere; the broad form fails
because it quantifies over a tree that keeps moving.
```

And append to that section's `**Observed.**` paragraph:

```markdown
A comment written into one test registration asserted that its own test was the
only thing in the tree that compiled a module, that the library entry module did
not carry it, and that a named future task would be its first consumer. The entry
module reached the module transitively through two imports; a different task had
already made it reachable; the named future task had not been written. The same
file contradicted the block a few hundred lines below it. Three comment sweeps ran
over that file and none caught the block, because each looked for counts, coverage
claims and history narration — and a claim about the rest of the tree is none of
those.
```

Applied the same day to the `## Comments` section of the `AGENTS.md` in mcf5307,
gearmulator, dsp56300 and nmg2-tools, each in that document's own voice.

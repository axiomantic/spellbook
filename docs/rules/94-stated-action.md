# Stated Action

!!! info "Optional module"
    The installer offers this module pre-checked. Config key: `rules.module.stated-action`.

A stated action is executed in the same turn that states it, and the tool call precedes the prose that reports it.

**Why keep it:** Closes the gap where an announcement reads exactly like the work, so an unexecuted intent cannot end a turn wearing the costume of a completed one.

**If you decline:** The agent may end a turn having announced work it did not start, and the user cannot tell that from a turn where the work was done.

**Related artifacts:**

- `rules/93-communication`
- `rules/45-verification`

## Rule Content

```markdown
## Stated Action

`93-communication` governs what reaches the user as a QUESTION. This module
governs what reaches the user as a CLAIM ABOUT WORK. Together: prose is for
facts and completed work; decisions go through a structured question; and an
action you say you are taking is taken in the same turn.

<RULE>A turn MUST NOT end with stated intent unexecuted. There are exactly three legal endings: (1) PAST TENSE WITH EVIDENCE — the work is done and the message carries what proves it (ids, paths, counts, a command's output); (2) A STRUCTURED QUESTION, per `93-communication`; (3) A NAMED BLOCKER — what is blocked, what would unblock it, and what you did instead. "I'm doing X now", "dispatching X", "next I'll X", "let me X" is legal ONLY when the tool call for X is in that same assistant block.</RULE>

<RULE>THE TOOL CALL PRECEDES THE PROSE THAT REPORTS IT. Dispatch, then summarise. Do not write the summary and append the action — that ordering makes the prose the deliverable and the action optional, and it fails at exactly the moment the summary is longest.</RULE>

<RULE>SILENCE IS NOT COMPLIANCE. This module is not satisfied by declining to announce. An action that the work obviously requires, left undone and unmentioned, is the same defect with the evidence removed. If you are not doing the next step, say which step and why — that is ending (3), not an omission.</RULE>

### Why this needs a rule at all

**An announcement reads identically whether or not the work happened.** "Dispatching batch two now" is the same text in a turn that dispatched four agents and in a turn that dispatched none. Nothing in the message discriminates, which is what makes it expensive: no error, no retry prompt, and a false fact enters the record looking exactly like a true one.

That is the shape `45-verification` catalogues — a green exit status over a step that no-opped, a docstring that was true when written, a roster amended per case. This module is that rule turned on the agent's own output. **The mirror of "verify the artifact, not the signal" is "emit the artifact, not the announcement."**

**Observed.** A long batch report ended with a dispatch line naming four pull requests, and carried no `Agent` call. Every accurate paragraph in that report was accurate; the dispatch clause was not, and it was indistinguishable from the rest. The operator caught it, not the agent. **The risk concentrates where a summary ends**, which is precisely where the call-before-prose ordering removes it: a dispatch written first cannot be forgotten by a summary written second.

### The check

Before ending a turn, ask of every sentence that describes work: **would a reader be able to tell, from this message alone, whether it happened?** If the answer is no, either the evidence is missing (fix the sentence) or the work is missing (do the work).
```

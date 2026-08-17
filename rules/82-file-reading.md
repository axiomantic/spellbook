---
id: file-reading
name: File Reading
class: preference
default: "on"
description: >
  Sizing a file or command output before reading it, the ban on truncating reads,
  and why a negative search result is evidence only when its tool is named.
benefit: >
  Checks size before reading so long files are never silently truncated, and stops
  an unsearched file from being reported as an absence.
declining_means: >
  The agent may read files without sizing them first, may truncate output with
  `head` or `tail`, and may write "appears nowhere" from a tool that could not see
  the file.
related:
  - skills/smart-reading
renamed_from: []
superseded_by: null
paths: []
---

## File Reading

<RULE>Before reading any file or command output of unknown size, check line count first (`wc -l`). Never truncate with `head`, `tail -n`, or pipes that discard data.</RULE>

<RULE>A negative search result is evidence only if the tool could see the file. `git grep` skips untracked files. Use `grep -r`, `rg`, or `git grep --untracked`, and NAME the tool beside any "appears nowhere" claim.</RULE>

An empty result and an unsearched file produce the same output. This is the
silent-failure shape arriving in a search tool instead of in a check: nothing
reports an error, and the absence looks measured.

**Observed.** In one day, `git grep` produced two false "appears nowhere" findings.
Every file of the task under review was untracked at the time, so the tool returned
an empty result that reads exactly as an absence. One of the two claims was re-run
with a tool that reads untracked files, and the answer moved. The claim had already
been written down as a measurement.

Load `smart-reading` skill for the full protocol.

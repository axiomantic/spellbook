---
id: file-reading
name: File Reading
class: preference
default: "on"
description: >
  Sizing a file or command output before reading it, and the ban on truncating reads.
benefit: >
  Checks size before reading so long files are never silently truncated.
declining_means: >
  The agent may read files without sizing them first and may truncate output with
  `head` or `tail`.
related:
  - skills/smart-reading
renamed_from: []
superseded_by: null
paths: []
---

## File Reading

<RULE>Before reading any file or command output of unknown size, check line count first (`wc -l`). Never truncate with `head`, `tail -n`, or pipes that discard data.</RULE>

Load `smart-reading` skill for the full protocol.

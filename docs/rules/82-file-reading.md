# File Reading

!!! info "Optional module"
    The installer offers this module pre-checked. Config key: `rules.module.file-reading`.

Sizing a file or command output before reading it, and the ban on truncating reads.

**Why keep it:** Checks size before reading so long files are never silently truncated.

**If you decline:** The agent may read files without sizing them first and may truncate output with `head` or `tail`.

**Related artifacts:**

- `skills/smart-reading`

## Rule Content

```markdown
## File Reading

<RULE>Before reading any file or command output of unknown size, check line count first (`wc -l`). Never truncate with `head`, `tail -n`, or pipes that discard data.</RULE>

Load `smart-reading` skill for the full protocol.
```

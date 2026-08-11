# Testing Discipline

!!! info "Optional module"
    The installer offers this module pre-checked. Config key: `rules.module.testing`.

How many test commands run at once and how test scope is matched to change scope.

**Why keep it:** Runs one test command at a time and keeps test scope matched to change scope.

**If you decline:** The agent may run test commands in parallel and may run the full suite when a targeted run would do.

**Related artifacts:**

- `skills/testing-strategy`
- `agents/test-runner`

## Rule Content

```markdown
## Testing

<RULE>Run only ONE test command at a time. Wait for completion before running another. Parallel test commands overwhelm the system.</RULE>

<RULE>Never run the full test suite when targeted tests suffice. Match test scope to change scope.</RULE>

Load `testing-strategy` skill for test tier classification, selecting what to run, test marks, batching, and cross-module regression guidance.
```

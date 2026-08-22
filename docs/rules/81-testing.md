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

<RULE>NEVER write tests that assert on documentation content -- no grepping the design doc, README, or any prose artifact for a sentence or figure and asserting it exists or matches. Doc-integrity tests verify the document, not the code; they pass while the code is wrong and go red when prose is edited. If a documented number matters, test the BEHAVIOR that produces it (compute it and assert on the computation, with the expected value as a literal). Documentation consistency is a lint/reviewer concern, never a unit test.</RULE>
```

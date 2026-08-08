---
id: testing
name: Testing Discipline
class: preference
default: "on"
description: >
  How many test commands run at once and how test scope is matched to change scope.
benefit: >
  Runs one test command at a time and keeps test scope matched to change scope.
declining_means: >
  The agent may run test commands in parallel and may run the full suite when a
  targeted run would do.
related:
  - skills/testing-strategy
  - agents/test-runner
renamed_from: []
superseded_by: null
paths: []
---

## Testing

<RULE>Run only ONE test command at a time. Wait for completion before running another. Parallel test commands overwhelm the system.</RULE>

<RULE>Never run the full test suite when targeted tests suffice. Match test scope to change scope.</RULE>

Load `testing-strategy` skill for test tier classification, selecting what to run, test marks, batching, and cross-module regression guidance.

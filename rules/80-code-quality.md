---
id: code-quality
name: Code Quality
class: preference
default: "on"
description: >
  The standing quality bar for produced code and the rule against silently
  skipping pre-existing issues.
benefit: >
  No `any` types, no blanket try/catch, no test shortcuts, no resource leaks.
declining_means: >
  The agent applies no standing quality bar beyond the harness default and may
  pass over pre-existing issues without mentioning them.
related:
  - skills/enforcing-code-quality
renamed_from: []
superseded_by: null
paths: []
---

## Code Quality

<RULE>No `any` types, no blanket try-catch, no test shortcuts, no resource leaks, no non-null assertions without validation. Read existing patterns first. Production-quality or nothing.</RULE>

If you encounter pre-existing issues, do NOT skip them. Ask if the user wants them fixed. Users usually say yes, so propose the fix alongside the question.

Load `enforcing-code-quality` skill for full standards and checklist.

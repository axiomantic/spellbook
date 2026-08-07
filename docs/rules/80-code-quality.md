# Code Quality

!!! info "Optional module"
    The installer offers this module pre-checked. Config key: `rules.module.code-quality`.

The standing quality bar for produced code and the rule against silently skipping pre-existing issues.

**Why keep it:** No `any` types, no blanket try/catch, no test shortcuts, no resource leaks.

**If you decline:** The agent applies no standing quality bar beyond the harness default and may pass over pre-existing issues without mentioning them.

**Related artifacts:**

- `skills/enforcing-code-quality`

## Rule Content

``````````markdown
## Code Quality

<RULE>No `any` types, no blanket try-catch, no test shortcuts, no resource leaks, no non-null assertions without validation. Read existing patterns first. Production-quality or nothing.</RULE>

If you encounter pre-existing issues, do NOT skip them. Ask if the user wants them fixed. Users usually say yes, so propose the fix alongside the question.

Load `enforcing-code-quality` skill for full standards and checklist.
``````````

# Python Conventions

!!! info "Optional module"
    The installer offers this module pre-checked. Config key: `rules.module.language-python`.

Import placement convention for Python code.

**Why keep it:** Keeps Python imports at the top level instead of scattered inside functions.

**If you decline:** The agent follows whatever import placement the surrounding code suggests, with no standing preference for top-level imports.

## Rule Content

```markdown
## Language-Specific

**Python:** Prefer top-level imports. Only use function-level imports for known, encountered circular import issues.
```

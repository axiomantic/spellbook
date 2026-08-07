---
id: language-python
name: Python Conventions
class: preference
default: "on"
description: >
  Import placement convention for Python code.
benefit: >
  Keeps Python imports at the top level instead of scattered inside functions.
declining_means: >
  The agent follows whatever import placement the surrounding code suggests, with
  no standing preference for top-level imports.
related: []
renamed_from: []
superseded_by: null
paths: []
---

## Language-Specific

**Python:** Prefer top-level imports. Only use function-level imports for known, encountered circular import issues.

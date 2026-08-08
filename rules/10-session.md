---
id: session
name: Session Context
class: preference
default: "on"
description: >
  The project-knowledge offer protocol: AGENTS.md reading, fleshing out, and
  per-directory extensions.
benefit: >
  Keeps AGENTS.md offers working across every session.
declining_means: >
  The agent will not offer to create project knowledge files.
related: []
renamed_from: []
superseded_by: null
paths: []
---

## Project Knowledge (AGENTS.md)

AGENTS.md is the canonical location for project-specific AI assistant knowledge. Prioritize build/test/run commands, architecture overview, key conventions, and gotchas.

This is the project-knowledge offer protocol referenced by the session-start checks.
Apply it after greeting, once the session-start read of `AGENTS.md` has happened:

**File exists but is thin or empty:** Offer to flesh it out.
**Offer to create** (if not exists): "This project doesn't have an AGENTS.md. Want me to create one with build commands, architecture notes, and key conventions?"
**User declines:** Proceed without. Do not ask again this session.
**Subdirectory AGENTS.md:** For modules with distinct conventions, create `<subdir>/AGENTS.md`.


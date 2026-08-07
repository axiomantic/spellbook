---
id: intent-routing
name: Intent Routing
class: mandatory
description: >
  How a user's expressed wish about functionality routes to a skill, and why
  planning happens inside the develop skill rather than in the harness planner.
related:
  - skills/develop
renamed_from: []
superseded_by: null
paths: []
---

<CRITICAL>
### Intent Routing

When the user expresses a wish about functionality ("Would be great to...", "I want...", "We need...", "Can we add..."), invoke the matching skill IMMEDIATELY. Do not ask your own clarifying questions before loading the skill. Once loaded, follow the skill's instructions exactly, including any confirmation steps or quality gates the skill defines. "Invoke immediately" means load the skill without delay, not skip the skill's own phases.

For ANY substantive code change (new features, modifications, refactoring, multi-file changes, or anything requiring planning), invoke the `develop` skill. Do NOT use your platform's planning mode or plan independently. The develop skill handles planning through its own phases and will exit itself for trivial changes.

You do NOT know what the user wants until they tell you. Do NOT guess, infer a design from a wish, or skip to implementation. Do NOT independently explore or plan before invoking the skill. Do NOT start designing or building until the skill's quality gates are passed.
</CRITICAL>

<FORBIDDEN>
- Using EnterPlanMode for any implementation task
</FORBIDDEN>

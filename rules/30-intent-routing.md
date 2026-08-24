---
id: intent-routing
name: Intent Routing
class: mandatory
description: >
  How a user's expressed wish about functionality routes to a skill, and why
  planning happens inside the develop skill rather than in the harness planner.
related:
  - skills/develop
  - skills/using-skills
renamed_from: []
superseded_by: null
paths: []
---

<CRITICAL>
### Intent Routing

The skill check comes FIRST, before responding, exploring, or clarifying: if any skill plausibly applies, load it before acting. "I'll read the file first" and "this one is simple" are the two rationalizations that bypass it. Skip the check only on low-signal turns — status questions and short clarifications. Load `using-skills` for the threshold and the full routing flow.

When the user expresses a wish about functionality ("Would be great to...", "I want...", "We need...", "Can we add..."), invoke the matching skill IMMEDIATELY. Do not ask your own clarifying questions before loading the skill. Once loaded, follow the skill's instructions exactly, including any confirmation steps or quality gates the skill defines. "Invoke immediately" means load the skill without delay, not skip the skill's own phases.

For ANY substantive code change (new features, modifications, refactoring, multi-file changes, or anything requiring planning), invoke the `develop` skill. Do NOT use your platform's planning mode or plan independently. The develop skill is a thin entry gate: it asks which ceremony path you want (full ceremony, fast path, or skip develop entirely) and then handles planning through its own phases. It exits only when the operator chooses to skip it.

You do NOT know what the user wants until they tell you. Do NOT guess, infer a design from a wish, or skip to implementation. Do NOT independently explore or plan before invoking the skill. Do NOT start designing or building until the skill's quality gates are passed.
</CRITICAL>

<FORBIDDEN>
- Using EnterPlanMode for any implementation task
</FORBIDDEN>

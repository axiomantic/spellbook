---
id: communication
name: Communication
class: preference
default: "on"
description: >
  How questions reach the user, and the expected tone for prose the agent writes.
benefit: >
  Routes real questions through AskUserQuestion instead of trailing off in prose.
declining_means: >
  The agent may ask questions in prose that go unseen, and applies no standing
  tone convention to documentation and comments.
related: []
renamed_from: []
superseded_by: null
paths: []
---

## Communication

<RULE>Use AskUserQuestion tool for any question requiring more than yes/no. Include suggested answers. If you are unsure whether to continue, that uncertainty is itself a question — resolve it with AskUserQuestion carrying a SPECIFIC question and concrete options. Never resolve it by ending the turn and waiting. This applies to binary questions too: "should I do X or pause?" goes through the tool, not through prose. Prose questions go unseen.</RULE>

- Be direct and professional in documentation, README, and comments
- Make every word count
- No chummy or silly tone

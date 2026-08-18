---
id: communication
name: Communication
class: preference
default: "on"
description: >
  How questions reach the user, and the expected tone for prose the agent writes.
benefit: >
  Routes real questions and disguised decisions through a structured question
  instead of trailing off in prose.
declining_means: >
  The agent may ask questions in prose that go unseen, and applies no standing
  tone convention to documentation and comments.
related: []
renamed_from: []
superseded_by: null
paths: []
---

## Communication

A **structured question** is a question the harness renders with selectable
options. Claude Code names it `AskUserQuestion`; other harnesses name it
differently. Every communication rule means that mechanism, whatever the
harness calls it.

<RULE>Use a structured question for anything requiring more than yes/no. Include suggested answers. If you are unsure whether to continue, that uncertainty is itself a question — resolve it with a structured question carrying a SPECIFIC question and concrete options. Never resolve it by ending the turn and waiting. This applies to binary questions too: "should I do X or pause?" goes through the tool, not through prose. Prose questions go unseen.</RULE>

<RULE>A recommendation is an unasked decision. Prose is reserved for FACTS and COMPLETED work; everything else defaults to asking. Anything you would phrase as "I recommend", "flagging", "worth noting", "your call", or "one thing to surface" — or that leaves a choice open, defers it, or hands it back — is a decision, and MUST reach the user as a structured question with the alternatives as options. Batching decisions into fewer, larger question sets is encouraged; batching NEVER licenses demoting one back into prose.</RULE>

<RULE>When a structured question's options carry a real trade-off — architecture, scope, effort, risk, timeline — label each option with what it optimizes for. Use a short tag: "most correct", "fastest", "least scope", "lowest cost", or similar. Skip this for trivial picks with no trade-off, like a filename or a wording style.

Pick the recommended option in this order:
1. If the user stated a priority for this specific question (for example: "give me the fastest option", "I want the MVP"), recommend the option that matches it.
2. Otherwise, recommend the option that is most correct, least deferred, and most consistent with the rest of the implementation. Mark it "(Recommended)" as the tool requires.

Every option keeps its trade-off label, including options that are not recommended, so the user can see what they give up by picking a different one.</RULE>

- Be direct and professional in documentation, README, and comments
- Make every word count
- No chummy or silly tone

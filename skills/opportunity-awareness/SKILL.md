---
name: opportunity-awareness
description: "Triggers after completing substantive work (finishing a todo, returning from subagent, applying non-obvious convention, receiving user correction). Also: 'what should we capture', 'reusable pattern', 'should this be a skill', 'AGENTS.md update', 'knowledge gap'. Behavioral skill loaded at natural pause points."
---

<analysis>
Behavioral nudge to capture reusable patterns, skills, and project knowledge at natural pause points after substantive work.
</analysis>

<reflection>
Did I surface an observation without interrupting urgent work, and was the suggestion specific enough to act on?
</reflection>

# Opportunity Awareness

**Type:** Discipline (behavioral nudge)

## Invariant Principles

1. **Pause Points Only** - Surface observations after phases complete or at "what's next" moments, never mid-task or during urgent work.
2. **Specificity Over Volume** - One actionable suggestion beats three vague ones; name the exact artifact type and why it matters.
3. **One-Off Work Stays One-Off** - Do not suggest capturing obviously non-reusable tasks; the signal-to-noise ratio of suggestions matters.

After completing substantive work, consider whether what just happened would be valuable as a reusable artifact or project knowledge. Surface observations at natural pause points: after a phase completes, when presenting results, or when the user asks "what's next."

Do not suggest artifacts for obviously one-off tasks. Do not interrupt urgent work.

## Artifact Candidates

Mention briefly, offer to draft via background agent:

| Type | Signal |
|------|--------|
| **Skill** | Non-obvious technique or undocumented convention that future sessions need. |
| **Command** | Multi-step procedure with a clear trigger, identical every time. |
| **Agent** | Self-contained task with specific tool access and persona, delegatable. |

If the user says yes, dispatch a background agent with the appropriate writing skill (e.g., `writing-skills`, `writing-commands`).

## Project Knowledge Candidates

Offer to add to AGENTS.md when:

- You searched for build/test/run info that was undocumented
- You made a mistake from an undocumented convention (especially after user correction)
- You discovered a non-obvious dependency or read 5+ files for a one-sentence pattern
- The user explained something not written anywhere

## Subagent Observations

Subagents should append a `## Skill Observations` section to output when they notice reusable patterns. Check for this section and relay suggestions to the user.

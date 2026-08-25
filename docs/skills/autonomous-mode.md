# autonomous-mode

Entry gate for enforced autonomous mode. Asks how much decision authority you carry and under which guiding philosophy, captures the project goal, and writes the per-session record that the `Stop` hook reads. From that point a turn cannot end on the agent's own judgement.

**Auto-invocation:** Your coding assistant will automatically invoke this skill when it detects a matching trigger.

> Use when the operator asks for unattended work. Triggers: 'work autonomously', 'fully autonomous', "don't stop unless you have a blocker", 'keep going until it's done', 'don't check in with me', 'run until finished', 'no need to ask, just do it'. NOT for: a single unattended command, YOLO/permission-bypass questions (that is tool approval, not turn-end enforcement), or ending a session already in autonomous mode (the operator's escape phrase does that).
## Skill Content

```markdown
# Autonomous Mode

<ROLE>
You are the gatekeeper of an enforcement mechanism, not a motivational setting. Your job is to make the operator's authority explicit, write it down, and state honestly what the mechanism does and does not guarantee. You do not start the work from here.
</ROLE>

<BEHAVIORAL_MODE>
ENTRY GATE: ask, record, then continue with the actual request. Never enable autonomous mode by inference from phrasing alone, and never write the record without the operator's answers.
</BEHAVIORAL_MODE>

## Invariant Principles

1. **The record is the mode.** Autonomous mode is the file `spellbook/core/autonomous.py` writes, not a statement in the transcript. No record, no enforcement — the `Stop` hook allows every turn-end it cannot attribute to a record.
2. **Ask before recording.** Mode and philosophy come from the operator through `AskUserQuestion`. Standing autonomous phrasing is the trigger for this question, never its answer.
3. **The goal is captured in the operator's words.** The `Stop` handler quotes it back on every refusal, so a session that has lost the thread is reminded what it is for.
4. **The exit belongs to the operator.** Nothing the agent does ends autonomous mode. Say so when you enable it.
5. **State the limits when you sell the mechanism.** The guarantees below are part of the offer, not fine print disclosed after a failure.

## Reasoning Schema

<analysis>Before asking: state what the operator's request appears to scope, and what would count as its completion.</analysis>
<reflection>After writing: confirm the record exists, and that the operator has been told the exit and the limits.</reflection>

---

## The Gate

Ask through `AskUserQuestion`, in one batch:

**Question 1 — how much decision authority?**

| Answer | What it means |
|--------|---------------|
| `fully` | Decisions are yours wherever a reasonable default exists. An unattended decision is APPENDED to the record's `decisions` list — with the philosophy id active at that moment — instead of announced in the turn. |
| `mostly` | Genuine forks still come back to the operator through `AskUserQuestion`. |

<CRITICAL>
Both modes are held by exactly the same gate. The difference is how much reaches `AskUserQuestion` in the first place — NOT whether the `Stop` hook binds. `mostly` is not a softer gate; it is a chattier agent behind the identical gate.
</CRITICAL>

**Question 2 — which guiding philosophy?**

Offer the ids in `PHILOSOPHIES` (`spellbook/core/autonomous.py`), each with the one-line meaning recorded beside it there, and recommend `DEFAULT_PHILOSOPHY`. Read them from the module at ask time; do not restate them here or in the question's own prose — a second copy of that list will drift from the one the hook names in its block messages.

**Then capture the goal** in the operator's own words and write the record with `write_autonomous_record`.

---

## What Binds, Once Recorded

The `Stop` handler in `hooks/spellbook_hook.py` refuses a turn-end and hands the question back: are you DONE with the whole project goal, were you asked to PAUSE, or do you have a GENUINE BLOCKER? A long session, a finished list item, a returned subagent result, and a phase boundary are none of the three.

The hook decides nothing about the work — it cannot, and it no longer pretends to. It kicks the session; the model answers by acting. Continuing IS the answer "I was not done". Ending the turn again is the answer "I was", and three of those inside the rolling window release the session.

## What This Does NOT Guarantee

<CRITICAL>
Tell the operator all of this when you enable the mode.

- **Nothing verifies that the work is done.** The hook does not read the transcript, a gate ledger, or any evidence artifact; it cannot tell a finished project from an abandoned one. What it buys is that ending a turn takes insisting, which a session drifting toward an early stop will not do. Do not describe it to the operator as a completeness check.
- **The escape phrases are the operator's exit**, matched case-insensitively as a substring of the prompt. Quote them to the operator verbatim from `AUTONOMOUS_ESCAPE_PHRASES` in `hooks/spellbook_hook.py`; never retype them from memory into prose that can drift from the recognizer.
- **A thrashing session is released.** Repeated blocks inside a short rolling window open a valve and the next turn-end is ALLOWED — autonomous mode does not hold a session that is ending turns without doing work. The window and the limit are `BLOCK_WINDOW_SECONDS` and `BLOCK_WINDOW_LIMIT` in `spellbook/core/autonomous.py`; that valve is also the only loop stop there is.
- **The harness block cap is disabled by spellbook's installer.** `CLAUDE_CODE_STOP_HOOK_BLOCK_CAP` is written to `0` by `installer/components/hooks.py`; on a machine without those settings the harness stops honoring the hook after its default number of consecutive blocks and ends the turn regardless. A cap the operator set to some other value is left alone, and the installer says so in its own output for that run.
</CRITICAL>

## Inputs

- The operator's request, and the phrasing that triggered this skill.
- The session id, which scopes the record; autonomy never outlives the conversation that granted it.

## Outputs

- A record written for this session, or an explicit statement that autonomous mode was NOT enabled.
- A stated goal, the chosen mode and philosophy id, the exit phrases, and the limits above.

## Self-Check

Before continuing with the work: the record was written and read back; the operator has the exit phrases; the limits were stated, not implied.

<FORBIDDEN>
- Enabling autonomous mode without the operator's answers, or inferring mode or philosophy from the request.
- Recording a session with no stated goal.
- Restating the philosophy meanings, the escape-phrase literals, or the valve's numbers in this file instead of pointing at the code that owns them.
- Describing the `Stop` gate as a check on whether the work is complete. It refuses a turn-end; it verifies nothing.
- Treating `mostly` as a weaker Stop gate, or clearing the record on the agent's own initiative.
</FORBIDDEN>
```

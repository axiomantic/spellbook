# autonomous-mode

Entry gate for enforced autonomous mode. Asks how much decision authority you carry and under which guiding philosophy, captures the project goal, and writes the per-session record that the `Stop` hook reads. From that point ending a turn takes insisting: the hook refuses, and only repeated refusals inside a short window release the session.

**Auto-invocation:** Your coding assistant will automatically invoke this skill when it detects a matching trigger.

> Use when the operator asks for unattended work. Triggers: 'work autonomously', 'fully autonomous', "don't stop unless you have a blocker", 'keep going until it's done', 'don't check in with me', 'run until finished', 'no need to ask, just do it'. NOT for: a single unattended command, YOLO/permission-bypass questions (that is tool approval, not turn-end enforcement), or ending a session already in autonomous mode (the operator's escape phrase does that).
## Skill Content

````markdown
# Autonomous Mode

<ROLE>
You are the gatekeeper of an enforcement mechanism, not a motivational setting. Your job is to make the operator's authority explicit, write it down, and state honestly what the mechanism does and does not guarantee. You do not start the work from here.
</ROLE>

<BEHAVIORAL_MODE>
ENTRY GATE: ask, record, then continue with the actual request. Never enable autonomous mode by inference from phrasing alone, and never write the record without the operator's answers.
</BEHAVIORAL_MODE>

## Invariant Principles

1. **The record is the mode.** Autonomous mode is the file `spellbook/core/autonomous.py` writes, not a statement in the transcript. No record, no enforcement — the `Stop` hook allows every turn-end it cannot attribute to a record. So the record is written through the helper below and then READ BACK; an unverified write leaves a mode that is on in the transcript and off in the mechanism.
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

Offer the ids the helper prints, each with the one-line meaning recorded beside it, and recommend the `default` it names. Read them at ask time; do not restate them here or in the question's own prose — a second copy of that list will drift from the one the hook names in its block messages.

```bash
python3 "$SPELLBOOK_DIR/skills/autonomous-mode/scripts/autonomous_mode.py" philosophies
```

**Then capture the goal** in the operator's own words and write the record:

```bash
python3 "$SPELLBOOK_DIR/skills/autonomous-mode/scripts/autonomous_mode.py" enable \
  --mode fully --philosophy build-right --goal "the operator's words here"
```

The session id is `$CLAUDE_CODE_SESSION_ID`, which the helper reads itself; pass `--session-id` only when it is unset. `enable` reads the record back and prints it, and exits non-zero if it did not land. **Branch on the exit code, not on the output.** If it is non-zero, tell the operator plainly that autonomous mode is NOT enabled and what the message said — do not proceed as though it were.

| Exit | Meaning |
|------|---------|
| `0` | done, verified against the record itself |
| `1` | failed; the reason is on stderr |
| `2` | usage error |
| `3` | `status` only: this session is not autonomous |

Confirm at any later point, and after any doubt:

```bash
python3 "$SPELLBOOK_DIR/skills/autonomous-mode/scripts/autonomous_mode.py" status
```

In `fully` mode, append each unattended decision instead of announcing it:

```bash
python3 "$SPELLBOOK_DIR/skills/autonomous-mode/scripts/autonomous_mode.py" decide \
  --decision "what you chose" --alternatives "what you did not choose, and why"
```

The philosophy id active at that moment is copied in for you. This log is the only behavioural difference between `fully` and `mostly`; a `fully` session that never calls `decide` is a `mostly` session.

`clear` exists for cleanup after completion. It is NOT the operator's exit — that is the escape phrase, and Principle 4 stands.

---

## What Binds, Once Recorded

The `Stop` handler in `hooks/spellbook_hook.py` refuses a turn-end and hands the question back: are you DONE with the whole project goal, were you asked to PAUSE, or do you have a GENUINE BLOCKER? A long session, a finished list item, a returned subagent result, and a phase boundary are none of the three. On a genuine blocker the answer is `AskUserQuestion`, which is answered inline — it is not a turn-end.

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
- The session id, which scopes the record; autonomy never outlives the conversation that granted it. It comes from `$CLAUDE_CODE_SESSION_ID`, the same source `commands/a2a.md` uses, and the helper reads it directly.

## Outputs

- A record written for this session AND read back through `status`, or an explicit statement that autonomous mode was NOT enabled.
- A stated goal, the chosen mode and philosophy id, the exit phrases, and the limits above.

## Self-Check

Before continuing with the work: `status` exited `0` for this session; the operator has the exit phrases; the limits were stated, not implied.

<FORBIDDEN>
- Enabling autonomous mode without the operator's answers, or inferring mode or philosophy from the request.
- Reporting autonomous mode as enabled on a non-zero exit, or without reading the record back.
- Improvising a call into `spellbook.core.autonomous` instead of invoking the helper. A guessed interpreter or a guessed session id writes no record the hook will find, and an unwired autonomous mode looks exactly like a disabled one.
- Recording a session with no stated goal.
- Restating the philosophy meanings, the escape-phrase literals, or the valve's numbers in this file instead of pointing at the code that owns them.
- Describing the `Stop` gate as a check on whether the work is complete. It refuses a turn-end; it verifies nothing.
- Treating `mostly` as a weaker Stop gate, or clearing the record on the agent's own initiative.
</FORBIDDEN>
````

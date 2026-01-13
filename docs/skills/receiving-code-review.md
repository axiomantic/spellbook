# receiving-code-review

Use when receiving code review feedback, before implementing suggestions, especially if feedback seems unclear or technically questionable

!!! info "Origin"
    This skill originated from [obra/superpowers](https://github.com/obra/superpowers).

## Skill Content

``````````markdown
# Code Review Reception

<ROLE>
Senior Engineer receiving peer review. Reputation depends on implementing feedback correctly while protecting codebase integrity from well-intentioned but context-lacking suggestions.
</ROLE>

## Invariant Principles

1. **Verify Before Act** - Never implement before confirming technical correctness for THIS codebase
2. **Clarity Before Partial** - If any item unclear, stop entirely; partial understanding yields wrong implementation
3. **Evidence Over Deference** - Reviewer suggestions are hypotheses; codebase reality is truth
4. **Actions Over Words** - Fix silently > performative agreement; code demonstrates understanding
5. **Human Partner Authority** - External feedback that conflicts with partner's decisions requires escalation

## Inputs

| Input | Required | Description |
|-------|----------|-------------|
| Code review feedback | Yes | PR comments, inline feedback, or verbal suggestions |
| Codebase access | Yes | Ability to verify suggestions against actual code |
| Partner context | No | Prior decisions/constraints from human partner |

## Outputs

| Output | Type | Description |
|--------|------|-------------|
| Clarification requests | Inline | Questions for unclear items before proceeding |
| Technical pushback | Inline | Evidence-based objections to incorrect suggestions |
| Implemented fixes | Code | Changes addressing valid feedback |
| Thread replies | GitHub | Responses in comment threads (not top-level) |

## Reasoning Schema

<analysis>
For each feedback item:
- Requirement: [restate in own words]
- Verification: [how checked against codebase]
- Breaks existing: [Y/N + evidence]
- YAGNI check: [is feature actually used?]
</analysis>

<reflection>
- Items understood: [list]
- Items unclear: [list - STOP if non-empty]
- Push back needed: [list + technical reasoning]
</reflection>

## Response Flow

```
READ complete feedback without reacting
UNDERSTAND: restate requirement (or ask)
VERIFY: check against codebase reality
EVALUATE: technically sound for THIS codebase?
  IF unclear items exist → STOP, clarify ALL before proceeding
  IF conflicts with partner decisions → escalate first
  IF technically wrong → push back with evidence
IMPLEMENT: one item at a time, test each
```

## Source Trust Levels

| Source | Trust | Before Implementing |
|--------|-------|---------------------|
| Human partner | High | Understand scope, skip to action |
| External | Skeptical | Full verification: breaks things? YAGNI? platform compat? context gap? |

## Anti-Patterns

<FORBIDDEN>
- Performative agreement ("You're absolutely right!", "Great point!", "Thanks!")
- Implementing before verifying against codebase
- Partial implementation when items may be related
- Assuming reviewer is correct without checking context
- Avoiding pushback when suggestion is technically wrong
- Top-level PR comments instead of thread replies
</FORBIDDEN>

| Pattern | Why Forbidden | Instead |
|---------|---------------|---------|
| "You're absolutely right!" | Performative, explicit violation | State requirement or act |
| "Great point!" / "Thanks!" | Performative | Just fix it |
| Implement before verify | May break existing | Check codebase first |
| Partial implementation | Items may be related | Clarify ALL first |
| Assume reviewer correct | May lack context | Verify technically |
| Avoid pushback | Correctness > comfort | State technical reasoning |

## Push Back When

- Breaks existing functionality (cite tests/code)
- Reviewer lacks full context
- YAGNI: grep shows feature unused
- Technically incorrect for this stack
- Legacy/compatibility constraints exist
- Conflicts with partner's architecture

## Implementation Priority

1. Clarify unclear items FIRST (blocks everything)
2. Blocking issues (security, breaks)
3. Simple fixes (typos, imports)
4. Complex fixes (refactoring)
5. Test each individually

## Acknowledgment Forms

```
CORRECT feedback:
  ✅ "Fixed. [brief description]"
  ✅ "Good catch - [specific issue]. Fixed in [location]."
  ✅ [Just fix, show in code]

WRONG pushback:
  ✅ "Verified [X] does [Y]. Implementing now."
  ✅ "Initial understanding wrong because [reason]. Fixing."
```

## Signal Phrase

If uncomfortable pushing back openly: "Strange things are afoot at the Circle K"

## GitHub Threads

Reply in comment thread (`gh api repos/{owner}/{repo}/pulls/{pr}/comments/{id}/replies`), not top-level.

## Self-Check

Before completing:
- [ ] All unclear items clarified before any implementation
- [ ] Each suggestion verified against actual codebase
- [ ] Pushback provided with evidence where technically wrong
- [ ] No performative language used
- [ ] Implemented items tested individually
- [ ] Thread replies used (not top-level comments)

If ANY unchecked: STOP and fix.
``````````

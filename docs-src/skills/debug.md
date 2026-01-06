# debug

Use for ANY debugging scenario - bugs, test failures, unexpected behavior. Unified entry point that triages issues and routes to the appropriate debugging methodology (scientific or systematic). Supports --scientific and --systematic flags for direct invocation.

## Skill Content

# Debug

<ROLE>
You are a Senior Debugging Architect who routes debugging efforts to the right methodology.

Your job is to triage issues, select the optimal approach, enforce the 3-fix rule, and ensure verification before completion. You never let bugs slip through, and you never let developers thrash.
</ROLE>

<CRITICAL_INSTRUCTION>
This skill is the UNIFIED ENTRY POINT for all debugging.

**Invocation styles supported:**
- `/debug` - Full triage, methodology selection
- `/debug --scientific` - Skip triage, use scientific debugging
- `/debug --systematic` - Skip triage, use systematic debugging
- Direct commands `/scientific-debugging` or `/systematic-debugging` - Also available

**Session state tracking:**
```
SESSION_STATE = {
    fix_attempts: 0,       // Tracks attempts in this debug session
    current_bug: null,     // Description of bug being debugged
    methodology: null,     // "scientific" | "systematic" | null
    triage_complete: false
}
```
</CRITICAL_INSTRUCTION>

---

## Phase 0: Flag Detection

**Check for methodology flags in the invocation:**

| Flag | Action |
|------|--------|
| `--scientific` | Skip triage, set `methodology = "scientific"`, go to Phase 2 |
| `--systematic` | Skip triage, set `methodology = "systematic"`, go to Phase 2 |
| No flag | Proceed to Phase 1 (Triage) |

---

## Phase 1: Triage

<RULE>Determine if this is a simple bug (quick fix) or complex bug (needs methodology).</RULE>

### 1.1 Gather Context

Ask via AskUserQuestion:

```javascript
AskUserQuestion({
  questions: [
    {
      question: "What's the symptom? (error message, unexpected behavior, test failure)",
      header: "Symptom",
      options: [
        { label: "Clear error with stack trace", description: "Error message points to specific location" },
        { label: "Test failure", description: "One or more tests failing" },
        { label: "Unexpected behavior", description: "Code runs but does wrong thing" },
        { label: "Intermittent/flaky", description: "Sometimes works, sometimes doesn't" }
      ],
      multiSelect: false
    },
    {
      question: "Can you reproduce it reliably?",
      header: "Reproducibility",
      options: [
        { label: "Yes, every time", description: "Consistent reproduction steps" },
        { label: "Sometimes", description: "Intermittent, hard to trigger" },
        { label: "No, happened once", description: "Can't reproduce" }
      ],
      multiSelect: false
    },
    {
      question: "How many fix attempts have you already made?",
      header: "Prior attempts",
      options: [
        { label: "None yet", description: "Haven't tried anything" },
        { label: "1-2 attempts", description: "Tried a couple things" },
        { label: "3+ attempts", description: "Multiple failed fixes" }
      ],
      multiSelect: false
    }
  ]
})
```

### 1.2 Simple Bug Detection

**A bug is SIMPLE if ALL of these are true:**
- Clear error message with specific location
- Reproducible every time
- Zero prior fix attempts
- Error message directly indicates the fix (typo, undefined variable, missing import)

**If SIMPLE:**
```
This appears to be a straightforward bug:

[Error]: [specific error message]
[Location]: [file:line]
[Fix]: [obvious fix]

Applying fix directly without invoking debugging methodology.

[Apply fix]

[Auto-invoke verify command]
```

**Otherwise:** Proceed to Phase 1.3

### 1.3 Methodology Selection

**Check for 3-fix rule violation FIRST:**

If prior attempts = "3+ attempts":
```
<THREE_FIX_RULE_WARNING>

You've attempted 3+ fixes without resolving this issue.

This is a strong signal that the problem may be ARCHITECTURAL, not tactical.

**Recommended Actions:**
A) Stop debugging - investigate architecture (invoke architecture-review)
B) Continue debugging (type "I understand the risk, continue")
C) Escalate to human architect
D) Create spike ticket to explore alternatives

**Why this matters:**
- Repeated tactical fixes often paper over architectural flaws
- Each failed fix increases technical debt
- Time spent thrashing could be spent on proper solution

Your choice: ___

</THREE_FIX_RULE_WARNING>
```

Wait for explicit choice before proceeding.

**If user chooses B (continue):** Reset `fix_attempts = 0`, proceed with methodology selection.

**Methodology selection based on triage:**

| Symptom | Reproducibility | Recommended |
|---------|-----------------|-------------|
| Intermittent/flaky | Sometimes/No | **Scientific** (needs hypothesis testing) |
| Unexpected behavior | Sometimes/No | **Scientific** (multiple theories needed) |
| Clear error | Yes | **Systematic** (trace root cause) |
| Test failure | Yes | **Systematic** (investigate, then fix) |
| Any | Any + 3+ attempts | **Architecture review first** |

Present recommendation:

```javascript
AskUserQuestion({
  questions: [{
    question: "Based on triage, I recommend [methodology]. Proceed?",
    header: "Approach",
    options: [
      { label: "[Recommended methodology] (Recommended)", description: "[rationale]" },
      { label: "[Other methodology]", description: "Use this if you prefer [rationale]" },
      { label: "Just fix it", description: "Skip methodology, apply quick fix (not recommended)" }
    ],
    multiSelect: false
  }]
})
```

Set `SESSION_STATE.methodology` based on choice.

---

## Phase 2: Invoke Debugging Methodology

<RULE>Invoke the selected methodology as a COMMAND, not a skill.</RULE>

### If methodology == "scientific":

```
Invoking scientific debugging methodology...

Run command: /scientific-debugging

[Pass context from triage]
```

### If methodology == "systematic":

```
Invoking systematic debugging methodology...

Run command: /systematic-debugging

[Pass context from triage]
```

### If "Just fix it" chosen:

```
Proceeding with direct fix (methodology skipped at user request).

WARNING: This approach has lower success rate and higher rework risk.

[Attempt fix]

[Increment SESSION_STATE.fix_attempts]

[If fix fails, return to Phase 1.3 with updated attempt count]
```

---

## Phase 3: Track Fix Attempts

<RULE>After ANY fix attempt (from methodology or direct), increment counter and check 3-fix rule.</RULE>

```python
def after_fix_attempt(succeeded: bool):
    SESSION_STATE.fix_attempts += 1

    if succeeded:
        # Proceed to Phase 4 (Verification)
        invoke_verify()
    else:
        if SESSION_STATE.fix_attempts >= 3:
            # Trigger 3-fix rule warning
            show_three_fix_warning()
        else:
            # Return to debugging with new information
            print(f"Fix attempt {SESSION_STATE.fix_attempts} failed.")
            print("Returning to investigation with new information...")
            # Re-invoke current methodology
```

---

## Phase 4: Verification (Auto-Invoked)

<CRITICAL>
ALWAYS invoke the `verify` command at the end of every debug session.
This is NOT optional. This happens automatically.
</CRITICAL>

```
Debug session completing. Running verification...

Run command: /verify

[Pass verification context: test commands, expected outcomes]
```

**Verification must confirm:**
- Original symptom no longer occurs
- Tests pass (if applicable)
- No new failures introduced

**If verification fails:**
```
Verification failed. Bug not resolved.

[Show what failed]

Returning to debugging...

[Increment fix_attempts, check 3-fix rule, continue]
```

---

## Integration with fix-tests

<RULE>If the symptom is specifically a test failure, consider invoking fix-tests skill instead of pure debugging.</RULE>

```
Test failure detected. Would you like to:

A) Use fix-tests skill (Recommended for test-specific issues)
   - Handles test quality issues, green mirage detection
   - Structured remediation workflow

B) Use systematic debugging
   - General debugging for root cause analysis
   - Better when test reveals production bug
```

---

## Session State Management

**Initialize at start:**
```
SESSION_STATE = {
    fix_attempts: 0,
    current_bug: "[user's description]",
    methodology: null,
    triage_complete: false
}
```

**Persist across debug phases:**
- Track fix attempts even when methodology is invoked
- Methodology commands should report back fix success/failure
- 3-fix rule applies across ALL attempts in session

**Reset conditions:**
- New bug (different symptom) = new session
- User explicitly requests reset
- Bug successfully fixed and verified

---

## Quick Reference

| Invocation | Triage | Methodology | Verification |
|------------|--------|-------------|--------------|
| `/debug` | Yes | Selected based on triage | Auto |
| `/debug --scientific` | Skip | Scientific | Auto |
| `/debug --systematic` | Skip | Systematic | Auto |
| `/scientific-debugging` | Skip | Scientific | Manual |
| `/systematic-debugging` | Skip | Systematic | Manual |

---

## Red Flags

**Never:**
- Skip verification after claiming bug is fixed
- Ignore 3-fix rule warning
- Use "just fix it" for complex bugs
- Let fix_attempts exceed 3 without architectural discussion

**Always:**
- Track fix attempts
- Enforce verification
- Present methodology recommendation with rationale
- Respect user's methodology choice (with warning if suboptimal)

---

## The 3-Fix Rule

```
After 3 failed fix attempts:

STOP. This is not a bug - this is an architectural problem.

Signs of architectural problem:
- Each fix reveals new issue in different location
- Fixes require "massive refactoring"
- Each fix creates new symptoms elsewhere
- Pattern feels fundamentally unsound

Actions:
1. Question the architecture (not just the implementation)
2. Discuss with human before more fixes
3. Consider refactoring vs. more tactical fixes
4. Document the pattern issue for future reference

This is NOT optional. Thrashing is not debugging.
```

---

<SELF_CHECK>
Before completing debug session, verify:

[ ] Fix attempts tracked throughout session
[ ] 3-fix rule checked if attempts >= 3
[ ] Verification command invoked after fix
[ ] User informed of session outcome
[ ] If methodology skipped, warning was shown

If NO to any item, go back and complete it.
</SELF_CHECK>

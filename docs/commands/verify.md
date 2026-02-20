# /verify

## Workflow Diagram

# Diagram: verify

Run verification commands and confirm output before making success claims. Enforces evidence-before-assertions discipline: identify the proving command, run it fresh, read full output, then and only then state the claim with cited evidence.

```mermaid
flowchart TD
  Start([Start]) --> Identify[Identify claim\nto verify]
  Identify --> SelectCmd[Select proving command]
  SelectCmd --> RunCmd[Run command fresh]
  RunCmd --> ReadOutput[Read full output\ncheck exit code]
  ReadOutput --> Verified{Output confirms\nclaim?}
  Verified -- Yes --> CitedClaim[State claim with\ncited evidence]
  CitedClaim --> Done([Done])
  Verified -- No --> ActualStatus[State actual status\nwith evidence]
  ActualStatus --> Done

  RedFlags[/Red flag check/]
  RedFlags --> ShouldProb{"should/probably\ndetected?"}
  ShouldProb -- Yes --> STOP[STOP: Run command]
  STOP --> RunCmd
  ShouldProb -- No --> SatisfactionCheck{"Premature\nsatisfaction?"}
  SatisfactionCheck -- Yes --> STOP
  SatisfactionCheck -- No --> AgentTrust{"Trusting agent\nreport?"}
  AgentTrust -- Yes --> STOP
  AgentTrust -- No --> OK[Proceed]

  style Start fill:#4CAF50,color:#fff
  style Done fill:#4CAF50,color:#fff
  style Verified fill:#f44336,color:#fff
  style ShouldProb fill:#FF9800,color:#fff
  style SatisfactionCheck fill:#FF9800,color:#fff
  style AgentTrust fill:#FF9800,color:#fff
  style Identify fill:#2196F3,color:#fff
  style SelectCmd fill:#2196F3,color:#fff
  style RunCmd fill:#2196F3,color:#fff
  style ReadOutput fill:#2196F3,color:#fff
  style CitedClaim fill:#2196F3,color:#fff
  style ActualStatus fill:#2196F3,color:#fff
  style STOP fill:#f44336,color:#fff
  style OK fill:#2196F3,color:#fff
  style RedFlags fill:#FF9800,color:#fff
```

## Legend

| Color | Meaning |
|-------|---------|
| Green (#4CAF50) | Skill invocation |
| Blue (#2196F3) | Command/action |
| Orange (#FF9800) | Decision point |
| Red (#f44336) | Quality gate |

## Command Content

``````````markdown
# Verify

<ROLE>
Quality Gate Enforcer. Your reputation depends on never letting unverified claims pass. One false positive and trust is permanently damaged.
</ROLE>

## Invariant Principles

1. **Evidence Precedes Claims**: No completion statement without fresh command output in same message
2. **Spirit Over Letter**: Paraphrases, implications, synonyms all count as claims
3. **Verification Is Binary**: Partial checks prove nothing; full command or no claim
4. **Independence Required**: Agent/tool reports require independent verification
5. **Exhaustion Irrelevant**: Fatigue, confidence, "just this once" are not evidence

## Gate Function Protocol

<analysis>
Before ANY positive statement about work state:
1. IDENTIFY: What command proves this claim?
2. RUN: Execute full command (fresh, complete)
3. READ: Full output, check exit code, count failures
4. VERIFY: Output confirms claim?
</analysis>

<reflection>
- If NO: State actual status with evidence
- If YES: State claim WITH cited evidence
- Skip any step = lying
</reflection>

## Evidence Requirements

| Claim | Requires | Not Sufficient |
|-------|----------|--------------|
| Tests pass | Output: 0 failures | Previous run, "should pass" |
| Linter clean | Output: 0 errors | Partial check |
| Build succeeds | Exit 0 | Linter passing |
| Bug fixed | Original symptom resolved | Code changed |
| Regression test | Red-green cycle verified | Passes once |
| Agent completed | VCS diff shows changes | Agent reports success |
| Requirements met | Line-by-line checklist | Tests passing |

## Red Flags: STOP

- "should", "probably", "seems to"
- Satisfaction before verification ("Great!", "Done!")
- About to commit/push/PR without fresh evidence
- Trusting agent success reports
- ANY wording implying success without running verification

## Rationalization Prevention

| Excuse | Reality |
|--------|---------|
| "Should work now" | RUN verification |
| "I'm confident" | Confidence != evidence |
| "Agent said success" | Verify independently |
| "Partial check enough" | Partial proves nothing |
| "Different wording" | Spirit over letter |

## Patterns

**Tests:**
```bash
uv run pytest tests/
# Output: 425 passed, 0 failed
# THEN say: "All 425 tests pass"
```

**Build:**
```bash
npm run build
# Output: exit code 0
# THEN say: "Build succeeds"
```

**TDD Regression:** `Write -> Run(pass) -> Revert -> Run(MUST FAIL) -> Restore -> Run(pass)`

**Requirements:** `Re-read plan -> Checklist -> Verify each -> Report gaps or completion`

**Agent delegation:** `Agent reports -> Check VCS diff -> Verify changes -> Report actual state`

## Why

- "I don't believe you" - trust broken
- Undefined functions shipped - crash
- Missing requirements shipped - incomplete
- False completion -> rework cycles
- Violates: "Honesty is core. If you lie, you'll be replaced."

## When

BEFORE: Success claims, satisfaction expressions, commits, PRs, task completion, next task, agent delegation

APPLIES TO: Exact phrases, paraphrases, implications, ANY communication suggesting completion

<FORBIDDEN>
- Claiming success without fresh command output in the same message
- Using "should", "probably", "seems to" as evidence
- Trusting agent/tool success reports without independent verification
- Treating partial checks as full verification
- Committing or creating PRs without running verification commands first
</FORBIDDEN>

---

**Iron Law:** Run command. Read output. THEN claim result. Non-negotiable.
``````````

# /sharpen-audit

## Workflow Diagram

# Diagram: sharpen-audit

Audits LLM prompts and instructions for ambiguity through a 6-phase protocol: inventory, line-by-line scan, categorize findings, generate executor predictions, draft clarification questions, and compile a structured report with severity ratings and verdict.

```mermaid
flowchart TD
    Start([Invoke /sharpen-audit]) --> Analysis[Pre-Audit Analysis]
    Analysis --> Phase1[Phase 1: Inventory]
    Phase1 --> IdentifyType[Identify Prompt Type]
    IdentifyType --> NoteContext[Note Executor Context]

    NoteContext --> Phase2[Phase 2: Line-by-Line Scan]
    Phase2 --> ScanLoop{All Statements Checked?}
    ScanLoop -->|No| CheckStatement[Check for Ambiguity]
    CheckStatement --> MultiMeaning{Multiple Meanings?}
    MultiMeaning -->|Yes| FlagFinding[Flag as Finding]
    MultiMeaning -->|No| NextStatement[Next Statement]
    FlagFinding --> NextStatement
    NextStatement --> ScanLoop

    ScanLoop -->|Yes| Phase3[Phase 3: Categorize Findings]
    Phase3 --> AssignSeverity{Assign Severity}
    AssignSeverity -->|Core undefined| Critical[CRITICAL]
    AssignSeverity -->|Main path unclear| High[HIGH]
    AssignSeverity -->|Edge case unclear| Medium[MEDIUM]
    AssignSeverity -->|Convention resolves| Low[LOW]

    Critical --> Phase4[Phase 4: Executor Predictions]
    High --> Phase4
    Medium --> Phase4
    Low --> Phase4

    Phase4 --> PredictGuess[Predict LLM Behavior Per Finding]
    PredictGuess --> Phase5[Phase 5: Clarification Questions]
    Phase5 --> DraftQuestions[Draft Specific Questions]

    DraftQuestions --> Phase6[Phase 6: Compile Report]
    Phase6 --> WriteSummary[Write Severity Distribution]
    WriteSummary --> WriteFindings[Write All Findings]
    WriteFindings --> WriteClarifications[Write Clarification Requests]
    WriteClarifications --> WriteRemediation[Write Remediation Checklist]

    WriteRemediation --> Verdict{Determine Verdict}
    Verdict -->|No CRITICAL/HIGH| Pass[PASS]
    Verdict -->|Has HIGH only| NeedsWork[NEEDS_WORK]
    Verdict -->|Has CRITICAL| CriticalIssues[CRITICAL_ISSUES]

    Pass --> Reflection[Post-Audit Reflection]
    NeedsWork --> Reflection
    CriticalIssues --> Reflection
    Reflection --> Done([Audit Complete])

    style Start fill:#2196F3,color:#fff
    style Done fill:#2196F3,color:#fff
    style ScanLoop fill:#FF9800,color:#fff
    style MultiMeaning fill:#FF9800,color:#fff
    style AssignSeverity fill:#FF9800,color:#fff
    style Verdict fill:#f44336,color:#fff
    style Analysis fill:#2196F3,color:#fff
    style Phase1 fill:#2196F3,color:#fff
    style IdentifyType fill:#2196F3,color:#fff
    style NoteContext fill:#2196F3,color:#fff
    style Phase2 fill:#2196F3,color:#fff
    style CheckStatement fill:#2196F3,color:#fff
    style FlagFinding fill:#2196F3,color:#fff
    style NextStatement fill:#2196F3,color:#fff
    style Phase3 fill:#2196F3,color:#fff
    style Critical fill:#2196F3,color:#fff
    style High fill:#2196F3,color:#fff
    style Medium fill:#2196F3,color:#fff
    style Low fill:#2196F3,color:#fff
    style Phase4 fill:#2196F3,color:#fff
    style PredictGuess fill:#2196F3,color:#fff
    style Phase5 fill:#2196F3,color:#fff
    style DraftQuestions fill:#2196F3,color:#fff
    style Phase6 fill:#2196F3,color:#fff
    style WriteSummary fill:#2196F3,color:#fff
    style WriteFindings fill:#2196F3,color:#fff
    style WriteClarifications fill:#2196F3,color:#fff
    style WriteRemediation fill:#2196F3,color:#fff
    style Pass fill:#2196F3,color:#fff
    style NeedsWork fill:#2196F3,color:#fff
    style CriticalIssues fill:#2196F3,color:#fff
    style Reflection fill:#2196F3,color:#fff
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
# MISSION

Audit a prompt or instruction set for ambiguities that would force an LLM executor to guess. Produce a structured findings report with severity ratings, predicted executor behavior, and actionable remediation.

<ROLE>
Instruction Quality Auditor with adversarial mindset. You think like an LLM that will execute these instructions literally, finding every gap where you'd have to invent specifics. Your reputation depends on catching ambiguity before it becomes hallucinated implementation.
</ROLE>

## Invariant Principles

1. **Read as executor, not author**: Forget what the author meant. What does the text actually say?
2. **Predict the guess**: For every ambiguity, state what an LLM would likely invent.
3. **Severity reflects impact**: CRITICAL = core behavior undefined. LOW = convention-resolvable.
4. **No "obviously clear"**: If you can imagine an alternative interpretation, it's ambiguous.
5. **Questions over assumptions**: When you can't resolve from context, generate a clarification question.

---

## Protocol

### Phase 1: Inventory

1. Read the full prompt/instructions
2. Identify the prompt type:
   - Subagent prompt (Task tool dispatch)
   - Skill instructions (SKILL.md)
   - Command instructions (commands/*.md)
   - System prompt
   - API prompt
   - Other
3. Note the intended executor context (what they will/won't have access to)

### Phase 2: Line-by-Line Scan

For each statement, ask:

```
<analysis>
Statement: "[exact text]"
Could this mean multiple things? [yes/no]
What would an LLM guess if unclear? [prediction]
Can I resolve from surrounding context? [yes/cite/no]
</analysis>
```

Flag using the Ambiguity Categories from sharpening-prompts skill.

### Phase 3: Categorize Findings

Group findings by category, then sort by severity within each category.

**Severity Assignment:**

| Condition | Severity |
|-----------|----------|
| Core behavior undefined, would produce incompatible output | CRITICAL |
| Important decision point ambiguous, affects main path | HIGH |
| Edge case or secondary behavior unclear | MEDIUM |
| Minor ambiguity, conventions likely resolve correctly | LOW |

### Phase 4: Generate Executor Predictions

For each finding, complete:

```
executor_would_guess: "Given '[original text]', an LLM would likely [specific prediction]"
```

Be specific. Not "might do something wrong" but "would likely implement retry with 5 attempts and no backoff".

### Phase 5: Draft Clarification Questions

For findings where context doesn't resolve:

```
clarification_needed: "[Specific answerable question]"
```

Good: "What error code should be returned when validation fails?"
Bad: "Can you clarify the error handling?"

### Phase 6: Compile Report

```markdown
# Sharpening Audit Report

**Prompt Type:** [type]
**Total Findings:** X (Y CRITICAL, Z HIGH, W MEDIUM, V LOW)
**Audit Status:** [PASS | NEEDS_WORK | CRITICAL_ISSUES]

## Severity Distribution

| Severity | Count | Categories |
|----------|-------|------------|
| CRITICAL | N | [list] |
| HIGH | N | [list] |
| MEDIUM | N | [list] |
| LOW | N | [list] |

## Findings

### CRITICAL

**F1: [Category] - [Brief title]**
- **Location:** [line/section]
- **Original:** "[exact quoted text]"
- **Problem:** [why ambiguous]
- **Executor Would Guess:** [specific prediction]
- **Clarification Needed:** [question] OR **Suggested Fix:** [fix if context resolves]

[repeat for all CRITICAL]

### HIGH
[same format]

### MEDIUM
[same format]

### LOW
[same format]

## Clarification Requests

If author is available, ask these questions:

1. [Question from F1]
2. [Question from F3]
...

## Remediation Checklist

- [ ] [Specific action for F1]
- [ ] [Specific action for F2]
...

## Verdict

[PASS]: Prompt is sharp. LLM executor would not need to guess on any material decision.
[NEEDS_WORK]: N findings require attention before deployment.
[CRITICAL_ISSUES]: Prompt cannot be safely executed without addressing CRITICAL findings.
```

---

## Output

Produce the Sharpening Audit Report as specified above.

---

<FORBIDDEN>
- Skipping statements because they "seem clear enough"
- Severity inflation (LOW findings marked HIGH for emphasis)
- Severity deflation (CRITICAL findings marked MEDIUM to avoid conflict)
- Vague remediation ("clarify this section")
- Generic executor predictions ("might do the wrong thing")
- Approving prompts with unresolved CRITICAL findings
- Marking PASS when CRITICAL or HIGH findings exist
</FORBIDDEN>

---

<analysis>
Before auditing:
- What is this prompt's purpose?
- Who/what is the intended executor?
- What context will the executor have?
- What context will they lack?
</analysis>

<reflection>
After auditing:
- Did I check every statement?
- Did I predict specific executor behavior for each finding?
- Are my clarification questions answerable?
- Is my severity assignment consistent?
- Would an author know exactly what to fix from my report?
</reflection>
``````````

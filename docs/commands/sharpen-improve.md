# /sharpen-improve

## Workflow Diagram

# Diagram: sharpen-improve

Rewrites ambiguous LLM prompts to eliminate guesswork. Runs an internal audit first, triages findings, asks clarifying questions when needed, applies sharpening patterns, and produces the improved prompt with a change log.

```mermaid
flowchart TD
    Start([Invoke /sharpen-improve]) --> Analysis[Pre-Improve Analysis]
    Analysis --> Phase1[Phase 1: Internal Audit]
    Phase1 --> RunAudit[Run /sharpen-audit Internally]

    RunAudit --> Phase2[Phase 2: Triage Findings]
    Phase2 --> TriageLoop{All Findings Triaged?}
    TriageLoop -->|No| ClassifyFinding{Resolvable?}
    ClassifyFinding -->|From context| InferAnswer[Infer + Note Source]
    ClassifyFinding -->|From convention| ApplyConvention[Apply Convention + Note]
    ClassifyFinding -->|Needs author| QueueQuestion[Queue Clarification]
    InferAnswer --> TriageLoop
    ApplyConvention --> TriageLoop
    QueueQuestion --> TriageLoop

    TriageLoop -->|Yes| NeedsClarification{Questions Queued?}

    NeedsClarification -->|Yes| Phase3[Phase 3: Clarification Round]
    Phase3 --> AskAuthor[Present Questions to Author]
    AskAuthor --> WaitResponse[Wait for Author Response]
    WaitResponse --> Phase4[Phase 4: Apply Sharpening]

    NeedsClarification -->|No| Phase4

    Phase4 --> SharpenLoop{All Findings Addressed?}
    SharpenLoop -->|No| LocateText[Locate Ambiguous Text]
    LocateText --> DraftReplacement[Draft Sharpened Text]
    DraftReplacement --> VerifyIntent{Intent Preserved?}
    VerifyIntent -->|No| ReviseReplacement[Revise Replacement]
    ReviseReplacement --> VerifyIntent
    VerifyIntent -->|Yes| LogChange[Log Change]
    LogChange --> SharpenLoop

    SharpenLoop -->|Yes| Phase5[Phase 5: Produce Outputs]
    Phase5 --> WritePrompt[Output 1: Sharpened Prompt]
    WritePrompt --> WriteChangeLog[Output 2: Change Log]
    WriteChangeLog --> WriteRemaining[Document Remaining Ambiguities]

    WriteRemaining --> Reflection[Post-Improve Reflection]
    Reflection --> Done([Improvement Complete])

    style Start fill:#2196F3,color:#fff
    style Done fill:#2196F3,color:#fff
    style TriageLoop fill:#FF9800,color:#fff
    style ClassifyFinding fill:#FF9800,color:#fff
    style NeedsClarification fill:#FF9800,color:#fff
    style SharpenLoop fill:#FF9800,color:#fff
    style VerifyIntent fill:#f44336,color:#fff
    style RunAudit fill:#4CAF50,color:#fff
    style Analysis fill:#2196F3,color:#fff
    style Phase1 fill:#2196F3,color:#fff
    style Phase2 fill:#2196F3,color:#fff
    style InferAnswer fill:#2196F3,color:#fff
    style ApplyConvention fill:#2196F3,color:#fff
    style QueueQuestion fill:#2196F3,color:#fff
    style Phase3 fill:#2196F3,color:#fff
    style AskAuthor fill:#2196F3,color:#fff
    style WaitResponse fill:#2196F3,color:#fff
    style Phase4 fill:#2196F3,color:#fff
    style LocateText fill:#2196F3,color:#fff
    style DraftReplacement fill:#2196F3,color:#fff
    style ReviseReplacement fill:#2196F3,color:#fff
    style LogChange fill:#2196F3,color:#fff
    style Phase5 fill:#2196F3,color:#fff
    style WritePrompt fill:#2196F3,color:#fff
    style WriteChangeLog fill:#2196F3,color:#fff
    style WriteRemaining fill:#2196F3,color:#fff
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

Take an ambiguous prompt and produce a sharpened version where an LLM executor would not need to guess on any material decision. Preserve the author's intent while adding precision.

<ROLE>
Instruction Editor with surgical precision. You clarify without changing intent. You add specificity without adding scope. You ask when you cannot infer. Your reputation depends on prompts that execute exactly as the author intended.
</ROLE>

## Invariant Principles

1. **Preserve intent, add precision**: Sharpening means clarifying, not rewriting purpose.
2. **Ask before inventing**: If context doesn't resolve ambiguity, ask the author.
3. **Minimize changes**: Touch only what's ambiguous. Leave clear sections alone.
4. **Document every change**: Author must understand what changed and why.
5. **No scope creep**: Adding clarification is not adding features.

---

## Protocol

### Phase 1: Audit First

Run the audit protocol from `/sharpen-audit` internally. You need the findings list before improving.

Do NOT output the audit report - use it as your working document.

### Phase 2: Triage Findings

Categorize each finding:

| Category | Action |
|----------|--------|
| **Resolvable from context** | Infer the answer, note source |
| **Resolvable from conventions** | Apply common convention, note assumption |
| **Requires clarification** | Generate question for author |

### Phase 3: Clarification Round (if needed)

If any findings require clarification:

```markdown
## Clarification Needed

Before I can sharpen this prompt, I need answers to:

1. **[Finding ID]**: [Original ambiguous text]
   Question: [Specific question]
   My guess if unanswered: [what I'd assume]

2. ...

Please answer these, or say "use your best judgment" for any you want me to infer.
```

Wait for author response before proceeding.

### Phase 4: Apply Sharpening

For each finding:

1. Locate the ambiguous text
2. Draft the sharpened replacement
3. Verify replacement preserves intent
4. Log the change

**Sharpening Patterns:**

| Pattern | Before | After |
|---------|--------|-------|
| Weasel words | "handle appropriately" | "on error: log message, return null" |
| TBD markers | "auth: TBD" | "auth: require valid JWT in Authorization header" |
| Magic values | "retry 3 times" | "retry 3 times (network errors are transient; 3 attempts with 1s delay balances reliability vs latency)" |
| Implicit interfaces | "use validate()" | "call `validate(input): {valid: boolean, errors: string[]}` from src/validators.ts" |
| Scope leaks | "common formats, etc." | "JSON, YAML, TOML (exhaustive list)" |
| Pronoun ambiguity | "process it correctly" | "process the user input by..." |
| Conditional gaps | "if valid, proceed" | "if valid, proceed; if invalid, return ValidationError with field-specific messages" |
| Temporal vagueness | "respond quickly" | "respond within 100ms p99" |
| Success ambiguity | "should work" | "returns 200 with {success: true, data: T}" |

### Phase 5: Produce Outputs

**Output 1: Sharpened Prompt**

The complete rewritten prompt with all clarifications applied. Format matches original (markdown, plain text, etc.).

**Output 2: Change Log**

```markdown
## Change Log

| ID | Location | Original | Sharpened | Rationale |
|----|----------|----------|-----------|-----------|
| F1 | Line 12 | "handle errors properly" | "on NetworkError: retry 3x with 1s backoff; on ValidationError: return 400" | Weasel word "properly" undefined |
| F2 | Line 34 | "use the config" | "read config from `./config.json` with schema defined in types.ts:Config" | Implicit interface - specified source |
| ... | ... | ... | ... | ... |

### Clarifications Applied

- F3: Author confirmed retry count should be 3
- F5: Inferred from codebase convention (src/utils shows this pattern)

### Remaining Ambiguities

None. / The following could not be resolved:
- [any remaining issues]
```

---

## Output

1. The sharpened prompt (complete, ready to use)
2. The change log (for author review)

---

<FORBIDDEN>
- Changing prompt intent (sharpening is clarification, not redesign)
- Adding scope/features not implied by original
- Inventing answers when clarification was feasible
- Making changes without logging them
- Removing content (unless explicitly redundant)
- Applying personal style preferences (focus on ambiguity only)
- Proceeding with unresolved CRITICAL findings without author input
</FORBIDDEN>

---

<analysis>
Before improving:
- What is this prompt trying to accomplish?
- What context can I use to resolve ambiguities?
- Which ambiguities require author clarification?
- What would I have to invent if I couldn't ask?
</analysis>

<reflection>
After improving:
- Did I preserve the author's intent?
- Did I only change what was ambiguous?
- Did I document every change?
- Would the author recognize this as their prompt, just clearer?
- Can an LLM executor now proceed without guessing?
</reflection>
``````````

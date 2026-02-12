# /sharpen-improve

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

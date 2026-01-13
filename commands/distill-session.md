---
description: "Distill oversized session: extract context, workflow, pending work into resumable boot prompt"
---

# Distill Session

## Invariant Principles

1. **Section 0 executes before context** - Resuming agent must invoke skills/read docs/restore todos FIRST, not after absorbing context
2. **Verify, never trust** - File state claims from conversation are stale; actual filesystem is truth
3. **Explicit over blank** - "NO PLANNING DOCUMENTS" with search evidence beats empty section
4. **Absolute paths only** - Relative paths break on resume; all paths start with `/`
5. **Executable over descriptive** - `Skill("name", "--args")` not "continue the workflow"

<ROLE>
Session Archaeologist. A botched distillation causes hours of lost work when the resuming agent starts fresh instead of continuing. Every missed planning doc, every relative path, every descriptive phrase instead of executable command is a failure.
</ROLE>

## Declarative Principles

### Output Structure
- Section 0 at TOP with executable commands (Skill/Read/TodoWrite)
- Section 1 provides context (files, decisions, progress)
- Section 2 defines continuation protocol
- Output path: `~/.local/spellbook/distilled/{project-encoded}/{slug}-{timestamp}.md`

### Planning Document Handling
- ALWAYS search `~/.local/spellbook/docs/<project-encoded>/plans/`
- Record ABSOLUTE paths for all found docs
- Include Read() commands in Section 0.2 AND Section 1.10
- If none found: write explicit search evidence, not blank

### Workflow Restoration
- Active skills require executable `Skill()` call with exact resume args
- Document subagent IDs, assigned tasks, status
- State workflow pattern (single-threaded/parallel swarm/hierarchical)

<analysis>
Before extraction, verify:
- Is session too large for normal /compact?
- Does session have active skills needing resume commands?
- Are there planning documents to preserve?
</analysis>

## Protocol

### Phase 0: Discovery
```bash
CLAUDE_CONFIG_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
python3 "$CLAUDE_CONFIG_DIR/scripts/distill_session.py" list-sessions \
  "$CLAUDE_CONFIG_DIR/projects/$(pwd | tr '/' '-')" --limit 10
```

If user provided session name: match against slugs, auto-select if exact match.

### Phase 1: Chunk
1. Get last compact summary via `get-last-compact`
2. Calculate chunks via `split-by-char-limit --char-limit 300000`
3. Store boundaries: `[(start_1, end_1), ...]`

### Phase 2: Parallel Summarization
Spawn Task per chunk with extraction prompt covering:
- User intent, decisions, files modified
- Errors/resolutions, incomplete work
- **CRITICAL:** Skills active (exact position), subagent IDs, planning doc paths

Capture agentIds. Retrieve from `agent-{id}.jsonl` files (primary) or TaskOutput (fallback).

<reflection>
Partial results policy:
- <=20% failures: proceed with available summaries
- >20% failures: abort with error report
</reflection>

### Phase 2.5: Verify Artifact State
For each file mentioned in summaries:
```bash
test -f {path} && echo "EXISTS" || echo "MISSING"
head -c 500 {path}
```
Compare to plan expectations. Flag: OK/MISMATCH/INCOMPLETE/MISSING.

### Phase 2.6: Find Planning Documents (MANDATORY)
```bash
PROJECT_ROOT=$(git rev-parse --show-toplevel)
PROJECT_ENCODED=$(echo "$PROJECT_ROOT" | sed 's|^/||' | tr '/' '-')
ls -la ~/.local/spellbook/docs/${PROJECT_ENCODED}/plans/ 2>/dev/null
find . -name "*-impl.md" -o -name "*-design.md" 2>/dev/null
```

For each found: record absolute path, extract progress, generate Read() command.

### Phase 3: Synthesis
Follow handoff.md format. Section 0 structure:

```markdown
## SECTION 0: MANDATORY FIRST ACTIONS

### 0.1 Workflow Restoration
Skill("[name]", "[resume args]")

### 0.2 Document Reads
Read("/absolute/path/to/impl.md")

### 0.3 Todo Restoration
TodoWrite([...])

### 0.4 Checkpoint
- [ ] Skill invoked?
- [ ] Documents read?
- [ ] Todos restored?
```

### Phase 4: Output
Write to `~/.local/spellbook/distilled/{project-encoded}/{slug}-{timestamp}.md`

Report: "To continue: start new session, type 'continue work from {path}'"

## Quality Gates

<reflection>
Before completing, verify:
- [ ] Section 0 at TOP with executable Skill()/Read()/TodoWrite()
- [ ] Planning docs searched, paths absolute or explicit "NONE"
- [ ] File state verified against filesystem, not conversation
- [ ] All paths start with `/`
- [ ] Fresh instance executing Section 0 restores workflow before reading context
</reflection>

<FORBIDDEN>
- Placing Section 0 anywhere except the TOP of output
- Writing "continue the workflow" instead of executable `Skill("name", "--args")`
- Leaving sections 1.9/1.10 blank without explicit search evidence
- Using relative paths (all paths must start with `/`)
- Trusting conversation claims about file state without filesystem verification
</FORBIDDEN>

## Anti-Patterns

| Pattern | Why Fatal | Prevention |
|---------|-----------|------------|
| Missing Section 0 | Agent reads context first, starts ad-hoc | Section 0 MUST be at TOP |
| "Continue workflow" | Not executable | Write `Skill("name", "--args")` |
| Blank 1.9/1.10 | Agent misses plan docs | Always search, write explicit result |
| Relative paths | Break on resume | All paths start with `/` |
| Trusting claims | State is stale | Verify with actual file reads |

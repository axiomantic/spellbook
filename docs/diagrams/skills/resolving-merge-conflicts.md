<!-- diagram-meta: {"source": "skills/resolving-merge-conflicts/SKILL.md", "source_hash": "sha256:58f8ab125df4ff9e40a28241599e78ab2df250d0a8fdb4e08fff2c34249cfa0b", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: resolving-merge-conflicts

Resolve git merge conflicts through mandatory 3-way analysis and synthesis, never selecting ours/theirs, preserving both branches' intent.

```mermaid
flowchart TD
    START([Merge Conflict Detected]) --> DETECT[List Conflicted Files]
    DETECT --> CLASSIFY{Conflict type?}
    CLASSIFY -->|Mechanical| AUTO[Auto-Resolve]
    AUTO --> NEXT_FILE
    CLASSIFY -->|Binary| ASK_USER[Ask User to Choose]
    ASK_USER --> NEXT_FILE
    CLASSIFY -->|Complex| ANALYSIS[3-Way Diff Analysis]
    ANALYSIS --> BASE[Examine Base State]
    BASE --> OURS[Examine Ours: Change + Intent]
    OURS --> THEIRS[Examine Theirs: Change + Intent]
    THEIRS --> TESTS_EXIST{Tests cover this code?}
    TESTS_EXIST -->|Yes| NOTE_TESTS[Note Test Constraints]
    TESTS_EXIST -->|No| PLAN
    NOTE_TESTS --> PLAN
    PLAN[Draft Synthesis Plan]
    PLAN --> APPROVE{User approves plan?}
    APPROVE -->|No| REVISE[Revise Plan]
    REVISE --> APPROVE
    APPROVE -->|Yes| EXECUTE[Surgical Line-By-Line Edit]
    EXECUTE --> SIZE_CHECK{Change >20 lines?}
    SIZE_CHECK -->|Yes| EXPLICIT_OK{Explicit approval?}
    EXPLICIT_OK -->|No| REDUCE[Reduce Scope]
    REDUCE --> EXECUTE
    EXPLICIT_OK -->|Yes| SYNTHESIS_TEST
    SIZE_CHECK -->|No| SYNTHESIS_TEST
    SYNTHESIS_TEST{Synthesis sentence test?}
    SYNTHESIS_TEST -->|Contains ours/theirs| REDO[Redo as True Synthesis]
    REDO --> EXECUTE
    SYNTHESIS_TEST -->|Names both contributions| NEXT_FILE
    NEXT_FILE{More conflicts?}
    NEXT_FILE -->|Yes| CLASSIFY
    NEXT_FILE -->|No| VERIFY_TESTS{Tests pass?}
    VERIFY_TESTS -->|No| FIX[Fix Until Passing]
    FIX --> VERIFY_TESTS
    VERIFY_TESTS -->|Yes| LINT{Lint/Build clean?}
    LINT -->|No| FIX_LINT[Fix Lint Issues]
    FIX_LINT --> LINT
    LINT -->|Yes| MARKERS{No conflict markers?}
    MARKERS -->|No| CLEAN[Remove Remaining Markers]
    CLEAN --> MARKERS
    MARKERS -->|Yes| DONE([All Conflicts Resolved])

    style START fill:#4CAF50,color:#fff
    style DONE fill:#4CAF50,color:#fff
    style DETECT fill:#2196F3,color:#fff
    style AUTO fill:#2196F3,color:#fff
    style ASK_USER fill:#2196F3,color:#fff
    style ANALYSIS fill:#2196F3,color:#fff
    style BASE fill:#2196F3,color:#fff
    style OURS fill:#2196F3,color:#fff
    style THEIRS fill:#2196F3,color:#fff
    style PLAN fill:#2196F3,color:#fff
    style EXECUTE fill:#2196F3,color:#fff
    style CLASSIFY fill:#FF9800,color:#fff
    style TESTS_EXIST fill:#FF9800,color:#fff
    style APPROVE fill:#FF9800,color:#fff
    style SIZE_CHECK fill:#FF9800,color:#fff
    style EXPLICIT_OK fill:#FF9800,color:#fff
    style NEXT_FILE fill:#FF9800,color:#fff
    style SYNTHESIS_TEST fill:#f44336,color:#fff
    style VERIFY_TESTS fill:#f44336,color:#fff
    style LINT fill:#f44336,color:#fff
    style MARKERS fill:#f44336,color:#fff
```

## Legend

| Color | Meaning |
|-------|---------|
| Green (#4CAF50) | Skill invocation |
| Blue (#2196F3) | Command/action |
| Orange (#FF9800) | Decision point |
| Red (#f44336) | Quality gate |

## Cross-Reference

| Node | Source Reference |
|------|----------------|
| List Conflicted Files | Resolution Workflow step 1: detect and classify |
| Conflict type? | Conflict Classification table: Mechanical, Binary, Complex |
| Auto-Resolve | Mechanical: regenerate locks, chronological changelog merge |
| Ask User to Choose | Acceptable Amputation Cases: binary files, no synthesis possible |
| 3-Way Diff Analysis | Resolution Workflow step 2: base vs ours vs theirs |
| Examine Base/Ours/Theirs | Reasoning Schema: merge base state, ours changed, theirs changed |
| Tests cover this code? | Invariant Principle 4: evidence-based decisions |
| Draft Synthesis Plan | Plan Template: base, ours, theirs, synthesis, risk |
| User approves plan? | Invariant Principle 5: consent before loss |
| Surgical Line-By-Line Edit | Invariant Principle 3: surgical precision |
| Change >20 lines? | Invariant Principle 3: >20 line changes require explicit approval |
| Synthesis sentence test | Mechanical Synthesis Test in Self-Check section |
| Tests pass? | Self-Check: tests pass, both ours and theirs functionality |
| Lint/Build clean? | Self-Check: lint/build clean |
| No conflict markers? | Self-Check: all conflicts resolved, no markers remain |

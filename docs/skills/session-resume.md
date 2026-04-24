# session-resume

**Auto-invocation:** Your coding assistant will automatically invoke this skill when it detects a matching trigger.

> Session resume protocol and session repairs handling. Loaded when spellbook_session_init returns resume_available: true, or when session_init returns a repairs array. Triggers: 'resume', 'continue', 'where were we', session resume, session repairs.
## Skill Content

``````````markdown
<analysis>
Protocol for restoring prior session state (skill phase, todos, workflow) and handling session repairs from spellbook_session_init.
</analysis>

<reflection>
Did I execute the boot prompt immediately and announce restoration in the greeting, including any repair items?
</reflection>

## Invariant Principles

1. **Boot Prompt Executes Immediately** - The resume boot prompt runs before any other user interaction; it is not optional or deferrable.
2. **Continuation Intent Governs Action** - The user's first message determines whether to resume, start fresh, or default to resume; never assume.
3. **Corrupted State Is Announced, Not Silently Skipped** - If todos or workflow state is malformed, inform the user explicitly rather than proceeding with partial data.

## Session Resume Protocol

When `spellbook_session_init` returns `resume_available: true`, follow this protocol exactly.

### Resume Fields

| Field                     | Type   | Description                        |
| ------------------------- | ------ | ---------------------------------- |
| `resume_available`        | bool   | Recent session (<24h) exists       |
| `resume_session_id`       | string | Session soul ID                    |
| `resume_age_hours`        | float  | Hours since bound                  |
| `resume_bound_at`         | string | ISO bind timestamp                 |
| `resume_active_skill`     | string | Active skill (e.g., "develop")     |
| `resume_skill_phase`      | string | Skill phase (e.g., "DESIGN")       |
| `resume_pending_todos`    | int    | Incomplete todo count              |
| `resume_todos_corrupted`  | bool   | Todo JSON malformed                |
| `resume_workflow_pattern` | string | Workflow (e.g., "TDD")             |
| `resume_boot_prompt`      | string | Section 0 boot prompt              |

### Resume Execution

1. Execute `resume_boot_prompt` IMMEDIATELY (Section 0 actions)
2. Section 0 includes: skill invocation with `--resume <phase>` if active, `Read()` for planning docs, `TodoWrite()` for todo state, behavioral constraints from prior session
3. After Section 0, announce restoration in greeting

If `resume_todos_corrupted: true`: announce to user that todo state was malformed and requires manual restoration.

### Continuation Detection

| Pattern                                     | Intent      | Action                                        |
| ------------------------------------------- | ----------- | --------------------------------------------- |
| "continue", "resume", "where were we"       | continue    | Execute boot prompt                           |
| "start fresh", "new session", "clean slate" | fresh_start | Skip resume, return `resume_available: false` |
| "ok", "next", neutral message               | neutral     | Execute boot prompt (if session exists)       |

## Session Repairs

When `spellbook_session_init` returns a `repairs` array, display each repair according to its severity:

| Severity  | Action                                                    |
| --------- | --------------------------------------------------------- |
| `error`   | Display prominently. These may affect functionality.      |
| `warning` | Display as informational. Suggest the fix command.        |

### Example Greeting with Repairs

> Welcome to spellbook-enhanced Claude.
>
> Repairs needed:
> - (currently none; list retained for future repair items)
``````````

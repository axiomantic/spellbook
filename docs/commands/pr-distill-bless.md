# /pr-distill-bless

## Workflow Diagram

# Diagram: pr-distill-bless

Save a discovered pattern for future PR distillation. Validates pattern ID, checks for duplicates, and persists to project config.

```mermaid
flowchart TD
    Start([Pattern ID Input]) --> ValidateID{"Pattern ID\nValid?"}
    ValidateID -->|No| RejectID["Reject: Invalid\nFormat"]
    RejectID --> ShowRules["Show Validation\nRules"]
    ShowRules --> Done2([Aborted])
    ValidateID -->|Yes| CheckReserved{"Reserved Prefix\n_builtin-?"}
    CheckReserved -->|Yes| RejectBuiltin["Reject: Built-in\nPattern"]
    RejectBuiltin --> Done2
    CheckReserved -->|No| LoadConfig["Load Existing\nConfig"]
    LoadConfig --> ConfigExists{"Config File\nExists?"}
    ConfigExists -->|No| CreateDefaults["Create Config\nWith Defaults"]
    ConfigExists -->|Yes| CheckDuplicate{"Pattern Already\nBlessed?"}
    CreateDefaults --> AddPattern["Add to\nblessed_patterns"]
    CheckDuplicate -->|No| AddPattern
    CheckDuplicate -->|Yes| WarnOverwrite["Warn: Pattern\nExists"]
    WarnOverwrite --> ConfirmOverwrite{"Confirm\nOverwrite?"}
    ConfirmOverwrite -->|No| Done2
    ConfirmOverwrite -->|Yes| UpdatePattern["Update Existing\nPattern"]
    AddPattern --> SaveConfig["Save Updated\nConfig"]
    UpdatePattern --> SaveConfig
    SaveConfig --> VerifyPersist{"Pattern in\nConfig File?"}
    VerifyPersist -->|No| SaveConfig
    VerifyPersist -->|Yes| Done([Pattern Blessed])

    style Start fill:#4CAF50,color:#fff
    style Done fill:#4CAF50,color:#fff
    style Done2 fill:#f44336,color:#fff
    style RejectID fill:#2196F3,color:#fff
    style ShowRules fill:#2196F3,color:#fff
    style RejectBuiltin fill:#2196F3,color:#fff
    style LoadConfig fill:#2196F3,color:#fff
    style CreateDefaults fill:#2196F3,color:#fff
    style AddPattern fill:#2196F3,color:#fff
    style WarnOverwrite fill:#2196F3,color:#fff
    style UpdatePattern fill:#2196F3,color:#fff
    style SaveConfig fill:#2196F3,color:#fff
    style ValidateID fill:#f44336,color:#fff
    style CheckReserved fill:#FF9800,color:#fff
    style ConfigExists fill:#FF9800,color:#fff
    style CheckDuplicate fill:#FF9800,color:#fff
    style ConfirmOverwrite fill:#FF9800,color:#fff
    style VerifyPersist fill:#f44336,color:#fff
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
# PR Distill Bless

<ROLE>
Pattern Curator. Your reputation depends on blessing patterns that genuinely reduce review burden without hiding important changes.
</ROLE>

## Invariant Principles

1. **User Confirmation Required**: Never bless patterns automatically. User must explicitly invoke this command.
2. **Validate Pattern ID**: Pattern must match validation rules (lowercase, hyphens, 2-50 chars).
3. **Warn on Overwrite**: If pattern already exists, warn and confirm before updating.
4. **Persistence Is Immediate**: Once blessed, pattern affects all future distillations in this project.

## Execution

<analysis>
When invoked with `/distilling-prs-bless <pattern-id>`:
1. Validate pattern ID format
2. Load existing config (or create with defaults)
3. Check if pattern already blessed
4. If new: add to blessed_patterns
5. If exists: warn and confirm overwrite
6. Save updated config
</analysis>

<reflection>
After blessing:
- Verify pattern appears in config file
- Confirm future distillations will recognize pattern
- Pattern will increase confidence for matching changes
</reflection>

## Usage

```
/distilling-prs-bless <pattern-id>
```

### Examples

```
/distilling-prs-bless query-count-json
/distilling-prs-bless import-cleanup
/distilling-prs-bless test-factory-setup
```

## Pattern ID Rules

| Requirement | Valid | Invalid |
|------------|-------|---------|
| Length | 2-50 chars | `a`, `very-long-pattern-id-...` |
| Characters | `[a-z0-9-]` | `CAPS`, `under_score` |
| Start | Letter | `123-foo` |
| End | Letter or number | `foo-` |
| No double hyphen | `foo-bar` | `foo--bar` |

Reserved prefix: `_builtin-` (built-in patterns only)

## Configuration

Blessed patterns stored in:
`~/.local/spellbook/docs/<project-encoded>/distilling-prs-config.json`

```json
{
  "blessed_patterns": ["query-count-json", "import-cleanup"]
}
```

## Notes

- Pattern IDs come from "Discovered Patterns" section of distillation reports
- Blessing is project-specific and persists across sessions
- To remove a blessed pattern, manually edit the config file

<FORBIDDEN>
- Blessing patterns without user explicitly running this command
- Accepting invalid pattern IDs that don't match validation rules
- Overwriting existing patterns without warning
- Blessing built-in patterns (they're already recognized)
</FORBIDDEN>
``````````

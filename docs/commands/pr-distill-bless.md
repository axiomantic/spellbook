# /pr-distill-bless

## Workflow Diagram

# PR Distill Bless - Command Diagram

## Process Flow

```mermaid
flowchart TD
    subgraph Legend
        direction LR
        L1[Process]
        L2{Decision}
        L3([Terminal])
        L4[/"Input/Output"/]
        style L1 fill:#2196F3,color:#fff
        style L2 fill:#FF9800,color:#fff
        style L3 fill:#51cf66,color:#000
        style L4 fill:#fff,color:#000
    end

    Start([User invokes<br>/distilling-prs-bless pattern-id]) --> Validate

    subgraph Validation ["Phase 1: Pattern ID Validation"]
        Validate[Parse pattern-id<br>from command args]
        Validate --> CheckFormat{Matches format rules?<br>a-z0-9 hyphens, 2-50 chars<br>starts with letter<br>ends letter/number<br>no double hyphens}
        CheckFormat -->|No| RejectInvalid([Reject:<br>show validation error])
        CheckFormat -->|Yes| CheckReserved{Starts with<br>_builtin- prefix?}
        CheckReserved -->|Yes| RejectBuiltin([Reject:<br>built-in patterns<br>cannot be blessed])
        CheckReserved -->|No| LoadConfig
    end

    subgraph ConfigLoad ["Phase 2: Configuration"]
        LoadConfig[Load distilling-prs-config.json<br>from project config dir]
        LoadConfig --> ConfigExists{Config file<br>exists?}
        ConfigExists -->|No| CreateDefaults[Create config with<br>empty blessed_patterns]
        ConfigExists -->|Yes| CheckExisting
        CreateDefaults --> CheckExisting
    end

    subgraph Blessing ["Phase 3: Bless Pattern"]
        CheckExisting{Pattern already<br>in blessed_patterns?}
        CheckExisting -->|No| AddPattern[Add pattern-id<br>to blessed_patterns]
        CheckExisting -->|Yes| WarnOverwrite[Warn: pattern<br>already exists]
        WarnOverwrite --> ConfirmOverwrite{User confirms<br>overwrite?}
        ConfirmOverwrite -->|No| Abort([Abort:<br>pattern unchanged])
        ConfirmOverwrite -->|Yes| UpdatePattern[Update existing<br>pattern entry]
        AddPattern --> SaveConfig
        UpdatePattern --> SaveConfig
        SaveConfig[Save updated config<br>to disk]
    end

    subgraph Verify ["Phase 4: Verification"]
        SaveConfig --> VerifyPresent{Pattern appears<br>in saved config?}
        VerifyPresent -->|No| SaveConfig
        VerifyPresent -->|Yes| ConfirmFuture[Confirm future<br>distillations will<br>recognize pattern]
        ConfirmFuture --> Success([Success:<br>pattern blessed])
    end

    style Start fill:#51cf66,color:#000
    style Success fill:#51cf66,color:#000
    style RejectInvalid fill:#ff6b6b,color:#000
    style RejectBuiltin fill:#ff6b6b,color:#000
    style Abort fill:#ff6b6b,color:#000

    style Validate fill:#2196F3,color:#fff
    style LoadConfig fill:#2196F3,color:#fff
    style CreateDefaults fill:#2196F3,color:#fff
    style AddPattern fill:#2196F3,color:#fff
    style WarnOverwrite fill:#2196F3,color:#fff
    style UpdatePattern fill:#2196F3,color:#fff
    style SaveConfig fill:#2196F3,color:#fff
    style ConfirmFuture fill:#2196F3,color:#fff

    style CheckFormat fill:#FF9800,color:#fff
    style CheckReserved fill:#FF9800,color:#fff
    style ConfigExists fill:#FF9800,color:#fff
    style CheckExisting fill:#FF9800,color:#fff
    style ConfirmOverwrite fill:#FF9800,color:#fff

    style VerifyPresent fill:#ff6b6b,color:#000
```

## Legend

| Color | Meaning |
|-------|---------|
| Green (#51cf66) | Terminal nodes (start/success) |
| Blue (#2196F3) | Process/action steps |
| Orange (#FF9800) | Decision points |
| Red (#ff6b6b) | Quality gates / rejection terminals |

## Node Reference

| Node | Source Section |
|------|---------------|
| Validate, CheckFormat, CheckReserved | Pattern ID Rules table, Invariant 2 |
| LoadConfig, ConfigExists, CreateDefaults | Execution steps 2-3, Configuration section |
| CheckExisting, WarnOverwrite, ConfirmOverwrite | Execution steps 3-5, Invariant 3 |
| AddPattern, UpdatePattern, SaveConfig | Execution step 6, Invariant 4 |
| VerifyPresent, ConfirmFuture | Reflection section |
| RejectInvalid, RejectBuiltin | FORBIDDEN rules, Pattern ID Rules |
| Abort | Invariant 3 (overwrite confirmation) |

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
- To remove a blessed pattern, manually edit the config file

<FORBIDDEN>
- Blessing patterns without user explicitly running this command
- Accepting invalid pattern IDs that don't match validation rules
- Overwriting existing patterns without warning
- Blessing built-in patterns (they're already recognized)
</FORBIDDEN>

<FINAL_EMPHASIS>
Blessed patterns persist and affect all future distillations. Never bless without user confirmation, never skip validation, never overwrite silently.
</FINAL_EMPHASIS>
``````````

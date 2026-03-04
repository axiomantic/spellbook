# Git Safety Protocol

<ROLE>
Git Safety Enforcer. Your reputation depends on never executing git operations with side effects without explicit user consent. One unauthorized `--force` push can destroy work permanently.
</ROLE>

## Invariant Principles

1. **User Agency**: Repository state changes require explicit user consent
2. **Reversibility Awareness**: Destructive operations demand impact disclosure before execution
3. **Context Preservation**: Never discard uncommitted work without warning
4. **Clean History**: No auto-generated footers, no issue tags in commits
5. **Interactive Incompatibility**: Never use `-i` flags; CLI environment cannot handle them

## Permission Matrix

| Risk Level | Operations | Requirement |
|------------|-----------|-------------|
| Standard | commit, push, checkout, restore, stash, merge, rebase, reset | Permission |
| Destructive | `--force`, `--hard` | Warning + explicit confirmation |
| Forbidden | `--no-verify`, config modification, `-i` flags | Never (unless user explicitly requests `--no-verify`) |

<FORBIDDEN>
- Co-authorship footers in commits
- GitHub issue tags in commits (e.g., `fixes #123`) — tags belong in PR title/description only, added manually by user
</FORBIDDEN>

## Pre-Operation Validation

<analysis>
Before any git operation with side effects:
- User intent confirmed?
- Uncommitted changes at risk?
- Target branch/ref exists?
- Destructive impact explained?
</analysis>

## Confirmation Template

```
Running: `git [command]`
Effect: [description]
[If destructive]: Warning: Cannot be undone.
Proceed?
```

## Skill Reference

Skills reference this pattern as:

```markdown
## Git Operations
Follow patterns/git-safety-protocol.md
```

<FINAL_EMPHASIS>
Never execute git operations with side effects without stopping to ask. Never run destructive operations without explicitly disclosing their impact first. Unauthorized git actions destroy real work irreversibly.
</FINAL_EMPHASIS>

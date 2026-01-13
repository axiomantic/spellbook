# Git Safety Protocol

## Invariant Principles

1. **User Agency**: Repository state changes require explicit user consent
2. **Reversibility Awareness**: Destructive operations demand impact disclosure
3. **Context Preservation**: Never discard uncommitted work without warning
4. **Clean History**: No auto-generated footers, no issue tags in commits
5. **Interactive Incompatibility**: CLI environment cannot handle `-i` flags

## Permission Matrix

| Risk Level | Operations | Requirement |
|------------|-----------|-------------|
| Standard | commit, push, checkout, restore, stash, merge, rebase, reset | Permission |
| Destructive | `--force`, `--hard` | Warning + explicit confirmation |
| Forbidden | `--no-verify`, config modification, `-i` flags | Never (unless user explicitly requests `--no-verify`) |

## Prohibited in Commits

- Co-authorship footers
- GitHub issue tags (e.g., `fixes #123`)

## Pre-Operation Validation

<analysis>
Before git operation with side effects:
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

```markdown
## Git Operations
Follow patterns/git-safety-protocol.md
```

# Git Safety Protocol

## Purpose
Standard safety checks and confirmation requirements for git operations. Reference this pattern instead of repeating safety rules in each skill.

## Core Rules

| Operation | Requirement |
|-----------|-------------|
| `commit` | Ask permission first |
| `push` | Ask permission first |
| `checkout` | Ask permission first |
| `restore` | Ask permission first |
| `stash` | Ask permission first |
| `merge` | Ask permission first |
| `rebase` | Ask permission first |
| `reset` | Ask permission first |
| `push --force` | Warn strongly, require explicit confirmation |
| `reset --hard` | Warn strongly, require explicit confirmation |

## Pre-Operation Checklist

Before ANY git operation with side effects:

```
1. [ ] Confirm user intent
2. [ ] Check for uncommitted changes that might be lost
3. [ ] Verify target branch/ref exists
4. [ ] For destructive ops: explain what will be lost
```

## Prohibited Actions

- NEVER use `--no-verify` unless user explicitly requests
- NEVER use `--force` on main/master without strong warning
- NEVER modify git config
- NEVER use interactive flags (`-i`) - not supported
- NEVER put co-authorship footers in commits
- NEVER tag GitHub issues in commit messages

## Confirmation Format

```
I'm about to run: `git [command]`

This will: [explain effect]
[If destructive]: Warning: This cannot be undone.

Proceed? (yes/no)
```

## Usage in Skills

Reference this pattern:
```markdown
## Git Operations
Follow patterns/git-safety-protocol.md for all git commands.
```

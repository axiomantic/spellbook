# /merge-work-packets

Verify all tracks are complete, invoke smart-merge to combine branches, and run QA gates.

## Usage

```bash
/merge-work-packets <packet_dir> [--continue-merge]
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `packet_dir` | path | Yes | Directory containing `manifest.json` |
| `--continue-merge` | flag | No | Continue after manual conflict resolution |

## Overview

After all work packets have been executed (either in parallel sessions or sequentially), this command merges the work back together and ensures quality standards are met.

## Workflow

1. **Verify completion** - Check that all tracks have completion markers
2. **Invoke smart-merge** - Use the smart-merge skill to combine branches
3. **Handle conflicts** - If conflicts occur:
   - Offer manual resolution or abort
   - Use `--continue-merge` after resolving
4. **Run QA gates** - Execute all configured quality gates:
   - `pytest` (or project test runner)
   - `green-mirage-audit`
   - `factchecker`
5. **Report results** - Success or failure with details

## Verification

Before merging, the command verifies:

```
Verifying track completion...
  Track 1 (backend): .track-1-complete.json exists
  Track 2 (frontend): .track-2-complete.json exists
  Track 3 (tests): .track-3-complete.json exists

All 3 tracks complete. Proceeding to merge.
```

## Conflict Resolution

If smart-merge encounters conflicts:

```
Merge conflict detected in src/api/auth.ts

OPTIONS:
A) Manual resolution - Open editor to resolve, then run --continue-merge
B) Abort - Cancel merge and investigate

Your choice: ___
```

After manual resolution:

```bash
/merge-work-packets ~/.claude/work-packets/user-auth/ --continue-merge
```

## QA Gates

The command runs all QA gates specified in the manifest:

```json
{
  "post_merge_qa": ["tests", "green-mirage-audit", "factchecker"]
}
```

Each gate must pass before the merge is considered successful.

## Example

```bash
# Merge all completed work packets
/merge-work-packets ~/.claude/work-packets/user-auth/

# Continue after resolving conflicts
/merge-work-packets ~/.claude/work-packets/user-auth/ --continue-merge
```

## Output

```
Verifying track completion...
  All 3 tracks complete.

Invoking smart-merge skill...
  Merging track-1-backend into main...
  Merging track-2-frontend into main...
  Merging track-3-tests into main...
  Merge complete.

Running QA gates...
  pytest: PASSED (45 tests)
  green-mirage-audit: PASSED (no green mirages)
  factchecker: PASSED (no false claims)

All QA gates passed.
Feature merge complete!

Next steps:
- Review changes: git diff main~1
- Create PR: gh pr create
- Or: /finishing-a-development-branch
```

## Related

- [/execute-work-packet](execute-work-packet.md) - Execute a single packet
- [/execute-work-packets-seq](execute-work-packets-seq.md) - Execute all packets sequentially
- [smart-merge](../skills/smart-merge.md) - Skill for intelligent branch merging
- [implement-feature](../skills/implement-feature.md) - Skill that generates work packets

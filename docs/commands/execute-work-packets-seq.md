# /execute-work-packets-seq

Execute all work packets in dependency order, one at a time. Use this when you want to work through all tracks sequentially in a single session (with context resets between tracks).

## Usage

```bash
/execute-work-packets-seq <packet_dir>
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `packet_dir` | path | Yes | Directory containing `manifest.json` and packet files |

## Overview

This command executes the entire feature implementation by working through work packets sequentially. It's the alternative to running parallel sessions ("swarmed" mode) when you prefer a single-session workflow.

## Workflow

1. **Load manifest** - Read `manifest.json` from the packet directory
2. **Topological sort** - Order tracks by dependencies (independent tracks first)
3. **Execute each packet** - Process tracks in dependency order:
   - Execute all tasks for the track
   - Create completion marker
   - Suggest `/shift-change` to reset context
4. **Completion** - When all tracks done, suggest `/merge-work-packets`

## Context Management

After each track completes, the command suggests running `/shift-change` to:

- Reset context for the next track
- Preserve progress in the checkpoint/completion markers
- Prevent context overflow during long implementations

## Recovery

If execution is interrupted:

1. The command checks for existing completion markers
2. Skips already-completed tracks
3. Resumes the in-progress track from its checkpoint
4. Continues with remaining tracks

## Example

```bash
# Execute all packets for a feature
/execute-work-packets-seq ~/.claude/work-packets/user-auth/

# Directory structure:
# ~/.claude/work-packets/user-auth/
# ├── manifest.json
# ├── track-1-backend.md
# ├── track-2-frontend.md
# ├── track-3-tests.md
# └── checkpoints/
```

## Output

```
Executing work packets sequentially...

Track 1: backend (no dependencies)
  Executing track-1-backend.md...
  [TDD workflow for each task]
  Track 1 complete.

  Suggest: /shift-change to reset context before next track

Track 2: frontend (depends on: backend)
  Verifying Track 1 completion... OK
  Executing track-2-frontend.md...
  [TDD workflow for each task]
  Track 2 complete.

...

All tracks complete!
Suggest: /merge-work-packets ~/.claude/work-packets/user-auth/
```

## Related

- [/execute-work-packet](execute-work-packet.md) - Execute a single packet
- [/merge-work-packets](merge-work-packets.md) - Merge completed packets
- [/shift-change](shift-change.md) - Reset session context
- [implement-feature](../skills/implement-feature.md) - Skill that generates work packets

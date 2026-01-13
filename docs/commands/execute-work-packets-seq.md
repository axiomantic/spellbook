# /execute-work-packets-seq

## Command Content

``````````markdown
# Execute Work Packets Sequentially

<ROLE>
Workflow Orchestrator. Stakes: wrong ordering corrupts builds, skipped dependencies cause silent failures.
</ROLE>

## Invariant Principles

1. **Dependency ordering is inviolable.** Never execute track before dependencies complete.
2. **Completion markers are truth.** Track state exists only in `track-{id}.completion.json`.
3. **Failure halts sequence.** No partial execution; dependent tracks must not start.
4. **Execution is idempotent.** Skip tracks with existing completion markers on resume.
5. **Context compaction preserves capacity.** Suggest /handoff between tracks to prevent overflow.

## Parameters

- `packet_dir` (required): Directory containing manifest.json and packet files

## Manifest Schema

```json
{
  "format_version": "1.0.0",
  "feature": "feature-name",
  "tracks": [{
    "id": 1,
    "name": "Track name",
    "packet": "track-1.md",
    "worktree": "/path/to/wt",
    "branch": "feature/track-1",
    "depends_on": []
  }],
  "merge_strategy": "worktree-merge",
  "post_merge_qa": ["pytest", "green-mirage-audit"]
}
```

## Execution Protocol

### 1. Load Manifest

<analysis>
Required fields: format_version, feature, tracks[], merge_strategy, post_merge_qa
Each track requires: id, name, packet, worktree, branch, depends_on[]
</analysis>

Abort if any required field missing.

### 2. Topological Sort

**Algorithm:**
```
completed = [], execution_order = []
while tracks remain:
  find track where ALL depends_on in completed
  if none found: ABORT (circular dependency)
  add track to execution_order, track.id to completed
```

<reflection>
Validate: all dependency IDs reference valid tracks. Report cycle path if circular.
</reflection>

### 3. Sequential Execution

For each track in execution_order:

```
# Skip if already complete (idempotent)
if exists "$packet_dir/track-{id}.completion.json": skip

# Execute via /execute-work-packet
/execute-work-packet {packet_dir}/{track.packet}

# Verify completion marker created
if not exists completion marker: ABORT
```

Invoke /execute-work-packet blocking. Wait for completion before next track.

### 4. Context Compaction

After each track:
- Display progress (completed/total)
- Suggest `/handoff` to preserve session capacity
- Critical for 3+ track sequences

### 5. Completion

All tracks complete when every `track-{id}.completion.json` exists with `"status": "complete"`.

**Output:**
```
All tracks completed. Next: /merge-work-packets {packet_dir}
```

## Error Handling

| Error | Response |
|-------|----------|
| Track execution fails | STOP. Report track, task, message. Suggest --resume. |
| Circular dependency | ABORT at sort. Report cycle path. |
| Missing completion marker | Execution protocol violation. Re-run track. |
| Missing dependency ID | Manifest corruption. Abort, verify manifest. |

## Recovery

On resume with same packet_dir:
1. Scan for existing completion markers
2. Topological sort identifies remaining tracks
3. Skip completed, resume from first incomplete

<FORBIDDEN>
- Executing a track before ALL its dependencies have completion markers
- Continuing after a track failure (corrupts dependency assumptions)
- Skipping topological sort (manual ordering is error-prone)
- Modifying completion markers manually (source of truth corruption)
</FORBIDDEN>

## When to Use

**Sequential (this command):** Dependencies exist, debugging, learning workflow, resource-constrained.

**Parallel (/execute-work-packet individually):** Independent tracks, speed priority, sufficient resources.
``````````

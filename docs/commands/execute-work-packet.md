# /execute-work-packet

## Command Content

``````````markdown
# Execute Work Packet

<ROLE>
Work Packet Executor. Quality measured by zero incomplete tasks proceeding past gates.
</ROLE>

<analysis>
Work packet execution requires: dependency satisfaction, TDD rigor, checkpoint resilience, verification gates.
</analysis>

## Invariant Principles

1. **Dependency-First**: Never begin work until all dependent tracks have completion markers
2. **TDD-Mandatory**: Every task follows RED-GREEN-REFACTOR; no implementation without failing test first
3. **Checkpoint-Resilient**: Atomic checkpoints after each task enable fine-grained recovery
4. **Evidence-Gated**: Acceptance criteria verified through fact-checking; claims require proof
5. **Isolation-Enforced**: Worktree branch must match packet specification; no cross-contamination

## Parameters

| Parameter | Required | Purpose |
|-----------|----------|---------|
| `packet_path` | Yes | Absolute path to work packet .md file |
| `--resume` | No | Resume from existing checkpoint |

## Execution States

```
[Parse] -> [Dependencies] -> [Checkpoint?] -> [Worktree] -> [TDD Loop] -> [Complete]
                |                                              |
                v                                              v
            [Wait/Abort]                                  [Fail/Stop]
```

## Phase 1: Parse Packet

Extract from packet file:
- `format_version`, `feature`, `track`, `worktree`, `branch`
- `tasks[]`: id, description, files, acceptance criteria

Load manifest from `$packet_dir/manifest.json` to get dependency graph.

## Phase 2: Dependency Gate

<reflection>
Why gate on dependencies? Parallel tracks may modify shared interfaces. Without dependency ordering, merge conflicts and semantic breaks propagate.
</reflection>

**Check**: For each `track_id` in `depends_on`, verify `track-{id}.completion.json` exists.

**If dependencies missing**:
- Display blocking tracks
- Offer: **Wait** (poll 30s intervals, 30min timeout) or **Abort**

## Phase 3: Checkpoint Resume

If `--resume` and checkpoint exists at `track-{track}.checkpoint.json`:
- Load `last_completed_task`, `next_task`
- Skip to `next_task`

**Checkpoint Schema**:
```json
{"format_version":"1.0.0","track":1,"last_completed_task":"1.2","commit":"abc123","timestamp":"ISO8601","next_task":"1.3"}
```

## Phase 4: Worktree Verification

Navigate to packet's worktree. Verify branch matches expectation.

**HARD FAIL** if branch mismatch. No implicit checkout.

## Phase 5: TDD Task Loop

For each task (skipping completed if resuming):

### 5a. Display
```
=== Task {id}: {description} ===
Files: {files} | Acceptance: {acceptance}
```

### 5b. TDD Cycle
Invoke `test-driven-development` skill:
- RED: Write failing test first
- GREEN: Minimal implementation to pass
- REFACTOR: Improve without changing behavior

### 5c. Code Review Gate
Invoke `requesting-code-review` skill. Address ALL feedback before proceeding.

### 5d. Fact-Check Gate
Invoke `fact-checking` skill:
- Verify acceptance criteria met (evidence required)
- Confirm test coverage for task files
- Check no regressions

<reflection>
Why three gates? TDD ensures correctness, review catches design issues, fact-check prevents Green Mirage (tests pass but criteria unmet).
</reflection>

### 5e. Checkpoint
Atomic write to `track-{track}.checkpoint.json` with current commit, completed task, next task.

## Phase 6: Completion Marker

After ALL tasks pass all gates:

```json
{"format_version":"1.0.0","status":"complete","commit":"<final>","timestamp":"ISO8601"}
```

Write to `track-{track}.completion.json`. This unblocks dependent tracks.

## Error Handling

| Condition | Action |
|-----------|--------|
| Dependency timeout (30min) | Abort, suggest checking blocking tracks |
| TDD failure | STOP. No checkpoint. No proceed. |
| Review issues | Address all, may re-run TDD |
| Fact-check fail | Return to TDD. Task not complete. |

**CRITICAL**: Never checkpoint failed tasks. Never proceed past unverified gates.

## Recovery

```bash
/execute-work-packet <packet_path> --resume
```

Loads checkpoint, skips completed, continues from `next_task`.

## Completion Output

```
Track {track}: COMPLETE
Tasks: {count}/{count} passed
Commit: {hash}
Next: /merge-work-packets (if last track) or await dependent execution
```

<FORBIDDEN>
- Proceeding past any gate without explicit pass
- Checkpointing tasks that failed any gate
- Starting work before dependencies verified
- Implicit branch checkout on mismatch
- Skipping TDD for "simple" changes
</FORBIDDEN>
``````````

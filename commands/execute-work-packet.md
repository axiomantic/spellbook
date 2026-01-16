---
description: Execute a single work packet - read packet, check dependencies, run tasks via TDD, mark complete.
disable-model-invocation: true
---

# Execute Work Packet

<ROLE>
Work Packet Executor. Quality measured by zero incomplete tasks proceeding past gates.
</ROLE>

<analysis>
Work packet execution requires: dependency satisfaction, TDD rigor, checkpoint resilience, verification gates.
</analysis>

Execute a single work packet following Test-Driven Development methodology with proper dependency checking and checkpoint management.

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

## Phase 1: Parse and Validate Packet

```bash
# Load the packet file
packet_file="<packet_path>"
packet_dir="$(dirname "$packet_file")"

# Extract packet metadata using parse_packet_file
# This loads YAML frontmatter and extracts tasks
```

The packet parser extracts:
- `format_version`: Version of packet format
- `feature`: Feature name
- `track`: Track number (1, 2, 3, etc.)
- `worktree`: Path to track's worktree
- `branch`: Branch name
- `tasks`: List of task dictionaries with id, description, files, acceptance

Load manifest from `$packet_dir/manifest.json` to get dependency graph.

## Phase 2: Dependency Gate

<CRITICAL>
Dependency violations cause cascading failures. A track that starts before its dependencies complete may build on interfaces that will change, creating merge conflicts and semantic breaks that require full rework. The 30-minute wait exists because waiting is cheaper than rebuilding.
</CRITICAL>

<reflection>
Why gate on dependencies? Parallel tracks may modify shared interfaces. Without dependency ordering, merge conflicts and semantic breaks propagate.
</reflection>

```bash
# Load manifest from packet directory
manifest_file="$packet_dir/manifest.json"

# Parse manifest using read_json_safe to get all tracks
# Find current track in manifest
# Get depends_on list for this track
```

**Dependency Check:**
For each track ID in `depends_on`:
1. Check if `track-{id}.completion.json` exists in packet_dir
2. If ALL dependencies have completion markers: proceed
3. If ANY dependency missing:
   - Display: "Track {track} depends on tracks {depends_on}"
   - Display: "Missing completion markers: {missing_tracks}"
   - Offer options:
     - **Wait**: Poll every 30 seconds for 30 minutes, checking for completion markers
     - **Abort**: Exit and report dependencies not met

## Phase 3: Checkpoint Resume

If `--resume` and checkpoint exists:

```bash
checkpoint_file="$packet_dir/track-{track}.checkpoint.json"

if [ "$resume" = true ] && [ -f "$checkpoint_file" ]; then
  # Load checkpoint using read_json_safe
  # Get last_completed_task and next_task
  # Skip to next_task instead of starting from beginning
else
  # Start from first task
fi
```

**Checkpoint Schema:**
```json
{
  "format_version": "1.0.0",
  "track": 1,
  "last_completed_task": "1.2",
  "commit": "abc123",
  "timestamp": "ISO8601",
  "next_task": "1.3"
}
```

## Phase 4: Worktree Verification

```bash
# Navigate to the track's worktree
cd "<worktree_path_from_packet>"

# Verify we're on the correct branch
current_branch=$(git branch --show-current)
expected_branch="<branch_from_packet>"

if [ "$current_branch" != "$expected_branch" ]; then
  echo "ERROR: Expected branch $expected_branch, but on $current_branch"
  exit 1
fi
```

**HARD FAIL** if branch mismatch. No implicit checkout.

## Phase 5: TDD Task Loop

For each task in the packet's task list (skipping completed if resuming):

**IF resuming from checkpoint:**
- Skip tasks until we reach `next_task` from checkpoint
- Continue from that task

### 5a. Display Task Info

```
=== Task {task.id}: {task.description} ===
Files: {task.files}
Acceptance: {task.acceptance}
```

### 5b. TDD Cycle

<CRITICAL>
TDD is not optional. Writing implementation before a failing test creates Green Mirage: code that appears to work but has no specification. When tests are written after implementation, they test what the code does, not what it should do. Skipping TDD for "simple" changes is how regressions enter production.
</CRITICAL>

Invoke the `test-driven-development` skill using the Skill tool with:
- Task description: {task.description}
- Target files: {task.files}
- Acceptance criteria: {task.acceptance}

Follow the TDD RED-GREEN-REFACTOR cycle:
- **RED**: Write failing test first
- **GREEN**: Implement minimal code to pass
- **REFACTOR**: Improve code quality without changing behavior

### 5c. Code Review Gate

Invoke the `requesting-code-review` skill using the Skill tool with:
- Files changed in this task
- Focus: code quality, edge cases, test coverage

Address ALL reviewer feedback before proceeding. May require re-running TDD cycle with fixes.

### 5d. Fact-Check Gate

Invoke the `fact-checking` skill using the Skill tool with:
- Verify acceptance criteria met (evidence required)
- Check test coverage for task files
- Confirm no regressions introduced

<reflection>
Why three gates? TDD ensures correctness, review catches design issues, fact-check prevents Green Mirage (tests pass but criteria unmet).
</reflection>

### 5e. Create Checkpoint

```bash
# Get current git commit
current_commit=$(git rev-parse HEAD)

# Determine next task (if exists)
next_task_id="<next_task_id or null>"

# Write checkpoint using atomic_write_json
checkpoint_data='{
  "format_version": "1.0.0",
  "track": <track_number>,
  "last_completed_task": "<task.id>",
  "commit": "<current_commit>",
  "timestamp": "<ISO8601_timestamp>",
  "next_task": "<next_task_id or null>"
}'

# Save to packet_dir/track-{track}.checkpoint.json
```

### 5f. Continue to Next Task

## Phase 6: Completion Marker

After ALL tasks pass all gates:

```bash
# Get final commit
final_commit=$(git rev-parse HEAD)

# Create completion marker using atomic_write_json
completion_data='{
  "format_version": "1.0.0",
  "status": "complete",
  "commit": "<final_commit>",
  "timestamp": "<ISO8601_timestamp>"
}'

# Save to packet_dir/track-{track}.completion.json
```

**Completion Marker Schema:**
```json
{
  "format_version": "1.0.0",
  "status": "complete",
  "commit": "abc123",
  "timestamp": "ISO8601"
}
```

This unblocks dependent tracks.

## Phase 7: Report Completion

Display:
```
Track {track}: COMPLETE
Tasks: {task_count}/{task_count} passed
Commit: {commit_hash}

Next steps:
- If this was the last track, run: /merge-work-packets
- If more tracks remain, they will execute when dependencies are met
```

## Error Handling

| Condition | Action |
|-----------|--------|
| Dependency timeout (30min) | Abort, suggest checking blocking tracks |
| TDD failure | STOP. No checkpoint. No proceed. Report failure details. |
| Review issues | Address all, may re-run TDD cycle |
| Fact-check fail | Return to TDD. Task not complete. |

**Dependency timeout:**
- If waiting for dependencies exceeds 30 minutes, abort with clear message
- Suggest user check status of blocking tracks

**TDD failure:**
- If test-driven-development skill reports failure, STOP
- Do not proceed to next task
- Do not create checkpoint for failed task
- Report failure details to user

**Code review issues:**
- Address all reviewer feedback before proceeding
- May require re-running TDD cycle with fixes

**Factcheck failure:**
- If acceptance criteria not met, STOP
- Return to TDD phase to fix
- Do not mark task complete

**CRITICAL**: Never checkpoint failed tasks. Never proceed past unverified gates.

## Recovery

To resume a partially completed track:

```bash
/execute-work-packet <packet_path> --resume
```

This will:
- Load checkpoint
- Skip completed tasks
- Resume from next_task
- Continue TDD workflow

## Notes

- All file operations use atomic writes (atomic_write_json) to prevent corruption
- Checkpoints created after each task for fine-grained recovery
- Skills invoked using the Skill tool (test-driven-development, requesting-code-review, fact-checking)
- Worktree isolation ensures parallel tracks don't conflict
- Completion marker enables dependent tracks to proceed

<FORBIDDEN>
- Proceeding past any gate without explicit pass
- Checkpointing tasks that failed any gate
- Starting work before dependencies verified
- Implicit branch checkout on mismatch
- Skipping TDD for "simple" changes
</FORBIDDEN>

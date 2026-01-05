---
description: Execute a single work packet - read packet, check dependencies, run tasks via TDD, mark complete.
disable-model-invocation: true
---

# Execute Work Packet

Execute a single work packet following Test-Driven Development methodology with proper dependency checking and checkpoint management.

## Parameters

- `packet_path` (required): Absolute path to work packet .md file
- `--resume` (optional): Resume from checkpoint if exists

## Execution Protocol

### Step 1: Parse and Validate Packet

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

### Step 2: Load Manifest and Check Dependencies

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

### Step 3: Check for Checkpoint and Resume

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

**Checkpoint Format:**
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

### Step 4: Setup Worktree Environment

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

### Step 5: Execute Tasks with TDD

For each task in the packet's task list:

**IF resuming from checkpoint:**
- Skip tasks until we reach `next_task` from checkpoint
- Continue from that task

**For each task:**

1. **Display Task Info:**
   ```
   === Task {task.id}: {task.description} ===
   Files: {task.files}
   Acceptance: {task.acceptance}
   ```

2. **Invoke test-driven-development skill:**
   ```
   Invoke the test-driven-development skill using the Skill tool with:
   - Task description: {task.description}
   - Target files: {task.files}
   - Acceptance criteria: {task.acceptance}

   Follow the TDD RED-GREEN-REFACTOR cycle:
   - RED: Write failing test
   - GREEN: Implement minimal code to pass
   - REFACTOR: Improve code quality
   ```

3. **After TDD completion, invoke code reviewer:**
   ```
   Invoke the requesting-code-review skill using the Skill tool with:
   - Files changed in this task
   - Focus: code quality, edge cases, test coverage

   Address any issues found before proceeding.
   ```

4. **Invoke factchecker for verification:**
   ```
   Invoke the factchecker skill using the Skill tool with:
   - Verify acceptance criteria met
   - Check test coverage for task files
   - Confirm no regressions introduced
   ```

5. **Create Checkpoint:**
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

6. **Continue to next task**

### Step 6: Create Completion Marker

After ALL tasks complete:

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

**Completion Marker Format:**
```json
{
  "format_version": "1.0.0",
  "status": "complete",
  "commit": "abc123",
  "timestamp": "ISO8601"
}
```

### Step 7: Report Completion

Display:
```
✓ Track {track} completed successfully
✓ All {task_count} tasks completed
✓ Completion marker created
✓ Final commit: {commit_hash}

Next steps:
- If this was the last track, run: /merge-work-packets
- If more tracks remain, they will execute when dependencies are met
```

## Error Handling

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
- Skills invoked using the Skill tool (test-driven-development, requesting-code-review, factchecker)
- Worktree isolation ensures parallel tracks don't conflict
- Completion marker enables dependent tracks to proceed

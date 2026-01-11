---
description: Execute all work packets in dependency order, one at a time, with context compaction between tracks.
disable-model-invocation: true
---

# Execute Work Packets Sequentially

Execute all work packets from a manifest in dependency order, ensuring each track completes before starting dependent tracks.

## Parameters

- `packet_dir` (required): Directory containing manifest.json and packet files

## Execution Protocol

### Step 1: Load and Validate Manifest

```bash
packet_dir="<packet_dir>"
manifest_file="$packet_dir/manifest.json"

# Load manifest using read_json_safe
# Verify all required fields exist:
# - format_version
# - feature
# - tracks (array)
# - merge_strategy
# - post_merge_qa
```

**Manifest Structure:**
```json
{
  "format_version": "1.0.0",
  "feature": "feature-name",
  "tracks": [
    {
      "id": 1,
      "name": "Track name",
      "packet": "track-1.md",
      "worktree": "/path/to/wt",
      "branch": "feature/track-1",
      "depends_on": []
    }
  ],
  "merge_strategy": "worktree-merge",
  "post_merge_qa": ["pytest", "green-mirage-audit"]
}
```

### Step 2: Topological Sort by Dependencies

**Goal:** Execute tracks in an order that respects dependencies.

**Algorithm:**
1. Initialize: `completed = []`, `execution_order = []`
2. While tracks remain:
   - Find track where ALL `depends_on` IDs are in `completed`
   - Add that track to `execution_order`
   - Add track ID to `completed`
3. If no track found but tracks remain: circular dependency error

**Example:**
```
Track 1: depends_on []
Track 2: depends_on [1]
Track 3: depends_on [1, 2]

Execution order: [1, 2, 3]
```

**Validation:**
- Detect circular dependencies
- Ensure all dependency IDs reference valid tracks
- Verify topological sort produces valid ordering

### Step 3: Sequential Execution Loop

For each track in execution_order:

```
=== Executing Track {track.id}: {track.name} ===

Packet: {packet_dir}/{track.packet}
Worktree: {track.worktree}
Branch: {track.branch}
Dependencies: {track.depends_on}
```

**Execute using /execute-work-packet:**

```bash
Invoke /execute-work-packet command with:
- packet_path: "{packet_dir}/{track.packet}"
- No --resume flag (fresh execution)

Follow all steps from execute-work-packet:
1. Parse packet
2. Check dependencies (should pass since we're in order)
3. Setup worktree
4. Execute tasks with TDD
5. Create completion marker
```

**Wait for completion:**
- Execute-work-packet is blocking
- Only proceed to next track when current track completes
- If execution fails, STOP entire sequence

### Step 4: Context Compaction (Between Tracks)

After each track completes:

```
✓ Track {track.id} completed

Context size is growing. To preserve session capacity:

Invoke /handoff command to:
- Capture track completion state
- Preserve manifest location and progress
- Clear implementation details from context
- Prepare for next track execution

After compaction, the next track will execute in a fresh context.
```

**Why compact between tracks:**
- Prevents context overflow in long-running sequences
- Each track starts with clean context
- Manifest and completion markers preserve state
- Enables recovery if session drops

**User decision:**
- Suggest compaction after each track
- User can decline and continue
- Critical for sequences with 3+ tracks

### Step 5: Progress Tracking

**Track completion markers:**
```bash
# After each track, verify completion marker exists
completion_file="$packet_dir/track-{track.id}.completion.json"

if [ ! -f "$completion_file" ]; then
  echo "ERROR: Track {track.id} did not create completion marker"
  exit 1
fi
```

**Display progress:**
```
=== Execution Progress ===

✓ Track 1: Core API (complete)
✓ Track 2: Frontend (complete)
→ Track 3: Tests (next)
  Track 4: Documentation (blocked on 3)

Completed: 2/4
Remaining: 2
```

### Step 6: Completion Detection

All tracks complete when:
- Every track has a completion marker: `track-{id}.completion.json`
- All markers have `"status": "complete"`
- No errors reported

**Final status check:**
```bash
# Verify all tracks complete
for track in manifest.tracks:
  completion_file="$packet_dir/track-{track.id}.completion.json"
  if [ ! -f "$completion_file" ]; then
    echo "ERROR: Track {track.id} incomplete"
    exit 1
  fi
done
```

### Step 7: Suggest Next Step

When all tracks complete:

```
✓ All tracks completed successfully!

Tracks executed:
  ✓ Track 1: Core API
  ✓ Track 2: Frontend
  ✓ Track 3: Tests
  ✓ Track 4: Documentation

Next step: Merge all tracks

Run: /merge-work-packets {packet_dir}

This will:
1. Verify all completion markers
2. Invoke worktree-merge skill
3. Run QA gates: {manifest.post_merge_qa}
4. Report final integration status
```

## Error Handling

**Track execution failure:**
- If /execute-work-packet fails, STOP sequence
- Do not proceed to dependent tracks
- Report failure details:
  - Which track failed
  - Which task within track failed
  - Error message
- Suggest resumption with --resume flag

**Missing dependency:**
- Should not occur due to topological sort
- If detected, indicates manifest corruption
- Abort sequence, suggest manifest verification

**Circular dependency:**
- Detected during topological sort in Step 2
- Report cycle: "Track A depends on B, B depends on A"
- Abort sequence, suggest manifest fix

**Completion marker missing:**
- If track claims success but no marker exists
- Indicates execution protocol violation
- Re-run track or create marker manually

## Recovery

**Resume after failure:**

If sequence stops mid-execution:
1. Check which tracks have completion markers
2. Re-run /execute-work-packets-seq with same packet_dir
3. Topological sort will identify completed tracks
4. Skip tracks with completion markers
5. Resume from first incomplete track

**Implementation:**
```bash
# Before executing each track
completion_file="$packet_dir/track-{track.id}.completion.json"

if [ -f "$completion_file" ]; then
  echo "✓ Track {track.id} already complete, skipping"
  continue
fi

# Otherwise, execute track
```

## Performance Considerations

**Sequential vs Parallel:**
- This command executes serially
- For parallel execution, use individual /execute-work-packet commands
- Sequential execution ensures:
  - Clear dependency resolution
  - Easier debugging (one thing at a time)
  - Lower resource usage
  - Context compaction between tracks

**When to use sequential:**
- Dependencies exist between tracks
- Resource-constrained environment
- Debugging execution flow
- Learning/testing the workflow

**When to use parallel:**
- Tracks are independent
- Want maximum speed
- Have sufficient resources
- Comfortable with concurrent debugging

## Example Session

```
User: /execute-work-packets-seq /Users/me/.local/spellbook/docs/myproject/packets

=== Loading manifest ===
Feature: User Authentication
Tracks: 4
Dependencies detected: 2 → [1], 3 → [1,2], 4 → [3]

=== Topological sort ===
Execution order: [1, 2, 3, 4]

=== Executing Track 1: Core API ===
Packet: /Users/me/.local/spellbook/docs/myproject/packets/track-1.md
Dependencies: none
Status: Starting...

[TDD execution for all Track 1 tasks...]

✓ Track 1 completed
Completion marker: track-1.completion.json

Context compaction suggested. Run /handoff? [yes/no]

=== Executing Track 2: Frontend ===
Packet: /Users/me/.local/spellbook/docs/myproject/packets/track-2.md
Dependencies: [1] ✓ satisfied
Status: Starting...

[Continues for all tracks...]

=== All tracks complete ===
Next: /merge-work-packets /Users/me/.local/spellbook/docs/myproject/packets
```

## Notes

- Respects manifest.json as source of truth
- Completion markers enable idempotent execution
- Compaction prevents context overflow
- Topological sort handles complex dependency graphs
- Each track isolated in its own worktree
- Skills (TDD, code review, factcheck) invoked via Skill tool
- Integration testing deferred to merge phase

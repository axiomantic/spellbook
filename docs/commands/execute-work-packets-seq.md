# /execute-work-packets-seq

## Command Content

``````````markdown
# Execute Work Packets Sequentially

<ROLE>
Workflow Orchestrator. Stakes: wrong ordering corrupts builds, skipped dependencies cause silent failures.
</ROLE>

Execute all work packets from a manifest in dependency order, ensuring each track completes before starting dependent tracks.

## Invariant Principles

1. **Dependency ordering is inviolable.** Never execute track before dependencies complete.
2. **Completion markers are truth.** Track state exists only in `track-{id}.completion.json`.
3. **Failure halts sequence.** No partial execution; dependent tracks must not start.
4. **Execution is idempotent.** Skip tracks with existing completion markers on resume.
5. **Context compaction preserves capacity.** Suggest /handoff between tracks to prevent overflow.

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

<analysis>
Required fields: format_version, feature, tracks[], merge_strategy, post_merge_qa
Each track requires: id, name, packet, worktree, branch, depends_on[]
Abort if any required field missing.
</analysis>

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

<CRITICAL>
**Goal:** Execute tracks in an order that respects dependencies. NEVER execute a track before ALL its dependencies have completion markers. Dependency ordering is the foundation of correctness; violation corrupts the entire build.
</CRITICAL>

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

**Check for existing completion (idempotent):**
```bash
# Before executing each track
completion_file="$packet_dir/track-{track.id}.completion.json"

if [ -f "$completion_file" ]; then
  echo "✓ Track {track.id} already complete, skipping"
  continue
fi
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

<CRITICAL>
**Wait for completion:**
- Execute-work-packet is blocking
- Only proceed to next track when current track completes
- If execution fails, STOP entire sequence immediately
- Continuing after failure corrupts dependency assumptions and invalidates all downstream tracks
</CRITICAL>

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

| Error | Response |
|-------|----------|
| Track execution fails | STOP. Report track, task, message. Suggest --resume. |
| Circular dependency | ABORT at sort. Report cycle path. |
| Missing completion marker | Execution protocol violation. Re-run track. |
| Missing dependency ID | Manifest corruption. Abort, verify manifest. |

**Track execution failure details:**
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

<FORBIDDEN>
- Executing a track before ALL its dependencies have completion markers
- Continuing after a track failure (corrupts dependency assumptions)
- Skipping topological sort (manual ordering is error-prone)
- Modifying completion markers manually (source of truth corruption)
</FORBIDDEN>

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

<FINAL_EMPHASIS>
Dependency ordering is inviolable. Failure halts the sequence. These are not guidelines; they are correctness invariants. Violating them corrupts the entire feature build.
</FINAL_EMPHASIS>
``````````

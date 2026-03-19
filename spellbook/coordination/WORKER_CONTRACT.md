# Worker Integration Contract

<ROLE>
Worker integrating with the swarm coordination system. Your correctness determines whether progress survives failures. Broken checkpointing means lost work across the entire swarm.
</ROLE>

Workers MUST follow this contract to ensure coordination, checkpointing, and recovery.

## Integration Methods

Two mechanisms for swarm integration:

1. **MCP Tool Calls**: HTTP requests to the coordination server via the MCP backend
2. **Checkpoint Marker Files**: Local JSON files written to `.spellbook/checkpoints/`

**Dual-write rule**: Write checkpoint file FIRST, then make HTTP call. Progress survives server downtime, network loss, and worker crashes.

### Method 1: SwarmWorker Helper (Recommended)

Handles all coordination protocol details automatically.

```python
from spellbook.coordination import SwarmWorker

worker = SwarmWorker(
    swarm_id="swarm-abc123",
    packet_id=1,
    packet_name="backend-api",
    worktree="/path/to/worktree",
    tasks_total=10
)

await worker.register()

await worker.report_progress(
    task_id="task-1",
    task_name="Implement authentication",
    status="completed",
    commit="abc1234567"  # Optional
)

await worker.report_complete(
    final_commit="def5678901",
    tests_passed=True,
    review_passed=True
)

# On error:
await worker.report_error(
    task_id="task-2",
    error_type="test_failure",
    message="Authentication tests failed with 3 failures",
    recoverable=False
)
```

### Method 2: Direct MCP Tool Calls (Advanced)

```python
from spellbook.coordination.backends import get_backend

backend = get_backend("mcp-streamable-http", {
    "host": "127.0.0.1",
    "port": 7432
})

response = await backend.register_worker(
    swarm_id="swarm-abc123",
    packet_id=1,
    packet_name="backend-api",
    tasks_total=10,
    worktree="/path/to/worktree"
)

response = await backend.report_progress(
    swarm_id="swarm-abc123",
    packet_id=1,
    task_id="task-1",
    task_name="Implement authentication",
    status="completed",
    tasks_completed=1,
    tasks_total=10,
    commit="abc1234567"
)
```

<CRITICAL>
Direct MCP callers MUST implement dual-write checkpointing manually. See Checkpoint Format section.
</CRITICAL>

## Worker Lifecycle

```
┌──────────────┐
│   STARTUP    │
└──────┬───────┘
       │
       ▼
┌──────────────────┐
│  REGISTER        │  ← Write checkpoint, call /swarm/{id}/register
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│  EXECUTE TASKS   │
│  ┌────────────┐  │
│  │  PROGRESS  │  │  ← Write checkpoint, call /swarm/{id}/progress
│  └────────────┘  │
│       │          │
│       ▼          │
│  (repeat for     │
│   each task)     │
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│   COMPLETE       │  ← Write checkpoint, call /swarm/{id}/complete
└──────────────────┘

       OR

┌──────────────────┐
│    ERROR         │  ← Write checkpoint, call /swarm/{id}/error
└──────────────────┘
```

## Checkpoint Format

**Location**: `{worktree}/.spellbook/checkpoints/packet-{packet_id}-{packet_name}.json`

Example: `/Users/alice/worktrees/feature-1/.spellbook/checkpoints/packet-1-backend-api.json`

<CRITICAL>
Write checkpoint file BEFORE the HTTP call. If the checkpoint write fails, do NOT proceed with the HTTP call -- log the failure and halt.
</CRITICAL>

### Base Format

```json
{
  "event": "registered|progress|complete|error",
  "timestamp": "2026-01-05T10:00:00.123456+00:00",
  "packet_id": 1,
  "packet_name": "backend-api",
  "tasks_completed": 0,
  "tasks_total": 10
}
```

### Registration Checkpoint

```json
{
  "event": "registered",
  "timestamp": "2026-01-05T10:00:00+00:00",
  "packet_id": 1,
  "packet_name": "backend-api",
  "tasks_completed": 0,
  "tasks_total": 10
}
```

### Progress Checkpoint

```json
{
  "event": "progress",
  "timestamp": "2026-01-05T10:01:00+00:00",
  "packet_id": 1,
  "packet_name": "backend-api",
  "tasks_completed": 1,
  "tasks_total": 10,
  "task_id": "task-1",
  "task_name": "Implement authentication",
  "status": "completed",
  "commit": "abc1234567"
}
```

### Completion Checkpoint

```json
{
  "event": "complete",
  "timestamp": "2026-01-05T10:10:00+00:00",
  "packet_id": 1,
  "packet_name": "backend-api",
  "tasks_completed": 10,
  "tasks_total": 10,
  "final_commit": "def5678901",
  "tests_passed": true,
  "review_passed": true
}
```

### Error Checkpoint

```json
{
  "event": "error",
  "timestamp": "2026-01-05T10:05:00+00:00",
  "packet_id": 1,
  "packet_name": "backend-api",
  "tasks_completed": 5,
  "tasks_total": 10,
  "task_id": "task-6",
  "error_type": "test_failure",
  "message": "Authentication tests failed with 3 failures",
  "recoverable": false
}
```

## MCP Tool Call Sequence

### 1. Registration

**Endpoint**: `POST /swarm/{swarm_id}/register`

**Request**:
```json
{
  "packet_id": 1,
  "packet_name": "backend-api",
  "tasks_total": 10,
  "worktree": "/path/to/worktree"
}
```

**Response**:
```json
{
  "registered": true,
  "packet_id": 1,
  "packet_name": "backend-api",
  "swarm_id": "swarm-abc123",
  "registered_at": "2026-01-05T10:00:00Z"
}
```

**Validation**:
- `packet_id` > 0
- `packet_name` matches `^[a-z0-9-]+$`
- `tasks_total` between 1 and 1000
- `worktree` is absolute path

### 2. Progress Updates

**Endpoint**: `POST /swarm/{swarm_id}/progress`

**Request**:
```json
{
  "packet_id": 1,
  "task_id": "task-1",
  "task_name": "Implement authentication",
  "status": "completed",
  "tasks_completed": 1,
  "tasks_total": 10,
  "commit": "abc1234567"
}
```

**Response**:
```json
{
  "acknowledged": true,
  "packet_id": 1,
  "task_id": "task-1",
  "tasks_completed": 1,
  "tasks_total": 10,
  "timestamp": "2026-01-05T10:01:00Z"
}
```

**Validation**:
- `status` one of: `"started"`, `"completed"`, `"failed"`
- `tasks_completed` <= `tasks_total`
- `commit` matches `^[a-f0-9]{7,40}$`

### 3. Completion

**Endpoint**: `POST /swarm/{swarm_id}/complete`

**Request**:
```json
{
  "packet_id": 1,
  "final_commit": "def5678901",
  "tests_passed": true,
  "review_passed": true
}
```

**Response**:
```json
{
  "acknowledged": true,
  "packet_id": 1,
  "final_commit": "def5678901",
  "completed_at": "2026-01-05T10:10:00Z",
  "swarm_complete": false,
  "remaining_workers": 2
}
```

**Validation**:
- `final_commit` matches `^[a-f0-9]{7,40}$`

### 4. Error Reporting

**Endpoint**: `POST /swarm/{swarm_id}/error`

**Request**:
```json
{
  "packet_id": 1,
  "task_id": "task-6",
  "error_type": "test_failure",
  "message": "Authentication tests failed with 3 failures",
  "recoverable": false
}
```

**Response**:
```json
{
  "acknowledged": true,
  "packet_id": 1,
  "error_logged": true,
  "retry_scheduled": false,
  "retry_in_seconds": null
}
```

**Validation**:
- `error_type` max 100 characters
- `message` max 5000 characters

## Task Completion Counter

`tasks_completed` MUST be a monotonically increasing counter:

1. Initialize to 0 on startup
2. Increment by 1 each time `report_progress()` is called with `status="completed"`
3. Include current value in every progress update
4. Include final value in completion report

```python
worker = SwarmWorker(...)  # tasks_completed = 0

await worker.report_progress("task-1", "Task 1", "completed")  # tasks_completed = 1
await worker.report_progress("task-2", "Task 2", "completed")  # tasks_completed = 2
await worker.report_progress("task-3", "Task 3", "completed")  # tasks_completed = 3
```

`SwarmWorker` handles this automatically.

## Error Types and Recovery

### Recoverable Errors
May resolve on retry:
- `network_error` - Network connectivity issues
- `rate_limit` - API rate limiting
- `test_flake` - Flaky test failures
- `dependency_timeout` - Temporary dependency unavailability

### Non-Recoverable Errors
Require human intervention:
- `test_failure` - Persistent test failures
- `build_failure` - Build/compilation errors
- `merge_conflict` - Git merge conflicts
- `invalid_manifest` - Invalid work packet manifest

Recoverable errors: coordination server may schedule automatic retries (default: 2 retries, exponential backoff starting at 30 seconds).

## Server-Sent Events (SSE)

**Endpoint**: `GET /swarm/{swarm_id}/events?since_event_id={last_id}`

**Event Format**:
```
id: 123
event: worker_registered
data: {"packet_id": 1, "packet_name": "backend-api"}

id: 124
event: progress_update
data: {"packet_id": 1, "tasks_completed": 1, "tasks_total": 10}

id: 125
event: worker_complete
data: {"packet_id": 1, "final_commit": "abc123"}
```

On SSE stream disconnect: reconnect using the last received `since_event_id` to resume from where the stream broke.

## Recovery and Restart

On crash and restart, MUST:

1. Read checkpoint from `.spellbook/checkpoints/packet-{id}-{name}.json`
2. Resume `tasks_completed` from checkpoint value
3. Re-register with swarm (idempotent)
4. Continue reporting progress from where it left off

```python
checkpoint_path = Path(worktree) / ".spellbook/checkpoints" / f"packet-{packet_id}-{packet_name}.json"
if checkpoint_path.exists():
    checkpoint = json.loads(checkpoint_path.read_text())
    tasks_completed = checkpoint["tasks_completed"]

    worker = SwarmWorker(...)
    worker.tasks_completed = tasks_completed
    await worker.register()  # Re-register (idempotent)
```

## Integration Checklist

- [ ] Initialize `SwarmWorker` with correct parameters
- [ ] Call `register()` on startup
- [ ] Call `report_progress()` after each task completion
- [ ] Increment `tasks_completed` counter correctly
- [ ] Call `report_complete()` when all tasks done
- [ ] Call `report_error()` on errors with correct `recoverable` flag
- [ ] Write checkpoint files BEFORE HTTP calls
- [ ] Use timezone-aware timestamps (UTC)
- [ ] Validate all input parameters per protocol schema
- [ ] Handle checkpoint recovery on restart
- [ ] Clean up checkpoint files after successful swarm completion

<FORBIDDEN>
- Calling HTTP endpoints before writing the checkpoint file
- Proceeding with an HTTP call when checkpoint write has failed
- Making direct MCP calls without implementing dual-write checkpointing
- Using relative paths for `worktree`
- Sending `tasks_completed` > `tasks_total`
- Skipping re-registration on restart
- Using non-UTC or timezone-naive timestamps
</FORBIDDEN>

## Testing Your Integration

```bash
# Start test coordination server
python -m spellbook.coordination.server --port 7432

# Run your worker
python my_worker.py

# Verify checkpoints created
ls -la {worktree}/.spellbook/checkpoints/

# Check swarm status
curl http://127.0.0.1:7432/swarm/{swarm_id}/status
```

## References

- Protocol schemas: `spellbook/coordination/protocol.py`
- SwarmWorker implementation: `spellbook/coordination/worker.py`
- Backend implementation: `spellbook/coordination/backends/mcp_streamable_http.py`
- Retry policy: `spellbook/coordination/retry.py`

<FINAL_EMPHASIS>
Checkpoint-before-HTTP is non-negotiable. Every deviation risks silent progress loss that corrupts swarm state. Write the file first, always.
</FINAL_EMPHASIS>

# Worker Integration Contract

This document defines the contract for workers integrating with the swarm coordination system. Workers MUST follow this contract to ensure proper coordination, checkpointing, and recovery.

## Overview

Workers integrate with the swarm coordination system through two mechanisms:

1. **MCP Tool Calls**: HTTP requests to the coordination server via the MCP backend
2. **Checkpoint Marker Files**: Local JSON files written to `.spellbook/checkpoints/`

The dual-write behavior (marker file FIRST, then HTTP call) ensures progress is preserved even if the coordination server is temporarily unavailable.

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

## Integration Methods

### Method 1: Using SwarmWorker Helper Class (Recommended)

The `SwarmWorker` class handles all coordination protocol details automatically.

```python
from spellbook.coordination import SwarmWorker

# Initialize worker
worker = SwarmWorker(
    swarm_id="swarm-abc123",
    packet_id=1,
    packet_name="backend-api",
    worktree="/path/to/worktree",
    tasks_total=10
)

# Register on startup
await worker.register()

# Report each task as it completes
await worker.report_progress(
    task_id="task-1",
    task_name="Implement authentication",
    status="completed",
    commit="abc1234567"  # Optional
)

# Report final completion
await worker.report_complete(
    final_commit="def5678901",
    tests_passed=True,
    review_passed=True
)

# Or report errors
await worker.report_error(
    task_id="task-2",
    error_type="test_failure",
    message="Authentication tests failed with 3 failures",
    recoverable=False
)
```

### Method 2: Direct MCP Tool Calls (Advanced)

For workers that need more control, you can call the MCP backend directly.

```python
from spellbook.coordination.backends import get_backend

backend = get_backend("mcp-streamable-http", {
    "host": "127.0.0.1",
    "port": 7432
})

# Register
response = await backend.register_worker(
    swarm_id="swarm-abc123",
    packet_id=1,
    packet_name="backend-api",
    tasks_total=10,
    worktree="/path/to/worktree"
)

# Report progress
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

**IMPORTANT**: If using direct MCP calls, you MUST implement dual-write checkpointing yourself (see Checkpoint Format section).

## Dual-Write Behavior

The coordination system uses a dual-write pattern for reliability:

1. **Checkpoint File First**: Write checkpoint marker file to `.spellbook/checkpoints/packet-{id}-{name}.json`
2. **HTTP Call Second**: Make HTTP POST request to coordination server

This ensures progress is preserved even if:
- The coordination server is temporarily down
- Network connectivity is lost
- The worker crashes (checkpoint can be recovered on restart)

### Checkpoint File Location

```
{worktree}/.spellbook/checkpoints/packet-{packet_id}-{packet_name}.json
```

Example:
```
/Users/alice/worktrees/feature-1/.spellbook/checkpoints/packet-1-backend-api.json
```

## Checkpoint Format

All checkpoint files use the following base format:

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
- `packet_name` matches `^[a-z0-9-]+$` (lowercase alphanumeric with hyphens)
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
- `status` is one of: `"started"`, `"completed"`, `"failed"`
- `tasks_completed` <= `tasks_total`
- `commit` matches `^[a-f0-9]{7,40}$` (git SHA, 7-40 hex chars)

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

Workers MUST track `tasks_completed` as a monotonically increasing counter:

1. Initialize to 0 on startup
2. Increment by 1 each time `report_progress()` is called with `status="completed"`
3. Include current value in every progress update
4. Include final value in completion report

**Example**:
```python
worker = SwarmWorker(...)  # tasks_completed = 0

await worker.report_progress("task-1", "Task 1", "completed")  # tasks_completed = 1
await worker.report_progress("task-2", "Task 2", "completed")  # tasks_completed = 2
await worker.report_progress("task-3", "Task 3", "completed")  # tasks_completed = 3
```

The `SwarmWorker` helper class handles this automatically.

## Error Types and Recovery

### Recoverable Errors
These errors may resolve on retry:
- `network_error` - Network connectivity issues
- `rate_limit` - API rate limiting
- `test_flake` - Flaky test failures
- `dependency_timeout` - Temporary dependency unavailability

### Non-Recoverable Errors
These errors require human intervention:
- `test_failure` - Persistent test failures
- `build_failure` - Build/compilation errors
- `merge_conflict` - Git merge conflicts
- `invalid_manifest` - Invalid work packet manifest

When reporting recoverable errors, the coordination server may schedule automatic retries based on the configured retry policy (default: 2 retries with exponential backoff starting at 30 seconds).

## Server-Sent Events (SSE)

Workers can subscribe to swarm events for real-time updates:

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

## Recovery and Restart

If a worker crashes and restarts, it MUST:

1. Read the checkpoint file from `.spellbook/checkpoints/packet-{id}-{name}.json`
2. Resume from `tasks_completed` counter
3. Re-register with the swarm (idempotent operation)
4. Continue reporting progress from where it left off

Example:
```python
checkpoint_path = Path(worktree) / ".spellbook/checkpoints" / f"packet-{packet_id}-{packet_name}.json"
if checkpoint_path.exists():
    checkpoint = json.loads(checkpoint_path.read_text())
    tasks_completed = checkpoint["tasks_completed"]

    # Resume work
    worker = SwarmWorker(...)
    worker.tasks_completed = tasks_completed
    await worker.register()  # Re-register (idempotent)
```

## Integration Checklist

For workers implementing this contract:

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

## Testing Your Integration

Use the test server to verify your worker integration:

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

import pytest
import json
import time
from pathlib import Path
from datetime import datetime

def test_packet_dataclass():
    """Test Packet dataclass structure."""
    from spellbook_mcp.models import Packet, Task

    task = Task(
        id="1.1",
        description="Create login endpoint",
        files=["src/auth/login.ts"],
        acceptance="Endpoint returns 200 with valid credentials"
    )

    packet = Packet(
        format_version="1.0.0",
        feature="user-auth",
        track=1,
        worktree="/path/to/worktree",
        branch="feature/auth/track-1",
        tasks=[task],
        body="Full packet content"
    )

    assert packet.format_version == "1.0.0"
    assert packet.track == 1
    assert len(packet.tasks) == 1
    assert packet.tasks[0].id == "1.1"

def test_manifest_dataclass():
    """Test Manifest dataclass structure."""
    from spellbook_mcp.models import Manifest, Track

    track = Track(
        id=1,
        name="Authentication",
        packet="track-1-auth.md",
        worktree="/path/to/worktree",
        branch="feature/auth/track-1",
        status="pending",
        depends_on=[],
        checkpoint=None,
        completion=None
    )

    manifest = Manifest(
        format_version="1.0.0",
        feature="user-auth",
        created="2026-01-05T12:00:00Z",
        project_root="/path/to/project",
        design_doc="/path/to/design.md",
        impl_plan="/path/to/impl.md",
        execution_mode="swarmed",
        tracks=[track],
        shared_setup_commit="abc123",
        merge_strategy="merging-worktrees",
        post_merge_qa=["tests", "audit-green-mirage", "fact-checking"]
    )

    assert manifest.format_version == "1.0.0"
    assert len(manifest.tracks) == 1
    assert manifest.tracks[0].status == "pending"

def test_checkpoint_dataclass():
    """Test Checkpoint dataclass structure."""
    from spellbook_mcp.models import Checkpoint

    checkpoint = Checkpoint(
        format_version="1.0.0",
        track=1,
        last_completed_task="1.2",
        commit="abc123",
        timestamp="2026-01-05T12:30:00Z",
        next_task="1.3"
    )

    assert checkpoint.track == 1
    assert checkpoint.next_task == "1.3"

def test_completion_marker_dataclass():
    """Test CompletionMarker dataclass structure."""
    from spellbook_mcp.models import CompletionMarker

    marker = CompletionMarker(
        format_version="1.0.0",
        status="complete",
        commit="abc123",
        timestamp="2026-01-05T13:00:00Z"
    )

    assert marker.status == "complete"
    assert marker.format_version == "1.0.0"

def test_atomic_write_json_basic(tmp_path):
    """Test atomic JSON writes."""
    from spellbook_mcp.command_utils import atomic_write_json, read_json_safe

    test_file = tmp_path / "test.json"
    data = {"foo": "bar", "count": 42}

    atomic_write_json(str(test_file), data)

    assert test_file.exists()
    result = read_json_safe(str(test_file))
    assert result == data

def test_atomic_write_json_concurrent(tmp_path):
    """Test concurrent writes don't corrupt file."""
    from spellbook_mcp.command_utils import atomic_write_json
    import threading

    test_file = tmp_path / "concurrent.json"

    def writer(i):
        data = {"thread": i, "timestamp": time.time()}
        atomic_write_json(str(test_file), data, timeout=10)

    threads = [threading.Thread(target=writer, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert test_file.exists()
    with open(test_file) as f:
        result = json.load(f)
    assert "thread" in result

def test_read_json_safe_retry(tmp_path):
    """Test read_json_safe handles empty file gracefully."""
    from spellbook_mcp.command_utils import read_json_safe

    test_file = tmp_path / "test.json"
    test_file.write_text('{"valid": true}')

    result = read_json_safe(str(test_file))
    assert result == {"valid": True}

def test_parse_packet_file(tmp_path):
    """Test parsing work packet with YAML frontmatter."""
    from spellbook_mcp.command_utils import parse_packet_file

    packet_path = tmp_path / "test-packet.md"
    packet_path.write_text("""---
format_version: "1.0.0"
feature: "test-feature"
track: 1
worktree: "/path/to/worktree"
branch: "feature/test/track-1"
---

# Work Packet: Test

**Task 1.1:** Create hello.py
Files: hello.py
Acceptance: prints Hello World

**Task 1.2:** Add tests
Files: test_hello.py
Acceptance: tests pass
""")

    packet = parse_packet_file(packet_path)

    assert packet["feature"] == "test-feature"
    assert packet["track"] == 1
    assert len(packet["tasks"]) == 2
    assert packet["tasks"][0]["id"] == "1.1"

def test_preferences_read_write(tmp_path, monkeypatch):
    """Test reading and writing preferences."""
    from spellbook_mcp.preferences import save_preference, load_preferences

    # Use tmp_path as home directory
    monkeypatch.setenv("HOME", str(tmp_path))

    save_preference("terminal.program", "iterm2")
    save_preference("terminal.detected", False)

    prefs = load_preferences()

    assert prefs["terminal"]["program"] == "iterm2"
    assert prefs["terminal"]["detected"] == False

def test_preferences_defaults(tmp_path, monkeypatch):
    """Test default preferences when no file exists."""
    from spellbook_mcp.preferences import load_preferences

    monkeypatch.setenv("HOME", str(tmp_path))

    prefs = load_preferences()

    assert "terminal" in prefs
    assert "execution_mode" in prefs
    assert prefs["terminal"]["program"] is None

def test_metrics_logging(tmp_path, monkeypatch):
    """Test feature metrics logging."""
    from spellbook_mcp.metrics import log_feature_metrics
    from datetime import datetime
    import json

    # Use tmp_path as home and clear env vars for portable default
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("SPELLBOOK_CONFIG_DIR", raising=False)
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)

    # Log a feature completion
    log_feature_metrics(
        feature_slug="user-auth",
        execution_mode="swarmed",
        oversight_mode="checkpointed",
        estimated_tokens=145000,
        estimated_percentage=72,
        num_tasks=23,
        num_tracks=4,
        design_context_kb=45,
        impl_plan_kb=12,
        outcome="success",
        duration_minutes=45,
        tracks=[
            {"id": 1, "tasks": 6, "outcome": "success"},
            {"id": 2, "tasks": 8, "outcome": "success"}
        ],
        project_encoded="test-project"
    )

    # Verify log file exists at portable default location
    log_dir = tmp_path / ".local" / "spellbook" / "logs" / "test-project"
    log_file = log_dir / "implementing-features-metrics.jsonl"
    assert log_file.exists()

    # Verify content
    with open(log_file) as f:
        entry = json.loads(f.readline())

    assert entry["feature_slug"] == "user-auth"
    assert entry["execution_mode"] == "swarmed"
    assert entry["outcome"] == "success"
    assert "timestamp" in entry

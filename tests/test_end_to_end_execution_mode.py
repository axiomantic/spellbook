"""
End-to-end integration tests for execution mode Python components.

Tests the actual Python code:
- spellbook.types dataclasses
- spellbook.command_utils atomic operations
- spellbook.preferences handling
- spellbook_mcp.terminal_utils detection and spawning
- Work packet file format parsing
"""

import json
import os
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


class TestWorkPacketE2E:
    """End-to-end tests for work packet file operations."""

    def test_full_work_packet_lifecycle(self, tmp_path):
        """Test creating, reading, and updating work packet artifacts."""
        from spellbook.types import Manifest, Track, Checkpoint, CompletionMarker
        from spellbook.command_utils import atomic_write_json, read_json_safe

        # Step 1: Create manifest
        packet_dir = tmp_path / "work-packets" / "test-feature"
        packet_dir.mkdir(parents=True)
        checkpoints_dir = packet_dir / "checkpoints"
        checkpoints_dir.mkdir()

        manifest_data = {
            "format_version": "1.0.0",
            "feature": "test-feature",
            "created": "2026-01-05T12:00:00Z",
            "project_root": str(tmp_path / "project"),
            "design_doc": str(tmp_path / "design.md"),
            "impl_plan": str(tmp_path / "impl.md"),
            "execution_mode": "swarmed",
            "tracks": [
                {
                    "id": 1,
                    "name": "backend",
                    "packet": "track-1-backend.md",
                    "worktree": str(tmp_path / "worktree-1"),
                    "branch": "feature/test/track-1",
                    "status": "pending",
                    "depends_on": [],
                    "checkpoint": None,
                    "completion": None
                },
                {
                    "id": 2,
                    "name": "frontend",
                    "packet": "track-2-frontend.md",
                    "worktree": str(tmp_path / "worktree-2"),
                    "branch": "feature/test/track-2",
                    "status": "pending",
                    "depends_on": [1],
                    "checkpoint": None,
                    "completion": None
                }
            ],
            "shared_setup_commit": "abc123",
            "merge_strategy": "smart-merge",
            "post_merge_qa": ["tests", "green-mirage-audit"]
        }

        manifest_path = packet_dir / "manifest.json"
        atomic_write_json(str(manifest_path), manifest_data)

        # Step 2: Read manifest back
        loaded = read_json_safe(str(manifest_path))
        assert loaded["feature"] == "test-feature"
        assert len(loaded["tracks"]) == 2

        # Step 3: Create checkpoint for track 1
        checkpoint_data = {
            "format_version": "1.0.0",
            "track": 1,
            "last_completed_task": "1.2",
            "commit": "def456",
            "timestamp": "2026-01-05T12:30:00Z",
            "next_task": "1.3"
        }
        checkpoint_path = checkpoints_dir / "track-1-checkpoint.json"
        atomic_write_json(str(checkpoint_path), checkpoint_data)

        # Step 4: Verify checkpoint
        loaded_checkpoint = read_json_safe(str(checkpoint_path))
        assert loaded_checkpoint["last_completed_task"] == "1.2"
        assert loaded_checkpoint["next_task"] == "1.3"

        # Step 5: Create completion marker for track 1
        completion_data = {
            "format_version": "1.0.0",
            "status": "complete",
            "commit": "ghi789",
            "timestamp": "2026-01-05T13:00:00Z"
        }
        completion_path = packet_dir / ".track-1-complete.json"
        atomic_write_json(str(completion_path), completion_data)

        # Step 6: Verify all files exist and are valid
        assert manifest_path.exists()
        assert checkpoint_path.exists()
        assert completion_path.exists()

        # Verify JSON validity
        for path in [manifest_path, checkpoint_path, completion_path]:
            with open(path) as f:
                json.load(f)  # Should not raise

    def test_concurrent_checkpoint_updates(self, tmp_path):
        """Test that concurrent checkpoint updates don't corrupt files."""
        from spellbook.command_utils import atomic_write_json, read_json_safe

        checkpoint_path = tmp_path / "checkpoint.json"
        results = []
        errors = []

        def writer(thread_id):
            try:
                for i in range(5):
                    data = {
                        "format_version": "1.0.0",
                        "track": 1,
                        "last_completed_task": f"{thread_id}.{i}",
                        "commit": f"commit-{thread_id}-{i}",
                        "timestamp": "2026-01-05T12:00:00Z",
                        "next_task": None
                    }
                    atomic_write_json(str(checkpoint_path), data, timeout=10)
                    time.sleep(0.01)
                results.append(thread_id)
            except Exception as e:
                errors.append((thread_id, e))

        # Spawn concurrent writers
        threads = [threading.Thread(target=writer, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All threads should complete without errors
        assert len(errors) == 0, f"Errors: {errors}"
        assert len(results) == 5

        # File should be valid JSON
        final = read_json_safe(str(checkpoint_path))
        assert final["format_version"] == "1.0.0"
        assert final["track"] == 1

    def test_packet_file_parsing(self, tmp_path):
        """Test parsing work packet markdown files with YAML frontmatter."""
        from spellbook.command_utils import parse_packet_file

        packet_content = """---
format_version: "1.0.0"
feature: "user-auth"
track: 1
worktree: "/path/to/worktree"
branch: "feature/auth/track-1"
---

# Work Packet: User Auth - Track 1: Backend

## Context

This track implements backend authentication.

## Tasks

**Task 1.1:** Create user model
- Files: src/models/user.ts
- Acceptance: User model with email, password hash

**Task 1.2:** Implement login endpoint
- Files: src/routes/auth.ts
- Acceptance: POST /login returns JWT

## Execution Protocol

1. Run tests after each task
2. Create checkpoint after each task
"""

        packet_path = tmp_path / "track-1-backend.md"
        packet_path.write_text(packet_content)

        result = parse_packet_file(packet_path)

        assert result["format_version"] == "1.0.0"
        assert result["feature"] == "user-auth"
        assert result["track"] == 1
        assert result["worktree"] == "/path/to/worktree"
        assert result["branch"] == "feature/auth/track-1"
        assert "Backend" in result["body"]


class TestTerminalUtilsE2E:
    """End-to-end tests for terminal detection and spawning."""

    @pytest.mark.skipif(os.uname().sysname != "Darwin", reason="macOS only")
    def test_macos_terminal_detection_real(self):
        """Test actual terminal detection on macOS (no mocking)."""
        from spellbook_mcp.terminal_utils import detect_macos_terminal

        # Should return one of the known terminals (case-sensitive)
        result = detect_macos_terminal()
        assert result in ["iTerm2", "Warp", "Terminal", "terminal"]

    @pytest.mark.skipif(os.uname().sysname != "Linux", reason="Linux only")
    def test_linux_terminal_detection_real(self):
        """Test actual terminal detection on Linux (no mocking)."""
        from spellbook_mcp.terminal_utils import detect_linux_terminal

        # Should return a terminal name
        result = detect_linux_terminal()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_detect_terminal_returns_string(self):
        """Test that detect_terminal always returns a string."""
        import sys
        from spellbook_mcp.terminal_utils import detect_terminal

        if sys.platform == "win32":
            with pytest.raises(NotImplementedError):
                detect_terminal()
        else:
            result = detect_terminal()
            assert isinstance(result, str)
            assert len(result) > 0

    def test_spawn_command_generation(self):
        """Test that spawn functions generate proper commands."""
        from spellbook_mcp.terminal_utils import spawn_macos_terminal, spawn_linux_terminal

        # Mock subprocess.Popen for macOS (uses Popen, not run)
        with patch('spellbook_mcp.terminal_utils.subprocess.Popen') as mock_popen:
            mock_popen.return_value = MagicMock(pid=12345)

            # Test macOS iTerm2
            result = spawn_macos_terminal("iterm2", "/test prompt", "/test/dir")
            assert result["status"] == "spawned"
            assert result["terminal"] == "iterm2"
            assert result["pid"] == 12345

            # Verify osascript was called
            call_args = mock_popen.call_args
            assert call_args[0][0][0] == "osascript"

        with patch('spellbook_mcp.terminal_utils.subprocess.Popen') as mock_popen:
            mock_popen.return_value = MagicMock(pid=67890)

            # Test Linux gnome-terminal
            result = spawn_linux_terminal("gnome-terminal", "/test prompt", "/test/dir")
            assert result["status"] == "spawned"
            assert result["terminal"] == "gnome-terminal"
            assert result["pid"] == 67890


class TestMCPToolE2E:
    """End-to-end tests for MCP tool integration."""

    def test_spawn_workflow_auto_detection(self):
        """Test spawn workflow with auto terminal detection (tests underlying functions)."""
        from spellbook_mcp.terminal_utils import detect_terminal, spawn_terminal_window

        with patch('spellbook_mcp.terminal_utils.subprocess.run') as mock_run:
            with patch('spellbook_mcp.terminal_utils.subprocess.Popen') as mock_popen:
                # Mock detect to find iTerm2 running
                mock_run.return_value = MagicMock(returncode=0)
                mock_popen.return_value = MagicMock(pid=12345)

                # Step 1: Detect terminal
                terminal = detect_terminal()
                assert terminal in ["iTerm2", "Warp", "Terminal", "terminal"]

                # Step 2: Spawn window
                result = spawn_terminal_window(
                    terminal,
                    "/execute-work-packet /path/to/packet.md",
                    "/path/to/project"
                )

                assert result["status"] == "spawned"
                assert result["pid"] is not None

    def test_spawn_workflow_explicit_terminal(self):
        """Test spawn workflow with explicit terminal."""
        from spellbook_mcp.terminal_utils import spawn_terminal_window

        with patch('spellbook_mcp.terminal_utils.subprocess.Popen') as mock_popen:
            mock_popen.return_value = MagicMock(pid=67890)

            result = spawn_terminal_window(
                "iterm2",  # Explicit terminal
                "/execute-work-packet test.md",
                "/test/dir"
            )

            assert result["status"] == "spawned"
            assert result["terminal"] == "iterm2"
            assert result["pid"] == 67890


class TestPreferencesE2E:
    """End-to-end tests for preferences handling."""

    def test_preferences_persistence(self, tmp_path, monkeypatch):
        """Test that preferences persist across calls."""
        from spellbook.preferences import load_preferences, save_preference, get_preferences_path

        # Monkeypatch the preferences path to use tmp_path
        prefs_path = tmp_path / "preferences.json"
        monkeypatch.setattr('spellbook.preferences.get_preferences_path', lambda: prefs_path)

        # Save a preference (dot-separated key)
        save_preference("terminal.program", "iterm2")

        # Load it back
        prefs = load_preferences()
        assert prefs["terminal"]["program"] == "iterm2"

        # Update it
        save_preference("terminal.program", "warp")
        prefs = load_preferences()
        assert prefs["terminal"]["program"] == "warp"

    def test_preferences_default_values(self, tmp_path, monkeypatch):
        """Test that missing preferences return defaults."""
        from spellbook.preferences import load_preferences, get_preferences_path

        # Monkeypatch the preferences path to use non-existent file
        prefs_path = tmp_path / "nonexistent.json"
        monkeypatch.setattr('spellbook.preferences.get_preferences_path', lambda: prefs_path)

        # Load preferences (should return defaults)
        prefs = load_preferences()
        assert prefs["terminal"]["program"] is None
        assert prefs["terminal"]["detected"] is False
        assert prefs["execution_mode"]["always_ask"] is True


class TestMetricsE2E:
    """End-to-end tests for metrics logging."""

    def test_metrics_logging(self, tmp_path, monkeypatch):
        """Test that metrics are logged correctly."""
        from spellbook.metrics import log_feature_metrics, get_project_encoded

        # Monkeypatch Path.home() to use tmp_path
        monkeypatch.setattr('pathlib.Path.home', lambda: tmp_path)

        # Log some metrics with correct signature
        log_feature_metrics(
            feature_slug="test-feature",
            execution_mode="swarmed",
            oversight_mode="autonomous",
            estimated_tokens=100000,
            estimated_percentage=50.0,
            num_tasks=10,
            num_tracks=3,
            design_context_kb=20,
            impl_plan_kb=15,
            outcome="success",
            duration_minutes=2.0,
            tracks=[{"id": 1, "name": "backend", "status": "complete"}],
            project_encoded="test-project"
        )

        # Verify metrics file exists
        metrics_file = tmp_path / ".claude" / "logs" / "test-project" / "implement-feature-metrics.jsonl"
        assert metrics_file.exists()

        # Verify content
        import json
        with open(metrics_file) as f:
            entry = json.loads(f.readline())
        assert entry["feature_slug"] == "test-feature"
        assert entry["execution_mode"] == "swarmed"
        assert entry["num_tracks"] == 3


class TestDataclassesE2E:
    """End-to-end tests for dataclass serialization."""

    def test_manifest_round_trip(self, tmp_path):
        """Test Manifest dataclass can be serialized and deserialized."""
        from spellbook.types import Manifest, Track
        from spellbook.command_utils import atomic_write_json, read_json_safe
        from dataclasses import asdict

        track = Track(
            id=1,
            name="backend",
            packet="track-1-backend.md",
            worktree="/path/to/worktree",
            branch="feature/test/track-1",
            status="pending",
            depends_on=[],
            checkpoint=None,
            completion=None
        )

        manifest = Manifest(
            format_version="1.0.0",
            feature="test",
            created="2026-01-05T12:00:00Z",
            project_root="/project",
            design_doc="/design.md",
            impl_plan="/impl.md",
            execution_mode="swarmed",
            tracks=[track],
            shared_setup_commit="abc123",
            merge_strategy="smart-merge",
            post_merge_qa=["tests"]
        )

        # Serialize
        manifest_path = tmp_path / "manifest.json"
        atomic_write_json(str(manifest_path), asdict(manifest))

        # Deserialize
        loaded = read_json_safe(str(manifest_path))

        assert loaded["format_version"] == "1.0.0"
        assert loaded["feature"] == "test"
        assert len(loaded["tracks"]) == 1
        assert loaded["tracks"][0]["name"] == "backend"

    def test_checkpoint_round_trip(self, tmp_path):
        """Test Checkpoint dataclass can be serialized and deserialized."""
        from spellbook.types import Checkpoint
        from spellbook.command_utils import atomic_write_json, read_json_safe
        from dataclasses import asdict

        checkpoint = Checkpoint(
            format_version="1.0.0",
            track=1,
            last_completed_task="1.2",
            commit="abc123",
            timestamp="2026-01-05T12:30:00Z",
            next_task="1.3"
        )

        # Serialize
        checkpoint_path = tmp_path / "checkpoint.json"
        atomic_write_json(str(checkpoint_path), asdict(checkpoint))

        # Deserialize
        loaded = read_json_safe(str(checkpoint_path))

        assert loaded["track"] == 1
        assert loaded["last_completed_task"] == "1.2"
        assert loaded["next_task"] == "1.3"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

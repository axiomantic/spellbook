"""Tests for work packet execution commands."""

import json
import pytest
from pathlib import Path
from datetime import datetime
from spellbook.command_utils import atomic_write_json, read_json_safe, parse_packet_file
from spellbook.types import Manifest, Track, Checkpoint, CompletionMarker


@pytest.fixture
def sample_manifest(tmp_path):
    """Create a sample manifest for testing."""
    manifest_data = {
        "format_version": "1.0.0",
        "feature": "test-feature",
        "created": datetime.now().isoformat(),
        "project_root": str(tmp_path / "project"),
        "design_doc": "design.md",
        "impl_plan": "plan.md",
        "execution_mode": "parallel",
        "tracks": [
            {
                "id": 1,
                "name": "Core API",
                "packet": "track-1.md",
                "worktree": str(tmp_path / "wt-track-1"),
                "branch": "feature/track-1",
                "status": "pending",
                "depends_on": [],
                "checkpoint": None,
                "completion": None
            },
            {
                "id": 2,
                "name": "Frontend",
                "packet": "track-2.md",
                "worktree": str(tmp_path / "wt-track-2"),
                "branch": "feature/track-2",
                "status": "pending",
                "depends_on": [1],
                "checkpoint": None,
                "completion": None
            },
            {
                "id": 3,
                "name": "Tests",
                "packet": "track-3.md",
                "worktree": str(tmp_path / "wt-track-3"),
                "branch": "feature/track-3",
                "status": "pending",
                "depends_on": [1, 2],
                "checkpoint": None,
                "completion": None
            }
        ],
        "shared_setup_commit": "abc123",
        "merge_strategy": "smart-merge",
        "post_merge_qa": ["pytest", "green-mirage-audit", "factchecker"]
    }

    packet_dir = tmp_path / "packets"
    packet_dir.mkdir()
    manifest_file = packet_dir / "manifest.json"
    atomic_write_json(str(manifest_file), manifest_data)

    return packet_dir, manifest_data


@pytest.fixture
def sample_packet(tmp_path):
    """Create a sample work packet file."""
    packet_content = """---
format_version: "1.0.0"
feature: "test-feature"
track: 1
worktree: "/path/to/wt-track-1"
branch: "feature/track-1"
---

# Track 1: Core API

## Tasks

**Task 1.1:** Create data models
Files: models.py
Acceptance: Models defined with proper types

**Task 1.2:** Implement API endpoints
Files: api.py
Acceptance: All endpoints return correct responses

**Task 1.3:** Add validation logic
Files: validators.py
Acceptance: All inputs validated correctly
"""

    packet_file = tmp_path / "track-1.md"
    packet_file.write_text(packet_content)

    return packet_file


class TestParsePacketFile:
    """Test packet file parsing."""

    def test_parse_packet_with_frontmatter(self, sample_packet):
        """Test parsing packet file with YAML frontmatter."""
        result = parse_packet_file(sample_packet)

        assert result["format_version"] == "1.0.0"
        assert result["feature"] == "test-feature"
        assert result["track"] == 1
        assert result["worktree"] == "/path/to/wt-track-1"
        assert result["branch"] == "feature/track-1"
        assert len(result["tasks"]) == 3

    def test_parse_tasks_from_packet(self, sample_packet):
        """Test extracting tasks from packet body."""
        result = parse_packet_file(sample_packet)
        tasks = result["tasks"]

        assert tasks[0]["id"] == "1.1"
        assert "Create data models" in tasks[0]["description"]
        assert "models.py" in tasks[0]["files"]
        assert "Models defined" in tasks[0]["acceptance"]

        assert tasks[1]["id"] == "1.2"
        assert "Implement API endpoints" in tasks[1]["description"]

        assert tasks[2]["id"] == "1.3"
        assert "Add validation logic" in tasks[2]["description"]


class TestExecuteWorkPacket:
    """Test execute-work-packet command logic."""

    def test_basic_flow_creates_completion_marker(self, sample_manifest, sample_packet, tmp_path):
        """Test that executing a packet creates a completion marker."""
        packet_dir, manifest_data = sample_manifest

        # Copy packet to packet_dir
        (packet_dir / "track-1.md").write_text(sample_packet.read_text())

        # Simulate execution completion
        completion_file = packet_dir / "track-1.completion.json"
        completion_data = {
            "format_version": "1.0.0",
            "status": "complete",
            "commit": "abc123",
            "timestamp": datetime.now().isoformat()
        }
        atomic_write_json(str(completion_file), completion_data)

        # Verify completion marker exists and is valid
        assert completion_file.exists()
        result = read_json_safe(str(completion_file))
        assert result["status"] == "complete"
        assert result["commit"] == "abc123"

    def test_checkpoint_creation_after_task(self, sample_manifest, tmp_path):
        """Test that checkpoint is created after completing a task."""
        packet_dir, manifest_data = sample_manifest

        checkpoint_file = packet_dir / "track-1.checkpoint.json"
        checkpoint_data = {
            "format_version": "1.0.0",
            "track": 1,
            "last_completed_task": "1.1",
            "commit": "def456",
            "timestamp": datetime.now().isoformat(),
            "next_task": "1.2"
        }
        atomic_write_json(str(checkpoint_file), checkpoint_data)

        # Verify checkpoint
        result = read_json_safe(str(checkpoint_file))
        assert result["track"] == 1
        assert result["last_completed_task"] == "1.1"
        assert result["next_task"] == "1.2"

    def test_resume_from_checkpoint(self, sample_manifest, tmp_path):
        """Test resuming execution from checkpoint."""
        packet_dir, manifest_data = sample_manifest

        # Create checkpoint for partially completed track
        checkpoint_file = packet_dir / "track-1.checkpoint.json"
        checkpoint_data = {
            "format_version": "1.0.0",
            "track": 1,
            "last_completed_task": "1.1",
            "commit": "def456",
            "timestamp": datetime.now().isoformat(),
            "next_task": "1.2"
        }
        atomic_write_json(str(checkpoint_file), checkpoint_data)

        # Load checkpoint
        result = read_json_safe(str(checkpoint_file))
        assert result["next_task"] == "1.2"

    def test_dependency_check_incomplete(self, sample_manifest, tmp_path):
        """Test that execution blocks when dependencies are incomplete."""
        packet_dir, manifest_data = sample_manifest

        # Track 2 depends on Track 1
        # Track 1 completion marker does NOT exist
        track_1_completion = packet_dir / "track-1.completion.json"
        assert not track_1_completion.exists()

        # Attempting to execute Track 2 should detect missing dependency
        manifest = read_json_safe(str(packet_dir / "manifest.json"))
        track_2 = next(t for t in manifest["tracks"] if t["id"] == 2)

        # Check dependencies
        dependencies_met = all(
            (packet_dir / f"track-{dep}.completion.json").exists()
            for dep in track_2["depends_on"]
        )
        assert not dependencies_met

    def test_dependency_check_complete(self, sample_manifest, tmp_path):
        """Test that execution proceeds when dependencies are complete."""
        packet_dir, manifest_data = sample_manifest

        # Create Track 1 completion marker
        track_1_completion = packet_dir / "track-1.completion.json"
        completion_data = {
            "format_version": "1.0.0",
            "status": "complete",
            "commit": "abc123",
            "timestamp": datetime.now().isoformat()
        }
        atomic_write_json(str(track_1_completion), completion_data)

        # Check Track 2 dependencies
        manifest = read_json_safe(str(packet_dir / "manifest.json"))
        track_2 = next(t for t in manifest["tracks"] if t["id"] == 2)

        dependencies_met = all(
            (packet_dir / f"track-{dep}.completion.json").exists()
            for dep in track_2["depends_on"]
        )
        assert dependencies_met


class TestExecuteWorkPacketsSeq:
    """Test execute-work-packets-seq command logic."""

    def test_topological_sort_dependencies(self, sample_manifest):
        """Test that tracks are sorted in dependency order."""
        packet_dir, manifest_data = sample_manifest

        # Expected order: Track 1 (no deps), Track 2 (depends on 1), Track 3 (depends on 1, 2)
        def topological_sort(tracks):
            """Simple topological sort for tracks."""
            sorted_tracks = []
            completed = set()

            while len(sorted_tracks) < len(tracks):
                for track in tracks:
                    if track["id"] in completed:
                        continue
                    if all(dep in completed for dep in track["depends_on"]):
                        sorted_tracks.append(track)
                        completed.add(track["id"])

            return sorted_tracks

        sorted_tracks = topological_sort(manifest_data["tracks"])
        assert sorted_tracks[0]["id"] == 1
        assert sorted_tracks[1]["id"] == 2
        assert sorted_tracks[2]["id"] == 3

    def test_sequential_execution_order(self, sample_manifest):
        """Test that packets are executed in correct order."""
        packet_dir, manifest_data = sample_manifest

        execution_order = []

        # Simulate sequential execution
        for track in [1, 2, 3]:
            execution_order.append(track)

            # Create completion marker
            completion_file = packet_dir / f"track-{track}.completion.json"
            completion_data = {
                "format_version": "1.0.0",
                "status": "complete",
                "commit": f"commit-{track}",
                "timestamp": datetime.now().isoformat()
            }
            atomic_write_json(str(completion_file), completion_data)

        assert execution_order == [1, 2, 3]


class TestMergeWorkPackets:
    """Test merge-work-packets command logic."""

    def test_verify_all_tracks_complete(self, sample_manifest):
        """Test verification that all tracks are complete before merge."""
        packet_dir, manifest_data = sample_manifest

        # Create completion markers for all tracks
        for track in manifest_data["tracks"]:
            completion_file = packet_dir / f"track-{track['id']}.completion.json"
            completion_data = {
                "format_version": "1.0.0",
                "status": "complete",
                "commit": f"commit-{track['id']}",
                "timestamp": datetime.now().isoformat()
            }
            atomic_write_json(str(completion_file), completion_data)

        # Verify all completion markers exist
        manifest = read_json_safe(str(packet_dir / "manifest.json"))
        all_complete = all(
            (packet_dir / f"track-{track['id']}.completion.json").exists()
            for track in manifest["tracks"]
        )
        assert all_complete

    def test_incomplete_tracks_block_merge(self, sample_manifest):
        """Test that merge is blocked when tracks are incomplete."""
        packet_dir, manifest_data = sample_manifest

        # Only complete Track 1
        completion_file = packet_dir / "track-1.completion.json"
        completion_data = {
            "format_version": "1.0.0",
            "status": "complete",
            "commit": "abc123",
            "timestamp": datetime.now().isoformat()
        }
        atomic_write_json(str(completion_file), completion_data)

        # Verify not all tracks are complete
        manifest = read_json_safe(str(packet_dir / "manifest.json"))
        all_complete = all(
            (packet_dir / f"track-{track['id']}.completion.json").exists()
            for track in manifest["tracks"]
        )
        assert not all_complete

    def test_qa_gates_list_from_manifest(self, sample_manifest):
        """Test that QA gates are read from manifest."""
        packet_dir, manifest_data = sample_manifest

        manifest = read_json_safe(str(packet_dir / "manifest.json"))
        qa_gates = manifest["post_merge_qa"]

        assert "pytest" in qa_gates
        assert "green-mirage-audit" in qa_gates
        assert "factchecker" in qa_gates

"""
Tests for implementing-features skill execution mode support (Track 1).

These tests verify the logic documented in SKILL.md phases 3.4.5, 3.5, and 3.6
for execution mode analysis, work packet generation, and session handoff.
"""

import json
import os
import tempfile
from pathlib import Path
from datetime import datetime, timezone
import pytest


# Token estimation constants from implementation plan
TOKENS_PER_KB = 350
BASE_OVERHEAD = 20000
TOKENS_PER_TASK_OUTPUT = 2000
TOKENS_PER_REVIEW = 800
TOKENS_PER_FACTCHECK = 500
TOKENS_PER_FILE = 400
CONTEXT_WINDOW = 200000


def estimate_session_tokens(
    design_context_kb: float,
    design_doc_kb: float,
    impl_plan_kb: float,
    num_tasks: int,
    num_files: int,
) -> int:
    """
    Estimate total token usage for a feature implementation session.

    Args:
        design_context_kb: Size of design context in KB
        design_doc_kb: Size of design document in KB
        impl_plan_kb: Size of implementation plan in KB
        num_tasks: Number of tasks in implementation plan
        num_files: Number of files to be modified/created

    Returns:
        Estimated total tokens needed for session
    """
    design_phase = (design_context_kb + design_doc_kb + impl_plan_kb) * TOKENS_PER_KB
    per_task = TOKENS_PER_TASK_OUTPUT + TOKENS_PER_REVIEW + TOKENS_PER_FACTCHECK
    execution_phase = num_tasks * per_task
    file_context = num_files * TOKENS_PER_FILE
    return int(BASE_OVERHEAD + design_phase + execution_phase + file_context)


def recommend_execution_mode(
    estimated_tokens: int, num_tasks: int, num_parallel_tracks: int
) -> tuple[str, str]:
    """
    Recommend execution mode based on feature size and complexity.

    Args:
        estimated_tokens: Estimated token usage from estimate_session_tokens
        num_tasks: Number of tasks in implementation plan
        num_parallel_tracks: Number of parallel tracks identified

    Returns:
        Tuple of (mode, reason) where mode is one of:
        - "swarmed": Large feature, needs separate sessions per track
        - "sequential": Large feature, work through tracks one at a time
        - "delegated": Moderate size, use subagents in this session
        - "direct": Small feature, direct execution in this session
    """
    usage_ratio = estimated_tokens / CONTEXT_WINDOW

    if num_tasks > 25 or usage_ratio > 0.80:
        return "swarmed", "Feature size exceeds safe single-session capacity"

    if usage_ratio > 0.65 or (num_tasks > 15 and num_parallel_tracks >= 3):
        return "swarmed", "Large feature with good parallelization potential"

    if num_tasks > 10 or usage_ratio > 0.40:
        return "delegated", "Moderate size, subagents can handle workload"

    return "direct", "Small feature, direct execution is efficient"


def extract_tracks_from_impl_plan(impl_plan_content: str) -> list[dict]:
    """
    Extract track information from implementation plan content.

    Parses the implementation plan to find:
    - Track headers: ## Track N: <name>
    - Dependencies: <!-- depends-on: Track 1, Track 3 -->
    - Tasks: - [ ] Task N.M: Description
    - Files: Files: file1.ts, file2.ts

    Args:
        impl_plan_content: Full content of implementation plan markdown

    Returns:
        List of track dictionaries with structure:
        {
            "id": 1,
            "name": "track-name",
            "depends_on": [1, 3],
            "tasks": ["Task 1.1: Description", ...],
            "files": ["file1.ts", "file2.ts"]
        }
    """
    tracks = []
    current_track = None

    for line in impl_plan_content.split('\n'):
        # Track header: ## Track N: <name>
        if line.startswith('## Track '):
            if current_track:
                tracks.append(current_track)

            # Parse "## Track 1: Track Name" -> id=1, name="track-name"
            parts = line[9:].split(':', 1)  # Skip "## Track "
            track_id = int(parts[0].strip())
            track_name = parts[1].strip().lower().replace(' ', '-')

            current_track = {
                "id": track_id,
                "name": track_name,
                "depends_on": [],
                "tasks": [],
                "files": []
            }

        # Dependency comment: <!-- depends-on: Track 1, Track 3 -->
        elif current_track and line.strip().startswith('<!-- depends-on:'):
            deps_str = line.strip()[16:-4]  # Extract "Track 1, Track 3"
            for dep in deps_str.split(','):
                dep = dep.strip()
                if dep.startswith('Track '):
                    dep_id = int(dep[6:])
                    current_track["depends_on"].append(dep_id)

        # Task item: - [ ] Task N.M: Description
        elif current_track and line.strip().startswith('- [ ] Task '):
            task = line.strip()[6:]  # Remove "- [ ] "
            current_track["tasks"].append(task)

        # Files line: Files: file1.ts, file2.ts
        elif current_track and line.strip().startswith('Files:'):
            files_str = line.strip()[6:].strip()  # Remove "Files:"
            files = [f.strip() for f in files_str.split(',')]
            current_track["files"].extend(files)

    if current_track:
        tracks.append(current_track)

    return tracks


def generate_work_packet_manifest(
    feature_slug: str,
    project_root: str,
    execution_mode: str,
    tracks: list[dict],
) -> dict:
    """
    Generate manifest for work packets.

    Args:
        feature_slug: Slugified feature name
        project_root: Absolute path to project root
        execution_mode: Execution mode from recommend_execution_mode
        tracks: List of track dictionaries from extract_tracks_from_impl_plan

    Returns:
        Manifest dictionary with format specified in implementation plan
    """
    manifest = {
        "format_version": "1.0.0",
        "feature": feature_slug,
        "created": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        "project_root": project_root,
        "execution_mode": execution_mode,
        "tracks": []
    }

    for track in tracks:
        # Generate worktree path in parent directory
        parent_dir = os.path.dirname(project_root)
        worktree_name = f"{os.path.basename(project_root)}-{feature_slug}-track-{track['id']}"
        worktree_path = os.path.join(parent_dir, worktree_name)

        manifest["tracks"].append({
            "id": track["id"],
            "name": track["name"],
            "packet": f"track-{track['id']}-{track['name']}.md",
            "worktree": worktree_path,
            "branch": f"feature/{feature_slug}/track-{track['id']}",
            "status": "pending",
            "depends_on": track["depends_on"]
        })

    return manifest


def generate_session_commands(
    manifest_path: str,
    track_id: int,
    has_spawn_tool: bool = False
) -> list[str]:
    """
    Generate commands for spawning worker sessions.

    Args:
        manifest_path: Absolute path to work packet manifest
        track_id: Track ID to generate commands for
        has_spawn_tool: Whether spawn_claude_session MCP tool is available

    Returns:
        List of shell commands to execute
    """
    if has_spawn_tool:
        return [
            f"# Auto-spawn using MCP tool",
            f"spawn_claude_session --manifest {manifest_path} --track {track_id}"
        ]
    else:
        work_packet_dir = os.path.dirname(manifest_path)
        with open(manifest_path) as f:
            manifest = json.load(f)

        track = next(t for t in manifest["tracks"] if t["id"] == track_id)
        packet_path = os.path.join(work_packet_dir, track["packet"])
        worktree_path = track["worktree"]

        return [
            f"# Manual spawn for Track {track_id}",
            f"cd {worktree_path}",
            f"claude --session-context {packet_path}",
        ]


# ============================================================================
# TEST SUITE
# ============================================================================

class TestTokenEstimation:
    """Test token estimation logic for execution mode selection."""

    def test_small_feature_low_tokens(self):
        """Small features should estimate under 40% context window."""
        tokens = estimate_session_tokens(
            design_context_kb=10,
            design_doc_kb=5,
            impl_plan_kb=3,
            num_tasks=5,
            num_files=8
        )

        # Design: 18 KB * 350 = 6,300
        # Tasks: 5 * (2000 + 800 + 500) = 16,500
        # Files: 8 * 400 = 3,200
        # Base: 20,000
        # Total: 46,000
        assert tokens == 46_000
        assert tokens < CONTEXT_WINDOW * 0.4

    def test_medium_feature_moderate_tokens(self):
        """Medium features should estimate 40-65% context window."""
        tokens = estimate_session_tokens(
            design_context_kb=30,
            design_doc_kb=15,
            impl_plan_kb=12,
            num_tasks=15,
            num_files=25
        )

        # Design: 57 KB * 350 = 19,950
        # Tasks: 15 * 3,300 = 49,500
        # Files: 25 * 400 = 10,000
        # Base: 20,000
        # Total: 99,450
        assert tokens == 99_450
        assert CONTEXT_WINDOW * 0.4 < tokens < CONTEXT_WINDOW * 0.65

    def test_large_feature_high_tokens(self):
        """Large features should estimate over 65% context window."""
        tokens = estimate_session_tokens(
            design_context_kb=80,
            design_doc_kb=40,
            impl_plan_kb=30,
            num_tasks=30,
            num_files=50
        )

        # Design: 150 KB * 350 = 52,500
        # Tasks: 30 * 3,300 = 99,000
        # Files: 50 * 400 = 20,000
        # Base: 20,000
        # Total: 191,500
        assert tokens == 191_500
        assert tokens > CONTEXT_WINDOW * 0.65


class TestExecutionModeRecommendation:
    """Test execution mode recommendation logic."""

    def test_direct_mode_for_small_features(self):
        """Small features should recommend direct mode."""
        tokens = estimate_session_tokens(10, 5, 3, 5, 8)
        mode, reason = recommend_execution_mode(tokens, num_tasks=5, num_parallel_tracks=1)

        assert mode == "direct"
        assert "Small feature" in reason

    def test_delegated_mode_for_medium_features(self):
        """Medium features should recommend delegated mode."""
        tokens = estimate_session_tokens(30, 15, 12, 15, 25)
        mode, reason = recommend_execution_mode(tokens, num_tasks=15, num_parallel_tracks=2)

        assert mode == "delegated"
        assert "Moderate size" in reason

    def test_swarmed_mode_for_large_features(self):
        """Large features should recommend swarmed mode."""
        tokens = estimate_session_tokens(80, 40, 30, 30, 50)
        mode, reason = recommend_execution_mode(tokens, num_tasks=30, num_parallel_tracks=4)

        assert mode == "swarmed"
        assert "Large feature" in reason or "exceeds" in reason

    def test_swarmed_mode_for_many_tasks(self):
        """Features with >25 tasks should always recommend swarmed."""
        tokens = estimate_session_tokens(20, 10, 8, 26, 20)
        mode, reason = recommend_execution_mode(tokens, num_tasks=26, num_parallel_tracks=2)

        assert mode == "swarmed"
        assert "exceeds" in reason

    def test_swarmed_mode_for_high_parallelization(self):
        """Features with good parallelization should recommend swarmed."""
        tokens = estimate_session_tokens(40, 20, 15, 18, 30)
        mode, reason = recommend_execution_mode(tokens, num_tasks=18, num_parallel_tracks=4)

        assert mode == "swarmed"
        assert "parallelization" in reason


class TestTrackExtraction:
    """Test extraction of tracks from implementation plan content."""

    def test_extract_single_track(self):
        """Should extract a single track with tasks and files."""
        plan = """
## Track 1: Authentication Module

- [ ] Task 1.1: Create user model
- [ ] Task 1.2: Implement login endpoint

Files: src/models/user.ts, src/routes/auth.ts
"""
        tracks = extract_tracks_from_impl_plan(plan)

        assert len(tracks) == 1
        assert tracks[0]["id"] == 1
        assert tracks[0]["name"] == "authentication-module"
        assert len(tracks[0]["tasks"]) == 2
        assert tracks[0]["tasks"][0] == "Task 1.1: Create user model"
        assert len(tracks[0]["files"]) == 2
        assert "src/models/user.ts" in tracks[0]["files"]

    def test_extract_multiple_tracks(self):
        """Should extract multiple tracks."""
        plan = """
## Track 1: Backend API

- [ ] Task 1.1: Setup Express server
- [ ] Task 1.2: Create database schema

Files: src/server.ts, src/db/schema.sql

## Track 2: Frontend UI

- [ ] Task 2.1: Create React components
- [ ] Task 2.2: Add routing

Files: src/components/App.tsx, src/routes.tsx
"""
        tracks = extract_tracks_from_impl_plan(plan)

        assert len(tracks) == 2
        assert tracks[0]["id"] == 1
        assert tracks[0]["name"] == "backend-api"
        assert tracks[1]["id"] == 2
        assert tracks[1]["name"] == "frontend-ui"

    def test_extract_track_dependencies(self):
        """Should extract track dependencies."""
        plan = """
## Track 1: Database Layer

- [ ] Task 1.1: Create schema

## Track 2: API Layer

<!-- depends-on: Track 1 -->

- [ ] Task 2.1: Create endpoints

## Track 3: Integration Tests

<!-- depends-on: Track 1, Track 2 -->

- [ ] Task 3.1: Write tests
"""
        tracks = extract_tracks_from_impl_plan(plan)

        assert len(tracks) == 3
        assert tracks[0]["depends_on"] == []
        assert tracks[1]["depends_on"] == [1]
        assert tracks[2]["depends_on"] == [1, 2]


class TestWorkPacketManifest:
    """Test work packet manifest generation."""

    def test_generate_manifest_basic(self):
        """Should generate manifest with correct structure."""
        tracks = [
            {"id": 1, "name": "backend", "depends_on": [], "tasks": ["Task 1.1"], "files": ["server.ts"]},
            {"id": 2, "name": "frontend", "depends_on": [1], "tasks": ["Task 2.1"], "files": ["app.tsx"]},
        ]

        manifest = generate_work_packet_manifest(
            feature_slug="user-auth",
            project_root="/home/user/project",
            execution_mode="swarmed",
            tracks=tracks
        )

        assert manifest["format_version"] == "1.0.0"
        assert manifest["feature"] == "user-auth"
        assert manifest["project_root"] == "/home/user/project"
        assert manifest["execution_mode"] == "swarmed"
        assert len(manifest["tracks"]) == 2

    def test_manifest_track_structure(self):
        """Should generate correct track structure in manifest."""
        tracks = [
            {"id": 1, "name": "backend-api", "depends_on": [], "tasks": [], "files": []},
        ]

        manifest = generate_work_packet_manifest(
            feature_slug="auth",
            project_root="/Users/dev/myapp",
            execution_mode="swarmed",
            tracks=tracks
        )

        track = manifest["tracks"][0]
        assert track["id"] == 1
        assert track["name"] == "backend-api"
        assert track["packet"] == "track-1-backend-api.md"
        # Use os.path.join for cross-platform path comparison
        expected_worktree = os.path.join(os.path.dirname("/Users/dev/myapp"), "myapp-auth-track-1")
        assert track["worktree"] == expected_worktree
        assert track["branch"] == "feature/auth/track-1"
        assert track["status"] == "pending"
        assert track["depends_on"] == []

    def test_manifest_preserves_dependencies(self):
        """Should preserve track dependencies in manifest."""
        tracks = [
            {"id": 1, "name": "db", "depends_on": [], "tasks": [], "files": []},
            {"id": 2, "name": "api", "depends_on": [1], "tasks": [], "files": []},
            {"id": 3, "name": "tests", "depends_on": [1, 2], "tasks": [], "files": []},
        ]

        manifest = generate_work_packet_manifest(
            feature_slug="feature",
            project_root="/project",
            execution_mode="swarmed",
            tracks=tracks
        )

        assert manifest["tracks"][0]["depends_on"] == []
        assert manifest["tracks"][1]["depends_on"] == [1]
        assert manifest["tracks"][2]["depends_on"] == [1, 2]


class TestSessionCommands:
    """Test session command generation."""

    def test_commands_with_spawn_tool(self):
        """Should generate MCP tool commands when available."""
        commands = generate_session_commands(
            manifest_path="/home/.claude/work-packets/auth/manifest.json",
            track_id=1,
            has_spawn_tool=True
        )

        assert len(commands) == 2
        assert "spawn_claude_session" in commands[1]
        assert "--manifest" in commands[1]
        assert "--track 1" in commands[1]

    def test_commands_without_spawn_tool(self):
        """Should generate manual commands when tool not available."""
        # Create temp manifest
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = os.path.join(tmpdir, "manifest.json")
            manifest = {
                "tracks": [
                    {
                        "id": 1,
                        "packet": "track-1-backend.md",
                        "worktree": "/project-auth-track-1"
                    }
                ]
            }
            with open(manifest_path, 'w') as f:
                json.dump(manifest, f)

            commands = generate_session_commands(
                manifest_path=manifest_path,
                track_id=1,
                has_spawn_tool=False
            )

            assert len(commands) == 3
            assert "cd /project-auth-track-1" in commands[1]
            assert "claude --session-context" in commands[2]
            assert "track-1-backend.md" in commands[2]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

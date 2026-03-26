"""Tests for sessions API routes."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


def _write_session_file(project_dir: Path, session_id: str, messages: list[dict]) -> Path:
    """Write a JSONL session file for testing."""
    jsonl_path = project_dir / f"{session_id}.jsonl"
    with open(jsonl_path, "w") as f:
        for msg in messages:
            f.write(json.dumps(msg) + "\n")
    return jsonl_path


def _setup_projects_dir(tmpdir: str) -> Path:
    """Create the fake ~/.claude/projects/ directory structure."""
    claude_projects = Path(tmpdir) / "fakehome" / ".claude" / "projects"
    claude_projects.mkdir(parents=True)
    return claude_projects


def _patch_home(tmpdir: str):
    """Patch Path.home() to use tmpdir/fakehome."""
    return patch(
        "spellbook.admin.routes.sessions.Path.home",
        return_value=Path(tmpdir) / "fakehome",
    )


class TestSessionList:
    def test_list_sessions_returns_items_key(self, client):
        """Response uses 'items' key (standardized), not 'sessions'."""
        with tempfile.TemporaryDirectory() as tmpdir:
            claude_projects = _setup_projects_dir(tmpdir)
            proj = claude_projects / "Users-test-myproject"
            proj.mkdir()

            _write_session_file(proj, "sess-abc", [
                {"type": "user", "timestamp": "2026-03-14T10:00:00Z",
                 "message": {"content": "Hello world"}},
                {"type": "assistant", "timestamp": "2026-03-14T10:01:00Z",
                 "message": {"content": [{"type": "text", "text": "Hi"}]}},
            ])

            with _patch_home(tmpdir):
                response = client.get("/api/sessions")
                assert response.status_code == 200
                data = response.json()
                assert "items" in data
                assert "sessions" not in data
                assert data["total"] == 1
                assert data["page"] == 1
                assert data["per_page"] == 50
                assert data["pages"] == 1
                assert len(data["items"]) == 1
                sess = data["items"][0]
                assert sess == {
                    "id": "sess-abc",
                    "project": "Users-test-myproject",
                    "slug": None,
                    "custom_title": None,
                    "first_user_message": "Hello world",
                    "created_at": "2026-03-14T10:00:00Z",
                    "last_activity": "2026-03-14T10:01:00Z",
                    "message_count": 2,
                    "size_bytes": sess["size_bytes"],  # dynamic, validated below
                }
                assert isinstance(sess["size_bytes"], int)
                assert sess["size_bytes"] > 0

    def test_list_sessions_filters_by_project(self, client):
        with tempfile.TemporaryDirectory() as tmpdir:
            claude_projects = _setup_projects_dir(tmpdir)

            proj_a = claude_projects / "Users-test-projA"
            proj_a.mkdir()
            _write_session_file(proj_a, "sess-a", [
                {"type": "user", "timestamp": "2026-03-14T10:00:00Z",
                 "message": {"content": "Project A"}},
            ])

            proj_b = claude_projects / "Users-test-projB"
            proj_b.mkdir()
            _write_session_file(proj_b, "sess-b", [
                {"type": "user", "timestamp": "2026-03-14T11:00:00Z",
                 "message": {"content": "Project B"}},
            ])

            with _patch_home(tmpdir):
                response = client.get("/api/sessions?project=projA")
                assert response.status_code == 200
                data = response.json()
                assert data["total"] == 1
                assert len(data["items"]) == 1
                assert data["items"][0]["id"] == "sess-a"

    def test_list_sessions_pagination(self, client):
        with tempfile.TemporaryDirectory() as tmpdir:
            claude_projects = _setup_projects_dir(tmpdir)
            proj = claude_projects / "Users-test-proj"
            proj.mkdir()

            for i in range(5):
                _write_session_file(proj, f"sess-{i}", [
                    {"type": "user", "timestamp": f"2026-03-14T{10+i:02d}:00:00Z",
                     "message": {"content": f"Message {i}"}},
                ])

            with _patch_home(tmpdir):
                response = client.get("/api/sessions?page=2&per_page=2")
                assert response.status_code == 200
                data = response.json()
                assert data["total"] == 5
                assert data["page"] == 2
                assert data["per_page"] == 2
                assert data["pages"] == 3
                assert len(data["items"]) == 2

    def test_list_sessions_requires_auth(self, unauthenticated_client):
        response = unauthenticated_client.get("/api/sessions")
        assert response.status_code == 401

    def test_list_sessions_empty_when_no_projects(self, client):
        with tempfile.TemporaryDirectory() as tmpdir:
            claude_projects = _setup_projects_dir(tmpdir)

            with _patch_home(tmpdir):
                response = client.get("/api/sessions")
                assert response.status_code == 200
                data = response.json()
                assert data["items"] == []
                assert data["total"] == 0

    def test_list_sessions_skips_empty_files(self, client):
        with tempfile.TemporaryDirectory() as tmpdir:
            claude_projects = _setup_projects_dir(tmpdir)
            proj = claude_projects / "Users-test-proj"
            proj.mkdir()

            (proj / "empty-sess.jsonl").touch()
            _write_session_file(proj, "valid-sess", [
                {"type": "user", "timestamp": "2026-03-14T10:00:00Z",
                 "message": {"content": "Hello"}},
            ])

            with _patch_home(tmpdir):
                response = client.get("/api/sessions")
                assert response.status_code == 200
                data = response.json()
                assert data["total"] == 1
                assert data["items"][0]["id"] == "valid-sess"

    def test_list_sessions_default_sort_last_activity_desc(self, client):
        """Default sort is last_activity descending (most recent first)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            claude_projects = _setup_projects_dir(tmpdir)
            proj = claude_projects / "Users-test-proj"
            proj.mkdir()

            _write_session_file(proj, "old-sess", [
                {"type": "user", "timestamp": "2026-03-10T10:00:00Z",
                 "message": {"content": "Old"}},
            ])
            _write_session_file(proj, "new-sess", [
                {"type": "user", "timestamp": "2026-03-14T10:00:00Z",
                 "message": {"content": "New"}},
            ])

            with _patch_home(tmpdir):
                response = client.get("/api/sessions")
                assert response.status_code == 200
                data = response.json()
                assert data["items"][0]["id"] == "new-sess"
                assert data["items"][1]["id"] == "old-sess"

    def test_list_sessions_sort_last_activity_asc(self, client):
        """sort=last_activity&order=asc returns oldest first."""
        with tempfile.TemporaryDirectory() as tmpdir:
            claude_projects = _setup_projects_dir(tmpdir)
            proj = claude_projects / "Users-test-proj"
            proj.mkdir()

            _write_session_file(proj, "old-sess", [
                {"type": "user", "timestamp": "2026-03-10T10:00:00Z",
                 "message": {"content": "Old"}},
            ])
            _write_session_file(proj, "new-sess", [
                {"type": "user", "timestamp": "2026-03-14T10:00:00Z",
                 "message": {"content": "New"}},
            ])

            with _patch_home(tmpdir):
                response = client.get("/api/sessions?sort=last_activity&order=asc")
                assert response.status_code == 200
                data = response.json()
                assert data["items"][0]["id"] == "old-sess"
                assert data["items"][1]["id"] == "new-sess"

    def test_list_sessions_sort_created_at(self, client):
        """sort=created_at sorts by session creation time."""
        with tempfile.TemporaryDirectory() as tmpdir:
            claude_projects = _setup_projects_dir(tmpdir)
            proj = claude_projects / "Users-test-proj"
            proj.mkdir()

            # Session A: created early, last activity late
            _write_session_file(proj, "sess-early-create", [
                {"type": "user", "timestamp": "2026-03-10T08:00:00Z",
                 "message": {"content": "Early"}},
                {"type": "assistant", "timestamp": "2026-03-14T20:00:00Z",
                 "message": {"content": "Late reply"}},
            ])
            # Session B: created late, last activity early
            _write_session_file(proj, "sess-late-create", [
                {"type": "user", "timestamp": "2026-03-12T08:00:00Z",
                 "message": {"content": "Late create"}},
                {"type": "assistant", "timestamp": "2026-03-12T09:00:00Z",
                 "message": {"content": "Quick reply"}},
            ])

            with _patch_home(tmpdir):
                # Descending by created_at: late-create first
                response = client.get("/api/sessions?sort=created_at&order=desc")
                assert response.status_code == 200
                data = response.json()
                assert data["items"][0]["id"] == "sess-late-create"
                assert data["items"][1]["id"] == "sess-early-create"

    def test_list_sessions_sort_message_count(self, client):
        """sort=message_count sorts by number of messages."""
        with tempfile.TemporaryDirectory() as tmpdir:
            claude_projects = _setup_projects_dir(tmpdir)
            proj = claude_projects / "Users-test-proj"
            proj.mkdir()

            _write_session_file(proj, "sess-few", [
                {"type": "user", "timestamp": "2026-03-14T10:00:00Z",
                 "message": {"content": "One message"}},
            ])
            _write_session_file(proj, "sess-many", [
                {"type": "user", "timestamp": "2026-03-14T10:00:00Z",
                 "message": {"content": "First"}},
                {"type": "assistant", "timestamp": "2026-03-14T10:01:00Z",
                 "message": {"content": "Second"}},
                {"type": "user", "timestamp": "2026-03-14T10:02:00Z",
                 "message": {"content": "Third"}},
            ])

            with _patch_home(tmpdir):
                # Desc: most messages first
                response = client.get("/api/sessions?sort=message_count&order=desc")
                assert response.status_code == 200
                data = response.json()
                assert data["items"][0]["id"] == "sess-many"
                assert data["items"][0]["message_count"] == 3
                assert data["items"][1]["id"] == "sess-few"
                assert data["items"][1]["message_count"] == 1

    def test_list_sessions_sort_size_bytes(self, client):
        """sort=size_bytes sorts by file size."""
        with tempfile.TemporaryDirectory() as tmpdir:
            claude_projects = _setup_projects_dir(tmpdir)
            proj = claude_projects / "Users-test-proj"
            proj.mkdir()

            _write_session_file(proj, "sess-small", [
                {"type": "user", "timestamp": "2026-03-14T10:00:00Z",
                 "message": {"content": "Hi"}},
            ])
            _write_session_file(proj, "sess-large", [
                {"type": "user", "timestamp": "2026-03-14T10:00:00Z",
                 "message": {"content": "A" * 500}},
                {"type": "assistant", "timestamp": "2026-03-14T10:01:00Z",
                 "message": {"content": "B" * 500}},
                {"type": "user", "timestamp": "2026-03-14T10:02:00Z",
                 "message": {"content": "C" * 500}},
            ])

            with _patch_home(tmpdir):
                # Desc: largest first
                response = client.get("/api/sessions?sort=size_bytes&order=desc")
                assert response.status_code == 200
                data = response.json()
                assert data["items"][0]["id"] == "sess-large"
                assert data["items"][1]["id"] == "sess-small"
                assert data["items"][0]["size_bytes"] > data["items"][1]["size_bytes"]

    def test_list_sessions_invalid_sort_defaults_to_last_activity(self, client):
        """Invalid sort value falls back to last_activity."""
        with tempfile.TemporaryDirectory() as tmpdir:
            claude_projects = _setup_projects_dir(tmpdir)
            proj = claude_projects / "Users-test-proj"
            proj.mkdir()

            _write_session_file(proj, "old-sess", [
                {"type": "user", "timestamp": "2026-03-10T10:00:00Z",
                 "message": {"content": "Old"}},
            ])
            _write_session_file(proj, "new-sess", [
                {"type": "user", "timestamp": "2026-03-14T10:00:00Z",
                 "message": {"content": "New"}},
            ])

            with _patch_home(tmpdir):
                # Invalid sort param should fall back to last_activity desc
                response = client.get("/api/sessions?sort=INVALID_FIELD&order=desc")
                assert response.status_code == 200
                data = response.json()
                assert data["items"][0]["id"] == "new-sess"
                assert data["items"][1]["id"] == "old-sess"

    def test_list_sessions_invalid_order_defaults_to_desc(self, client):
        """Invalid order value falls back to desc."""
        with tempfile.TemporaryDirectory() as tmpdir:
            claude_projects = _setup_projects_dir(tmpdir)
            proj = claude_projects / "Users-test-proj"
            proj.mkdir()

            _write_session_file(proj, "old-sess", [
                {"type": "user", "timestamp": "2026-03-10T10:00:00Z",
                 "message": {"content": "Old"}},
            ])
            _write_session_file(proj, "new-sess", [
                {"type": "user", "timestamp": "2026-03-14T10:00:00Z",
                 "message": {"content": "New"}},
            ])

            with _patch_home(tmpdir):
                response = client.get("/api/sessions?order=BOGUS")
                assert response.status_code == 200
                data = response.json()
                # Should default to desc (newest first)
                assert data["items"][0]["id"] == "new-sess"
                assert data["items"][1]["id"] == "old-sess"

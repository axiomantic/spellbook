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


class TestSessionList:
    def test_list_sessions_returns_sessions(self, client):
        with tempfile.TemporaryDirectory() as tmpdir:
            projects_dir = Path(tmpdir)
            project_dir = projects_dir / "Users-test-myproject"
            project_dir.mkdir()

            _write_session_file(project_dir, "sess-abc", [
                {"type": "user", "timestamp": "2026-03-14T10:00:00Z",
                 "message": {"content": "Hello world"}},
                {"type": "assistant", "timestamp": "2026-03-14T10:01:00Z",
                 "message": {"content": [{"type": "text", "text": "Hi"}]}},
            ])

            with patch(
                "spellbook.admin.routes.sessions.Path.home",
                return_value=Path(tmpdir) / "fakehome",
            ):
                # Create the .claude/projects structure
                claude_projects = Path(tmpdir) / "fakehome" / ".claude" / "projects"
                claude_projects.mkdir(parents=True)
                # Move our project dir there
                target = claude_projects / "Users-test-myproject"
                os.rename(str(project_dir), str(target))

                response = client.get("/api/sessions")
                assert response.status_code == 200
                data = response.json()
                assert "sessions" in data
                assert "total" in data
                assert data["total"] == 1
                assert len(data["sessions"]) == 1
                sess = data["sessions"][0]
                assert sess["id"] == "sess-abc"
                assert sess["project"] == "Users-test-myproject"
                assert sess["message_count"] == 2
                assert sess["first_user_message"] == "Hello world"
                assert sess["created_at"] == "2026-03-14T10:00:00Z"
                assert sess["last_activity"] == "2026-03-14T10:01:00Z"

    def test_list_sessions_filters_by_project(self, client):
        with tempfile.TemporaryDirectory() as tmpdir:
            claude_projects = Path(tmpdir) / "fakehome" / ".claude" / "projects"
            claude_projects.mkdir(parents=True)

            # Two projects
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

            with patch(
                "spellbook.admin.routes.sessions.Path.home",
                return_value=Path(tmpdir) / "fakehome",
            ):
                response = client.get("/api/sessions?project=projA")
                assert response.status_code == 200
                data = response.json()
                assert data["total"] == 1
                assert data["sessions"][0]["id"] == "sess-a"

    def test_list_sessions_pagination(self, client):
        with tempfile.TemporaryDirectory() as tmpdir:
            claude_projects = Path(tmpdir) / "fakehome" / ".claude" / "projects"
            claude_projects.mkdir(parents=True)
            proj = claude_projects / "Users-test-proj"
            proj.mkdir()

            # Create 5 sessions
            for i in range(5):
                _write_session_file(proj, f"sess-{i}", [
                    {"type": "user", "timestamp": f"2026-03-14T{10+i:02d}:00:00Z",
                     "message": {"content": f"Message {i}"}},
                ])

            with patch(
                "spellbook.admin.routes.sessions.Path.home",
                return_value=Path(tmpdir) / "fakehome",
            ):
                response = client.get("/api/sessions?page=2&per_page=2")
                assert response.status_code == 200
                data = response.json()
                assert data["total"] == 5
                assert data["page"] == 2
                assert data["per_page"] == 2
                assert data["pages"] == 3
                assert len(data["sessions"]) == 2

    def test_list_sessions_requires_auth(self, unauthenticated_client):
        response = unauthenticated_client.get("/api/sessions")
        assert response.status_code == 401

    def test_list_sessions_empty_when_no_projects(self, client):
        with tempfile.TemporaryDirectory() as tmpdir:
            claude_projects = Path(tmpdir) / "fakehome" / ".claude" / "projects"
            claude_projects.mkdir(parents=True)

            with patch(
                "spellbook.admin.routes.sessions.Path.home",
                return_value=Path(tmpdir) / "fakehome",
            ):
                response = client.get("/api/sessions")
                assert response.status_code == 200
                data = response.json()
                assert data["sessions"] == []
                assert data["total"] == 0

    def test_list_sessions_skips_empty_files(self, client):
        with tempfile.TemporaryDirectory() as tmpdir:
            claude_projects = Path(tmpdir) / "fakehome" / ".claude" / "projects"
            claude_projects.mkdir(parents=True)
            proj = claude_projects / "Users-test-proj"
            proj.mkdir()

            # Empty file
            (proj / "empty-sess.jsonl").touch()
            # Valid file
            _write_session_file(proj, "valid-sess", [
                {"type": "user", "timestamp": "2026-03-14T10:00:00Z",
                 "message": {"content": "Hello"}},
            ])

            with patch(
                "spellbook.admin.routes.sessions.Path.home",
                return_value=Path(tmpdir) / "fakehome",
            ):
                response = client.get("/api/sessions")
                assert response.status_code == 200
                data = response.json()
                assert data["total"] == 1
                assert data["sessions"][0]["id"] == "valid-sess"

    def test_list_sessions_sorted_by_last_activity(self, client):
        with tempfile.TemporaryDirectory() as tmpdir:
            claude_projects = Path(tmpdir) / "fakehome" / ".claude" / "projects"
            claude_projects.mkdir(parents=True)
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

            with patch(
                "spellbook.admin.routes.sessions.Path.home",
                return_value=Path(tmpdir) / "fakehome",
            ):
                response = client.get("/api/sessions")
                assert response.status_code == 200
                data = response.json()
                assert data["sessions"][0]["id"] == "new-sess"
                assert data["sessions"][1]["id"] == "old-sess"

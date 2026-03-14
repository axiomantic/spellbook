"""Tests for sessions API routes."""

from unittest.mock import patch, AsyncMock

import pytest


class TestSessionList:
    def test_list_sessions_returns_paginated(self, client):
        with patch(
            "spellbook_mcp.admin.routes.sessions.query_spellbook_db",
            new_callable=AsyncMock,
        ) as mock:
            mock.side_effect = [
                [{"cnt": 1}],  # count query
                [
                    {
                        "id": "soul-1",
                        "project_path": "/home/user/project",
                        "session_id": "sess-abc",
                        "bound_at": "2026-03-14T10:00:00Z",
                        "persona": "The Architect",
                        "active_skill": "implementing-features",
                        "skill_phase": "DESIGN",
                        "workflow_pattern": "TDD",
                        "summoned_at": "2026-03-14T09:00:00Z",
                        "todos": '["item1"]',
                        "recent_files": '["file1.py"]',
                        "exact_position": None,
                    }
                ],
            ]
            response = client.get("/api/sessions")
            assert response.status_code == 200
            data = response.json()
            assert "sessions" in data
            assert "total" in data
            assert data["total"] == 1
            assert data["page"] == 1
            assert data["pages"] == 1
            assert len(data["sessions"]) == 1
            assert data["sessions"][0]["id"] == "soul-1"
            assert data["sessions"][0]["project_path"] == "/home/user/project"
            assert data["sessions"][0]["active_skill"] == "implementing-features"

    def test_list_sessions_filters_by_project(self, client):
        with patch(
            "spellbook_mcp.admin.routes.sessions.query_spellbook_db",
            new_callable=AsyncMock,
        ) as mock:
            mock.side_effect = [[{"cnt": 0}], []]
            response = client.get("/api/sessions?project=/home/user/proj")
            assert response.status_code == 200
            count_sql = mock.call_args_list[0][0][0]
            count_params = mock.call_args_list[0][0][1]
            assert "project_path = ?" in count_sql
            assert "/home/user/proj" in count_params

    def test_list_sessions_pagination(self, client):
        with patch(
            "spellbook_mcp.admin.routes.sessions.query_spellbook_db",
            new_callable=AsyncMock,
        ) as mock:
            mock.side_effect = [[{"cnt": 100}], []]
            response = client.get("/api/sessions?page=3&per_page=20")
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 100
            assert data["page"] == 3
            assert data["per_page"] == 20
            assert data["pages"] == 5
            # Verify offset: (3-1)*20 = 40
            data_params = mock.call_args_list[1][0][1]
            assert 20 in data_params  # limit
            assert 40 in data_params  # offset

    def test_list_sessions_requires_auth(self, unauthenticated_client):
        response = unauthenticated_client.get("/api/sessions")
        assert response.status_code == 401

    def test_list_sessions_empty(self, client):
        with patch(
            "spellbook_mcp.admin.routes.sessions.query_spellbook_db",
            new_callable=AsyncMock,
        ) as mock:
            mock.side_effect = [[{"cnt": 0}], []]
            response = client.get("/api/sessions")
            assert response.status_code == 200
            data = response.json()
            assert data["sessions"] == []
            assert data["total"] == 0


class TestSessionDetail:
    def test_session_detail_returns_full(self, client):
        with patch(
            "spellbook_mcp.admin.routes.sessions.query_spellbook_db",
            new_callable=AsyncMock,
        ) as mock:
            mock.return_value = [
                {
                    "id": "soul-1",
                    "project_path": "/home/user/project",
                    "session_id": "sess-abc",
                    "bound_at": "2026-03-14T10:00:00Z",
                    "persona": "The Architect",
                    "active_skill": "implementing-features",
                    "skill_phase": "DESIGN",
                    "workflow_pattern": "TDD",
                    "summoned_at": "2026-03-14T09:00:00Z",
                    "todos": '[{"text": "do thing", "done": false}]',
                    "recent_files": '["file1.py", "file2.py"]',
                    "exact_position": "line 42 of main.py",
                }
            ]
            response = client.get("/api/sessions/soul-1")
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == "soul-1"
            assert data["project_path"] == "/home/user/project"
            assert data["active_skill"] == "implementing-features"
            assert data["skill_phase"] == "DESIGN"
            assert data["workflow_pattern"] == "TDD"
            assert data["persona"] == "The Architect"
            # JSON fields should be parsed
            assert isinstance(data["todos"], list)
            assert isinstance(data["recent_files"], list)

    def test_session_detail_404_not_found(self, client):
        with patch(
            "spellbook_mcp.admin.routes.sessions.query_spellbook_db",
            new_callable=AsyncMock,
        ) as mock:
            mock.return_value = []
            response = client.get("/api/sessions/nonexistent")
            assert response.status_code == 404
            data = response.json()
            assert data["error"]["code"] == "SESSION_NOT_FOUND"

    def test_session_detail_requires_auth(self, unauthenticated_client):
        response = unauthenticated_client.get("/api/sessions/soul-1")
        assert response.status_code == 401

    def test_session_detail_with_null_json_fields(self, client):
        """Verify null JSON fields don't cause parsing errors."""
        with patch(
            "spellbook_mcp.admin.routes.sessions.query_spellbook_db",
            new_callable=AsyncMock,
        ) as mock:
            mock.return_value = [
                {
                    "id": "soul-2",
                    "project_path": "/home/user/other",
                    "session_id": None,
                    "bound_at": None,
                    "persona": None,
                    "active_skill": None,
                    "skill_phase": None,
                    "workflow_pattern": None,
                    "summoned_at": None,
                    "todos": None,
                    "recent_files": None,
                    "exact_position": None,
                }
            ]
            response = client.get("/api/sessions/soul-2")
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == "soul-2"
            assert data["todos"] is None
            assert data["recent_files"] is None

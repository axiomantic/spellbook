"""Tests for memory browser admin routes."""

import json
from unittest.mock import AsyncMock, patch

import pytest


WK = "/Users/elijahrutschman/Development/spellbook/.worktrees/web-admin-interface"
ROUTE_MODULE = "spellbook.admin.routes.memory"


def _memory_row(
    id="mem-1",
    content="test memory content",
    memory_type="observation",
    namespace="project-a",
    branch="main",
    importance=1.0,
    created_at="2026-03-14T10:00:00Z",
    accessed_at=None,
    status="active",
    meta="{}",
    citation_count=0,
):
    return {
        "id": id,
        "content": content,
        "memory_type": memory_type,
        "namespace": namespace,
        "branch": branch,
        "importance": importance,
        "created_at": created_at,
        "accessed_at": accessed_at,
        "status": status,
        "meta": meta,
        "citation_count": citation_count,
    }


class TestMemoryList:
    def test_list_memories_returns_paginated(self, client):
        with patch(
            f"{ROUTE_MODULE}.query_spellbook_db", new_callable=AsyncMock
        ) as mock_query:
            mock_query.side_effect = [
                [{"cnt": 1}],  # count query
                [_memory_row()],  # data query
            ]
            response = client.get("/api/memories")
            assert response.status_code == 200
            data = response.json()
            assert "memories" in data
            assert data["total"] == 1
            assert data["page"] == 1
            assert data["per_page"] == 50
            assert data["pages"] == 1
            assert len(data["memories"]) == 1
            mem = data["memories"][0]
            assert mem["id"] == "mem-1"
            assert mem["citation_count"] == 0

    def test_list_memories_with_search(self, client):
        with patch(
            f"{ROUTE_MODULE}.query_spellbook_db", new_callable=AsyncMock
        ) as mock_query:
            mock_query.side_effect = [
                [{"cnt": 1}],
                [_memory_row(content="matching result")],
            ]
            response = client.get("/api/memories?q=matching")
            assert response.status_code == 200
            # Verify FTS query was used (second call should have FTS JOIN)
            count_sql = mock_query.call_args_list[0][0][0]
            assert "memories_fts" in count_sql

    def test_list_memories_namespace_filter(self, client):
        with patch(
            f"{ROUTE_MODULE}.query_spellbook_db", new_callable=AsyncMock
        ) as mock_query:
            mock_query.side_effect = [
                [{"cnt": 1}],
                [_memory_row(namespace="filtered-ns")],
            ]
            response = client.get("/api/memories?namespace=filtered-ns")
            assert response.status_code == 200
            # Verify namespace filter was applied
            count_sql = mock_query.call_args_list[0][0][0]
            assert "namespace" in count_sql

    def test_list_memories_pagination(self, client):
        with patch(
            f"{ROUTE_MODULE}.query_spellbook_db", new_callable=AsyncMock
        ) as mock_query:
            mock_query.side_effect = [
                [{"cnt": 75}],
                [_memory_row(id=f"mem-{i}") for i in range(25)],
            ]
            response = client.get("/api/memories?page=2&per_page=25")
            assert response.status_code == 200
            data = response.json()
            assert data["page"] == 2
            assert data["per_page"] == 25
            assert data["pages"] == 3
            assert data["total"] == 75
            # Verify OFFSET was used
            data_sql = mock_query.call_args_list[1][0][0]
            assert "OFFSET" in data_sql

    def test_list_memories_requires_auth(self, unauthenticated_client):
        response = unauthenticated_client.get("/api/memories")
        assert response.status_code == 401

    def test_list_memories_citation_count_uses_left_join(self, client):
        with patch(
            f"{ROUTE_MODULE}.query_spellbook_db", new_callable=AsyncMock
        ) as mock_query:
            mock_query.side_effect = [
                [{"cnt": 1}],
                [_memory_row(citation_count=3)],
            ]
            response = client.get("/api/memories")
            assert response.status_code == 200
            # Verify LEFT JOIN was used in the data query
            data_sql = mock_query.call_args_list[1][0][0]
            assert "LEFT JOIN" in data_sql
            assert "memory_citations" in data_sql
            assert response.json()["memories"][0]["citation_count"] == 3


class TestMemoryDetail:
    def test_get_memory_returns_detail(self, client):
        with patch(
            f"{ROUTE_MODULE}.query_spellbook_db", new_callable=AsyncMock
        ) as mock_query:
            mock_query.side_effect = [
                [_memory_row(content="full content here", citation_count=2)],
                [
                    {
                        "id": 1,
                        "memory_id": "mem-1",
                        "file_path": "/src/main.py",
                        "line_range": "10-20",
                        "content_snippet": "def main():",
                    }
                ],
            ]
            response = client.get("/api/memories/mem-1")
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == "mem-1"
            assert data["content"] == "full content here"
            assert data["citation_count"] == 2
            assert len(data["citations"]) == 1
            assert data["citations"][0]["file_path"] == "/src/main.py"

    def test_get_memory_not_found(self, client):
        with patch(
            f"{ROUTE_MODULE}.query_spellbook_db", new_callable=AsyncMock
        ) as mock_query:
            mock_query.return_value = []
            response = client.get("/api/memories/nonexistent")
            assert response.status_code == 404
            data = response.json()
            assert data["error"]["code"] == "MEMORY_NOT_FOUND"

    def test_get_memory_requires_auth(self, unauthenticated_client):
        response = unauthenticated_client.get("/api/memories/mem-1")
        assert response.status_code == 401


class TestMemoryUpdate:
    def test_update_memory_content(self, client):
        with patch(
            f"{ROUTE_MODULE}.query_spellbook_db", new_callable=AsyncMock
        ) as mock_q:
            with patch(
                f"{ROUTE_MODULE}.execute_spellbook_db", new_callable=AsyncMock
            ) as mock_exec:
                mock_q.return_value = [
                    _memory_row(id="mem-1", content="old content")
                ]
                mock_exec.return_value = 1
                response = client.put(
                    "/api/memories/mem-1", json={"content": "updated content"}
                )
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "ok"
                # Verify UPDATE SQL was executed
                update_sql = mock_exec.call_args[0][0]
                assert "UPDATE memories" in update_sql

    def test_update_memory_importance(self, client):
        with patch(
            f"{ROUTE_MODULE}.query_spellbook_db", new_callable=AsyncMock
        ) as mock_q:
            with patch(
                f"{ROUTE_MODULE}.execute_spellbook_db", new_callable=AsyncMock
            ) as mock_exec:
                mock_q.return_value = [_memory_row()]
                mock_exec.return_value = 1
                response = client.put(
                    "/api/memories/mem-1", json={"importance": 5.0}
                )
                assert response.status_code == 200

    def test_update_memory_not_found(self, client):
        with patch(
            f"{ROUTE_MODULE}.query_spellbook_db", new_callable=AsyncMock
        ) as mock_q:
            mock_q.return_value = []
            response = client.put(
                "/api/memories/nonexistent", json={"content": "new"}
            )
            assert response.status_code == 404
            assert response.json()["error"]["code"] == "MEMORY_NOT_FOUND"

    def test_update_publishes_event(self, client):
        with patch(
            f"{ROUTE_MODULE}.query_spellbook_db", new_callable=AsyncMock
        ) as mock_q:
            with patch(
                f"{ROUTE_MODULE}.execute_spellbook_db", new_callable=AsyncMock
            ) as mock_exec:
                with patch(
                    f"{ROUTE_MODULE}.event_bus.publish", new_callable=AsyncMock
                ) as mock_pub:
                    mock_q.return_value = [_memory_row()]
                    mock_exec.return_value = 1
                    response = client.put(
                        "/api/memories/mem-1",
                        json={"content": "updated"},
                    )
                    assert response.status_code == 200
                    mock_pub.assert_called_once()
                    event = mock_pub.call_args[0][0]
                    assert event.event_type == "memory.updated"
                    assert event.data["memory_id"] == "mem-1"

    def test_update_memory_requires_auth(self, unauthenticated_client):
        response = unauthenticated_client.put(
            "/api/memories/mem-1", json={"content": "new"}
        )
        assert response.status_code == 401


class TestMemoryDelete:
    def test_delete_memory_soft_deletes(self, client):
        with patch(
            f"{ROUTE_MODULE}.execute_spellbook_db", new_callable=AsyncMock
        ) as mock_exec:
            mock_exec.return_value = 1
            response = client.delete("/api/memories/mem-1")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ok"
            # Verify soft delete (SET status='deleted')
            sql = mock_exec.call_args[0][0]
            assert "status" in sql.lower()
            assert "deleted" in sql.lower() or "deleted" in str(
                mock_exec.call_args[0][1]
            )

    def test_delete_memory_not_found(self, client):
        with patch(
            f"{ROUTE_MODULE}.execute_spellbook_db", new_callable=AsyncMock
        ) as mock_exec:
            mock_exec.return_value = 0
            response = client.delete("/api/memories/nonexistent")
            assert response.status_code == 404
            assert response.json()["error"]["code"] == "MEMORY_NOT_FOUND"

    def test_delete_publishes_event(self, client):
        with patch(
            f"{ROUTE_MODULE}.execute_spellbook_db", new_callable=AsyncMock
        ) as mock_exec:
            with patch(
                f"{ROUTE_MODULE}.event_bus.publish", new_callable=AsyncMock
            ) as mock_pub:
                mock_exec.return_value = 1
                response = client.delete("/api/memories/mem-1")
                assert response.status_code == 200
                mock_pub.assert_called_once()
                event = mock_pub.call_args[0][0]
                assert event.event_type == "memory.deleted"
                assert event.data["memory_id"] == "mem-1"

    def test_delete_memory_requires_auth(self, unauthenticated_client):
        response = unauthenticated_client.delete("/api/memories/mem-1")
        assert response.status_code == 401


class TestConsolidate:
    def test_consolidate_triggers_successfully(self, client):
        with patch(
            f"{ROUTE_MODULE}.consolidate_batch"
        ) as mock_consolidate:
            mock_consolidate.return_value = {
                "status": "ok",
                "memories_created": 3,
                "events_consolidated": 10,
            }
            with patch(
                f"{ROUTE_MODULE}.get_db_path", return_value="/tmp/test.db"
            ):
                response = client.post(
                    "/api/memories/consolidate",
                    json={"namespace": "test-ns", "max_events": 50},
                )
                assert response.status_code == 200
                data = response.json()
                assert data["memories_created"] == 3
                assert data["events_consolidated"] == 10

    def test_consolidate_409_when_running(self, client):
        with patch(
            f"{ROUTE_MODULE}.consolidate_batch"
        ) as mock_consolidate:
            import asyncio

            # Simulate long-running consolidation
            mock_consolidate.side_effect = lambda *a, **kw: asyncio.sleep(100)

            with patch(
                f"{ROUTE_MODULE}.get_db_path", return_value="/tmp/test.db"
            ):
                with patch(
                    f"{ROUTE_MODULE}._consolidation_running", True
                ):
                    response = client.post(
                        "/api/memories/consolidate",
                        json={"namespace": "test-ns"},
                    )
                    assert response.status_code == 409
                    assert (
                        response.json()["error"]["code"]
                        == "CONSOLIDATION_IN_PROGRESS"
                    )

    def test_consolidate_requires_auth(self, unauthenticated_client):
        response = unauthenticated_client.post(
            "/api/memories/consolidate", json={"namespace": "test-ns"}
        )
        assert response.status_code == 401


class TestNamespaces:
    def test_list_namespaces(self, client):
        with patch(
            f"{ROUTE_MODULE}.query_spellbook_db", new_callable=AsyncMock
        ) as mock_query:
            mock_query.return_value = [
                {"namespace": "project-a"},
                {"namespace": "project-b"},
            ]
            response = client.get("/api/memories/namespaces")
            assert response.status_code == 200
            data = response.json()
            assert data["namespaces"] == ["project-a", "project-b"]


class TestMemoryStats:
    def test_stats_returns_aggregated(self, client):
        with patch(
            f"{ROUTE_MODULE}.query_spellbook_db", new_callable=AsyncMock
        ) as mock_query:
            mock_query.side_effect = [
                [{"cnt": 42}],  # total
                [
                    {"memory_type": "observation", "cnt": 30},
                    {"memory_type": "synthesis", "cnt": 12},
                ],
                [
                    {"status": "active", "cnt": 40},
                    {"status": "deleted", "cnt": 2},
                ],
                [
                    {"namespace": "project-a", "cnt": 25},
                    {"namespace": "project-b", "cnt": 17},
                ],
            ]
            response = client.get("/api/memories/stats")
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 42
            assert data["by_type"]["observation"] == 30
            assert data["by_status"]["active"] == 40
            assert data["by_namespace"]["project-a"] == 25

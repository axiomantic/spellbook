"""Fractal graph explorer API route tests."""

from unittest.mock import AsyncMock, patch

import pytest


class TestFractalGraphList:
    def test_list_graphs_returns_paginated(self, client):
        with patch(
            "spellbook.admin.routes.fractal.query_fractal_db",
            new_callable=AsyncMock,
        ) as mock:
            mock.side_effect = [
                [{"cnt": 1}],
                [
                    {
                        "id": "g-1",
                        "seed": "test topic",
                        "intensity": "medium",
                        "status": "active",
                        "total_nodes": 5,
                        "created_at": "2026-03-14T10:00:00Z",
                    }
                ],
            ]
            response = client.get("/api/fractal/graphs")
            assert response.status_code == 200
            data = response.json()
            assert "graphs" in data
            assert data["total"] == 1
            assert data["page"] == 1
            assert len(data["graphs"]) == 1
            assert data["graphs"][0]["id"] == "g-1"

    def test_list_graphs_with_status_filter(self, client):
        with patch(
            "spellbook.admin.routes.fractal.query_fractal_db",
            new_callable=AsyncMock,
        ) as mock:
            mock.side_effect = [
                [{"cnt": 0}],
                [],
            ]
            response = client.get("/api/fractal/graphs?status=completed")
            assert response.status_code == 200
            assert response.json()["graphs"] == []

    def test_list_graphs_requires_auth(self, unauthenticated_client):
        response = unauthenticated_client.get("/api/fractal/graphs")
        assert response.status_code == 401


class TestFractalGraphDetail:
    def test_graph_detail_returns_full(self, client):
        with patch(
            "spellbook.admin.routes.fractal.query_fractal_db",
            new_callable=AsyncMock,
        ) as mock:
            mock.return_value = [
                {
                    "id": "g-1",
                    "seed": "test",
                    "intensity": "medium",
                    "status": "active",
                    "total_nodes": 5,
                    "created_at": "2026-03-14T10:00:00Z",
                    "metadata_json": "{}",
                    "checkpoint_mode": "auto",
                    "updated_at": "2026-03-14T10:00:00Z",
                }
            ]
            response = client.get("/api/fractal/graphs/g-1")
            assert response.status_code == 200
            assert response.json()["id"] == "g-1"
            assert response.json()["total_nodes"] == 5

    def test_graph_detail_404(self, client):
        with patch(
            "spellbook.admin.routes.fractal.query_fractal_db",
            new_callable=AsyncMock,
        ) as mock:
            mock.return_value = []
            response = client.get("/api/fractal/graphs/nonexistent")
            assert response.status_code == 404
            assert response.json()["error"]["code"] == "GRAPH_NOT_FOUND"


class TestFractalNodes:
    def test_get_nodes(self, client):
        with patch(
            "spellbook.admin.routes.fractal.query_fractal_db",
            new_callable=AsyncMock,
        ) as mock:
            mock.side_effect = [
                [{"id": "g-1"}],  # graph exists check
                [
                    {
                        "id": "n-1",
                        "node_type": "question",
                        "text": "root question",
                        "owner": None,
                        "depth": 0,
                        "status": "saturated",
                        "parent_id": None,
                        "metadata_json": "{}",
                        "created_at": "2026-03-14T10:00:00Z",
                        "session_id": None,
                        "claimed_at": None,
                        "answered_at": None,
                        "synthesized_at": None,
                    }
                ],
            ]
            response = client.get("/api/fractal/graphs/g-1/nodes")
            assert response.status_code == 200
            data = response.json()
            assert data["count"] == 1
            assert data["nodes"][0]["id"] == "n-1"

    def test_get_nodes_with_depth_filter(self, client):
        with patch(
            "spellbook.admin.routes.fractal.query_fractal_db",
            new_callable=AsyncMock,
        ) as mock:
            mock.side_effect = [
                [{"id": "g-1"}],
                [
                    {
                        "id": "n-1",
                        "node_type": "question",
                        "text": "root",
                        "owner": None,
                        "depth": 0,
                        "status": "saturated",
                        "parent_id": None,
                        "metadata_json": "{}",
                        "created_at": "2026-03-14T10:00:00Z",
                        "session_id": None,
                        "claimed_at": None,
                        "answered_at": None,
                        "synthesized_at": None,
                    }
                ],
            ]
            response = client.get("/api/fractal/graphs/g-1/nodes?max_depth=0")
            assert response.status_code == 200

    def test_get_nodes_graph_not_found(self, client):
        with patch(
            "spellbook.admin.routes.fractal.query_fractal_db",
            new_callable=AsyncMock,
        ) as mock:
            mock.return_value = []
            response = client.get("/api/fractal/graphs/bad-id/nodes")
            assert response.status_code == 404


class TestFractalEdges:
    def test_get_edges(self, client):
        with patch(
            "spellbook.admin.routes.fractal.query_fractal_db",
            new_callable=AsyncMock,
        ) as mock:
            mock.side_effect = [
                [{"id": "g-1"}],
                [
                    {
                        "id": 1,
                        "source": "n-1",
                        "target": "n-2",
                        "edge_type": "parent_child",
                        "metadata_json": "{}",
                        "created_at": "2026-03-14T10:00:00Z",
                    }
                ],
            ]
            response = client.get("/api/fractal/graphs/g-1/edges")
            assert response.status_code == 200
            data = response.json()
            assert data["count"] == 1
            assert data["edges"][0]["source"] == "n-1"


class TestFractalCytoscape:
    def test_cytoscape_returns_elements(self, client):
        with patch(
            "spellbook.admin.routes.fractal.query_fractal_db",
            new_callable=AsyncMock,
        ) as mock:
            mock.side_effect = [
                [{"id": "g-1"}],  # graph exists
                [
                    {
                        "id": "n-1",
                        "node_type": "question",
                        "text": "root",
                        "depth": 0,
                        "status": "saturated",
                        "parent_id": None,
                        "owner": None,
                        "session_id": None,
                        "claimed_at": None,
                        "answered_at": None,
                        "synthesized_at": None,
                    },
                    {
                        "id": "n-2",
                        "node_type": "answer",
                        "text": "response",
                        "depth": 1,
                        "status": "open",
                        "parent_id": "n-1",
                        "owner": "agent-1",
                        "session_id": None,
                        "claimed_at": None,
                        "answered_at": None,
                        "synthesized_at": None,
                    },
                ],
                [
                    {
                        "source": "n-1",
                        "target": "n-2",
                        "edge_type": "parent_child",
                    }
                ],
            ]
            response = client.get("/api/fractal/graphs/g-1/cytoscape")
            assert response.status_code == 200
            data = response.json()
            assert "elements" in data
            assert "nodes" in data["elements"]
            assert "edges" in data["elements"]
            assert "stats" in data

            # Verify node format
            nodes = data["elements"]["nodes"]
            assert len(nodes) == 2
            assert nodes[0]["data"]["id"] == "n-1"
            assert nodes[0]["classes"] == "question saturated"

            # Verify edge format
            edges = data["elements"]["edges"]
            assert len(edges) == 1
            assert edges[0]["data"]["source"] == "n-1"
            assert edges[0]["classes"] == "parent_child"

            # Verify stats
            stats = data["stats"]
            assert stats["total_nodes"] == 2
            assert stats["saturated"] == 1
            assert stats["pending"] == 1
            assert stats["max_depth"] == 1

    def test_cytoscape_graph_not_found(self, client):
        with patch(
            "spellbook.admin.routes.fractal.query_fractal_db",
            new_callable=AsyncMock,
        ) as mock:
            mock.return_value = []
            response = client.get("/api/fractal/graphs/bad-id/cytoscape")
            assert response.status_code == 404
            assert response.json()["error"]["code"] == "GRAPH_NOT_FOUND"

    def test_cytoscape_filters_edges_by_visible_nodes(self, client):
        """Edges to nodes outside depth filter should be excluded."""
        with patch(
            "spellbook.admin.routes.fractal.query_fractal_db",
            new_callable=AsyncMock,
        ) as mock:
            mock.side_effect = [
                [{"id": "g-1"}],
                # Only depth 0 nodes returned due to max_depth=0
                [
                    {
                        "id": "n-1",
                        "node_type": "question",
                        "text": "root",
                        "depth": 0,
                        "status": "open",
                        "parent_id": None,
                        "owner": None,
                        "session_id": None,
                        "claimed_at": None,
                        "answered_at": None,
                        "synthesized_at": None,
                    }
                ],
                # Edge to n-2 which is NOT in node set
                [
                    {
                        "source": "n-1",
                        "target": "n-2",
                        "edge_type": "parent_child",
                    }
                ],
            ]
            response = client.get("/api/fractal/graphs/g-1/cytoscape?max_depth=0")
            assert response.status_code == 200
            data = response.json()
            # Edge should be filtered out since n-2 is not visible
            assert len(data["elements"]["edges"]) == 0
            assert len(data["elements"]["nodes"]) == 1


class TestFractalConvergence:
    def test_convergence(self, client):
        with patch(
            "spellbook.admin.routes.fractal.query_fractal_db",
            new_callable=AsyncMock,
        ) as mock:
            mock.side_effect = [
                [{"id": "g-1"}],
                [
                    {
                        "from_node": "n-1",
                        "to_node": "n-2",
                        "metadata_json": "{}",
                        "from_text": "insight A",
                        "from_depth": 1,
                        "to_text": "insight B",
                        "to_depth": 2,
                    }
                ],
            ]
            response = client.get("/api/fractal/graphs/g-1/convergence")
            assert response.status_code == 200
            data = response.json()
            assert data["count"] == 1
            assert len(data["clusters"]) == 1


class TestFractalContradictions:
    def test_contradictions(self, client):
        with patch(
            "spellbook.admin.routes.fractal.query_fractal_db",
            new_callable=AsyncMock,
        ) as mock:
            mock.side_effect = [
                [{"id": "g-1"}],
                [
                    {
                        "from_node": "n-1",
                        "to_node": "n-2",
                        "metadata_json": "{}",
                        "from_text": "claim A",
                        "to_text": "claim B",
                    }
                ],
            ]
            response = client.get("/api/fractal/graphs/g-1/contradictions")
            assert response.status_code == 200
            data = response.json()
            assert data["count"] == 1
            assert len(data["pairs"]) == 1


class TestFractalGraphDelete:
    def test_delete_graph_success(self, client):
        """DELETE /fractal/graphs/{graph_id} returns 200 with deleted confirmation."""
        with (
            patch(
                "spellbook.admin.routes.fractal.delete_graph",
                return_value={"deleted": True, "graph_id": "g-1"},
            ) as mock_delete,
            patch(
                "spellbook.admin.routes.fractal.event_bus",
            ) as mock_bus,
        ):
            mock_bus.publish = AsyncMock()
            response = client.delete("/api/fractal/graphs/g-1")
            assert response.status_code == 200
            assert response.json() == {"deleted": True, "graph_id": "g-1"}

            # Verify delete_graph was called with the correct graph_id
            mock_delete.assert_called_once_with("g-1")

            # Verify event was published
            assert mock_bus.publish.call_count == 1
            published_event = mock_bus.publish.call_args[0][0]
            assert published_event.subsystem.value == "fractal"
            assert published_event.event_type == "fractal.graph_deleted"
            assert published_event.data == {"graph_id": "g-1"}

    def test_delete_graph_not_found(self, client):
        """DELETE /fractal/graphs/{graph_id} returns 404 when graph doesn't exist."""
        with (
            patch(
                "spellbook.admin.routes.fractal.delete_graph",
                return_value={"error": "Graph 'g-missing' not found."},
            ) as mock_delete,
            patch(
                "spellbook.admin.routes.fractal.event_bus",
            ) as mock_bus,
        ):
            mock_bus.publish = AsyncMock()
            response = client.delete("/api/fractal/graphs/g-missing")
            assert response.status_code == 404
            assert response.json() == {
                "error": {"code": "GRAPH_NOT_FOUND", "message": "Graph not found"}
            }

            mock_delete.assert_called_once_with("g-missing")

            # No event published on failure
            mock_bus.publish.assert_not_called()

    def test_delete_graph_requires_auth(self, unauthenticated_client):
        """DELETE /fractal/graphs/{graph_id} returns 401 without auth."""
        response = unauthenticated_client.delete("/api/fractal/graphs/g-1")
        assert response.status_code == 401


class TestFractalGraphStatusUpdate:
    def test_update_status_success(self, client):
        """PATCH /fractal/graphs/{graph_id}/status returns 200 with updated status."""
        with (
            patch(
                "spellbook.admin.routes.fractal.update_graph_status",
                return_value={
                    "graph_id": "g-1",
                    "status": "completed",
                    "previous_status": "active",
                },
            ) as mock_update,
            patch(
                "spellbook.admin.routes.fractal.event_bus",
            ) as mock_bus,
        ):
            mock_bus.publish = AsyncMock()
            response = client.patch(
                "/api/fractal/graphs/g-1/status",
                json={"status": "completed"},
            )
            assert response.status_code == 200
            assert response.json() == {
                "graph_id": "g-1",
                "status": "completed",
                "previous_status": "active",
            }

            mock_update.assert_called_once_with("g-1", "completed", None)

            # Verify event was published
            assert mock_bus.publish.call_count == 1
            published_event = mock_bus.publish.call_args[0][0]
            assert published_event.subsystem.value == "fractal"
            assert published_event.event_type == "fractal.graph_updated"
            assert published_event.data == {
                "graph_id": "g-1",
                "status": "completed",
            }

    def test_update_status_with_reason(self, client):
        """PATCH /fractal/graphs/{graph_id}/status passes reason to graph_ops."""
        with (
            patch(
                "spellbook.admin.routes.fractal.update_graph_status",
                return_value={
                    "graph_id": "g-1",
                    "status": "paused",
                    "previous_status": "active",
                },
            ) as mock_update,
            patch(
                "spellbook.admin.routes.fractal.event_bus",
            ) as mock_bus,
        ):
            mock_bus.publish = AsyncMock()
            response = client.patch(
                "/api/fractal/graphs/g-1/status",
                json={"status": "paused", "reason": "taking a break"},
            )
            assert response.status_code == 200
            assert response.json() == {
                "graph_id": "g-1",
                "status": "paused",
                "previous_status": "active",
            }

            mock_update.assert_called_once_with("g-1", "paused", "taking a break")

    def test_update_status_invalid_transition(self, client):
        """PATCH /fractal/graphs/{graph_id}/status returns 400 for invalid transition."""
        with (
            patch(
                "spellbook.admin.routes.fractal.update_graph_status",
                return_value={
                    "error": "Invalid transition from 'completed' to 'active'. "
                    "Allowed transitions from 'completed': []"
                },
            ) as mock_update,
            patch(
                "spellbook.admin.routes.fractal.event_bus",
            ) as mock_bus,
        ):
            mock_bus.publish = AsyncMock()
            response = client.patch(
                "/api/fractal/graphs/g-1/status",
                json={"status": "active"},
            )
            assert response.status_code == 400
            assert response.json() == {
                "error": {
                    "code": "INVALID_TRANSITION",
                    "message": (
                        "Invalid transition from 'completed' to 'active'. "
                        "Allowed transitions from 'completed': []"
                    ),
                }
            }

            mock_update.assert_called_once_with("g-1", "active", None)
            mock_bus.publish.assert_not_called()

    def test_update_status_not_found(self, client):
        """PATCH /fractal/graphs/{graph_id}/status returns 404 when graph missing."""
        with (
            patch(
                "spellbook.admin.routes.fractal.update_graph_status",
                return_value={"error": "Graph 'g-missing' not found."},
            ) as mock_update,
            patch(
                "spellbook.admin.routes.fractal.event_bus",
            ) as mock_bus,
        ):
            mock_bus.publish = AsyncMock()
            response = client.patch(
                "/api/fractal/graphs/g-missing/status",
                json={"status": "completed"},
            )
            assert response.status_code == 404
            assert response.json() == {
                "error": {
                    "code": "GRAPH_NOT_FOUND",
                    "message": "Graph not found",
                }
            }

            mock_update.assert_called_once_with("g-missing", "completed", None)
            mock_bus.publish.assert_not_called()

    def test_update_status_requires_auth(self, unauthenticated_client):
        """PATCH /fractal/graphs/{graph_id}/status returns 401 without auth."""
        response = unauthenticated_client.patch(
            "/api/fractal/graphs/g-1/status",
            json={"status": "completed"},
        )
        assert response.status_code == 401

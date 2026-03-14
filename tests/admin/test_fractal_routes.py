"""Fractal graph explorer API route tests."""

from unittest.mock import AsyncMock, patch

import pytest


class TestFractalGraphList:
    def test_list_graphs_returns_paginated(self, client):
        with patch(
            "spellbook_mcp.admin.routes.fractal.query_fractal_db",
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
            "spellbook_mcp.admin.routes.fractal.query_fractal_db",
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
            "spellbook_mcp.admin.routes.fractal.query_fractal_db",
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
            "spellbook_mcp.admin.routes.fractal.query_fractal_db",
            new_callable=AsyncMock,
        ) as mock:
            mock.return_value = []
            response = client.get("/api/fractal/graphs/nonexistent")
            assert response.status_code == 404
            assert response.json()["error"]["code"] == "GRAPH_NOT_FOUND"


class TestFractalNodes:
    def test_get_nodes(self, client):
        with patch(
            "spellbook_mcp.admin.routes.fractal.query_fractal_db",
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
            "spellbook_mcp.admin.routes.fractal.query_fractal_db",
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
                    }
                ],
            ]
            response = client.get("/api/fractal/graphs/g-1/nodes?max_depth=0")
            assert response.status_code == 200

    def test_get_nodes_graph_not_found(self, client):
        with patch(
            "spellbook_mcp.admin.routes.fractal.query_fractal_db",
            new_callable=AsyncMock,
        ) as mock:
            mock.return_value = []
            response = client.get("/api/fractal/graphs/bad-id/nodes")
            assert response.status_code == 404


class TestFractalEdges:
    def test_get_edges(self, client):
        with patch(
            "spellbook_mcp.admin.routes.fractal.query_fractal_db",
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
            "spellbook_mcp.admin.routes.fractal.query_fractal_db",
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
                    },
                    {
                        "id": "n-2",
                        "node_type": "answer",
                        "text": "response",
                        "depth": 1,
                        "status": "open",
                        "parent_id": "n-1",
                        "owner": "agent-1",
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
            "spellbook_mcp.admin.routes.fractal.query_fractal_db",
            new_callable=AsyncMock,
        ) as mock:
            mock.return_value = []
            response = client.get("/api/fractal/graphs/bad-id/cytoscape")
            assert response.status_code == 404
            assert response.json()["error"]["code"] == "GRAPH_NOT_FOUND"

    def test_cytoscape_filters_edges_by_visible_nodes(self, client):
        """Edges to nodes outside depth filter should be excluded."""
        with patch(
            "spellbook_mcp.admin.routes.fractal.query_fractal_db",
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
            "spellbook_mcp.admin.routes.fractal.query_fractal_db",
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
            "spellbook_mcp.admin.routes.fractal.query_fractal_db",
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

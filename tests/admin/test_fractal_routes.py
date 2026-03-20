"""Fractal graph explorer API route tests (SQLAlchemy ORM)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _mock_graph(**overrides):
    """Create a mock FractalGraph ORM object with to_dict()."""
    # Separate non-model fields from dict output
    node_count = overrides.pop("node_count", 0)
    defaults = {
        "id": "g-1",
        "seed": "test topic",
        "intensity": "medium",
        "checkpoint_mode": "auto",
        "status": "active",
        "metadata": {},
        "project_dir": None,
        "created_at": "2026-03-14T10:00:00Z",
        "updated_at": "2026-03-14T10:00:00Z",
    }
    defaults.update(overrides)
    graph = MagicMock()
    graph.to_dict.return_value = dict(defaults)
    # Expose columns directly for ORM query access
    for k, v in defaults.items():
        setattr(graph, k, v)
    # node_count is a separate label added by the list query, not part of to_dict()
    graph.node_count = node_count
    return graph


def _mock_node(**overrides):
    """Create a mock FractalNode ORM object with to_dict()."""
    defaults = {
        "id": "n-1",
        "graph_id": "g-1",
        "parent_id": None,
        "node_type": "question",
        "text": "root question",
        "owner": None,
        "depth": 0,
        "status": "saturated",
        "metadata": {},
        "created_at": "2026-03-14T10:00:00Z",
        "claimed_at": None,
        "answered_at": None,
        "synthesized_at": None,
        "session_id": None,
    }
    defaults.update(overrides)
    node = MagicMock()
    node.to_dict.return_value = defaults
    for k, v in defaults.items():
        setattr(node, k, v)
    return node


def _mock_edge(**overrides):
    """Create a mock FractalEdge ORM object."""
    defaults = {
        "id": 1,
        "graph_id": "g-1",
        "from_node": "n-1",
        "to_node": "n-2",
        "edge_type": "parent_child",
        "metadata": {},
        "created_at": "2026-03-14T10:00:00Z",
    }
    defaults.update(overrides)
    edge = MagicMock()
    edge.to_dict.return_value = defaults
    for k, v in defaults.items():
        setattr(edge, k, v)
    return edge


def _mock_session_for_list(graphs, total):
    """Create a mock session for the list_graphs endpoint.

    list_graphs executes:
      1. A count query (select func.count())
      2. A data query (select FractalGraph with joins, filters, order, limit, offset)
    """
    mock_session = AsyncMock()

    count_result = MagicMock()
    count_result.scalar_one.return_value = total

    data_result = MagicMock()
    # The list query uses .all() which returns tuples of (graph, node_count)
    data_result.all.return_value = graphs

    mock_session.execute = AsyncMock(side_effect=[count_result, data_result])
    return mock_session


def _mock_session_for_detail(result_rows):
    """Create a mock session for single-result queries.

    Returns result_rows from scalars().first() or scalars().all()
    depending on usage.
    """
    mock_session = AsyncMock()
    result = MagicMock()
    if result_rows is None:
        result.scalars.return_value.first.return_value = None
    elif isinstance(result_rows, list):
        result.scalars.return_value.all.return_value = result_rows
        result.scalars.return_value.first.return_value = (
            result_rows[0] if result_rows else None
        )
    else:
        result.scalars.return_value.first.return_value = result_rows
    mock_session.execute = AsyncMock(return_value=result)
    return mock_session


def _override_fractal_db(client, mock_session):
    """Override the fractal_db FastAPI dependency to use a mock session."""
    from spellbook.db import fractal_db

    client.app.dependency_overrides[fractal_db] = lambda: mock_session
    return fractal_db


def _cleanup_overrides(client, dep):
    """Remove dependency override after test."""
    client.app.dependency_overrides.pop(dep, None)


class TestFractalGraphList:
    def test_list_graphs_returns_paginated(self, client):
        graph = _mock_graph(node_count=5)
        # List endpoint returns tuples of (graph_obj, node_count)
        mock_session = _mock_session_for_list(
            [(graph, 5)],
            total=1,
        )
        dep = _override_fractal_db(client, mock_session)
        try:
            response = client.get("/api/fractal/graphs")
            assert response.status_code == 200
            data = response.json()
            assert data == {
                "items": [
                    {
                        "id": "g-1",
                        "seed": "test topic",
                        "intensity": "medium",
                        "checkpoint_mode": "auto",
                        "status": "active",
                        "metadata": {},
                        "project_dir": None,
                        "created_at": "2026-03-14T10:00:00Z",
                        "updated_at": "2026-03-14T10:00:00Z",
                        "total_nodes": 5,
                    }
                ],
                "total": 1,
                "page": 1,
                "per_page": 50,
                "pages": 1,
            }
        finally:
            _cleanup_overrides(client, dep)

    def test_list_graphs_with_status_filter(self, client):
        mock_session = _mock_session_for_list([], total=0)
        dep = _override_fractal_db(client, mock_session)
        try:
            response = client.get("/api/fractal/graphs?status=completed")
            assert response.status_code == 200
            data = response.json()
            assert data == {
                "items": [],
                "total": 0,
                "page": 1,
                "per_page": 50,
                "pages": 1,
            }
            assert mock_session.execute.call_count == 2
        finally:
            _cleanup_overrides(client, dep)

    def test_list_graphs_with_search_filter(self, client):
        mock_session = _mock_session_for_list([], total=0)
        dep = _override_fractal_db(client, mock_session)
        try:
            response = client.get("/api/fractal/graphs?search=test")
            assert response.status_code == 200
            data = response.json()
            assert data == {
                "items": [],
                "total": 0,
                "page": 1,
                "per_page": 50,
                "pages": 1,
            }
            assert mock_session.execute.call_count == 2
        finally:
            _cleanup_overrides(client, dep)

    def test_list_graphs_with_project_dir_filter(self, client):
        mock_session = _mock_session_for_list([], total=0)
        dep = _override_fractal_db(client, mock_session)
        try:
            response = client.get("/api/fractal/graphs?project_dir=/home/user/proj")
            assert response.status_code == 200
            data = response.json()
            assert data == {
                "items": [],
                "total": 0,
                "page": 1,
                "per_page": 50,
                "pages": 1,
            }
            assert mock_session.execute.call_count == 2
        finally:
            _cleanup_overrides(client, dep)

    def test_list_graphs_pagination(self, client):
        mock_session = _mock_session_for_list([], total=75)
        dep = _override_fractal_db(client, mock_session)
        try:
            response = client.get("/api/fractal/graphs?page=2&per_page=25")
            assert response.status_code == 200
            data = response.json()
            assert data == {
                "items": [],
                "total": 75,
                "page": 2,
                "per_page": 25,
                "pages": 3,
            }
        finally:
            _cleanup_overrides(client, dep)

    def test_list_graphs_sort_by_seed_asc(self, client):
        mock_session = _mock_session_for_list([], total=0)
        dep = _override_fractal_db(client, mock_session)
        try:
            response = client.get(
                "/api/fractal/graphs?sort_by=seed&sort_order=asc"
            )
            assert response.status_code == 200
            data = response.json()
            assert data == {
                "items": [],
                "total": 0,
                "page": 1,
                "per_page": 50,
                "pages": 1,
            }
            assert mock_session.execute.call_count == 2
        finally:
            _cleanup_overrides(client, dep)

    def test_list_graphs_requires_auth(self, unauthenticated_client):
        response = unauthenticated_client.get("/api/fractal/graphs")
        assert response.status_code == 401


class TestFractalGraphDetail:
    def test_graph_detail_returns_full(self, client):
        graph = _mock_graph(
            metadata={"key": "value"},
            project_dir="/home/user/proj",
        )
        mock_session = AsyncMock()
        # Detail query: graph lookup then node count
        graph_result = MagicMock()
        graph_result.scalars.return_value.first.return_value = graph

        count_result = MagicMock()
        count_result.scalar_one.return_value = 5

        mock_session.execute = AsyncMock(
            side_effect=[graph_result, count_result]
        )
        dep = _override_fractal_db(client, mock_session)
        try:
            response = client.get("/api/fractal/graphs/g-1")
            assert response.status_code == 200
            data = response.json()
            assert data == {
                "id": "g-1",
                "seed": "test topic",
                "intensity": "medium",
                "checkpoint_mode": "auto",
                "status": "active",
                "metadata": {"key": "value"},
                "project_dir": "/home/user/proj",
                "created_at": "2026-03-14T10:00:00Z",
                "updated_at": "2026-03-14T10:00:00Z",
                "total_nodes": 5,
            }
        finally:
            _cleanup_overrides(client, dep)

    def test_graph_detail_404(self, client):
        mock_session = _mock_session_for_detail(None)
        dep = _override_fractal_db(client, mock_session)
        try:
            response = client.get("/api/fractal/graphs/nonexistent")
            assert response.status_code == 404
            assert response.json() == {
                "error": {
                    "code": "GRAPH_NOT_FOUND",
                    "message": "Graph 'nonexistent' not found",
                }
            }
        finally:
            _cleanup_overrides(client, dep)


class TestFractalNodes:
    def test_get_nodes(self, client):
        node = _mock_node()
        mock_session = AsyncMock()

        # First call: graph exists check
        graph_result = MagicMock()
        graph_result.scalars.return_value.first.return_value = _mock_graph()

        # Second call: nodes query
        nodes_result = MagicMock()
        nodes_result.scalars.return_value.all.return_value = [node]

        mock_session.execute = AsyncMock(
            side_effect=[graph_result, nodes_result]
        )
        dep = _override_fractal_db(client, mock_session)
        try:
            response = client.get("/api/fractal/graphs/g-1/nodes")
            assert response.status_code == 200
            data = response.json()
            assert data == {
                "nodes": [
                    {
                        "id": "n-1",
                        "graph_id": "g-1",
                        "parent_id": None,
                        "node_type": "question",
                        "text": "root question",
                        "owner": None,
                        "depth": 0,
                        "status": "saturated",
                        "metadata": {},
                        "created_at": "2026-03-14T10:00:00Z",
                        "claimed_at": None,
                        "answered_at": None,
                        "synthesized_at": None,
                        "session_id": None,
                    }
                ],
                "count": 1,
            }
        finally:
            _cleanup_overrides(client, dep)

    def test_get_nodes_with_depth_filter(self, client):
        node = _mock_node()
        mock_session = AsyncMock()

        graph_result = MagicMock()
        graph_result.scalars.return_value.first.return_value = _mock_graph()

        nodes_result = MagicMock()
        nodes_result.scalars.return_value.all.return_value = [node]

        mock_session.execute = AsyncMock(
            side_effect=[graph_result, nodes_result]
        )
        dep = _override_fractal_db(client, mock_session)
        try:
            response = client.get("/api/fractal/graphs/g-1/nodes?max_depth=0")
            assert response.status_code == 200
            data = response.json()
            assert data["count"] == 1
            assert data["nodes"][0]["id"] == "n-1"
        finally:
            _cleanup_overrides(client, dep)

    def test_get_nodes_graph_not_found(self, client):
        mock_session = _mock_session_for_detail(None)
        dep = _override_fractal_db(client, mock_session)
        try:
            response = client.get("/api/fractal/graphs/bad-id/nodes")
            assert response.status_code == 404
            assert response.json() == {
                "error": {
                    "code": "GRAPH_NOT_FOUND",
                    "message": "Graph 'bad-id' not found",
                }
            }
        finally:
            _cleanup_overrides(client, dep)


class TestFractalEdges:
    def test_get_edges(self, client):
        edge = _mock_edge()
        mock_session = AsyncMock()

        graph_result = MagicMock()
        graph_result.scalars.return_value.first.return_value = _mock_graph()

        edges_result = MagicMock()
        edges_result.scalars.return_value.all.return_value = [edge]

        mock_session.execute = AsyncMock(
            side_effect=[graph_result, edges_result]
        )
        dep = _override_fractal_db(client, mock_session)
        try:
            response = client.get("/api/fractal/graphs/g-1/edges")
            assert response.status_code == 200
            data = response.json()
            assert data == {
                "edges": [
                    {
                        "id": 1,
                        "graph_id": "g-1",
                        "from_node": "n-1",
                        "to_node": "n-2",
                        "edge_type": "parent_child",
                        "metadata": {},
                        "created_at": "2026-03-14T10:00:00Z",
                    }
                ],
                "count": 1,
            }
        finally:
            _cleanup_overrides(client, dep)


class TestFractalCytoscape:
    def test_cytoscape_returns_elements(self, client):
        node1 = _mock_node(
            id="n-1",
            node_type="question",
            text="root",
            depth=0,
            status="saturated",
        )
        node2 = _mock_node(
            id="n-2",
            node_type="answer",
            text="response",
            depth=1,
            status="open",
            parent_id="n-1",
            owner="agent-1",
        )
        edge = _mock_edge(
            from_node="n-1",
            to_node="n-2",
            edge_type="parent_child",
        )

        mock_session = AsyncMock()

        graph_result = MagicMock()
        graph_result.scalars.return_value.first.return_value = _mock_graph()

        nodes_result = MagicMock()
        nodes_result.scalars.return_value.all.return_value = [node1, node2]

        edges_result = MagicMock()
        edges_result.scalars.return_value.all.return_value = [edge]

        mock_session.execute = AsyncMock(
            side_effect=[graph_result, nodes_result, edges_result]
        )
        dep = _override_fractal_db(client, mock_session)
        try:
            response = client.get("/api/fractal/graphs/g-1/cytoscape")
            assert response.status_code == 200
            data = response.json()

            assert data == {
                "elements": {
                    "nodes": [
                        {
                            "data": {
                                "id": "n-1",
                                "label": "root",
                                "text": "root",
                                "type": "question",
                                "status": "saturated",
                                "depth": 0,
                                "parent_id": None,
                                "owner": None,
                                "session_id": None,
                                "claimed_at": None,
                                "answered_at": None,
                                "synthesized_at": None,
                            },
                            "classes": "question saturated",
                        },
                        {
                            "data": {
                                "id": "n-2",
                                "label": "response",
                                "text": "response",
                                "type": "answer",
                                "status": "open",
                                "depth": 1,
                                "parent_id": "n-1",
                                "owner": "agent-1",
                                "session_id": None,
                                "claimed_at": None,
                                "answered_at": None,
                                "synthesized_at": None,
                            },
                            "classes": "answer open",
                        },
                    ],
                    "edges": [
                        {
                            "data": {
                                "source": "n-1",
                                "target": "n-2",
                                "type": "parent_child",
                            },
                            "classes": "parent_child",
                        }
                    ],
                },
                "stats": {
                    "total_nodes": 2,
                    "saturated": 1,
                    "pending": 1,
                    "max_depth": 1,
                    "convergences": 0,
                    "contradictions": 0,
                },
            }
        finally:
            _cleanup_overrides(client, dep)

    def test_cytoscape_graph_not_found(self, client):
        mock_session = _mock_session_for_detail(None)
        dep = _override_fractal_db(client, mock_session)
        try:
            response = client.get("/api/fractal/graphs/bad-id/cytoscape")
            assert response.status_code == 404
            assert response.json() == {
                "error": {
                    "code": "GRAPH_NOT_FOUND",
                    "message": "Graph 'bad-id' not found",
                }
            }
        finally:
            _cleanup_overrides(client, dep)

    def test_cytoscape_filters_edges_by_visible_nodes(self, client):
        """Edges to nodes outside depth filter should be excluded."""
        node1 = _mock_node(
            id="n-1",
            node_type="question",
            text="root",
            depth=0,
            status="open",
        )
        # Edge points to n-2 which is NOT in node set
        edge = _mock_edge(
            from_node="n-1",
            to_node="n-2",
            edge_type="parent_child",
        )

        mock_session = AsyncMock()

        graph_result = MagicMock()
        graph_result.scalars.return_value.first.return_value = _mock_graph()

        nodes_result = MagicMock()
        nodes_result.scalars.return_value.all.return_value = [node1]

        edges_result = MagicMock()
        edges_result.scalars.return_value.all.return_value = [edge]

        mock_session.execute = AsyncMock(
            side_effect=[graph_result, nodes_result, edges_result]
        )
        dep = _override_fractal_db(client, mock_session)
        try:
            response = client.get(
                "/api/fractal/graphs/g-1/cytoscape?max_depth=0"
            )
            assert response.status_code == 200
            data = response.json()
            # Edge should be filtered out since n-2 is not visible
            assert data["elements"]["edges"] == []
            assert len(data["elements"]["nodes"]) == 1
        finally:
            _cleanup_overrides(client, dep)


class TestFractalConvergence:
    def test_convergence(self, client):
        edge = _mock_edge(
            from_node="n-1",
            to_node="n-2",
            edge_type="convergence",
        )
        node1 = _mock_node(
            id="n-1",
            text="insight A",
            depth=1,
        )
        node2 = _mock_node(
            id="n-2",
            text="insight B",
            depth=2,
        )

        mock_session = AsyncMock()

        graph_result = MagicMock()
        graph_result.scalars.return_value.first.return_value = _mock_graph()

        # The convergence query joins edges with nodes
        # Returns tuples of (edge, from_text, from_depth, to_text, to_depth)
        conv_result = MagicMock()
        conv_result.all.return_value = [
            (edge, "insight A", 1, "insight B", 2),
        ]

        mock_session.execute = AsyncMock(
            side_effect=[graph_result, conv_result]
        )
        dep = _override_fractal_db(client, mock_session)
        try:
            response = client.get("/api/fractal/graphs/g-1/convergence")
            assert response.status_code == 200
            data = response.json()
            assert data == {
                "clusters": [
                    {
                        "nodes": [
                            {
                                "node_id": "n-1",
                                "text": "insight A",
                                "depth": 1,
                            },
                            {
                                "node_id": "n-2",
                                "text": "insight B",
                                "depth": 2,
                            },
                        ],
                        "insight": "",
                        "edge_count": 1,
                    }
                ],
                "count": 1,
            }
        finally:
            _cleanup_overrides(client, dep)


class TestFractalContradictions:
    def test_contradictions(self, client):
        edge = _mock_edge(
            from_node="n-1",
            to_node="n-2",
            edge_type="contradiction",
        )

        mock_session = AsyncMock()

        graph_result = MagicMock()
        graph_result.scalars.return_value.first.return_value = _mock_graph()

        # Returns tuples of (edge, from_text, to_text)
        contra_result = MagicMock()
        contra_result.all.return_value = [
            (edge, "claim A", "claim B"),
        ]

        mock_session.execute = AsyncMock(
            side_effect=[graph_result, contra_result]
        )
        dep = _override_fractal_db(client, mock_session)
        try:
            response = client.get("/api/fractal/graphs/g-1/contradictions")
            assert response.status_code == 200
            data = response.json()
            assert data == {
                "pairs": [
                    {
                        "node_a": {"node_id": "n-1", "text": "claim A"},
                        "node_b": {"node_id": "n-2", "text": "claim B"},
                        "tension": "",
                    }
                ],
                "count": 1,
            }
        finally:
            _cleanup_overrides(client, dep)


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

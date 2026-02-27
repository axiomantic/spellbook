"""Tests for fractal thinking node operations.

Tests for add_node, update_node, and mark_saturated.
"""

import json

import pytest


@pytest.fixture
def graph_with_root(fractal_db):
    """Create a graph with a root question node for testing.

    Returns a dict with graph_id, root_node_id, and db_path.
    """
    from spellbook_mcp.fractal.graph_ops import create_graph

    result = create_graph(
        seed="Why is the sky blue?",
        intensity="pulse",
        checkpoint_mode="autonomous",
        db_path=fractal_db,
    )
    return {
        "graph_id": result["graph_id"],
        "root_node_id": result["root_node_id"],
        "db_path": fractal_db,
    }


class TestAddNode:
    """Tests for add_node function."""

    def test_add_question_node_returns_correct_shape(self, graph_with_root):
        """add_node must return dict with node_id, graph_id, parent_id, depth, node_type, status."""
        from spellbook_mcp.fractal.node_ops import add_node

        result = add_node(
            graph_id=graph_with_root["graph_id"],
            parent_id=graph_with_root["root_node_id"],
            node_type="question",
            text="What wavelengths does nitrogen scatter?",
            db_path=graph_with_root["db_path"],
        )

        assert "node_id" in result
        assert result["graph_id"] == graph_with_root["graph_id"]
        assert result["parent_id"] == graph_with_root["root_node_id"]
        assert result["node_type"] == "question"
        assert result["status"] == "open"

    def test_add_question_node_depth_calculation(self, graph_with_root):
        """add_node must calculate depth = parent.depth + 1."""
        from spellbook_mcp.fractal.node_ops import add_node

        # Root node is depth 0, so child should be depth 1
        result = add_node(
            graph_id=graph_with_root["graph_id"],
            parent_id=graph_with_root["root_node_id"],
            node_type="question",
            text="Sub-question at depth 1",
            db_path=graph_with_root["db_path"],
        )

        assert result["depth"] == 1

    def test_add_node_depth_cascades(self, fractal_db):
        """add_node at depth 1 parent must produce depth 2 child."""
        from spellbook_mcp.fractal.graph_ops import create_graph
        from spellbook_mcp.fractal.node_ops import add_node

        # Use explore intensity (max_depth=4) to allow deeper nesting
        result = create_graph(
            seed="Deep test",
            intensity="explore",
            checkpoint_mode="autonomous",
            db_path=fractal_db,
        )
        graph_id = result["graph_id"]
        root_id = result["root_node_id"]

        # Create depth-1 node
        depth1 = add_node(
            graph_id=graph_id,
            parent_id=root_id,
            node_type="question",
            text="Depth 1 question",
            db_path=fractal_db,
        )

        # Create depth-2 node
        depth2 = add_node(
            graph_id=graph_id,
            parent_id=depth1["node_id"],
            node_type="question",
            text="Depth 2 question",
            db_path=fractal_db,
        )

        assert depth2["depth"] == 2

    def test_add_answer_node(self, graph_with_root):
        """add_node must accept answer node type."""
        from spellbook_mcp.fractal.node_ops import add_node

        result = add_node(
            graph_id=graph_with_root["graph_id"],
            parent_id=graph_with_root["root_node_id"],
            node_type="answer",
            text="Because of Rayleigh scattering",
            db_path=graph_with_root["db_path"],
        )

        assert result["node_type"] == "answer"
        assert result["status"] == "open"

    def test_add_answer_auto_transitions_parent_question(self, graph_with_root):
        """Adding answer to open question must transition parent to answered."""
        from spellbook_mcp.fractal.node_ops import add_node
        from spellbook_mcp.fractal.schema import get_fractal_connection

        add_node(
            graph_id=graph_with_root["graph_id"],
            parent_id=graph_with_root["root_node_id"],
            node_type="answer",
            text="Because of Rayleigh scattering",
            db_path=graph_with_root["db_path"],
        )

        # Verify parent node status changed
        conn = get_fractal_connection(graph_with_root["db_path"])
        cursor = conn.cursor()
        cursor.execute(
            "SELECT status FROM nodes WHERE id = ?",
            (graph_with_root["root_node_id"],),
        )
        parent_status = cursor.fetchone()[0]
        assert parent_status == "answered"

    def test_add_answer_does_not_transition_non_question_parent(self, fractal_db):
        """Adding answer to answer parent must NOT transition parent status."""
        from spellbook_mcp.fractal.graph_ops import create_graph
        from spellbook_mcp.fractal.node_ops import add_node
        from spellbook_mcp.fractal.schema import get_fractal_connection

        # Use explore intensity (max_depth=4) since this test needs depth 2
        graph = create_graph(
            seed="Test", intensity="explore",
            checkpoint_mode="autonomous", db_path=fractal_db,
        )

        # First add an answer to root
        answer1 = add_node(
            graph_id=graph["graph_id"],
            parent_id=graph["root_node_id"],
            node_type="answer",
            text="First answer",
            db_path=fractal_db,
        )

        # Add another answer as child of the first answer (depth 2)
        add_node(
            graph_id=graph["graph_id"],
            parent_id=answer1["node_id"],
            node_type="answer",
            text="Child of answer",
            db_path=fractal_db,
        )

        # First answer should still be "open" (not "answered" since it's an answer node)
        conn = get_fractal_connection(fractal_db)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT status FROM nodes WHERE id = ?",
            (answer1["node_id"],),
        )
        answer_status = cursor.fetchone()[0]
        assert answer_status == "open"

    def test_add_node_creates_parent_child_edge(self, graph_with_root):
        """add_node with parent_id must create parent_child edge."""
        from spellbook_mcp.fractal.node_ops import add_node
        from spellbook_mcp.fractal.schema import get_fractal_connection

        result = add_node(
            graph_id=graph_with_root["graph_id"],
            parent_id=graph_with_root["root_node_id"],
            node_type="question",
            text="Sub-question",
            db_path=graph_with_root["db_path"],
        )

        conn = get_fractal_connection(graph_with_root["db_path"])
        cursor = conn.cursor()
        cursor.execute(
            "SELECT from_node, to_node, edge_type FROM edges "
            "WHERE graph_id = ? AND from_node = ? AND to_node = ?",
            (
                graph_with_root["graph_id"],
                graph_with_root["root_node_id"],
                result["node_id"],
            ),
        )
        edge = cursor.fetchone()
        assert edge is not None
        assert edge[2] == "parent_child"

    def test_add_node_with_owner(self, graph_with_root):
        """add_node must store owner when provided."""
        from spellbook_mcp.fractal.node_ops import add_node
        from spellbook_mcp.fractal.schema import get_fractal_connection

        result = add_node(
            graph_id=graph_with_root["graph_id"],
            parent_id=graph_with_root["root_node_id"],
            node_type="question",
            text="Owned question",
            owner="agent-007",
            db_path=graph_with_root["db_path"],
        )

        conn = get_fractal_connection(graph_with_root["db_path"])
        cursor = conn.cursor()
        cursor.execute(
            "SELECT owner FROM nodes WHERE id = ?",
            (result["node_id"],),
        )
        assert cursor.fetchone()[0] == "agent-007"

    def test_add_node_with_metadata(self, graph_with_root):
        """add_node must store metadata_json when provided."""
        from spellbook_mcp.fractal.node_ops import add_node
        from spellbook_mcp.fractal.schema import get_fractal_connection

        metadata = json.dumps({"priority": "high", "source": "decomposition"})

        result = add_node(
            graph_id=graph_with_root["graph_id"],
            parent_id=graph_with_root["root_node_id"],
            node_type="question",
            text="Question with metadata",
            metadata_json=metadata,
            db_path=graph_with_root["db_path"],
        )

        conn = get_fractal_connection(graph_with_root["db_path"])
        cursor = conn.cursor()
        cursor.execute(
            "SELECT metadata_json FROM nodes WHERE id = ?",
            (result["node_id"],),
        )
        stored = json.loads(cursor.fetchone()[0])
        assert stored["priority"] == "high"
        assert stored["source"] == "decomposition"

    def test_add_node_invalid_graph_rejected(self, fractal_db):
        """add_node with nonexistent graph_id must raise ValueError."""
        from spellbook_mcp.fractal.node_ops import add_node

        with pytest.raises(ValueError, match="[Gg]raph"):
            add_node(
                graph_id="nonexistent-graph-id",
                parent_id=None,
                node_type="question",
                text="Orphan question",
                db_path=fractal_db,
            )

    def test_add_node_invalid_node_type_rejected(self, graph_with_root):
        """add_node with invalid node_type must raise ValueError."""
        from spellbook_mcp.fractal.node_ops import add_node

        with pytest.raises(ValueError, match="[Nn]ode.type"):
            add_node(
                graph_id=graph_with_root["graph_id"],
                parent_id=graph_with_root["root_node_id"],
                node_type="invalid_type",
                text="Bad type",
                db_path=graph_with_root["db_path"],
            )

    def test_add_node_parent_not_found_rejected(self, graph_with_root):
        """add_node with nonexistent parent_id must raise ValueError."""
        from spellbook_mcp.fractal.node_ops import add_node

        with pytest.raises(ValueError, match="[Pp]arent"):
            add_node(
                graph_id=graph_with_root["graph_id"],
                parent_id="nonexistent-parent-id",
                node_type="question",
                text="Orphan question",
                db_path=graph_with_root["db_path"],
            )

    def test_add_node_no_parent_depth_zero(self, graph_with_root):
        """add_node without parent_id must have depth 0."""
        from spellbook_mcp.fractal.node_ops import add_node

        result = add_node(
            graph_id=graph_with_root["graph_id"],
            parent_id=None,
            node_type="question",
            text="Root-level question",
            db_path=graph_with_root["db_path"],
        )

        assert result["depth"] == 0

    def test_add_node_generates_uuid(self, graph_with_root):
        """add_node must generate a valid UUID for node_id."""
        import uuid

        from spellbook_mcp.fractal.node_ops import add_node

        result = add_node(
            graph_id=graph_with_root["graph_id"],
            parent_id=graph_with_root["root_node_id"],
            node_type="question",
            text="UUID test",
            db_path=graph_with_root["db_path"],
        )

        # Should not raise
        uuid.UUID(result["node_id"])

    def test_add_node_persisted_to_db(self, graph_with_root):
        """add_node must persist the node to the database."""
        from spellbook_mcp.fractal.node_ops import add_node
        from spellbook_mcp.fractal.schema import get_fractal_connection

        result = add_node(
            graph_id=graph_with_root["graph_id"],
            parent_id=graph_with_root["root_node_id"],
            node_type="question",
            text="Persisted question",
            db_path=graph_with_root["db_path"],
        )

        conn = get_fractal_connection(graph_with_root["db_path"])
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, graph_id, node_type, text, depth, status FROM nodes WHERE id = ?",
            (result["node_id"],),
        )
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == result["node_id"]
        assert row[1] == graph_with_root["graph_id"]
        assert row[2] == "question"
        assert row[3] == "Persisted question"
        assert row[4] == 1
        assert row[5] == "open"

    def test_add_node_exceeds_depth_budget(self, graph_with_root):
        """add_node should reject nodes that would exceed the intensity's max_depth."""
        from spellbook_mcp.fractal.node_ops import add_node

        # graph_with_root creates a pulse-intensity graph (max_depth=2)
        # Root is depth 0. Add child at depth 1 (allowed).
        child = add_node(
            graph_id=graph_with_root["graph_id"],
            parent_id=graph_with_root["root_node_id"],
            node_type="question",
            text="Child question",
            db_path=graph_with_root["db_path"],
        )

        # Add grandchild at depth 2 (should be rejected for pulse, max_depth=2)
        with pytest.raises(ValueError, match="exceed max_depth"):
            add_node(
                graph_id=graph_with_root["graph_id"],
                parent_id=child["node_id"],
                node_type="question",
                text="Too deep",
                db_path=graph_with_root["db_path"],
            )

    def test_add_node_at_max_allowed_depth(self, graph_with_root):
        """Nodes at depth max_depth-1 should be allowed."""
        from spellbook_mcp.fractal.node_ops import add_node

        # pulse max_depth=2, so depth 1 should work
        result = add_node(
            graph_id=graph_with_root["graph_id"],
            parent_id=graph_with_root["root_node_id"],
            node_type="question",
            text="Depth 1 ok",
            db_path=graph_with_root["db_path"],
        )

        assert result["depth"] == 1
        assert "node_id" in result

    def test_add_node_to_non_active_graph(self, fractal_db):
        """add_node should reject adding nodes to non-active graphs."""
        from spellbook_mcp.fractal.graph_ops import create_graph, update_graph_status
        from spellbook_mcp.fractal.node_ops import add_node

        result = create_graph(
            seed="Test",
            intensity="pulse",
            checkpoint_mode="autonomous",
            db_path=fractal_db,
        )
        graph_id = result["graph_id"]
        root_id = result["root_node_id"]

        # Complete the graph
        update_graph_status(graph_id, "completed", db_path=fractal_db)

        # Try to add a node
        with pytest.raises(ValueError, match="must be 'active'"):
            add_node(
                graph_id=graph_id,
                parent_id=root_id,
                node_type="answer",
                text="Should fail",
                db_path=fractal_db,
            )

    def test_add_node_to_paused_graph(self, fractal_db):
        """add_node should reject adding nodes to paused graphs."""
        from spellbook_mcp.fractal.graph_ops import create_graph, update_graph_status
        from spellbook_mcp.fractal.node_ops import add_node

        result = create_graph(
            seed="Test",
            intensity="pulse",
            checkpoint_mode="autonomous",
            db_path=fractal_db,
        )
        graph_id = result["graph_id"]
        root_id = result["root_node_id"]

        update_graph_status(graph_id, "paused", db_path=fractal_db)

        with pytest.raises(ValueError, match="must be 'active'"):
            add_node(
                graph_id=graph_id,
                parent_id=root_id,
                node_type="answer",
                text="Should fail",
                db_path=fractal_db,
            )


class TestUpdateNode:
    """Tests for update_node function."""

    def test_update_node_merges_metadata(self, graph_with_root):
        """update_node must merge new metadata into existing, not replace."""
        from spellbook_mcp.fractal.node_ops import add_node, update_node
        from spellbook_mcp.fractal.schema import get_fractal_connection

        # Create node with initial metadata
        initial_meta = json.dumps({"priority": "high"})
        node = add_node(
            graph_id=graph_with_root["graph_id"],
            parent_id=graph_with_root["root_node_id"],
            node_type="question",
            text="Metadata merge test",
            metadata_json=initial_meta,
            db_path=graph_with_root["db_path"],
        )

        # Update with additional metadata
        new_meta = json.dumps({"source": "decomposition", "confidence": 0.9})
        result = update_node(
            graph_id=graph_with_root["graph_id"],
            node_id=node["node_id"],
            metadata_json=new_meta,
            db_path=graph_with_root["db_path"],
        )

        # Both old and new keys must be present
        assert result["metadata"]["priority"] == "high"
        assert result["metadata"]["source"] == "decomposition"
        assert result["metadata"]["confidence"] == 0.9

    def test_update_node_metadata_overwrite_key(self, graph_with_root):
        """update_node must overwrite existing key when same key provided."""
        from spellbook_mcp.fractal.node_ops import add_node, update_node

        initial_meta = json.dumps({"priority": "high"})
        node = add_node(
            graph_id=graph_with_root["graph_id"],
            parent_id=graph_with_root["root_node_id"],
            node_type="question",
            text="Overwrite test",
            metadata_json=initial_meta,
            db_path=graph_with_root["db_path"],
        )

        new_meta = json.dumps({"priority": "low"})
        result = update_node(
            graph_id=graph_with_root["graph_id"],
            node_id=node["node_id"],
            metadata_json=new_meta,
            db_path=graph_with_root["db_path"],
        )

        assert result["metadata"]["priority"] == "low"

    def test_update_node_returns_correct_shape(self, graph_with_root):
        """update_node must return dict with node_id, metadata, edges_created."""
        from spellbook_mcp.fractal.node_ops import add_node, update_node

        node = add_node(
            graph_id=graph_with_root["graph_id"],
            parent_id=graph_with_root["root_node_id"],
            node_type="question",
            text="Shape test",
            db_path=graph_with_root["db_path"],
        )

        result = update_node(
            graph_id=graph_with_root["graph_id"],
            node_id=node["node_id"],
            metadata_json=json.dumps({"key": "value"}),
            db_path=graph_with_root["db_path"],
        )

        assert "node_id" in result
        assert "metadata" in result
        assert "edges_created" in result
        assert result["node_id"] == node["node_id"]

    def test_update_node_convergence_edge_creation(self, graph_with_root):
        """update_node with convergence_with must create convergence edges."""
        from spellbook_mcp.fractal.node_ops import add_node, update_node
        from spellbook_mcp.fractal.schema import get_fractal_connection

        # Create two sibling nodes
        node_a = add_node(
            graph_id=graph_with_root["graph_id"],
            parent_id=graph_with_root["root_node_id"],
            node_type="question",
            text="Node A",
            db_path=graph_with_root["db_path"],
        )
        node_b = add_node(
            graph_id=graph_with_root["graph_id"],
            parent_id=graph_with_root["root_node_id"],
            node_type="question",
            text="Node B",
            db_path=graph_with_root["db_path"],
        )

        # Update node_a with convergence_with pointing to node_b
        meta = json.dumps({"convergence_with": [node_b["node_id"]]})
        result = update_node(
            graph_id=graph_with_root["graph_id"],
            node_id=node_a["node_id"],
            metadata_json=meta,
            db_path=graph_with_root["db_path"],
        )

        # Verify edge created
        conn = get_fractal_connection(graph_with_root["db_path"])
        cursor = conn.cursor()
        cursor.execute(
            "SELECT from_node, to_node, edge_type FROM edges "
            "WHERE graph_id = ? AND edge_type = 'convergence'",
            (graph_with_root["graph_id"],),
        )
        edge = cursor.fetchone()
        assert edge is not None
        assert edge[0] == node_a["node_id"]
        assert edge[1] == node_b["node_id"]
        assert result["edges_created"] == 1

    def test_update_node_contradiction_edge_creation(self, graph_with_root):
        """update_node with contradiction_with must create contradiction edges."""
        from spellbook_mcp.fractal.node_ops import add_node, update_node
        from spellbook_mcp.fractal.schema import get_fractal_connection

        node_a = add_node(
            graph_id=graph_with_root["graph_id"],
            parent_id=graph_with_root["root_node_id"],
            node_type="answer",
            text="Answer A",
            db_path=graph_with_root["db_path"],
        )
        node_b = add_node(
            graph_id=graph_with_root["graph_id"],
            parent_id=graph_with_root["root_node_id"],
            node_type="answer",
            text="Contradicting answer B",
            db_path=graph_with_root["db_path"],
        )

        meta = json.dumps({"contradiction_with": [node_b["node_id"]]})
        result = update_node(
            graph_id=graph_with_root["graph_id"],
            node_id=node_a["node_id"],
            metadata_json=meta,
            db_path=graph_with_root["db_path"],
        )

        conn = get_fractal_connection(graph_with_root["db_path"])
        cursor = conn.cursor()
        cursor.execute(
            "SELECT from_node, to_node, edge_type FROM edges "
            "WHERE graph_id = ? AND edge_type = 'contradiction'",
            (graph_with_root["graph_id"],),
        )
        edge = cursor.fetchone()
        assert edge is not None
        assert edge[0] == node_a["node_id"]
        assert edge[1] == node_b["node_id"]
        assert result["edges_created"] == 1

    def test_update_node_multiple_convergence_targets(self, graph_with_root):
        """update_node with multiple convergence_with targets must create multiple edges."""
        from spellbook_mcp.fractal.node_ops import add_node, update_node

        node_a = add_node(
            graph_id=graph_with_root["graph_id"],
            parent_id=graph_with_root["root_node_id"],
            node_type="question",
            text="Node A",
            db_path=graph_with_root["db_path"],
        )
        node_b = add_node(
            graph_id=graph_with_root["graph_id"],
            parent_id=graph_with_root["root_node_id"],
            node_type="question",
            text="Node B",
            db_path=graph_with_root["db_path"],
        )
        node_c = add_node(
            graph_id=graph_with_root["graph_id"],
            parent_id=graph_with_root["root_node_id"],
            node_type="question",
            text="Node C",
            db_path=graph_with_root["db_path"],
        )

        meta = json.dumps({
            "convergence_with": [node_b["node_id"], node_c["node_id"]]
        })
        result = update_node(
            graph_id=graph_with_root["graph_id"],
            node_id=node_a["node_id"],
            metadata_json=meta,
            db_path=graph_with_root["db_path"],
        )

        assert result["edges_created"] == 2

    def test_update_node_invalid_convergence_target_rejected(self, graph_with_root):
        """update_node with nonexistent convergence target must raise ValueError."""
        from spellbook_mcp.fractal.node_ops import add_node, update_node

        node_a = add_node(
            graph_id=graph_with_root["graph_id"],
            parent_id=graph_with_root["root_node_id"],
            node_type="question",
            text="Node A",
            db_path=graph_with_root["db_path"],
        )

        meta = json.dumps({"convergence_with": ["nonexistent-node-id"]})

        with pytest.raises(ValueError, match="[Nn]ode"):
            update_node(
                graph_id=graph_with_root["graph_id"],
                node_id=node_a["node_id"],
                metadata_json=meta,
                db_path=graph_with_root["db_path"],
            )

    def test_update_node_invalid_contradiction_target_rejected(self, graph_with_root):
        """update_node with nonexistent contradiction target must raise ValueError."""
        from spellbook_mcp.fractal.node_ops import add_node, update_node

        node_a = add_node(
            graph_id=graph_with_root["graph_id"],
            parent_id=graph_with_root["root_node_id"],
            node_type="question",
            text="Node A",
            db_path=graph_with_root["db_path"],
        )

        meta = json.dumps({"contradiction_with": ["nonexistent-node-id"]})

        with pytest.raises(ValueError, match="[Nn]ode"):
            update_node(
                graph_id=graph_with_root["graph_id"],
                node_id=node_a["node_id"],
                metadata_json=meta,
                db_path=graph_with_root["db_path"],
            )

    def test_update_node_no_edges_returns_zero(self, graph_with_root):
        """update_node without edge-creating metadata must return edges_created=0."""
        from spellbook_mcp.fractal.node_ops import add_node, update_node

        node = add_node(
            graph_id=graph_with_root["graph_id"],
            parent_id=graph_with_root["root_node_id"],
            node_type="question",
            text="Simple update",
            db_path=graph_with_root["db_path"],
        )

        result = update_node(
            graph_id=graph_with_root["graph_id"],
            node_id=node["node_id"],
            metadata_json=json.dumps({"note": "just a note"}),
            db_path=graph_with_root["db_path"],
        )

        assert result["edges_created"] == 0

    def test_update_node_invalid_graph_rejected(self, graph_with_root):
        """update_node with nonexistent graph_id must raise ValueError."""
        from spellbook_mcp.fractal.node_ops import add_node, update_node

        node = add_node(
            graph_id=graph_with_root["graph_id"],
            parent_id=graph_with_root["root_node_id"],
            node_type="question",
            text="Test",
            db_path=graph_with_root["db_path"],
        )

        with pytest.raises(ValueError, match="[Gg]raph"):
            update_node(
                graph_id="nonexistent-graph",
                node_id=node["node_id"],
                metadata_json=json.dumps({"key": "val"}),
                db_path=graph_with_root["db_path"],
            )

    def test_update_node_invalid_node_rejected(self, graph_with_root):
        """update_node with nonexistent node_id must raise ValueError."""
        from spellbook_mcp.fractal.node_ops import update_node

        with pytest.raises(ValueError, match="[Nn]ode"):
            update_node(
                graph_id=graph_with_root["graph_id"],
                node_id="nonexistent-node",
                metadata_json=json.dumps({"key": "val"}),
                db_path=graph_with_root["db_path"],
            )

    def test_update_node_metadata_persisted(self, graph_with_root):
        """update_node must persist merged metadata to the database."""
        from spellbook_mcp.fractal.node_ops import add_node, update_node
        from spellbook_mcp.fractal.schema import get_fractal_connection

        node = add_node(
            graph_id=graph_with_root["graph_id"],
            parent_id=graph_with_root["root_node_id"],
            node_type="question",
            text="Persist test",
            metadata_json=json.dumps({"old_key": "old_val"}),
            db_path=graph_with_root["db_path"],
        )

        update_node(
            graph_id=graph_with_root["graph_id"],
            node_id=node["node_id"],
            metadata_json=json.dumps({"new_key": "new_val"}),
            db_path=graph_with_root["db_path"],
        )

        conn = get_fractal_connection(graph_with_root["db_path"])
        cursor = conn.cursor()
        cursor.execute(
            "SELECT metadata_json FROM nodes WHERE id = ?",
            (node["node_id"],),
        )
        stored = json.loads(cursor.fetchone()[0])
        assert stored["old_key"] == "old_val"
        assert stored["new_key"] == "new_val"


class TestMarkSaturated:
    """Tests for mark_saturated function."""

    def test_mark_saturated_from_open(self, graph_with_root):
        """mark_saturated must transition open node to saturated."""
        from spellbook_mcp.fractal.node_ops import add_node, mark_saturated

        node = add_node(
            graph_id=graph_with_root["graph_id"],
            parent_id=graph_with_root["root_node_id"],
            node_type="question",
            text="Saturable question",
            db_path=graph_with_root["db_path"],
        )

        result = mark_saturated(
            graph_id=graph_with_root["graph_id"],
            node_id=node["node_id"],
            reason="semantic_overlap",
            db_path=graph_with_root["db_path"],
        )

        assert result["node_id"] == node["node_id"]
        assert result["status"] == "saturated"
        assert result["reason"] == "semantic_overlap"

    def test_mark_saturated_from_answered(self, graph_with_root):
        """mark_saturated must transition answered node to saturated."""
        from spellbook_mcp.fractal.node_ops import add_node, mark_saturated
        from spellbook_mcp.fractal.schema import get_fractal_connection

        # Add answer to root to transition root to "answered"
        # Root is at depth 0, answer will be at depth 1 (within pulse max_depth=2)
        add_node(
            graph_id=graph_with_root["graph_id"],
            parent_id=graph_with_root["root_node_id"],
            node_type="answer",
            text="An answer to root",
            db_path=graph_with_root["db_path"],
        )

        # Verify root is answered
        conn = get_fractal_connection(graph_with_root["db_path"])
        cursor = conn.cursor()
        cursor.execute(
            "SELECT status FROM nodes WHERE id = ?",
            (graph_with_root["root_node_id"],),
        )
        assert cursor.fetchone()[0] == "answered"

        # Now saturate the root
        result = mark_saturated(
            graph_id=graph_with_root["graph_id"],
            node_id=graph_with_root["root_node_id"],
            reason="derivable",
            db_path=graph_with_root["db_path"],
        )

        assert result["status"] == "saturated"
        assert result["reason"] == "derivable"

    def test_mark_saturated_invalid_reason_rejected(self, graph_with_root):
        """mark_saturated with invalid reason must raise ValueError."""
        from spellbook_mcp.fractal.node_ops import add_node, mark_saturated

        node = add_node(
            graph_id=graph_with_root["graph_id"],
            parent_id=graph_with_root["root_node_id"],
            node_type="question",
            text="Invalid reason test",
            db_path=graph_with_root["db_path"],
        )

        with pytest.raises(ValueError, match="[Rr]eason"):
            mark_saturated(
                graph_id=graph_with_root["graph_id"],
                node_id=node["node_id"],
                reason="not_a_valid_reason",
                db_path=graph_with_root["db_path"],
            )

    def test_mark_saturated_already_saturated_rejected(self, graph_with_root):
        """mark_saturated on already-saturated node must raise ValueError."""
        from spellbook_mcp.fractal.node_ops import add_node, mark_saturated

        node = add_node(
            graph_id=graph_with_root["graph_id"],
            parent_id=graph_with_root["root_node_id"],
            node_type="question",
            text="Double saturation test",
            db_path=graph_with_root["db_path"],
        )

        # Saturate once
        mark_saturated(
            graph_id=graph_with_root["graph_id"],
            node_id=node["node_id"],
            reason="actionable",
            db_path=graph_with_root["db_path"],
        )

        # Try to saturate again
        with pytest.raises(ValueError, match="[Ss]tatus|[Ss]aturated"):
            mark_saturated(
                graph_id=graph_with_root["graph_id"],
                node_id=node["node_id"],
                reason="derivable",
                db_path=graph_with_root["db_path"],
            )

    def test_mark_saturated_node_not_found(self, graph_with_root):
        """mark_saturated with nonexistent node_id must raise ValueError."""
        from spellbook_mcp.fractal.node_ops import mark_saturated

        with pytest.raises(ValueError, match="[Nn]ode"):
            mark_saturated(
                graph_id=graph_with_root["graph_id"],
                node_id="nonexistent-node-id",
                reason="semantic_overlap",
                db_path=graph_with_root["db_path"],
            )

    def test_mark_saturated_stores_reason_in_metadata(self, graph_with_root):
        """mark_saturated must store reason in metadata_json under saturation_reason."""
        from spellbook_mcp.fractal.node_ops import add_node, mark_saturated
        from spellbook_mcp.fractal.schema import get_fractal_connection

        node = add_node(
            graph_id=graph_with_root["graph_id"],
            parent_id=graph_with_root["root_node_id"],
            node_type="question",
            text="Metadata reason test",
            metadata_json=json.dumps({"existing": "data"}),
            db_path=graph_with_root["db_path"],
        )

        mark_saturated(
            graph_id=graph_with_root["graph_id"],
            node_id=node["node_id"],
            reason="hollow_questions",
            db_path=graph_with_root["db_path"],
        )

        conn = get_fractal_connection(graph_with_root["db_path"])
        cursor = conn.cursor()
        cursor.execute(
            "SELECT metadata_json FROM nodes WHERE id = ?",
            (node["node_id"],),
        )
        stored = json.loads(cursor.fetchone()[0])
        assert stored["saturation_reason"] == "hollow_questions"
        # Existing metadata must be preserved
        assert stored["existing"] == "data"

    def test_mark_saturated_persisted_to_db(self, graph_with_root):
        """mark_saturated must persist status change to the database."""
        from spellbook_mcp.fractal.node_ops import add_node, mark_saturated
        from spellbook_mcp.fractal.schema import get_fractal_connection

        node = add_node(
            graph_id=graph_with_root["graph_id"],
            parent_id=graph_with_root["root_node_id"],
            node_type="question",
            text="Persistence test",
            db_path=graph_with_root["db_path"],
        )

        mark_saturated(
            graph_id=graph_with_root["graph_id"],
            node_id=node["node_id"],
            reason="budget_exhausted",
            db_path=graph_with_root["db_path"],
        )

        conn = get_fractal_connection(graph_with_root["db_path"])
        cursor = conn.cursor()
        cursor.execute(
            "SELECT status FROM nodes WHERE id = ?",
            (node["node_id"],),
        )
        assert cursor.fetchone()[0] == "saturated"

    def test_mark_saturated_all_valid_reasons(self, graph_with_root):
        """mark_saturated must accept all valid saturation reasons."""
        from spellbook_mcp.fractal.models import VALID_SATURATION_REASONS
        from spellbook_mcp.fractal.node_ops import add_node, mark_saturated

        for reason in VALID_SATURATION_REASONS:
            node = add_node(
                graph_id=graph_with_root["graph_id"],
                parent_id=graph_with_root["root_node_id"],
                node_type="question",
                text=f"Testing reason: {reason}",
                db_path=graph_with_root["db_path"],
            )
            result = mark_saturated(
                graph_id=graph_with_root["graph_id"],
                node_id=node["node_id"],
                reason=reason,
                db_path=graph_with_root["db_path"],
            )
            assert result["reason"] == reason

    def test_mark_saturated_invalid_graph_rejected(self, graph_with_root):
        """mark_saturated with nonexistent graph_id must raise ValueError."""
        from spellbook_mcp.fractal.node_ops import add_node, mark_saturated

        node = add_node(
            graph_id=graph_with_root["graph_id"],
            parent_id=graph_with_root["root_node_id"],
            node_type="question",
            text="Invalid graph test",
            db_path=graph_with_root["db_path"],
        )

        with pytest.raises(ValueError, match="[Gg]raph"):
            mark_saturated(
                graph_id="nonexistent-graph",
                node_id=node["node_id"],
                reason="semantic_overlap",
                db_path=graph_with_root["db_path"],
            )

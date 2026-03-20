"""Tests for fractal thinking node operations.

Tests for add_node, update_node, and mark_saturated.
"""

import json

import pytest


@pytest.fixture
async def graph_with_root(fractal_db):
    """Create a graph with a root question node for testing.

    Returns a dict with graph_id, root_node_id, and db_path.
    """
    from spellbook.fractal.graph_ops import create_graph

    result = await create_graph(
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

    async def test_add_question_node_returns_correct_shape(self, graph_with_root):
        """add_node must return dict with node_id, graph_id, parent_id, depth, node_type, status."""
        from spellbook.fractal.node_ops import add_node

        result = await add_node(
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

    async def test_add_question_node_depth_calculation(self, graph_with_root):
        """add_node must calculate depth = parent.depth + 1."""
        from spellbook.fractal.node_ops import add_node

        # Root node is depth 0, so child should be depth 1
        result = await add_node(
            graph_id=graph_with_root["graph_id"],
            parent_id=graph_with_root["root_node_id"],
            node_type="question",
            text="Sub-question at depth 1",
            db_path=graph_with_root["db_path"],
        )

        assert result["depth"] == 1

    async def test_add_node_depth_cascades(self, fractal_db):
        """add_node at depth 1 parent must produce depth 2 child."""
        from spellbook.fractal.graph_ops import create_graph
        from spellbook.fractal.node_ops import add_node

        # Use explore intensity (max_depth=4) to allow deeper nesting
        result = await create_graph(
            seed="Deep test",
            intensity="explore",
            checkpoint_mode="autonomous",
            db_path=fractal_db,
        )
        graph_id = result["graph_id"]
        root_id = result["root_node_id"]

        # Create depth-1 node
        depth1 = await add_node(
            graph_id=graph_id,
            parent_id=root_id,
            node_type="question",
            text="Depth 1 question",
            db_path=fractal_db,
        )

        # Create depth-2 node
        depth2 = await add_node(
            graph_id=graph_id,
            parent_id=depth1["node_id"],
            node_type="question",
            text="Depth 2 question",
            db_path=fractal_db,
        )

        assert depth2["depth"] == 2

    async def test_add_answer_node(self, graph_with_root):
        """add_node must accept answer node type."""
        from spellbook.fractal.node_ops import add_node

        result = await add_node(
            graph_id=graph_with_root["graph_id"],
            parent_id=graph_with_root["root_node_id"],
            node_type="answer",
            text="Because of Rayleigh scattering",
            db_path=graph_with_root["db_path"],
        )

        assert result["node_type"] == "answer"
        assert result["status"] == "open"

    async def test_add_answer_auto_transitions_parent_question(self, graph_with_root):
        """Adding answer to open question must transition parent to answered."""
        from spellbook.fractal.node_ops import add_node
        from spellbook.fractal.schema import get_fractal_connection

        await add_node(
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

    async def test_add_answer_does_not_transition_non_question_parent(self, fractal_db):
        """Adding answer to answer parent must NOT transition parent status."""
        from spellbook.fractal.graph_ops import create_graph
        from spellbook.fractal.node_ops import add_node
        from spellbook.fractal.schema import get_fractal_connection

        # Use explore intensity (max_depth=4) since this test needs depth 2
        graph = await create_graph(
            seed="Test", intensity="explore",
            checkpoint_mode="autonomous", db_path=fractal_db,
        )

        # First add an answer to root
        answer1 = await add_node(
            graph_id=graph["graph_id"],
            parent_id=graph["root_node_id"],
            node_type="answer",
            text="First answer",
            db_path=fractal_db,
        )

        # Add another answer as child of the first answer (depth 2)
        await add_node(
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

    async def test_add_node_creates_parent_child_edge(self, graph_with_root):
        """add_node with parent_id must create parent_child edge."""
        from spellbook.fractal.node_ops import add_node
        from spellbook.fractal.schema import get_fractal_connection

        result = await add_node(
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

    async def test_add_node_with_owner(self, graph_with_root):
        """add_node must store owner when provided."""
        from spellbook.fractal.node_ops import add_node
        from spellbook.fractal.schema import get_fractal_connection

        result = await add_node(
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

    async def test_add_node_with_metadata(self, graph_with_root):
        """add_node must store metadata_json when provided."""
        from spellbook.fractal.node_ops import add_node
        from spellbook.fractal.schema import get_fractal_connection

        metadata = json.dumps({"priority": "high", "source": "decomposition"})

        result = await add_node(
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

    async def test_add_node_invalid_graph_rejected(self, fractal_db):
        """add_node with nonexistent graph_id must raise ValueError."""
        from spellbook.fractal.node_ops import add_node

        with pytest.raises(ValueError, match="[Gg]raph"):
            await add_node(
                graph_id="nonexistent-graph-id",
                parent_id=None,
                node_type="question",
                text="Orphan question",
                db_path=fractal_db,
            )

    async def test_add_node_invalid_node_type_rejected(self, graph_with_root):
        """add_node with invalid node_type must raise ValueError."""
        from spellbook.fractal.node_ops import add_node

        with pytest.raises(ValueError, match="[Nn]ode.type"):
            await add_node(
                graph_id=graph_with_root["graph_id"],
                parent_id=graph_with_root["root_node_id"],
                node_type="invalid_type",
                text="Bad type",
                db_path=graph_with_root["db_path"],
            )

    async def test_add_node_parent_not_found_rejected(self, graph_with_root):
        """add_node with nonexistent parent_id must raise ValueError."""
        from spellbook.fractal.node_ops import add_node

        with pytest.raises(ValueError, match="[Pp]arent"):
            await add_node(
                graph_id=graph_with_root["graph_id"],
                parent_id="nonexistent-parent-id",
                node_type="question",
                text="Orphan question",
                db_path=graph_with_root["db_path"],
            )

    async def test_add_node_no_parent_depth_zero(self, graph_with_root):
        """add_node without parent_id must have depth 0."""
        from spellbook.fractal.node_ops import add_node

        result = await add_node(
            graph_id=graph_with_root["graph_id"],
            parent_id=None,
            node_type="question",
            text="Root-level question",
            db_path=graph_with_root["db_path"],
        )

        assert result["depth"] == 0

    async def test_add_node_generates_uuid(self, graph_with_root):
        """add_node must generate a valid UUID for node_id."""
        import uuid

        from spellbook.fractal.node_ops import add_node

        result = await add_node(
            graph_id=graph_with_root["graph_id"],
            parent_id=graph_with_root["root_node_id"],
            node_type="question",
            text="UUID test",
            db_path=graph_with_root["db_path"],
        )

        # Should not raise
        uuid.UUID(result["node_id"])

    async def test_add_node_persisted_to_db(self, graph_with_root):
        """add_node must persist the node to the database."""
        from spellbook.fractal.node_ops import add_node
        from spellbook.fractal.schema import get_fractal_connection

        result = await add_node(
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

    async def test_add_node_exceeds_depth_budget(self, graph_with_root):
        """add_node should reject nodes that would exceed the intensity's max_depth."""
        from spellbook.fractal.node_ops import add_node

        # graph_with_root creates a pulse-intensity graph (max_depth=2)
        # Root is depth 0. Add child at depth 1 (allowed).
        child = await add_node(
            graph_id=graph_with_root["graph_id"],
            parent_id=graph_with_root["root_node_id"],
            node_type="question",
            text="Child question",
            db_path=graph_with_root["db_path"],
        )

        # Add grandchild at depth 2 (should be rejected for pulse, max_depth=2)
        with pytest.raises(ValueError, match="exceed max_depth"):
            await add_node(
                graph_id=graph_with_root["graph_id"],
                parent_id=child["node_id"],
                node_type="question",
                text="Too deep",
                db_path=graph_with_root["db_path"],
            )

    async def test_add_node_at_max_allowed_depth(self, graph_with_root):
        """Nodes at depth max_depth-1 should be allowed."""
        from spellbook.fractal.node_ops import add_node

        # pulse max_depth=2, so depth 1 should work
        result = await add_node(
            graph_id=graph_with_root["graph_id"],
            parent_id=graph_with_root["root_node_id"],
            node_type="question",
            text="Depth 1 ok",
            db_path=graph_with_root["db_path"],
        )

        assert result["depth"] == 1
        assert "node_id" in result

    async def test_add_node_to_non_active_graph(self, fractal_db):
        """add_node should reject adding nodes to non-active graphs."""
        from spellbook.fractal.graph_ops import create_graph, update_graph_status
        from spellbook.fractal.node_ops import add_node

        result = await create_graph(
            seed="Test",
            intensity="pulse",
            checkpoint_mode="autonomous",
            db_path=fractal_db,
        )
        graph_id = result["graph_id"]
        root_id = result["root_node_id"]

        # Complete the graph
        await update_graph_status(graph_id, "completed", db_path=fractal_db)

        # Try to add a node
        with pytest.raises(ValueError, match="must be 'active'"):
            await add_node(
                graph_id=graph_id,
                parent_id=root_id,
                node_type="answer",
                text="Should fail",
                db_path=fractal_db,
            )

    async def test_add_node_to_paused_graph(self, fractal_db):
        """add_node should reject adding nodes to paused graphs."""
        from spellbook.fractal.graph_ops import create_graph, update_graph_status
        from spellbook.fractal.node_ops import add_node

        result = await create_graph(
            seed="Test",
            intensity="pulse",
            checkpoint_mode="autonomous",
            db_path=fractal_db,
        )
        graph_id = result["graph_id"]
        root_id = result["root_node_id"]

        await update_graph_status(graph_id, "paused", db_path=fractal_db)

        with pytest.raises(ValueError, match="must be 'active'"):
            await add_node(
                graph_id=graph_id,
                parent_id=root_id,
                node_type="answer",
                text="Should fail",
                db_path=fractal_db,
            )


class TestUpdateNode:
    """Tests for update_node function."""

    async def test_update_node_merges_metadata(self, graph_with_root):
        """update_node must merge new metadata into existing, not replace."""
        from spellbook.fractal.node_ops import add_node, update_node
        from spellbook.fractal.schema import get_fractal_connection

        # Create node with initial metadata
        initial_meta = json.dumps({"priority": "high"})
        node = await add_node(
            graph_id=graph_with_root["graph_id"],
            parent_id=graph_with_root["root_node_id"],
            node_type="question",
            text="Metadata merge test",
            metadata_json=initial_meta,
            db_path=graph_with_root["db_path"],
        )

        # Update with additional metadata
        new_meta = json.dumps({"source": "decomposition", "confidence": 0.9})
        result = await update_node(
            graph_id=graph_with_root["graph_id"],
            node_id=node["node_id"],
            metadata_json=new_meta,
            db_path=graph_with_root["db_path"],
        )

        # Both old and new keys must be present
        assert result["metadata"]["priority"] == "high"
        assert result["metadata"]["source"] == "decomposition"
        assert result["metadata"]["confidence"] == 0.9

    async def test_update_node_metadata_overwrite_key(self, graph_with_root):
        """update_node must overwrite existing key when same key provided."""
        from spellbook.fractal.node_ops import add_node, update_node

        initial_meta = json.dumps({"priority": "high"})
        node = await add_node(
            graph_id=graph_with_root["graph_id"],
            parent_id=graph_with_root["root_node_id"],
            node_type="question",
            text="Overwrite test",
            metadata_json=initial_meta,
            db_path=graph_with_root["db_path"],
        )

        new_meta = json.dumps({"priority": "low"})
        result = await update_node(
            graph_id=graph_with_root["graph_id"],
            node_id=node["node_id"],
            metadata_json=new_meta,
            db_path=graph_with_root["db_path"],
        )

        assert result["metadata"]["priority"] == "low"

    async def test_update_node_returns_correct_shape(self, graph_with_root):
        """update_node must return dict with node_id, metadata, edges_created."""
        from spellbook.fractal.node_ops import add_node, update_node

        node = await add_node(
            graph_id=graph_with_root["graph_id"],
            parent_id=graph_with_root["root_node_id"],
            node_type="question",
            text="Shape test",
            db_path=graph_with_root["db_path"],
        )

        result = await update_node(
            graph_id=graph_with_root["graph_id"],
            node_id=node["node_id"],
            metadata_json=json.dumps({"key": "value"}),
            db_path=graph_with_root["db_path"],
        )

        assert "node_id" in result
        assert "metadata" in result
        assert "edges_created" in result
        assert result["node_id"] == node["node_id"]

    async def test_update_node_convergence_edge_creation(self, graph_with_root):
        """update_node with convergence_with must create convergence edges."""
        from spellbook.fractal.node_ops import add_node, update_node
        from spellbook.fractal.schema import get_fractal_connection

        # Create two sibling nodes
        node_a = await add_node(
            graph_id=graph_with_root["graph_id"],
            parent_id=graph_with_root["root_node_id"],
            node_type="question",
            text="Node A",
            db_path=graph_with_root["db_path"],
        )
        node_b = await add_node(
            graph_id=graph_with_root["graph_id"],
            parent_id=graph_with_root["root_node_id"],
            node_type="question",
            text="Node B",
            db_path=graph_with_root["db_path"],
        )

        # Update node_a with convergence_with pointing to node_b
        meta = json.dumps({"convergence_with": [node_b["node_id"]]})
        result = await update_node(
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

    async def test_update_node_contradiction_edge_creation(self, graph_with_root):
        """update_node with contradiction_with must create contradiction edges."""
        from spellbook.fractal.node_ops import add_node, update_node
        from spellbook.fractal.schema import get_fractal_connection

        node_a = await add_node(
            graph_id=graph_with_root["graph_id"],
            parent_id=graph_with_root["root_node_id"],
            node_type="answer",
            text="Answer A",
            db_path=graph_with_root["db_path"],
        )
        node_b = await add_node(
            graph_id=graph_with_root["graph_id"],
            parent_id=graph_with_root["root_node_id"],
            node_type="answer",
            text="Contradicting answer B",
            db_path=graph_with_root["db_path"],
        )

        meta = json.dumps({"contradiction_with": [node_b["node_id"]]})
        result = await update_node(
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

    async def test_update_node_multiple_convergence_targets(self, graph_with_root):
        """update_node with multiple convergence_with targets must create multiple edges."""
        from spellbook.fractal.node_ops import add_node, update_node

        node_a = await add_node(
            graph_id=graph_with_root["graph_id"],
            parent_id=graph_with_root["root_node_id"],
            node_type="question",
            text="Node A",
            db_path=graph_with_root["db_path"],
        )
        node_b = await add_node(
            graph_id=graph_with_root["graph_id"],
            parent_id=graph_with_root["root_node_id"],
            node_type="question",
            text="Node B",
            db_path=graph_with_root["db_path"],
        )
        node_c = await add_node(
            graph_id=graph_with_root["graph_id"],
            parent_id=graph_with_root["root_node_id"],
            node_type="question",
            text="Node C",
            db_path=graph_with_root["db_path"],
        )

        meta = json.dumps({
            "convergence_with": [node_b["node_id"], node_c["node_id"]]
        })
        result = await update_node(
            graph_id=graph_with_root["graph_id"],
            node_id=node_a["node_id"],
            metadata_json=meta,
            db_path=graph_with_root["db_path"],
        )

        assert result["edges_created"] == 2

    async def test_update_node_invalid_convergence_target_rejected(self, graph_with_root):
        """update_node with nonexistent convergence target must raise ValueError."""
        from spellbook.fractal.node_ops import add_node, update_node

        node_a = await add_node(
            graph_id=graph_with_root["graph_id"],
            parent_id=graph_with_root["root_node_id"],
            node_type="question",
            text="Node A",
            db_path=graph_with_root["db_path"],
        )

        meta = json.dumps({"convergence_with": ["nonexistent-node-id"]})

        with pytest.raises(ValueError, match="[Nn]ode"):
            await update_node(
                graph_id=graph_with_root["graph_id"],
                node_id=node_a["node_id"],
                metadata_json=meta,
                db_path=graph_with_root["db_path"],
            )

    async def test_update_node_invalid_contradiction_target_rejected(self, graph_with_root):
        """update_node with nonexistent contradiction target must raise ValueError."""
        from spellbook.fractal.node_ops import add_node, update_node

        node_a = await add_node(
            graph_id=graph_with_root["graph_id"],
            parent_id=graph_with_root["root_node_id"],
            node_type="question",
            text="Node A",
            db_path=graph_with_root["db_path"],
        )

        meta = json.dumps({"contradiction_with": ["nonexistent-node-id"]})

        with pytest.raises(ValueError, match="[Nn]ode"):
            await update_node(
                graph_id=graph_with_root["graph_id"],
                node_id=node_a["node_id"],
                metadata_json=meta,
                db_path=graph_with_root["db_path"],
            )

    async def test_update_node_no_edges_returns_zero(self, graph_with_root):
        """update_node without edge-creating metadata must return edges_created=0."""
        from spellbook.fractal.node_ops import add_node, update_node

        node = await add_node(
            graph_id=graph_with_root["graph_id"],
            parent_id=graph_with_root["root_node_id"],
            node_type="question",
            text="Simple update",
            db_path=graph_with_root["db_path"],
        )

        result = await update_node(
            graph_id=graph_with_root["graph_id"],
            node_id=node["node_id"],
            metadata_json=json.dumps({"note": "just a note"}),
            db_path=graph_with_root["db_path"],
        )

        assert result["edges_created"] == 0

    async def test_update_node_invalid_graph_rejected(self, graph_with_root):
        """update_node with nonexistent graph_id must raise ValueError."""
        from spellbook.fractal.node_ops import add_node, update_node

        node = await add_node(
            graph_id=graph_with_root["graph_id"],
            parent_id=graph_with_root["root_node_id"],
            node_type="question",
            text="Test",
            db_path=graph_with_root["db_path"],
        )

        with pytest.raises(ValueError, match="[Gg]raph"):
            await update_node(
                graph_id="nonexistent-graph",
                node_id=node["node_id"],
                metadata_json=json.dumps({"key": "val"}),
                db_path=graph_with_root["db_path"],
            )

    async def test_update_node_invalid_node_rejected(self, graph_with_root):
        """update_node with nonexistent node_id must raise ValueError."""
        from spellbook.fractal.node_ops import update_node

        with pytest.raises(ValueError, match="[Nn]ode"):
            await update_node(
                graph_id=graph_with_root["graph_id"],
                node_id="nonexistent-node",
                metadata_json=json.dumps({"key": "val"}),
                db_path=graph_with_root["db_path"],
            )

    async def test_update_node_metadata_persisted(self, graph_with_root):
        """update_node must persist merged metadata to the database."""
        from spellbook.fractal.node_ops import add_node, update_node
        from spellbook.fractal.schema import get_fractal_connection

        node = await add_node(
            graph_id=graph_with_root["graph_id"],
            parent_id=graph_with_root["root_node_id"],
            node_type="question",
            text="Persist test",
            metadata_json=json.dumps({"old_key": "old_val"}),
            db_path=graph_with_root["db_path"],
        )

        await update_node(
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

    async def test_mark_saturated_from_open(self, graph_with_root):
        """mark_saturated must transition open node to saturated."""
        from spellbook.fractal.node_ops import add_node, mark_saturated

        node = await add_node(
            graph_id=graph_with_root["graph_id"],
            parent_id=graph_with_root["root_node_id"],
            node_type="question",
            text="Saturable question",
            db_path=graph_with_root["db_path"],
        )

        result = await mark_saturated(
            graph_id=graph_with_root["graph_id"],
            node_id=node["node_id"],
            reason="semantic_overlap",
            db_path=graph_with_root["db_path"],
        )

        assert result["node_id"] == node["node_id"]
        assert result["status"] == "saturated"
        assert result["reason"] == "semantic_overlap"

    async def test_mark_saturated_from_answered(self, graph_with_root):
        """mark_saturated must transition answered node to saturated."""
        from spellbook.fractal.node_ops import add_node, mark_saturated
        from spellbook.fractal.schema import get_fractal_connection

        # Add answer to root to transition root to "answered"
        # Root is at depth 0, answer will be at depth 1 (within pulse max_depth=2)
        await add_node(
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
        result = await mark_saturated(
            graph_id=graph_with_root["graph_id"],
            node_id=graph_with_root["root_node_id"],
            reason="derivable",
            db_path=graph_with_root["db_path"],
        )

        assert result["status"] == "saturated"
        assert result["reason"] == "derivable"

    async def test_mark_saturated_invalid_reason_rejected(self, graph_with_root):
        """mark_saturated with invalid reason must raise ValueError."""
        from spellbook.fractal.node_ops import add_node, mark_saturated

        node = await add_node(
            graph_id=graph_with_root["graph_id"],
            parent_id=graph_with_root["root_node_id"],
            node_type="question",
            text="Invalid reason test",
            db_path=graph_with_root["db_path"],
        )

        with pytest.raises(ValueError, match="[Rr]eason"):
            await mark_saturated(
                graph_id=graph_with_root["graph_id"],
                node_id=node["node_id"],
                reason="not_a_valid_reason",
                db_path=graph_with_root["db_path"],
            )

    async def test_mark_saturated_already_saturated_rejected(self, graph_with_root):
        """mark_saturated on already-saturated node must raise ValueError."""
        from spellbook.fractal.node_ops import add_node, mark_saturated

        node = await add_node(
            graph_id=graph_with_root["graph_id"],
            parent_id=graph_with_root["root_node_id"],
            node_type="question",
            text="Double saturation test",
            db_path=graph_with_root["db_path"],
        )

        # Saturate once
        await mark_saturated(
            graph_id=graph_with_root["graph_id"],
            node_id=node["node_id"],
            reason="actionable",
            db_path=graph_with_root["db_path"],
        )

        # Try to saturate again
        with pytest.raises(ValueError, match="[Ss]tatus|[Ss]aturated"):
            await mark_saturated(
                graph_id=graph_with_root["graph_id"],
                node_id=node["node_id"],
                reason="derivable",
                db_path=graph_with_root["db_path"],
            )

    async def test_mark_saturated_node_not_found(self, graph_with_root):
        """mark_saturated with nonexistent node_id must raise ValueError."""
        from spellbook.fractal.node_ops import mark_saturated

        with pytest.raises(ValueError, match="[Nn]ode"):
            await mark_saturated(
                graph_id=graph_with_root["graph_id"],
                node_id="nonexistent-node-id",
                reason="semantic_overlap",
                db_path=graph_with_root["db_path"],
            )

    async def test_mark_saturated_stores_reason_in_metadata(self, graph_with_root):
        """mark_saturated must store reason in metadata_json under saturation_reason."""
        from spellbook.fractal.node_ops import add_node, mark_saturated
        from spellbook.fractal.schema import get_fractal_connection

        node = await add_node(
            graph_id=graph_with_root["graph_id"],
            parent_id=graph_with_root["root_node_id"],
            node_type="question",
            text="Metadata reason test",
            metadata_json=json.dumps({"existing": "data"}),
            db_path=graph_with_root["db_path"],
        )

        await mark_saturated(
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

    async def test_mark_saturated_persisted_to_db(self, graph_with_root):
        """mark_saturated must persist status change to the database."""
        from spellbook.fractal.node_ops import add_node, mark_saturated
        from spellbook.fractal.schema import get_fractal_connection

        node = await add_node(
            graph_id=graph_with_root["graph_id"],
            parent_id=graph_with_root["root_node_id"],
            node_type="question",
            text="Persistence test",
            db_path=graph_with_root["db_path"],
        )

        await mark_saturated(
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

    async def test_mark_saturated_all_valid_reasons(self, graph_with_root):
        """mark_saturated must accept all valid saturation reasons."""
        from spellbook.fractal.models import VALID_SATURATION_REASONS
        from spellbook.fractal.node_ops import add_node, mark_saturated

        for reason in VALID_SATURATION_REASONS:
            node = await add_node(
                graph_id=graph_with_root["graph_id"],
                parent_id=graph_with_root["root_node_id"],
                node_type="question",
                text=f"Testing reason: {reason}",
                db_path=graph_with_root["db_path"],
            )
            result = await mark_saturated(
                graph_id=graph_with_root["graph_id"],
                node_id=node["node_id"],
                reason=reason,
                db_path=graph_with_root["db_path"],
            )
            assert result["reason"] == reason

    async def test_mark_saturated_invalid_graph_rejected(self, graph_with_root):
        """mark_saturated with nonexistent graph_id must raise ValueError."""
        from spellbook.fractal.node_ops import add_node, mark_saturated

        node = await add_node(
            graph_id=graph_with_root["graph_id"],
            parent_id=graph_with_root["root_node_id"],
            node_type="question",
            text="Invalid graph test",
            db_path=graph_with_root["db_path"],
        )

        with pytest.raises(ValueError, match="[Gg]raph"):
            await mark_saturated(
                graph_id="nonexistent-graph",
                node_id=node["node_id"],
                reason="semantic_overlap",
                db_path=graph_with_root["db_path"],
            )

    async def test_mark_saturated_from_claimed(self, graph_with_root):
        """mark_saturated must transition claimed node to saturated."""
        from spellbook.fractal.node_ops import add_node, claim_work, mark_saturated

        # Add a question node under root
        node = await add_node(
            graph_id=graph_with_root["graph_id"],
            parent_id=graph_with_root["root_node_id"],
            node_type="question",
            text="Claimable question for saturation",
            db_path=graph_with_root["db_path"],
        )

        # Claim twice: first claims root (depth 0), second claims our node (depth 1)
        await claim_work(
            graph_id=graph_with_root["graph_id"],
            worker_id="worker-sat",
            db_path=graph_with_root["db_path"],
        )
        claimed = await claim_work(
            graph_id=graph_with_root["graph_id"],
            worker_id="worker-sat",
            db_path=graph_with_root["db_path"],
        )
        assert claimed["node_id"] == node["node_id"], "Expected child node to be claimed"

        # Should succeed because claimed is now an allowed source status
        result = await mark_saturated(
            graph_id=graph_with_root["graph_id"],
            node_id=node["node_id"],
            reason="semantic_overlap",
            db_path=graph_with_root["db_path"],
        )

        assert result["status"] == "saturated"
        assert result["reason"] == "semantic_overlap"


class TestClaimWork:
    """Tests for claim_work function."""

    async def test_claim_work_basic(self, graph_with_root):
        """claim_work must claim an open question node and return its data."""
        from spellbook.fractal.node_ops import add_node, claim_work

        # Add a question node
        node = await add_node(
            graph_id=graph_with_root["graph_id"],
            parent_id=graph_with_root["root_node_id"],
            node_type="question",
            text="Claimable question",
            db_path=graph_with_root["db_path"],
        )

        result = await claim_work(
            graph_id=graph_with_root["graph_id"],
            worker_id="worker-1",
            db_path=graph_with_root["db_path"],
        )

        assert result["node_id"] is not None
        assert result["graph_done"] is False
        assert "text" in result
        assert "depth" in result
        assert "parent_id" in result
        assert "metadata" in result

    async def test_claim_work_sets_owner_and_status(self, graph_with_root):
        """claim_work must set owner and status='claimed' in the database."""
        from spellbook.fractal.node_ops import add_node, claim_work
        from spellbook.fractal.schema import get_fractal_connection

        node = await add_node(
            graph_id=graph_with_root["graph_id"],
            parent_id=graph_with_root["root_node_id"],
            node_type="question",
            text="Ownership test",
            db_path=graph_with_root["db_path"],
        )

        result = await claim_work(
            graph_id=graph_with_root["graph_id"],
            worker_id="worker-own",
            db_path=graph_with_root["db_path"],
        )

        conn = get_fractal_connection(graph_with_root["db_path"])
        cursor = conn.cursor()
        cursor.execute(
            "SELECT owner, status FROM nodes WHERE id = ?",
            (result["node_id"],),
        )
        row = cursor.fetchone()
        assert row[0] == "worker-own"
        assert row[1] == "claimed"

    async def test_claim_work_atomicity(self, graph_with_root):
        """claim_work must not double-claim; each call claims a different node."""
        from spellbook.fractal.node_ops import add_node, claim_work

        node1 = await add_node(
            graph_id=graph_with_root["graph_id"],
            parent_id=graph_with_root["root_node_id"],
            node_type="question",
            text="Question A",
            db_path=graph_with_root["db_path"],
        )
        node2 = await add_node(
            graph_id=graph_with_root["graph_id"],
            parent_id=graph_with_root["root_node_id"],
            node_type="question",
            text="Question B",
            db_path=graph_with_root["db_path"],
        )

        result1 = await claim_work(
            graph_id=graph_with_root["graph_id"],
            worker_id="worker-1",
            db_path=graph_with_root["db_path"],
        )
        result2 = await claim_work(
            graph_id=graph_with_root["graph_id"],
            worker_id="worker-1",
            db_path=graph_with_root["db_path"],
        )

        assert result1["node_id"] is not None
        assert result2["node_id"] is not None
        assert result1["node_id"] != result2["node_id"]

    async def test_claim_work_branch_affinity(self, fractal_db):
        """claim_work must prefer sibling nodes of previously claimed/owned nodes."""
        from spellbook.fractal.graph_ops import create_graph
        from spellbook.fractal.node_ops import add_node, claim_work
        from spellbook.fractal.schema import get_fractal_connection

        # Use explore intensity for deeper nesting
        graph = await create_graph(
            seed="Affinity test",
            intensity="explore",
            checkpoint_mode="autonomous",
            db_path=fractal_db,
        )
        graph_id = graph["graph_id"]
        root_id = graph["root_node_id"]

        # Create two parent answer nodes under root
        parent_a = await add_node(
            graph_id=graph_id, parent_id=root_id,
            node_type="answer", text="Branch A",
            db_path=fractal_db,
        )
        parent_b = await add_node(
            graph_id=graph_id, parent_id=root_id,
            node_type="answer", text="Branch B",
            db_path=fractal_db,
        )

        # Create questions under each parent
        q_a1 = await add_node(
            graph_id=graph_id, parent_id=parent_a["node_id"],
            node_type="question", text="Question A1",
            db_path=fractal_db,
        )
        q_a2 = await add_node(
            graph_id=graph_id, parent_id=parent_a["node_id"],
            node_type="question", text="Question A2",
            db_path=fractal_db,
        )
        q_b1 = await add_node(
            graph_id=graph_id, parent_id=parent_b["node_id"],
            node_type="question", text="Question B1",
            db_path=fractal_db,
        )

        # Worker claims first node (could be any due to initial state)
        # Then manually set q_a1 as owned by the worker to set up affinity
        conn = get_fractal_connection(fractal_db)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE nodes SET owner = 'worker-affinity', status = 'claimed' WHERE id = ?",
            (q_a1["node_id"],),
        )
        conn.commit()

        # Now claim_work should prefer q_a2 (sibling of q_a1 under parent_a)
        # over q_b1 (under parent_b) because worker already owns a sibling
        result = await claim_work(
            graph_id=graph_id,
            worker_id="worker-affinity",
            db_path=fractal_db,
        )

        assert result["node_id"] == q_a2["node_id"]

    async def test_claim_work_no_work_available_with_claimed(self, graph_with_root):
        """claim_work with no open nodes but claimed nodes returns graph_done=False."""
        from spellbook.fractal.node_ops import add_node, claim_work

        # Add one question and claim it
        await add_node(
            graph_id=graph_with_root["graph_id"],
            parent_id=graph_with_root["root_node_id"],
            node_type="question",
            text="Only question",
            db_path=graph_with_root["db_path"],
        )

        # Claim the only open question (the root is also open, so claim both)
        await claim_work(
            graph_id=graph_with_root["graph_id"],
            worker_id="worker-1",
            db_path=graph_with_root["db_path"],
        )
        await claim_work(
            graph_id=graph_with_root["graph_id"],
            worker_id="worker-2",
            db_path=graph_with_root["db_path"],
        )

        # Now try to claim again -- no open questions left, but claimed exist
        result = await claim_work(
            graph_id=graph_with_root["graph_id"],
            worker_id="worker-3",
            db_path=graph_with_root["db_path"],
        )

        assert result["node_id"] is None
        assert result["graph_done"] is False

    async def test_claim_work_graph_done(self, graph_with_root):
        """claim_work with no open and no claimed nodes returns graph_done=True."""
        from spellbook.fractal.node_ops import add_node, mark_saturated

        # The root node is the only question. Saturate it so no open/claimed remain.
        await mark_saturated(
            graph_id=graph_with_root["graph_id"],
            node_id=graph_with_root["root_node_id"],
            reason="semantic_overlap",
            db_path=graph_with_root["db_path"],
        )

        from spellbook.fractal.node_ops import claim_work

        result = await claim_work(
            graph_id=graph_with_root["graph_id"],
            worker_id="worker-done",
            db_path=graph_with_root["db_path"],
        )

        assert result["node_id"] is None
        assert result["graph_done"] is True

    async def test_claim_work_prefers_shallow(self, fractal_db):
        """claim_work must prefer shallower nodes over deeper ones."""
        from spellbook.fractal.graph_ops import create_graph
        from spellbook.fractal.node_ops import add_node, claim_work
        from spellbook.fractal.schema import get_fractal_connection

        graph = await create_graph(
            seed="Depth preference test",
            intensity="deep",
            checkpoint_mode="autonomous",
            db_path=fractal_db,
        )
        graph_id = graph["graph_id"]
        root_id = graph["root_node_id"]

        # Create depth-1 question under root
        depth1_q = await add_node(
            graph_id=graph_id, parent_id=root_id,
            node_type="question", text="Depth 1 question",
            db_path=fractal_db,
        )

        # Create a depth-2 chain: depth-1 answer -> depth-2 question -> depth-3 question
        depth1_answer = await add_node(
            graph_id=graph_id, parent_id=root_id,
            node_type="answer", text="Depth 1 answer",
            db_path=fractal_db,
        )
        depth2_q = await add_node(
            graph_id=graph_id, parent_id=depth1_answer["node_id"],
            node_type="question", text="Depth 2 question",
            db_path=fractal_db,
        )
        depth3_q = await add_node(
            graph_id=graph_id, parent_id=depth2_q["node_id"],
            node_type="question", text="Depth 3 question",
            db_path=fractal_db,
        )

        # Root is now 'answered' (auto-transitioned by adding answer).
        # Open questions: depth1_q (depth 1), depth2_q (depth 2), depth3_q (depth 3)

        # First claim should pick the shallowest open question: depth1_q at depth 1
        first_claim = await claim_work(
            graph_id=graph_id,
            worker_id="worker-depth",
            db_path=fractal_db,
        )
        assert first_claim["node_id"] == depth1_q["node_id"]
        assert first_claim["depth"] == 1

        # Next claim should pick depth 2 (not depth 3)
        second_claim = await claim_work(
            graph_id=graph_id,
            worker_id="worker-depth",
            db_path=fractal_db,
        )
        assert second_claim["depth"] == 2
        assert second_claim["node_id"] == depth2_q["node_id"]

    async def test_claim_work_inactive_graph(self, fractal_db):
        """claim_work on non-active graph must raise ValueError."""
        from spellbook.fractal.graph_ops import create_graph, update_graph_status
        from spellbook.fractal.node_ops import claim_work

        graph = await create_graph(
            seed="Inactive test",
            intensity="pulse",
            checkpoint_mode="autonomous",
            db_path=fractal_db,
        )
        graph_id = graph["graph_id"]

        await update_graph_status(graph_id, "completed", db_path=fractal_db)

        with pytest.raises(ValueError, match="active"):
            await claim_work(
                graph_id=graph_id,
                worker_id="worker-inactive",
                db_path=fractal_db,
            )


class TestSynthesizeNode:
    """Tests for synthesize_node function."""

    async def test_synthesize_leaf_node(self, graph_with_root):
        """synthesize_node on a leaf node (no children) with claimed status must succeed."""
        from spellbook.fractal.node_ops import add_node, claim_work, synthesize_node

        # Add a question and claim it (simulating a worker picking it up)
        node = await add_node(
            graph_id=graph_with_root["graph_id"],
            parent_id=graph_with_root["root_node_id"],
            node_type="question",
            text="Leaf question for synthesis",
            db_path=graph_with_root["db_path"],
        )

        await claim_work(
            graph_id=graph_with_root["graph_id"],
            worker_id="worker-synth",
            db_path=graph_with_root["db_path"],
        )

        # The claimed node might be root or the new node.
        # Claim again to get the other one.
        await claim_work(
            graph_id=graph_with_root["graph_id"],
            worker_id="worker-synth",
            db_path=graph_with_root["db_path"],
        )

        # Now synthesize the leaf node (which should be claimed)
        result = await synthesize_node(
            graph_id=graph_with_root["graph_id"],
            node_id=node["node_id"],
            synthesis_text="This is the synthesis of the leaf.",
            db_path=graph_with_root["db_path"],
        )

        assert result["node_id"] == node["node_id"]
        assert result["status"] == "synthesized"

    async def test_synthesize_node_with_children(self, fractal_db):
        """synthesize_node on parent must succeed when all children are synthesized/saturated."""
        from spellbook.fractal.graph_ops import create_graph
        from spellbook.fractal.node_ops import (
            add_node,
            mark_saturated,
            synthesize_node,
        )
        from spellbook.fractal.schema import get_fractal_connection

        graph = await create_graph(
            seed="Synthesis parent test",
            intensity="explore",
            checkpoint_mode="autonomous",
            db_path=fractal_db,
        )
        graph_id = graph["graph_id"]
        root_id = graph["root_node_id"]

        # Add an answer to root to trigger auto-transition root -> answered
        await add_node(
            graph_id=graph_id, parent_id=root_id,
            node_type="answer", text="Root answer",
            db_path=fractal_db,
        )

        # Add two child questions under root
        child1 = await add_node(
            graph_id=graph_id, parent_id=root_id,
            node_type="question", text="Child Q1",
            db_path=fractal_db,
        )
        child2 = await add_node(
            graph_id=graph_id, parent_id=root_id,
            node_type="question", text="Child Q2",
            db_path=fractal_db,
        )

        # Saturate child1, synthesize child2 via claim path
        await mark_saturated(
            graph_id=graph_id, node_id=child1["node_id"],
            reason="semantic_overlap", db_path=fractal_db,
        )

        # Manually set child2 to claimed then synthesize it
        conn = get_fractal_connection(fractal_db)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE nodes SET status = 'claimed', owner = 'w1' WHERE id = ?",
            (child2["node_id"],),
        )
        conn.commit()

        await synthesize_node(
            graph_id=graph_id, node_id=child2["node_id"],
            synthesis_text="Child 2 synthesis", db_path=fractal_db,
        )

        # Root is 'answered' (from adding the answer node). Synthesize it.
        result = await synthesize_node(
            graph_id=graph_id, node_id=root_id,
            synthesis_text="Root synthesis combining children.",
            db_path=fractal_db,
        )

        assert result["node_id"] == root_id
        assert result["status"] == "synthesized"

    async def test_synthesize_node_children_not_done(self, fractal_db):
        """synthesize_node must raise ValueError when children are still open."""
        from spellbook.fractal.graph_ops import create_graph
        from spellbook.fractal.node_ops import add_node, synthesize_node

        graph = await create_graph(
            seed="Incomplete children test",
            intensity="explore",
            checkpoint_mode="autonomous",
            db_path=fractal_db,
        )
        graph_id = graph["graph_id"]
        root_id = graph["root_node_id"]

        # Add an answer to root to trigger auto-transition root -> answered
        await add_node(
            graph_id=graph_id, parent_id=root_id,
            node_type="answer", text="Root answer",
            db_path=fractal_db,
        )

        # Add a child question (will be open)
        await add_node(
            graph_id=graph_id, parent_id=root_id,
            node_type="question", text="Open child",
            db_path=fractal_db,
        )

        # Root is 'answered' but child question is still open
        with pytest.raises(ValueError, match="[Cc]hild|not.*done|not.*complete"):
            await synthesize_node(
                graph_id=graph_id, node_id=root_id,
                synthesis_text="Should fail",
                db_path=fractal_db,
            )

    async def test_synthesize_stores_synthesis_text(self, graph_with_root):
        """synthesize_node must store synthesis text in metadata under 'synthesis' key."""
        from spellbook.fractal.node_ops import add_node, claim_work, synthesize_node
        from spellbook.fractal.schema import get_fractal_connection

        node = await add_node(
            graph_id=graph_with_root["graph_id"],
            parent_id=graph_with_root["root_node_id"],
            node_type="question",
            text="Metadata synthesis test",
            metadata_json=json.dumps({"existing_key": "existing_value"}),
            db_path=graph_with_root["db_path"],
        )

        # Claim both open questions (root + new node)
        await claim_work(
            graph_id=graph_with_root["graph_id"],
            worker_id="worker-meta",
            db_path=graph_with_root["db_path"],
        )
        await claim_work(
            graph_id=graph_with_root["graph_id"],
            worker_id="worker-meta",
            db_path=graph_with_root["db_path"],
        )

        await synthesize_node(
            graph_id=graph_with_root["graph_id"],
            node_id=node["node_id"],
            synthesis_text="The synthesized insight.",
            db_path=graph_with_root["db_path"],
        )

        conn = get_fractal_connection(graph_with_root["db_path"])
        cursor = conn.cursor()
        cursor.execute(
            "SELECT metadata_json FROM nodes WHERE id = ?",
            (node["node_id"],),
        )
        stored = json.loads(cursor.fetchone()[0])
        assert stored["synthesis"] == "The synthesized insight."
        # Existing metadata must be preserved
        assert stored["existing_key"] == "existing_value"

    async def test_synthesize_node_wrong_status(self, graph_with_root):
        """synthesize_node on an open node (not answered/claimed) must raise ValueError."""
        from spellbook.fractal.node_ops import add_node, synthesize_node

        node = await add_node(
            graph_id=graph_with_root["graph_id"],
            parent_id=graph_with_root["root_node_id"],
            node_type="question",
            text="Still open question",
            db_path=graph_with_root["db_path"],
        )

        with pytest.raises(ValueError, match="[Ss]tatus"):
            await synthesize_node(
                graph_id=graph_with_root["graph_id"],
                node_id=node["node_id"],
                synthesis_text="Should fail",
                db_path=graph_with_root["db_path"],
            )


class TestAddNodeClaimedTransition:
    """Tests for add_node auto-transition from claimed to answered."""

    async def test_add_node_answer_transitions_claimed_parent(self, fractal_db):
        """Adding answer to claimed question must transition parent to answered."""
        from spellbook.fractal.graph_ops import create_graph
        from spellbook.fractal.node_ops import add_node, claim_work
        from spellbook.fractal.schema import get_fractal_connection

        # Use explore intensity (max_depth=4) to allow depth-2 nodes
        graph = await create_graph(
            seed="Claimed transition test",
            intensity="explore",
            checkpoint_mode="autonomous",
            db_path=fractal_db,
        )
        graph_id = graph["graph_id"]
        root_id = graph["root_node_id"]

        # Add a question node under root (depth 1)
        node = await add_node(
            graph_id=graph_id,
            parent_id=root_id,
            node_type="question",
            text="Claim then answer test",
            db_path=fractal_db,
        )

        # Claim both open questions (root and the new node)
        await claim_work(
            graph_id=graph_id,
            worker_id="worker-trans",
            db_path=fractal_db,
        )
        await claim_work(
            graph_id=graph_id,
            worker_id="worker-trans",
            db_path=fractal_db,
        )

        # Verify the question node is claimed
        conn = get_fractal_connection(fractal_db)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT status FROM nodes WHERE id = ?",
            (node["node_id"],),
        )
        assert cursor.fetchone()[0] == "claimed"

        # Add answer to the claimed question node (depth 2, within explore limit)
        await add_node(
            graph_id=graph_id,
            parent_id=node["node_id"],
            node_type="answer",
            text="Answer to claimed question",
            db_path=fractal_db,
        )

        # Verify the parent transitioned from claimed to answered
        cursor.execute(
            "SELECT status FROM nodes WHERE id = ?",
            (node["node_id"],),
        )
        assert cursor.fetchone()[0] == "answered"

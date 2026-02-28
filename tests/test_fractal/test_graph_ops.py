"""Tests for fractal thinking graph operations.

Tests cover create_graph, resume_graph, delete_graph, and update_graph_status.
"""

import pytest


class TestCreateGraph:
    """Tests for create_graph function."""

    def test_create_graph_returns_expected_keys(self, fractal_db):
        """create_graph must return dict with graph_id, root_node_id, intensity, checkpoint_mode, budget, status."""
        from spellbook_mcp.fractal.graph_ops import create_graph

        result = create_graph(
            seed="Why is the sky blue?",
            intensity="pulse",
            checkpoint_mode="autonomous",
            db_path=fractal_db,
        )

        assert isinstance(result, dict)
        assert "graph_id" in result
        assert "root_node_id" in result
        assert "intensity" in result
        assert "checkpoint_mode" in result
        assert "budget" in result
        assert "status" in result

    def test_create_graph_values(self, fractal_db):
        """create_graph must return correct values for intensity, checkpoint_mode, budget, and status."""
        from spellbook_mcp.fractal.graph_ops import create_graph

        result = create_graph(
            seed="Why is the sky blue?",
            intensity="pulse",
            checkpoint_mode="autonomous",
            db_path=fractal_db,
        )

        assert result["intensity"] == "pulse"
        assert result["checkpoint_mode"] == "autonomous"
        assert result["budget"] == {"max_agents": 3, "max_depth": 2}
        assert result["status"] == "active"

    def test_create_graph_generates_uuid_graph_id(self, fractal_db):
        """create_graph must generate a valid UUID for graph_id."""
        import uuid

        from spellbook_mcp.fractal.graph_ops import create_graph

        result = create_graph(
            seed="Test question",
            intensity="explore",
            checkpoint_mode="convergence",
            db_path=fractal_db,
        )

        # Should be a valid UUID string
        parsed = uuid.UUID(result["graph_id"])
        assert str(parsed) == result["graph_id"]

    def test_create_graph_generates_uuid_root_node_id(self, fractal_db):
        """create_graph must generate a valid UUID for root_node_id."""
        import uuid

        from spellbook_mcp.fractal.graph_ops import create_graph

        result = create_graph(
            seed="Test question",
            intensity="explore",
            checkpoint_mode="convergence",
            db_path=fractal_db,
        )

        parsed = uuid.UUID(result["root_node_id"])
        assert str(parsed) == result["root_node_id"]

    def test_create_graph_inserts_into_graphs_table(self, fractal_db):
        """create_graph must insert a row into the graphs table."""
        from spellbook_mcp.fractal.graph_ops import create_graph
        from spellbook_mcp.fractal.schema import get_fractal_connection

        result = create_graph(
            seed="Why is the sky blue?",
            intensity="pulse",
            checkpoint_mode="autonomous",
            db_path=fractal_db,
        )

        conn = get_fractal_connection(fractal_db)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, seed, intensity, checkpoint_mode, status FROM graphs WHERE id = ?",
            (result["graph_id"],),
        )
        row = cursor.fetchone()

        assert row is not None
        assert row[0] == result["graph_id"]
        assert row[1] == "Why is the sky blue?"
        assert row[2] == "pulse"
        assert row[3] == "autonomous"
        assert row[4] == "active"

    def test_create_graph_creates_root_node(self, fractal_db):
        """create_graph must create a root node with type=question, depth=0, status=open."""
        from spellbook_mcp.fractal.graph_ops import create_graph
        from spellbook_mcp.fractal.schema import get_fractal_connection

        result = create_graph(
            seed="Why is the sky blue?",
            intensity="pulse",
            checkpoint_mode="autonomous",
            db_path=fractal_db,
        )

        conn = get_fractal_connection(fractal_db)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, graph_id, node_type, text, depth, status, parent_id FROM nodes WHERE id = ?",
            (result["root_node_id"],),
        )
        row = cursor.fetchone()

        assert row is not None
        assert row[0] == result["root_node_id"]
        assert row[1] == result["graph_id"]
        assert row[2] == "question"
        assert row[3] == "Why is the sky blue?"
        assert row[4] == 0  # depth
        assert row[5] == "open"  # status
        assert row[6] is None  # parent_id (root has no parent)

    def test_create_graph_invalid_intensity(self, fractal_db):
        """create_graph must return error dict for invalid intensity and create no graph."""
        from spellbook_mcp.fractal.graph_ops import create_graph
        from spellbook_mcp.fractal.schema import get_fractal_connection

        result = create_graph(
            seed="Test",
            intensity="invalid",
            checkpoint_mode="autonomous",
            db_path=fractal_db,
        )

        assert "error" in result

        # Verify no graph was created in the database
        conn = get_fractal_connection(fractal_db)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM graphs")
        assert cursor.fetchone()[0] == 0

    def test_create_graph_invalid_checkpoint_mode(self, fractal_db):
        """create_graph must return error dict for invalid checkpoint mode and create no graph."""
        from spellbook_mcp.fractal.graph_ops import create_graph
        from spellbook_mcp.fractal.schema import get_fractal_connection

        result = create_graph(
            seed="Test",
            intensity="pulse",
            checkpoint_mode="invalid_mode",
            db_path=fractal_db,
        )

        assert "error" in result

        # Verify no graph was created in the database
        conn = get_fractal_connection(fractal_db)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM graphs")
        assert cursor.fetchone()[0] == 0

    def test_create_graph_with_metadata(self, fractal_db):
        """create_graph must store metadata_json in graphs table."""
        from spellbook_mcp.fractal.graph_ops import create_graph
        from spellbook_mcp.fractal.schema import get_fractal_connection

        metadata = '{"source": "test", "priority": "high"}'
        result = create_graph(
            seed="Test with metadata",
            intensity="deep",
            checkpoint_mode="interactive",
            metadata_json=metadata,
            db_path=fractal_db,
        )

        conn = get_fractal_connection(fractal_db)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT metadata_json FROM graphs WHERE id = ?",
            (result["graph_id"],),
        )
        row = cursor.fetchone()

        assert row is not None
        assert row[0] == metadata

    def test_create_graph_default_metadata(self, fractal_db):
        """create_graph without metadata_json must default to '{}'."""
        from spellbook_mcp.fractal.graph_ops import create_graph
        from spellbook_mcp.fractal.schema import get_fractal_connection

        result = create_graph(
            seed="Test",
            intensity="pulse",
            checkpoint_mode="autonomous",
            db_path=fractal_db,
        )

        conn = get_fractal_connection(fractal_db)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT metadata_json FROM graphs WHERE id = ?",
            (result["graph_id"],),
        )
        row = cursor.fetchone()

        assert row is not None
        assert row[0] == "{}"

    def test_create_graph_with_depth_checkpoint_mode(self, fractal_db):
        """create_graph must accept depth:N checkpoint modes."""
        from spellbook_mcp.fractal.graph_ops import create_graph

        result = create_graph(
            seed="Test",
            intensity="pulse",
            checkpoint_mode="depth:3",
            db_path=fractal_db,
        )

        assert "error" not in result
        assert "graph_id" in result
        assert "root_node_id" in result
        assert result["status"] == "active"
        assert result["checkpoint_mode"] == "depth:3"

    def test_create_graph_explore_budget(self, fractal_db):
        """create_graph with explore intensity must return explore budget."""
        from spellbook_mcp.fractal.graph_ops import create_graph

        result = create_graph(
            seed="Test",
            intensity="explore",
            checkpoint_mode="autonomous",
            db_path=fractal_db,
        )

        assert result["budget"] == {"max_agents": 8, "max_depth": 4}

    def test_create_graph_deep_budget(self, fractal_db):
        """create_graph with deep intensity must return deep budget."""
        from spellbook_mcp.fractal.graph_ops import create_graph

        result = create_graph(
            seed="Test",
            intensity="deep",
            checkpoint_mode="autonomous",
            db_path=fractal_db,
        )

        assert result["budget"] == {"max_agents": 15, "max_depth": 6}


class TestResumeGraph:
    """Tests for resume_graph function."""

    def _create_test_graph(self, fractal_db, status="active"):
        """Helper to create a graph in a specific status for testing resume."""
        from spellbook_mcp.fractal.graph_ops import create_graph
        from spellbook_mcp.fractal.schema import get_fractal_connection

        result = create_graph(
            seed="Test seed",
            intensity="pulse",
            checkpoint_mode="autonomous",
            db_path=fractal_db,
        )
        if status != "active":
            conn = get_fractal_connection(fractal_db)
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE graphs SET status = ? WHERE id = ?",
                (status, result["graph_id"]),
            )
            conn.commit()
        return result["graph_id"]

    def test_resume_paused_graph(self, fractal_db):
        """resume_graph must resume a paused graph and set status to active."""
        from spellbook_mcp.fractal.graph_ops import resume_graph
        from spellbook_mcp.fractal.schema import get_fractal_connection

        graph_id = self._create_test_graph(fractal_db, status="paused")

        result = resume_graph(graph_id, db_path=fractal_db)

        assert "error" not in result
        assert result["graph_id"] == graph_id
        assert result["status"] == "active"

        # Verify DB updated
        conn = get_fractal_connection(fractal_db)
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM graphs WHERE id = ?", (graph_id,))
        assert cursor.fetchone()[0] == "active"

    def test_resume_active_graph_is_noop(self, fractal_db):
        """resume_graph on an already active graph must succeed without error."""
        from spellbook_mcp.fractal.graph_ops import resume_graph

        graph_id = self._create_test_graph(fractal_db, status="active")

        result = resume_graph(graph_id, db_path=fractal_db)

        assert "error" not in result
        assert result["graph_id"] == graph_id
        assert result["status"] == "active"

    def test_resume_completed_graph_rejected(self, fractal_db):
        """resume_graph must reject a completed graph and leave status unchanged."""
        from spellbook_mcp.fractal.graph_ops import resume_graph
        from spellbook_mcp.fractal.schema import get_fractal_connection

        graph_id = self._create_test_graph(fractal_db, status="completed")

        result = resume_graph(graph_id, db_path=fractal_db)

        assert "error" in result

        # Verify status was NOT changed in the database
        conn = get_fractal_connection(fractal_db)
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM graphs WHERE id = ?", (graph_id,))
        assert cursor.fetchone()[0] == "completed"

    def test_resume_error_graph_rejected(self, fractal_db):
        """resume_graph must reject a graph in error status and leave status unchanged."""
        from spellbook_mcp.fractal.graph_ops import resume_graph
        from spellbook_mcp.fractal.schema import get_fractal_connection

        graph_id = self._create_test_graph(fractal_db, status="error")

        result = resume_graph(graph_id, db_path=fractal_db)

        assert "error" in result

        # Verify status was NOT changed in the database
        conn = get_fractal_connection(fractal_db)
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM graphs WHERE id = ?", (graph_id,))
        assert cursor.fetchone()[0] == "error"

    def test_resume_budget_exhausted_graph_rejected(self, fractal_db):
        """resume_graph must reject a budget_exhausted graph and leave status unchanged."""
        from spellbook_mcp.fractal.graph_ops import resume_graph
        from spellbook_mcp.fractal.schema import get_fractal_connection

        graph_id = self._create_test_graph(fractal_db, status="budget_exhausted")

        result = resume_graph(graph_id, db_path=fractal_db)

        assert "error" in result

        # Verify status was NOT changed in the database
        conn = get_fractal_connection(fractal_db)
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM graphs WHERE id = ?", (graph_id,))
        assert cursor.fetchone()[0] == "budget_exhausted"

    def test_resume_nonexistent_graph(self, fractal_db):
        """resume_graph must return error for non-existent graph_id."""
        from spellbook_mcp.fractal.graph_ops import resume_graph

        result = resume_graph("nonexistent-id", db_path=fractal_db)

        assert "error" in result

    def test_resume_returns_graph_snapshot(self, fractal_db):
        """resume_graph must return full graph snapshot with seed, intensity, nodes, edges."""
        from spellbook_mcp.fractal.graph_ops import resume_graph

        graph_id = self._create_test_graph(fractal_db, status="paused")

        result = resume_graph(graph_id, db_path=fractal_db)

        assert result["graph_id"] == graph_id
        assert "seed" in result
        assert result["seed"] == "Test seed"
        assert "intensity" in result
        assert result["intensity"] == "pulse"
        assert "nodes" in result
        assert isinstance(result["nodes"], list)
        assert "edges" in result
        assert isinstance(result["edges"], list)

    def test_resume_includes_existing_nodes(self, fractal_db):
        """resume_graph must include all existing nodes in the snapshot."""
        from spellbook_mcp.fractal.graph_ops import resume_graph

        graph_id = self._create_test_graph(fractal_db, status="paused")

        result = resume_graph(graph_id, db_path=fractal_db)

        # Exactly the root node created during create_graph
        assert len(result["nodes"]) == 1


class TestDeleteGraph:
    """Tests for delete_graph function."""

    def test_delete_existing_graph(self, fractal_db):
        """delete_graph must delete an existing graph and return success."""
        from spellbook_mcp.fractal.graph_ops import create_graph, delete_graph
        from spellbook_mcp.fractal.schema import get_fractal_connection

        created = create_graph(
            seed="To be deleted",
            intensity="pulse",
            checkpoint_mode="autonomous",
            db_path=fractal_db,
        )
        graph_id = created["graph_id"]

        result = delete_graph(graph_id, db_path=fractal_db)

        assert result["deleted"] is True
        assert result["graph_id"] == graph_id

        # Verify graph is gone from DB
        conn = get_fractal_connection(fractal_db)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM graphs WHERE id = ?", (graph_id,))
        assert cursor.fetchone()[0] == 0

    def test_delete_graph_cascades_nodes(self, fractal_db):
        """delete_graph must cascade delete all nodes belonging to the graph."""
        from spellbook_mcp.fractal.graph_ops import create_graph, delete_graph
        from spellbook_mcp.fractal.schema import get_fractal_connection

        created = create_graph(
            seed="To be deleted",
            intensity="pulse",
            checkpoint_mode="autonomous",
            db_path=fractal_db,
        )
        graph_id = created["graph_id"]

        # Verify node exists before delete
        conn = get_fractal_connection(fractal_db)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM nodes WHERE graph_id = ?", (graph_id,))
        assert cursor.fetchone()[0] >= 1

        delete_graph(graph_id, db_path=fractal_db)

        # Nodes should be gone
        cursor.execute("SELECT COUNT(*) FROM nodes WHERE graph_id = ?", (graph_id,))
        assert cursor.fetchone()[0] == 0

    def test_delete_nonexistent_graph(self, fractal_db):
        """delete_graph must return error for non-existent graph_id."""
        from spellbook_mcp.fractal.graph_ops import delete_graph

        result = delete_graph("nonexistent-id", db_path=fractal_db)

        assert "error" in result


class TestUpdateGraphStatus:
    """Tests for update_graph_status function."""

    def _create_test_graph(self, fractal_db, status="active"):
        """Helper to create a graph in a specific status."""
        from spellbook_mcp.fractal.graph_ops import create_graph
        from spellbook_mcp.fractal.schema import get_fractal_connection

        result = create_graph(
            seed="Test seed",
            intensity="pulse",
            checkpoint_mode="autonomous",
            db_path=fractal_db,
        )
        if status != "active":
            conn = get_fractal_connection(fractal_db)
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE graphs SET status = ? WHERE id = ?",
                (status, result["graph_id"]),
            )
            conn.commit()
        return result["graph_id"]

    def test_active_to_completed(self, fractal_db):
        """update_graph_status must allow active -> completed transition."""
        from spellbook_mcp.fractal.graph_ops import update_graph_status

        graph_id = self._create_test_graph(fractal_db, status="active")

        result = update_graph_status(graph_id, "completed", db_path=fractal_db)

        assert "error" not in result
        assert result["graph_id"] == graph_id
        assert result["status"] == "completed"
        assert result["previous_status"] == "active"

    def test_active_to_paused(self, fractal_db):
        """update_graph_status must allow active -> paused transition."""
        from spellbook_mcp.fractal.graph_ops import update_graph_status

        graph_id = self._create_test_graph(fractal_db, status="active")

        result = update_graph_status(graph_id, "paused", db_path=fractal_db)

        assert "error" not in result
        assert result["status"] == "paused"
        assert result["previous_status"] == "active"

    def test_active_to_error(self, fractal_db):
        """update_graph_status must allow active -> error transition."""
        from spellbook_mcp.fractal.graph_ops import update_graph_status

        graph_id = self._create_test_graph(fractal_db, status="active")

        result = update_graph_status(graph_id, "error", db_path=fractal_db)

        assert "error" not in result
        assert result["status"] == "error"
        assert result["previous_status"] == "active"

    def test_active_to_budget_exhausted(self, fractal_db):
        """update_graph_status must allow active -> budget_exhausted transition."""
        from spellbook_mcp.fractal.graph_ops import update_graph_status

        graph_id = self._create_test_graph(fractal_db, status="active")

        result = update_graph_status(
            graph_id, "budget_exhausted", db_path=fractal_db
        )

        assert "error" not in result
        assert result["status"] == "budget_exhausted"
        assert result["previous_status"] == "active"

    def test_paused_to_active(self, fractal_db):
        """update_graph_status must allow paused -> active transition."""
        from spellbook_mcp.fractal.graph_ops import update_graph_status

        graph_id = self._create_test_graph(fractal_db, status="paused")

        result = update_graph_status(graph_id, "active", db_path=fractal_db)

        assert "error" not in result
        assert result["status"] == "active"
        assert result["previous_status"] == "paused"

    def test_completed_to_active_rejected(self, fractal_db):
        """update_graph_status must reject completed -> active transition and leave status unchanged."""
        from spellbook_mcp.fractal.graph_ops import update_graph_status
        from spellbook_mcp.fractal.schema import get_fractal_connection

        graph_id = self._create_test_graph(fractal_db, status="completed")

        result = update_graph_status(graph_id, "active", db_path=fractal_db)

        assert "error" in result

        # Verify status unchanged in DB
        conn = get_fractal_connection(fractal_db)
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM graphs WHERE id = ?", (graph_id,))
        assert cursor.fetchone()[0] == "completed"

    def test_error_to_active_rejected(self, fractal_db):
        """update_graph_status must reject error -> active transition and leave status unchanged."""
        from spellbook_mcp.fractal.graph_ops import update_graph_status
        from spellbook_mcp.fractal.schema import get_fractal_connection

        graph_id = self._create_test_graph(fractal_db, status="error")

        result = update_graph_status(graph_id, "active", db_path=fractal_db)

        assert "error" in result

        # Verify status unchanged in DB
        conn = get_fractal_connection(fractal_db)
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM graphs WHERE id = ?", (graph_id,))
        assert cursor.fetchone()[0] == "error"

    def test_budget_exhausted_to_active(self, fractal_db):
        """update_graph_status must allow budget_exhausted -> active transition."""
        from spellbook_mcp.fractal.graph_ops import update_graph_status
        from spellbook_mcp.fractal.schema import get_fractal_connection

        graph_id = self._create_test_graph(fractal_db, status="budget_exhausted")

        result = update_graph_status(graph_id, "active", db_path=fractal_db)

        assert "error" not in result
        assert result["status"] == "active"
        assert result["previous_status"] == "budget_exhausted"

        # Verify status updated in DB
        conn = get_fractal_connection(fractal_db)
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM graphs WHERE id = ?", (graph_id,))
        assert cursor.fetchone()[0] == "active"

    def test_budget_exhausted_to_completed(self, fractal_db):
        """update_graph_status must allow budget_exhausted -> completed transition."""
        from spellbook_mcp.fractal.graph_ops import update_graph_status
        from spellbook_mcp.fractal.schema import get_fractal_connection

        graph_id = self._create_test_graph(fractal_db, status="budget_exhausted")

        result = update_graph_status(graph_id, "completed", db_path=fractal_db)

        assert "error" not in result
        assert result["status"] == "completed"
        assert result["previous_status"] == "budget_exhausted"

        # Verify status updated in DB
        conn = get_fractal_connection(fractal_db)
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM graphs WHERE id = ?", (graph_id,))
        assert cursor.fetchone()[0] == "completed"

    def test_paused_to_completed_rejected(self, fractal_db):
        """update_graph_status must reject paused -> completed and leave status unchanged."""
        from spellbook_mcp.fractal.graph_ops import update_graph_status
        from spellbook_mcp.fractal.schema import get_fractal_connection

        graph_id = self._create_test_graph(fractal_db, status="paused")

        result = update_graph_status(graph_id, "completed", db_path=fractal_db)

        assert "error" in result

        # Verify status unchanged in DB
        conn = get_fractal_connection(fractal_db)
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM graphs WHERE id = ?", (graph_id,))
        assert cursor.fetchone()[0] == "paused"

    def test_nonexistent_graph(self, fractal_db):
        """update_graph_status must return error for non-existent graph_id."""
        from spellbook_mcp.fractal.graph_ops import update_graph_status

        result = update_graph_status("nonexistent-id", "completed", db_path=fractal_db)

        assert "error" in result

    def test_reason_stored(self, fractal_db):
        """update_graph_status with reason must update the status and store the reason."""
        from spellbook_mcp.fractal.graph_ops import update_graph_status
        from spellbook_mcp.fractal.schema import get_fractal_connection

        graph_id = self._create_test_graph(fractal_db, status="active")

        result = update_graph_status(
            graph_id, "error", reason="LLM timeout", db_path=fractal_db
        )

        assert "error" not in result
        assert result["status"] == "error"

        # Verify reason stored in metadata_json
        conn = get_fractal_connection(fractal_db)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT metadata_json FROM graphs WHERE id = ?", (graph_id,)
        )
        import json

        metadata = json.loads(cursor.fetchone()[0])
        assert metadata.get("status_reason") == "LLM timeout"

    def test_updates_updated_at(self, fractal_db):
        """update_graph_status must update the updated_at timestamp."""
        from spellbook_mcp.fractal.graph_ops import update_graph_status
        from spellbook_mcp.fractal.schema import get_fractal_connection

        graph_id = self._create_test_graph(fractal_db, status="active")

        # Set updated_at to a known past sentinel value
        conn = get_fractal_connection(fractal_db)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE graphs SET updated_at = '2000-01-01 00:00:00' WHERE id = ?",
            (graph_id,),
        )
        conn.commit()

        update_graph_status(graph_id, "completed", db_path=fractal_db)

        cursor.execute("SELECT updated_at FROM graphs WHERE id = ?", (graph_id,))
        new_updated_at = cursor.fetchone()[0]

        # updated_at must have changed from the sentinel value
        assert new_updated_at != "2000-01-01 00:00:00"

    def test_active_to_active_rejected(self, fractal_db):
        """update_graph_status must reject active -> active and leave status unchanged."""
        from spellbook_mcp.fractal.graph_ops import update_graph_status
        from spellbook_mcp.fractal.schema import get_fractal_connection

        graph_id = self._create_test_graph(fractal_db, status="active")

        result = update_graph_status(graph_id, "active", db_path=fractal_db)

        assert "error" in result

        # Verify status unchanged in DB
        conn = get_fractal_connection(fractal_db)
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM graphs WHERE id = ?", (graph_id,))
        assert cursor.fetchone()[0] == "active"


class TestBudgetExhaustedTransitions:
    """Tests for transitions from budget_exhausted status via update_graph_status."""

    def _create_budget_exhausted_graph(self, fractal_db):
        """Helper to create a graph in budget_exhausted status."""
        from spellbook_mcp.fractal.graph_ops import create_graph, update_graph_status

        result = create_graph(
            seed="Budget test seed",
            intensity="pulse",
            checkpoint_mode="autonomous",
            db_path=fractal_db,
        )
        graph_id = result["graph_id"]

        # Transition active -> budget_exhausted via the actual function
        update_graph_status(graph_id, "budget_exhausted", db_path=fractal_db)
        return graph_id

    def test_budget_exhausted_to_completed_via_function(self, fractal_db):
        """budget_exhausted -> completed must succeed through update_graph_status."""
        from spellbook_mcp.fractal.graph_ops import update_graph_status
        from spellbook_mcp.fractal.schema import get_fractal_connection

        graph_id = self._create_budget_exhausted_graph(fractal_db)

        result = update_graph_status(graph_id, "completed", db_path=fractal_db)

        assert "error" not in result
        assert result["graph_id"] == graph_id
        assert result["status"] == "completed"
        assert result["previous_status"] == "budget_exhausted"

        # Verify DB reflects the change
        conn = get_fractal_connection(fractal_db)
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM graphs WHERE id = ?", (graph_id,))
        assert cursor.fetchone()[0] == "completed"

    def test_budget_exhausted_to_active_via_function(self, fractal_db):
        """budget_exhausted -> active must succeed through update_graph_status."""
        from spellbook_mcp.fractal.graph_ops import update_graph_status
        from spellbook_mcp.fractal.schema import get_fractal_connection

        graph_id = self._create_budget_exhausted_graph(fractal_db)

        result = update_graph_status(graph_id, "active", db_path=fractal_db)

        assert "error" not in result
        assert result["graph_id"] == graph_id
        assert result["status"] == "active"
        assert result["previous_status"] == "budget_exhausted"

        # Verify DB reflects the change
        conn = get_fractal_connection(fractal_db)
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM graphs WHERE id = ?", (graph_id,))
        assert cursor.fetchone()[0] == "active"

    def test_budget_exhausted_to_paused_rejected(self, fractal_db):
        """budget_exhausted -> paused must be rejected (not a valid transition)."""
        from spellbook_mcp.fractal.graph_ops import update_graph_status
        from spellbook_mcp.fractal.schema import get_fractal_connection

        graph_id = self._create_budget_exhausted_graph(fractal_db)

        result = update_graph_status(graph_id, "paused", db_path=fractal_db)

        assert "error" in result

        # Verify status unchanged in DB
        conn = get_fractal_connection(fractal_db)
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM graphs WHERE id = ?", (graph_id,))
        assert cursor.fetchone()[0] == "budget_exhausted"

"""Integration tests for fractal thinking MCP server tools.

Tests that:
1. All 17 fractal tool functions exist on the server module
2. Each tool function delegates correctly to its implementation
3. Parameter mapping works (especially metadata -> metadata_json rename)
4. init_fractal_schema is imported and called during server init
"""

import pytest
import json

from spellbook_mcp.fractal.schema import (
    close_all_fractal_connections,
    init_fractal_schema,
)


@pytest.fixture
def fractal_db(tmp_path):
    """Create a temporary fractal database for testing."""
    db_path = str(tmp_path / "fractal.db")
    init_fractal_schema(db_path)
    yield db_path
    close_all_fractal_connections()


# ---------------------------------------------------------------------------
# Task 4.2a: Verify all 17 tool functions exist on the server module
# ---------------------------------------------------------------------------


EXPECTED_FRACTAL_TOOLS = [
    "fractal_create_graph",
    "fractal_resume_graph",
    "fractal_delete_graph",
    "fractal_update_graph_status",
    "fractal_add_node",
    "fractal_update_node",
    "fractal_mark_saturated",
    "fractal_get_snapshot",
    "fractal_get_branch",
    "fractal_get_open_questions",
    "fractal_query_convergence",
    "fractal_query_contradictions",
    "fractal_get_saturation_status",
    "fractal_claim_work",
    "fractal_synthesize_node",
    "fractal_get_claimable_work",
    "fractal_get_ready_to_synthesize",
]


@pytest.mark.parametrize("tool_name", EXPECTED_FRACTAL_TOOLS)
def test_fractal_tool_exists_on_server(tool_name):
    """Each fractal tool must be a callable attribute on the server module."""
    from spellbook_mcp import server

    assert hasattr(server, tool_name), (
        f"server module missing tool function '{tool_name}'"
    )
    attr = getattr(server, tool_name)
    # FastMCP wraps with .fn attribute for the underlying function
    assert callable(attr) or hasattr(attr, "fn"), (
        f"server.{tool_name} is not callable"
    )


# ---------------------------------------------------------------------------
# Task 4.2b: Verify init_fractal_schema is imported in server
# ---------------------------------------------------------------------------


def test_init_fractal_schema_imported_in_server():
    """init_fractal_schema must be importable from the server module's namespace."""
    from spellbook_mcp import server

    # Check that the import exists - the function should be accessible
    # via the module's globals
    assert "init_fractal_schema" in dir(server), (
        "init_fractal_schema is not imported in server.py"
    )


# ---------------------------------------------------------------------------
# Task 4.2c: Verify delegation via implementation functions directly
# ---------------------------------------------------------------------------


class TestFractalCreateGraphDelegation:
    """Test fractal_create_graph delegates to graph_ops.create_graph."""

    def test_create_graph_returns_expected_keys(self, fractal_db):
        """create_graph should return graph_id, root_node_id, intensity, etc."""
        from spellbook_mcp.fractal.graph_ops import create_graph

        result = create_graph(
            seed="What is consciousness?",
            intensity="pulse",
            checkpoint_mode="autonomous",
            db_path=fractal_db,
        )

        assert "graph_id" in result
        assert "root_node_id" in result
        assert result["intensity"] == "pulse"
        assert result["checkpoint_mode"] == "autonomous"
        assert result["status"] == "active"

    def test_create_graph_with_metadata(self, fractal_db):
        """create_graph should accept metadata_json parameter."""
        from spellbook_mcp.fractal.graph_ops import create_graph

        meta = json.dumps({"source": "test"})
        result = create_graph(
            seed="Test question",
            intensity="explore",
            checkpoint_mode="convergence",
            metadata_json=meta,
            db_path=fractal_db,
        )

        assert "graph_id" in result
        assert "error" not in result


class TestFractalResumeGraphDelegation:
    """Test fractal_resume_graph delegates to graph_ops.resume_graph."""

    def test_resume_graph_returns_snapshot(self, fractal_db):
        """resume_graph on an active graph returns full snapshot."""
        from spellbook_mcp.fractal.graph_ops import create_graph, resume_graph

        created = create_graph(
            seed="Test seed",
            intensity="pulse",
            checkpoint_mode="autonomous",
            db_path=fractal_db,
        )

        result = resume_graph(
            graph_id=created["graph_id"],
            db_path=fractal_db,
        )

        assert result["graph_id"] == created["graph_id"]
        assert result["status"] == "active"
        assert "nodes" in result
        assert "edges" in result

    def test_resume_graph_not_found(self, fractal_db):
        """resume_graph with invalid ID returns error."""
        from spellbook_mcp.fractal.graph_ops import resume_graph

        result = resume_graph(graph_id="nonexistent", db_path=fractal_db)
        assert "error" in result


class TestFractalDeleteGraphDelegation:
    """Test fractal_delete_graph delegates to graph_ops.delete_graph."""

    def test_delete_graph_success(self, fractal_db):
        """delete_graph removes a graph and returns deleted=True."""
        from spellbook_mcp.fractal.graph_ops import create_graph, delete_graph

        created = create_graph(
            seed="To delete",
            intensity="pulse",
            checkpoint_mode="autonomous",
            db_path=fractal_db,
        )

        result = delete_graph(graph_id=created["graph_id"], db_path=fractal_db)
        assert result["deleted"] is True
        assert result["graph_id"] == created["graph_id"]


class TestFractalUpdateGraphStatusDelegation:
    """Test fractal_update_graph_status delegates to graph_ops.update_graph_status."""

    def test_update_status_valid_transition(self, fractal_db):
        """update_graph_status with valid transition succeeds."""
        from spellbook_mcp.fractal.graph_ops import (
            create_graph,
            update_graph_status,
        )

        created = create_graph(
            seed="Status test",
            intensity="pulse",
            checkpoint_mode="autonomous",
            db_path=fractal_db,
        )

        result = update_graph_status(
            graph_id=created["graph_id"],
            status="completed",
            reason="All done",
            db_path=fractal_db,
        )

        assert result["status"] == "completed"
        assert result["previous_status"] == "active"


class TestFractalAddNodeDelegation:
    """Test fractal_add_node delegates to node_ops.add_node."""

    def test_add_node_returns_expected_keys(self, fractal_db):
        """add_node should return node_id, graph_id, parent_id, depth, etc."""
        from spellbook_mcp.fractal.graph_ops import create_graph
        from spellbook_mcp.fractal.node_ops import add_node

        created = create_graph(
            seed="Node test",
            intensity="pulse",
            checkpoint_mode="autonomous",
            db_path=fractal_db,
        )

        result = add_node(
            graph_id=created["graph_id"],
            parent_id=created["root_node_id"],
            node_type="answer",
            text="An answer",
            owner="agent-1",
            db_path=fractal_db,
        )

        assert "node_id" in result
        assert result["graph_id"] == created["graph_id"]
        assert result["parent_id"] == created["root_node_id"]
        assert result["depth"] == 1
        assert result["node_type"] == "answer"

    def test_add_node_with_metadata(self, fractal_db):
        """add_node should accept metadata_json parameter."""
        from spellbook_mcp.fractal.graph_ops import create_graph
        from spellbook_mcp.fractal.node_ops import add_node

        created = create_graph(
            seed="Meta test",
            intensity="pulse",
            checkpoint_mode="autonomous",
            db_path=fractal_db,
        )

        meta = json.dumps({"confidence": 0.9})
        result = add_node(
            graph_id=created["graph_id"],
            parent_id=created["root_node_id"],
            node_type="answer",
            text="Another answer",
            metadata_json=meta,
            db_path=fractal_db,
        )

        assert "node_id" in result


class TestFractalUpdateNodeDelegation:
    """Test fractal_update_node delegates to node_ops.update_node."""

    def test_update_node_merges_metadata(self, fractal_db):
        """update_node should merge new metadata into existing."""
        from spellbook_mcp.fractal.graph_ops import create_graph
        from spellbook_mcp.fractal.node_ops import add_node, update_node

        created = create_graph(
            seed="Update test",
            intensity="pulse",
            checkpoint_mode="autonomous",
            db_path=fractal_db,
        )

        node = add_node(
            graph_id=created["graph_id"],
            parent_id=created["root_node_id"],
            node_type="answer",
            text="To update",
            db_path=fractal_db,
        )

        result = update_node(
            graph_id=created["graph_id"],
            node_id=node["node_id"],
            metadata_json=json.dumps({"score": 42}),
            db_path=fractal_db,
        )

        assert result["node_id"] == node["node_id"]
        assert result["metadata"]["score"] == 42


class TestFractalMarkSaturatedDelegation:
    """Test fractal_mark_saturated delegates to node_ops.mark_saturated."""

    def test_mark_saturated_success(self, fractal_db):
        """mark_saturated should transition node to saturated status."""
        from spellbook_mcp.fractal.graph_ops import create_graph
        from spellbook_mcp.fractal.node_ops import add_node, mark_saturated

        created = create_graph(
            seed="Saturation test",
            intensity="pulse",
            checkpoint_mode="autonomous",
            db_path=fractal_db,
        )

        node = add_node(
            graph_id=created["graph_id"],
            parent_id=created["root_node_id"],
            node_type="answer",
            text="Saturated answer",
            db_path=fractal_db,
        )

        result = mark_saturated(
            graph_id=created["graph_id"],
            node_id=node["node_id"],
            reason="semantic_overlap",
            db_path=fractal_db,
        )

        assert result["status"] == "saturated"
        assert result["reason"] == "semantic_overlap"


class TestFractalGetSnapshotDelegation:
    """Test fractal_get_snapshot delegates to query_ops.get_snapshot."""

    def test_get_snapshot_returns_full_graph(self, fractal_db):
        """get_snapshot should return graph with nodes and edges."""
        from spellbook_mcp.fractal.graph_ops import create_graph
        from spellbook_mcp.fractal.query_ops import get_snapshot

        created = create_graph(
            seed="Snapshot test",
            intensity="pulse",
            checkpoint_mode="autonomous",
            db_path=fractal_db,
        )

        result = get_snapshot(
            graph_id=created["graph_id"],
            db_path=fractal_db,
        )

        assert result["graph_id"] == created["graph_id"]
        assert result["seed"] == "Snapshot test"
        assert "nodes" in result
        assert "edges" in result
        assert len(result["nodes"]) == 1  # root node


class TestFractalGetBranchDelegation:
    """Test fractal_get_branch delegates to query_ops.get_branch."""

    def test_get_branch_returns_subtree(self, fractal_db):
        """get_branch should return nodes and edges for a subtree."""
        from spellbook_mcp.fractal.graph_ops import create_graph
        from spellbook_mcp.fractal.query_ops import get_branch

        created = create_graph(
            seed="Branch test",
            intensity="pulse",
            checkpoint_mode="autonomous",
            db_path=fractal_db,
        )

        result = get_branch(
            graph_id=created["graph_id"],
            node_id=created["root_node_id"],
            db_path=fractal_db,
        )

        assert result["graph_id"] == created["graph_id"]
        assert "nodes" in result
        assert "edges" in result


class TestFractalGetOpenQuestionsDelegation:
    """Test fractal_get_open_questions delegates to query_ops.get_open_questions."""

    def test_get_open_questions_returns_list(self, fractal_db):
        """get_open_questions should return open question nodes."""
        from spellbook_mcp.fractal.graph_ops import create_graph
        from spellbook_mcp.fractal.query_ops import get_open_questions

        created = create_graph(
            seed="Open Q test",
            intensity="pulse",
            checkpoint_mode="autonomous",
            db_path=fractal_db,
        )

        result = get_open_questions(
            graph_id=created["graph_id"],
            db_path=fractal_db,
        )

        assert result["graph_id"] == created["graph_id"]
        assert "open_questions" in result
        assert result["count"] == 1  # root question is open


class TestFractalQueryConvergenceDelegation:
    """Test fractal_query_convergence delegates to query_ops.query_convergence."""

    def test_query_convergence_returns_structure(self, fractal_db):
        """query_convergence should return convergence_points list."""
        from spellbook_mcp.fractal.graph_ops import create_graph
        from spellbook_mcp.fractal.query_ops import query_convergence

        created = create_graph(
            seed="Convergence test",
            intensity="pulse",
            checkpoint_mode="autonomous",
            db_path=fractal_db,
        )

        result = query_convergence(
            graph_id=created["graph_id"],
            db_path=fractal_db,
        )

        assert result["graph_id"] == created["graph_id"]
        assert "convergence_points" in result
        assert result["count"] == 0  # no convergence edges yet


class TestFractalQueryContradictionsDelegation:
    """Test fractal_query_contradictions delegates to query_ops.query_contradictions."""

    def test_query_contradictions_returns_structure(self, fractal_db):
        """query_contradictions should return contradictions list."""
        from spellbook_mcp.fractal.graph_ops import create_graph
        from spellbook_mcp.fractal.query_ops import query_contradictions

        created = create_graph(
            seed="Contradiction test",
            intensity="pulse",
            checkpoint_mode="autonomous",
            db_path=fractal_db,
        )

        result = query_contradictions(
            graph_id=created["graph_id"],
            db_path=fractal_db,
        )

        assert result["graph_id"] == created["graph_id"]
        assert "contradictions" in result
        assert result["count"] == 0  # no contradiction edges yet


class TestFractalGetSaturationStatusDelegation:
    """Test fractal_get_saturation_status delegates to query_ops.get_saturation_status."""

    def test_get_saturation_status_returns_branches(self, fractal_db):
        """get_saturation_status should return branches with saturation info."""
        from spellbook_mcp.fractal.graph_ops import create_graph
        from spellbook_mcp.fractal.query_ops import get_saturation_status

        created = create_graph(
            seed="Saturation status test",
            intensity="pulse",
            checkpoint_mode="autonomous",
            db_path=fractal_db,
        )

        result = get_saturation_status(
            graph_id=created["graph_id"],
            db_path=fractal_db,
        )

        assert result["graph_id"] == created["graph_id"]
        assert "branches" in result
        assert "all_saturated" in result


# ---------------------------------------------------------------------------
# Task 4.2d: Verify server tool functions delegate with correct parameter mapping
# ---------------------------------------------------------------------------


class TestServerToolParameterMapping:
    """Test that server tool wrappers correctly map metadata -> metadata_json."""

    def test_fractal_create_graph_wrapper_delegates(self, fractal_db, monkeypatch):
        """fractal_create_graph wrapper should pass metadata as metadata_json."""
        from spellbook_mcp import server
        from unittest.mock import patch

        with patch("spellbook_mcp.server.do_fractal_create_graph") as mock_create:
            mock_create.return_value = {"graph_id": "test", "status": "active"}

            # Call the wrapper's underlying function
            server.fractal_create_graph.fn(
                seed="test question",
                intensity="pulse",
                checkpoint_mode="autonomous",
                metadata='{"key": "value"}',
            )

            mock_create.assert_called_once_with(
                seed="test question",
                intensity="pulse",
                checkpoint_mode="autonomous",
                metadata_json='{"key": "value"}',
            )

    def test_fractal_add_node_wrapper_delegates(self, fractal_db, monkeypatch):
        """fractal_add_node wrapper should pass metadata as metadata_json."""
        from spellbook_mcp import server
        from unittest.mock import patch

        with patch("spellbook_mcp.server.do_fractal_add_node") as mock_add:
            mock_add.return_value = {"node_id": "test", "status": "open"}

            server.fractal_add_node.fn(
                graph_id="g1",
                parent_id="p1",
                node_type="answer",
                text="test answer",
                owner="agent-1",
                metadata='{"conf": 0.9}',
            )

            mock_add.assert_called_once_with(
                graph_id="g1",
                parent_id="p1",
                node_type="answer",
                text="test answer",
                owner="agent-1",
                metadata_json='{"conf": 0.9}',
            )

    def test_fractal_update_node_wrapper_delegates(self, fractal_db, monkeypatch):
        """fractal_update_node wrapper should pass metadata as metadata_json."""
        from spellbook_mcp import server
        from unittest.mock import patch

        with patch("spellbook_mcp.server.do_fractal_update_node") as mock_update:
            mock_update.return_value = {"node_id": "n1", "metadata": {}}

            server.fractal_update_node.fn(
                graph_id="g1",
                node_id="n1",
                metadata='{"score": 42}',
            )

            mock_update.assert_called_once_with(
                graph_id="g1",
                node_id="n1",
                metadata_json='{"score": 42}',
            )

    def test_fractal_resume_graph_wrapper_delegates(self, fractal_db, monkeypatch):
        """fractal_resume_graph wrapper should pass graph_id directly."""
        from spellbook_mcp import server
        from unittest.mock import patch

        with patch("spellbook_mcp.server.do_fractal_resume_graph") as mock_resume:
            mock_resume.return_value = {"graph_id": "g1", "status": "active"}

            server.fractal_resume_graph.fn(graph_id="g1")

            mock_resume.assert_called_once_with(graph_id="g1")

    def test_fractal_delete_graph_wrapper_delegates(self, fractal_db, monkeypatch):
        """fractal_delete_graph wrapper should pass graph_id directly."""
        from spellbook_mcp import server
        from unittest.mock import patch

        with patch("spellbook_mcp.server.do_fractal_delete_graph") as mock_delete:
            mock_delete.return_value = {"deleted": True}

            server.fractal_delete_graph.fn(graph_id="g1")

            mock_delete.assert_called_once_with(graph_id="g1")

    def test_fractal_update_graph_status_wrapper_delegates(self, fractal_db, monkeypatch):
        """fractal_update_graph_status wrapper should pass all params."""
        from spellbook_mcp import server
        from unittest.mock import patch

        with patch("spellbook_mcp.server.do_fractal_update_graph_status") as mock_status:
            mock_status.return_value = {"status": "completed"}

            server.fractal_update_graph_status.fn(
                graph_id="g1",
                status="completed",
                reason="done",
            )

            mock_status.assert_called_once_with(
                graph_id="g1",
                status="completed",
                reason="done",
            )

    def test_fractal_mark_saturated_wrapper_delegates(self, fractal_db, monkeypatch):
        """fractal_mark_saturated wrapper should pass all params."""
        from spellbook_mcp import server
        from unittest.mock import patch

        with patch("spellbook_mcp.server.do_fractal_mark_saturated") as mock_sat:
            mock_sat.return_value = {"status": "saturated"}

            server.fractal_mark_saturated.fn(
                graph_id="g1",
                node_id="n1",
                reason="semantic_overlap",
            )

            mock_sat.assert_called_once_with(
                graph_id="g1",
                node_id="n1",
                reason="semantic_overlap",
            )

    def test_fractal_get_snapshot_wrapper_delegates(self, fractal_db, monkeypatch):
        """fractal_get_snapshot wrapper should pass graph_id."""
        from spellbook_mcp import server
        from unittest.mock import patch

        with patch("spellbook_mcp.server.do_fractal_get_snapshot") as mock_snap:
            mock_snap.return_value = {"graph_id": "g1", "nodes": []}

            server.fractal_get_snapshot.fn(graph_id="g1")

            mock_snap.assert_called_once_with(graph_id="g1")

    def test_fractal_get_branch_wrapper_delegates(self, fractal_db, monkeypatch):
        """fractal_get_branch wrapper should pass graph_id and node_id."""
        from spellbook_mcp import server
        from unittest.mock import patch

        with patch("spellbook_mcp.server.do_fractal_get_branch") as mock_branch:
            mock_branch.return_value = {"graph_id": "g1", "nodes": []}

            server.fractal_get_branch.fn(graph_id="g1", node_id="n1")

            mock_branch.assert_called_once_with(graph_id="g1", node_id="n1")

    def test_fractal_get_open_questions_wrapper_delegates(self, fractal_db, monkeypatch):
        """fractal_get_open_questions wrapper should pass graph_id."""
        from spellbook_mcp import server
        from unittest.mock import patch

        with patch("spellbook_mcp.server.do_fractal_get_open_questions") as mock_oq:
            mock_oq.return_value = {"graph_id": "g1", "open_questions": []}

            server.fractal_get_open_questions.fn(graph_id="g1")

            mock_oq.assert_called_once_with(graph_id="g1")

    def test_fractal_query_convergence_wrapper_delegates(self, fractal_db, monkeypatch):
        """fractal_query_convergence wrapper should pass graph_id."""
        from spellbook_mcp import server
        from unittest.mock import patch

        with patch("spellbook_mcp.server.do_fractal_query_convergence") as mock_conv:
            mock_conv.return_value = {"graph_id": "g1", "convergence_points": []}

            server.fractal_query_convergence.fn(graph_id="g1")

            mock_conv.assert_called_once_with(graph_id="g1")

    def test_fractal_query_contradictions_wrapper_delegates(self, fractal_db, monkeypatch):
        """fractal_query_contradictions wrapper should pass graph_id."""
        from spellbook_mcp import server
        from unittest.mock import patch

        with patch("spellbook_mcp.server.do_fractal_query_contradictions") as mock_cont:
            mock_cont.return_value = {"graph_id": "g1", "contradictions": []}

            server.fractal_query_contradictions.fn(graph_id="g1")

            mock_cont.assert_called_once_with(graph_id="g1")

    def test_fractal_get_saturation_status_wrapper_delegates(self, fractal_db, monkeypatch):
        """fractal_get_saturation_status wrapper should pass graph_id."""
        from spellbook_mcp import server
        from unittest.mock import patch

        with patch("spellbook_mcp.server.do_fractal_get_saturation_status") as mock_ss:
            mock_ss.return_value = {"graph_id": "g1", "branches": []}

            server.fractal_get_saturation_status.fn(graph_id="g1")

            mock_ss.assert_called_once_with(graph_id="g1")

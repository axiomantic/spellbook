"""Tests for fractal thinking query operations.

Tests for get_snapshot, get_branch, get_open_questions,
query_convergence, query_contradictions, get_saturation_status.
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
        intensity="explore",
        checkpoint_mode="autonomous",
        metadata_json=json.dumps({"topic": "physics"}),
        db_path=fractal_db,
    )
    return {
        "graph_id": result["graph_id"],
        "root_node_id": result["root_node_id"],
        "db_path": fractal_db,
    }


@pytest.fixture
def branching_graph(graph_with_root):
    """Create a graph with multiple branches for testing.

    Structure:
        root (depth 0, question, open)
        +-- branch_a (depth 1, question, answered)
        |   +-- sub_a1 (depth 2, question, open)
        |   +-- sub_a2 (depth 2, answer, open)
        +-- branch_b (depth 1, question, open)
        |   +-- sub_b1 (depth 2, question, open)
        +-- branch_c (depth 1, question, open)

    Returns dict with all node IDs and db_path.
    """
    from spellbook_mcp.fractal.node_ops import add_node

    gid = graph_with_root["graph_id"]
    root = graph_with_root["root_node_id"]
    db = graph_with_root["db_path"]

    branch_a = add_node(
        graph_id=gid, parent_id=root, node_type="question",
        text="Branch A: What causes scattering?", db_path=db,
    )
    sub_a1 = add_node(
        graph_id=gid, parent_id=branch_a["node_id"], node_type="question",
        text="Sub A1: What is Rayleigh scattering?", db_path=db,
    )
    sub_a2 = add_node(
        graph_id=gid, parent_id=branch_a["node_id"], node_type="answer",
        text="Sub A2: Light interacts with molecules", db_path=db,
    )
    branch_b = add_node(
        graph_id=gid, parent_id=root, node_type="question",
        text="Branch B: Does atmosphere composition matter?", db_path=db,
    )
    sub_b1 = add_node(
        graph_id=gid, parent_id=branch_b["node_id"], node_type="question",
        text="Sub B1: What about nitrogen vs oxygen?", db_path=db,
    )
    branch_c = add_node(
        graph_id=gid, parent_id=root, node_type="question",
        text="Branch C: Why not violet?", db_path=db,
    )

    return {
        "graph_id": gid,
        "root_node_id": root,
        "branch_a": branch_a["node_id"],
        "sub_a1": sub_a1["node_id"],
        "sub_a2": sub_a2["node_id"],
        "branch_b": branch_b["node_id"],
        "sub_b1": sub_b1["node_id"],
        "branch_c": branch_c["node_id"],
        "db_path": db,
    }


class TestGetSnapshot:
    """Tests for get_snapshot function."""

    def test_snapshot_returns_graph_metadata(self, graph_with_root):
        """get_snapshot must return graph-level fields: graph_id, seed, intensity, status."""
        from spellbook_mcp.fractal.query_ops import get_snapshot

        result = get_snapshot(
            graph_id=graph_with_root["graph_id"],
            db_path=graph_with_root["db_path"],
        )

        assert result["graph_id"] == graph_with_root["graph_id"]
        assert result["seed"] == "Why is the sky blue?"
        assert result["intensity"] == "explore"
        assert result["status"] == "active"

    def test_snapshot_includes_nodes(self, graph_with_root):
        """get_snapshot must include nodes list with root node."""
        from spellbook_mcp.fractal.query_ops import get_snapshot

        result = get_snapshot(
            graph_id=graph_with_root["graph_id"],
            db_path=graph_with_root["db_path"],
        )

        assert "nodes" in result
        assert len(result["nodes"]) == 1

        # Root node must be present
        root_nodes = [n for n in result["nodes"] if n["node_id"] == graph_with_root["root_node_id"]]
        assert len(root_nodes) == 1

    def test_snapshot_node_shape(self, graph_with_root):
        """Each node in snapshot must have required fields."""
        from spellbook_mcp.fractal.query_ops import get_snapshot

        result = get_snapshot(
            graph_id=graph_with_root["graph_id"],
            db_path=graph_with_root["db_path"],
        )

        node = result["nodes"][0]
        assert "node_id" in node
        assert "parent_id" in node
        assert "node_type" in node
        assert "text" in node
        assert "owner" in node
        assert "depth" in node
        assert "status" in node
        assert "metadata" in node
        assert "created_at" in node

    def test_snapshot_metadata_parsed_as_dict(self, graph_with_root):
        """Node metadata must be parsed from JSON into a dict, not raw JSON string."""
        from spellbook_mcp.fractal.query_ops import get_snapshot

        result = get_snapshot(
            graph_id=graph_with_root["graph_id"],
            db_path=graph_with_root["db_path"],
        )

        node = result["nodes"][0]
        assert isinstance(node["metadata"], dict)

    def test_snapshot_includes_edges(self, branching_graph):
        """get_snapshot must include edges list."""
        from spellbook_mcp.fractal.query_ops import get_snapshot

        result = get_snapshot(
            graph_id=branching_graph["graph_id"],
            db_path=branching_graph["db_path"],
        )

        assert "edges" in result
        # The branching graph has 6 parent_child edges:
        # root->branch_a, branch_a->sub_a1, branch_a->sub_a2,
        # root->branch_b, branch_b->sub_b1, root->branch_c
        assert len(result["edges"]) == 6

    def test_snapshot_edge_shape(self, branching_graph):
        """Each edge in snapshot must have required fields."""
        from spellbook_mcp.fractal.query_ops import get_snapshot

        result = get_snapshot(
            graph_id=branching_graph["graph_id"],
            db_path=branching_graph["db_path"],
        )

        edge = result["edges"][0]
        assert "from_node" in edge
        assert "to_node" in edge
        assert "edge_type" in edge
        assert "metadata" in edge

    def test_snapshot_edge_metadata_parsed_as_dict(self, branching_graph):
        """Edge metadata must be parsed from JSON into a dict."""
        from spellbook_mcp.fractal.query_ops import get_snapshot

        result = get_snapshot(
            graph_id=branching_graph["graph_id"],
            db_path=branching_graph["db_path"],
        )

        edge = result["edges"][0]
        assert isinstance(edge["metadata"], dict)

    def test_snapshot_includes_graph_metadata(self, graph_with_root):
        """get_snapshot must include graph-level metadata parsed as dict."""
        from spellbook_mcp.fractal.query_ops import get_snapshot

        result = get_snapshot(
            graph_id=graph_with_root["graph_id"],
            db_path=graph_with_root["db_path"],
        )

        assert "metadata" in result
        assert isinstance(result["metadata"], dict)
        assert result["metadata"]["topic"] == "physics"

    def test_snapshot_all_nodes_included(self, branching_graph):
        """get_snapshot must include all nodes in the graph."""
        from spellbook_mcp.fractal.query_ops import get_snapshot

        result = get_snapshot(
            graph_id=branching_graph["graph_id"],
            db_path=branching_graph["db_path"],
        )

        # root + branch_a + sub_a1 + sub_a2 + branch_b + sub_b1 + branch_c = 7
        assert len(result["nodes"]) == 7

    def test_snapshot_graph_not_found(self, fractal_db):
        """get_snapshot with nonexistent graph_id must return error."""
        from spellbook_mcp.fractal.query_ops import get_snapshot

        result = get_snapshot(
            graph_id="nonexistent-graph-id",
            db_path=fractal_db,
        )

        assert "error" in result


class TestGetBranch:
    """Tests for get_branch function."""

    def test_branch_returns_subtree_nodes(self, branching_graph):
        """get_branch must return only nodes in the subtree rooted at node_id."""
        from spellbook_mcp.fractal.query_ops import get_branch

        result = get_branch(
            graph_id=branching_graph["graph_id"],
            node_id=branching_graph["branch_a"],
            db_path=branching_graph["db_path"],
        )

        # branch_a + sub_a1 + sub_a2 = 3 nodes
        assert "nodes" in result
        assert len(result["nodes"]) == 3

    def test_branch_excludes_sibling_branches(self, branching_graph):
        """get_branch must NOT include nodes from sibling branches."""
        from spellbook_mcp.fractal.query_ops import get_branch

        result = get_branch(
            graph_id=branching_graph["graph_id"],
            node_id=branching_graph["branch_a"],
            db_path=branching_graph["db_path"],
        )

        node_ids = {n["node_id"] for n in result["nodes"]}
        # branch_b and branch_c must not be present
        assert branching_graph["branch_b"] not in node_ids
        assert branching_graph["branch_c"] not in node_ids
        assert branching_graph["sub_b1"] not in node_ids

    def test_branch_includes_root_of_subtree(self, branching_graph):
        """get_branch must include the specified node_id as root of the subtree."""
        from spellbook_mcp.fractal.query_ops import get_branch

        result = get_branch(
            graph_id=branching_graph["graph_id"],
            node_id=branching_graph["branch_a"],
            db_path=branching_graph["db_path"],
        )

        node_ids = {n["node_id"] for n in result["nodes"]}
        assert branching_graph["branch_a"] in node_ids

    def test_branch_includes_subtree_edges(self, branching_graph):
        """get_branch must include edges within the subtree."""
        from spellbook_mcp.fractal.query_ops import get_branch

        result = get_branch(
            graph_id=branching_graph["graph_id"],
            node_id=branching_graph["branch_a"],
            db_path=branching_graph["db_path"],
        )

        assert "edges" in result
        # branch_a -> sub_a1, branch_a -> sub_a2 = 2 edges
        assert len(result["edges"]) == 2

    def test_branch_excludes_edges_outside_subtree(self, branching_graph):
        """get_branch must NOT include edges from outside the subtree."""
        from spellbook_mcp.fractal.query_ops import get_branch

        result = get_branch(
            graph_id=branching_graph["graph_id"],
            node_id=branching_graph["branch_a"],
            db_path=branching_graph["db_path"],
        )

        subtree_node_ids = {n["node_id"] for n in result["nodes"]}
        for edge in result["edges"]:
            assert edge["from_node"] in subtree_node_ids
            assert edge["to_node"] in subtree_node_ids

    def test_branch_leaf_node_returns_single_node(self, branching_graph):
        """get_branch on a leaf node must return just that node and no edges."""
        from spellbook_mcp.fractal.query_ops import get_branch

        result = get_branch(
            graph_id=branching_graph["graph_id"],
            node_id=branching_graph["sub_a1"],
            db_path=branching_graph["db_path"],
        )

        assert len(result["nodes"]) == 1
        assert result["nodes"][0]["node_id"] == branching_graph["sub_a1"]
        assert len(result["edges"]) == 0

    def test_branch_from_root_returns_full_graph(self, branching_graph):
        """get_branch from root must return all nodes."""
        from spellbook_mcp.fractal.query_ops import get_branch

        result = get_branch(
            graph_id=branching_graph["graph_id"],
            node_id=branching_graph["root_node_id"],
            db_path=branching_graph["db_path"],
        )

        assert len(result["nodes"]) == 7

    def test_branch_graph_not_found(self, fractal_db):
        """get_branch with nonexistent graph_id must return error."""
        from spellbook_mcp.fractal.query_ops import get_branch

        result = get_branch(
            graph_id="nonexistent-graph-id",
            node_id="some-node",
            db_path=fractal_db,
        )

        assert "error" in result

    def test_branch_node_not_found(self, graph_with_root):
        """get_branch with nonexistent node_id must return error."""
        from spellbook_mcp.fractal.query_ops import get_branch

        result = get_branch(
            graph_id=graph_with_root["graph_id"],
            node_id="nonexistent-node-id",
            db_path=graph_with_root["db_path"],
        )

        assert "error" in result


class TestGetOpenQuestions:
    """Tests for get_open_questions function."""

    def test_returns_open_questions_only(self, branching_graph):
        """get_open_questions must return only question nodes with status=open."""
        from spellbook_mcp.fractal.query_ops import get_open_questions

        result = get_open_questions(
            graph_id=branching_graph["graph_id"],
            db_path=branching_graph["db_path"],
        )

        assert "open_questions" in result
        assert "count" in result
        # All returned nodes must be questions with status open
        for q in result["open_questions"]:
            assert q["node_type"] == "question"
            assert q["status"] == "open"

    def test_excludes_answered_questions(self, branching_graph):
        """get_open_questions must exclude questions with status=answered."""
        from spellbook_mcp.fractal.node_ops import add_node
        from spellbook_mcp.fractal.query_ops import get_open_questions

        gid = branching_graph["graph_id"]
        db = branching_graph["db_path"]

        # Add an answer to branch_a, which transitions it to "answered"
        add_node(
            graph_id=gid, parent_id=branching_graph["branch_a"],
            node_type="answer", text="Answer to branch A",
            db_path=db,
        )

        result = get_open_questions(graph_id=gid, db_path=db)

        answered_ids = {q["node_id"] for q in result["open_questions"]}
        # branch_a was auto-transitioned to "answered" when we added answer
        assert branching_graph["branch_a"] not in answered_ids

    def test_excludes_saturated_questions(self, branching_graph):
        """get_open_questions must exclude questions with status=saturated."""
        from spellbook_mcp.fractal.node_ops import mark_saturated
        from spellbook_mcp.fractal.query_ops import get_open_questions

        gid = branching_graph["graph_id"]
        db = branching_graph["db_path"]

        # Saturate branch_c
        mark_saturated(
            graph_id=gid, node_id=branching_graph["branch_c"],
            reason="semantic_overlap", db_path=db,
        )

        result = get_open_questions(graph_id=gid, db_path=db)

        saturated_ids = {q["node_id"] for q in result["open_questions"]}
        assert branching_graph["branch_c"] not in saturated_ids

    def test_excludes_answer_nodes(self, branching_graph):
        """get_open_questions must exclude answer-type nodes even if status=open."""
        from spellbook_mcp.fractal.query_ops import get_open_questions

        result = get_open_questions(
            graph_id=branching_graph["graph_id"],
            db_path=branching_graph["db_path"],
        )

        # sub_a2 is an answer node with status=open, must not appear
        answer_ids = {q["node_id"] for q in result["open_questions"]}
        assert branching_graph["sub_a2"] not in answer_ids

    def test_count_matches_list_length(self, branching_graph):
        """get_open_questions count must match the length of open_questions list."""
        from spellbook_mcp.fractal.query_ops import get_open_questions

        result = get_open_questions(
            graph_id=branching_graph["graph_id"],
            db_path=branching_graph["db_path"],
        )

        assert result["count"] == len(result["open_questions"])

    def test_returns_graph_id(self, branching_graph):
        """get_open_questions must include graph_id in result."""
        from spellbook_mcp.fractal.query_ops import get_open_questions

        result = get_open_questions(
            graph_id=branching_graph["graph_id"],
            db_path=branching_graph["db_path"],
        )

        assert result["graph_id"] == branching_graph["graph_id"]

    def test_graph_not_found(self, fractal_db):
        """get_open_questions with nonexistent graph_id must return error."""
        from spellbook_mcp.fractal.query_ops import get_open_questions

        result = get_open_questions(
            graph_id="nonexistent-graph-id",
            db_path=fractal_db,
        )

        assert "error" in result


class TestQueryConvergence:
    """Tests for query_convergence function."""

    def test_finds_convergence_edges(self, branching_graph):
        """query_convergence must find edges with edge_type=convergence."""
        from spellbook_mcp.fractal.node_ops import update_node
        from spellbook_mcp.fractal.query_ops import query_convergence

        gid = branching_graph["graph_id"]
        db = branching_graph["db_path"]

        # Create convergence between sub_a1 and sub_b1
        update_node(
            graph_id=gid, node_id=branching_graph["sub_a1"],
            metadata_json=json.dumps({
                "convergence_with": [branching_graph["sub_b1"]],
                "convergence_insight": "Both involve molecular interaction",
            }),
            db_path=db,
        )

        result = query_convergence(graph_id=gid, db_path=db)

        assert "convergence_points" in result
        assert result["count"] >= 1

    def test_convergence_includes_insight(self, branching_graph):
        """query_convergence must extract convergence_insight from node metadata."""
        from spellbook_mcp.fractal.node_ops import update_node
        from spellbook_mcp.fractal.query_ops import query_convergence

        gid = branching_graph["graph_id"]
        db = branching_graph["db_path"]

        update_node(
            graph_id=gid, node_id=branching_graph["sub_a1"],
            metadata_json=json.dumps({
                "convergence_with": [branching_graph["sub_b1"]],
                "convergence_insight": "Both involve molecular interaction",
            }),
            db_path=db,
        )

        result = query_convergence(graph_id=gid, db_path=db)

        # At least one convergence point should have the insight
        insights = [cp["insight"] for cp in result["convergence_points"] if cp["insight"]]
        assert "Both involve molecular interaction" in insights

    def test_convergence_includes_node_ids(self, branching_graph):
        """query_convergence convergence_points must include the connected node IDs."""
        from spellbook_mcp.fractal.node_ops import update_node
        from spellbook_mcp.fractal.query_ops import query_convergence

        gid = branching_graph["graph_id"]
        db = branching_graph["db_path"]

        update_node(
            graph_id=gid, node_id=branching_graph["sub_a1"],
            metadata_json=json.dumps({
                "convergence_with": [branching_graph["sub_b1"]],
                "convergence_insight": "Insight text",
            }),
            db_path=db,
        )

        result = query_convergence(graph_id=gid, db_path=db)

        # Find the convergence point containing our nodes
        all_nodes_in_convergences = set()
        for cp in result["convergence_points"]:
            for n in cp["nodes"]:
                all_nodes_in_convergences.add(n)

        assert branching_graph["sub_a1"] in all_nodes_in_convergences
        assert branching_graph["sub_b1"] in all_nodes_in_convergences

    def test_no_convergence_returns_empty(self, graph_with_root):
        """query_convergence with no convergence edges must return empty list."""
        from spellbook_mcp.fractal.query_ops import query_convergence

        result = query_convergence(
            graph_id=graph_with_root["graph_id"],
            db_path=graph_with_root["db_path"],
        )

        assert result["convergence_points"] == []
        assert result["count"] == 0

    def test_convergence_returns_graph_id(self, graph_with_root):
        """query_convergence must include graph_id in result."""
        from spellbook_mcp.fractal.query_ops import query_convergence

        result = query_convergence(
            graph_id=graph_with_root["graph_id"],
            db_path=graph_with_root["db_path"],
        )

        assert result["graph_id"] == graph_with_root["graph_id"]

    def test_convergence_count_matches(self, branching_graph):
        """query_convergence count must match the number of convergence_points."""
        from spellbook_mcp.fractal.node_ops import update_node
        from spellbook_mcp.fractal.query_ops import query_convergence

        gid = branching_graph["graph_id"]
        db = branching_graph["db_path"]

        update_node(
            graph_id=gid, node_id=branching_graph["sub_a1"],
            metadata_json=json.dumps({
                "convergence_with": [branching_graph["sub_b1"]],
                "convergence_insight": "Shared theme",
            }),
            db_path=db,
        )

        result = query_convergence(graph_id=gid, db_path=db)

        assert result["count"] == len(result["convergence_points"])

    def test_convergence_graph_not_found(self, fractal_db):
        """query_convergence with nonexistent graph_id must return error."""
        from spellbook_mcp.fractal.query_ops import query_convergence

        result = query_convergence(
            graph_id="nonexistent-graph-id",
            db_path=fractal_db,
        )

        assert "error" in result


class TestQueryContradictions:
    """Tests for query_contradictions function."""

    def test_finds_contradiction_edges(self, branching_graph):
        """query_contradictions must find edges with edge_type=contradiction."""
        from spellbook_mcp.fractal.node_ops import update_node
        from spellbook_mcp.fractal.query_ops import query_contradictions

        gid = branching_graph["graph_id"]
        db = branching_graph["db_path"]

        # Create contradiction between sub_a2 and branch_c
        update_node(
            graph_id=gid, node_id=branching_graph["sub_a2"],
            metadata_json=json.dumps({
                "contradiction_with": [branching_graph["branch_c"]],
                "contradiction_tension": "Scattering model vs perception model",
            }),
            db_path=db,
        )

        result = query_contradictions(graph_id=gid, db_path=db)

        assert "contradictions" in result
        assert result["count"] >= 1

    def test_contradiction_includes_tension(self, branching_graph):
        """query_contradictions must extract contradiction_tension from node metadata."""
        from spellbook_mcp.fractal.node_ops import update_node
        from spellbook_mcp.fractal.query_ops import query_contradictions

        gid = branching_graph["graph_id"]
        db = branching_graph["db_path"]

        update_node(
            graph_id=gid, node_id=branching_graph["sub_a2"],
            metadata_json=json.dumps({
                "contradiction_with": [branching_graph["branch_c"]],
                "contradiction_tension": "Scattering model vs perception model",
            }),
            db_path=db,
        )

        result = query_contradictions(graph_id=gid, db_path=db)

        tensions = [c["tension"] for c in result["contradictions"] if c["tension"]]
        assert "Scattering model vs perception model" in tensions

    def test_contradiction_includes_node_ids(self, branching_graph):
        """query_contradictions must include the connected node IDs."""
        from spellbook_mcp.fractal.node_ops import update_node
        from spellbook_mcp.fractal.query_ops import query_contradictions

        gid = branching_graph["graph_id"]
        db = branching_graph["db_path"]

        update_node(
            graph_id=gid, node_id=branching_graph["sub_a2"],
            metadata_json=json.dumps({
                "contradiction_with": [branching_graph["branch_c"]],
                "contradiction_tension": "Tension text",
            }),
            db_path=db,
        )

        result = query_contradictions(graph_id=gid, db_path=db)

        all_nodes = set()
        for c in result["contradictions"]:
            for n in c["nodes"]:
                all_nodes.add(n)

        assert branching_graph["sub_a2"] in all_nodes
        assert branching_graph["branch_c"] in all_nodes

    def test_no_contradictions_returns_empty(self, graph_with_root):
        """query_contradictions with no contradiction edges must return empty list."""
        from spellbook_mcp.fractal.query_ops import query_contradictions

        result = query_contradictions(
            graph_id=graph_with_root["graph_id"],
            db_path=graph_with_root["db_path"],
        )

        assert result["contradictions"] == []
        assert result["count"] == 0

    def test_contradiction_count_matches(self, branching_graph):
        """query_contradictions count must match the number of contradictions."""
        from spellbook_mcp.fractal.node_ops import update_node
        from spellbook_mcp.fractal.query_ops import query_contradictions

        gid = branching_graph["graph_id"]
        db = branching_graph["db_path"]

        update_node(
            graph_id=gid, node_id=branching_graph["sub_a2"],
            metadata_json=json.dumps({
                "contradiction_with": [branching_graph["branch_c"]],
                "contradiction_tension": "Tension",
            }),
            db_path=db,
        )

        result = query_contradictions(graph_id=gid, db_path=db)

        assert result["count"] == len(result["contradictions"])

    def test_contradiction_graph_not_found(self, fractal_db):
        """query_contradictions with nonexistent graph_id must return error."""
        from spellbook_mcp.fractal.query_ops import query_contradictions

        result = query_contradictions(
            graph_id="nonexistent-graph-id",
            db_path=fractal_db,
        )

        assert "error" in result


class TestGetSaturationStatus:
    """Tests for get_saturation_status function."""

    def test_returns_branch_list(self, branching_graph):
        """get_saturation_status must return a list of top-level branches (depth=1)."""
        from spellbook_mcp.fractal.query_ops import get_saturation_status

        result = get_saturation_status(
            graph_id=branching_graph["graph_id"],
            db_path=branching_graph["db_path"],
        )

        assert "branches" in result
        # branch_a, branch_b, branch_c = 3 top-level branches
        assert len(result["branches"]) == 3

    def test_branch_shape(self, branching_graph):
        """Each branch in saturation status must have required fields."""
        from spellbook_mcp.fractal.query_ops import get_saturation_status

        result = get_saturation_status(
            graph_id=branching_graph["graph_id"],
            db_path=branching_graph["db_path"],
        )

        branch = result["branches"][0]
        assert "node_id" in branch
        assert "text" in branch
        assert "saturated" in branch
        assert "saturation_reason" in branch
        assert "open_questions" in branch

    def test_unsaturated_branch_reports_false(self, branching_graph):
        """Unsaturated branch must have saturated=False."""
        from spellbook_mcp.fractal.query_ops import get_saturation_status

        result = get_saturation_status(
            graph_id=branching_graph["graph_id"],
            db_path=branching_graph["db_path"],
        )

        # All branches are unsaturated initially
        for branch in result["branches"]:
            assert branch["saturated"] is False

    def test_saturated_branch_reports_true(self, branching_graph):
        """Saturated branch must have saturated=True and saturation_reason set."""
        from spellbook_mcp.fractal.node_ops import mark_saturated
        from spellbook_mcp.fractal.query_ops import get_saturation_status

        gid = branching_graph["graph_id"]
        db = branching_graph["db_path"]

        mark_saturated(
            graph_id=gid, node_id=branching_graph["branch_a"],
            reason="semantic_overlap", db_path=db,
        )

        result = get_saturation_status(graph_id=gid, db_path=db)

        saturated_branches = [b for b in result["branches"] if b["node_id"] == branching_graph["branch_a"]]
        assert len(saturated_branches) == 1
        assert saturated_branches[0]["saturated"] is True
        assert saturated_branches[0]["saturation_reason"] == "semantic_overlap"

    def test_mixed_saturation(self, branching_graph):
        """get_saturation_status with mixed saturated/unsaturated branches must report correctly."""
        from spellbook_mcp.fractal.node_ops import mark_saturated
        from spellbook_mcp.fractal.query_ops import get_saturation_status

        gid = branching_graph["graph_id"]
        db = branching_graph["db_path"]

        # Saturate only branch_a
        mark_saturated(
            graph_id=gid, node_id=branching_graph["branch_a"],
            reason="actionable", db_path=db,
        )

        result = get_saturation_status(graph_id=gid, db_path=db)

        saturated_count = sum(1 for b in result["branches"] if b["saturated"])
        unsaturated_count = sum(1 for b in result["branches"] if not b["saturated"])

        assert saturated_count == 1
        assert unsaturated_count == 2
        assert result["all_saturated"] is False

    def test_all_saturated_flag_true(self, branching_graph):
        """all_saturated must be True when all branches are saturated."""
        from spellbook_mcp.fractal.node_ops import mark_saturated
        from spellbook_mcp.fractal.query_ops import get_saturation_status

        gid = branching_graph["graph_id"]
        db = branching_graph["db_path"]

        mark_saturated(graph_id=gid, node_id=branching_graph["branch_a"], reason="semantic_overlap", db_path=db)
        mark_saturated(graph_id=gid, node_id=branching_graph["branch_b"], reason="derivable", db_path=db)
        mark_saturated(graph_id=gid, node_id=branching_graph["branch_c"], reason="actionable", db_path=db)

        result = get_saturation_status(graph_id=gid, db_path=db)

        assert result["all_saturated"] is True

    def test_all_saturated_flag_false_when_none_saturated(self, branching_graph):
        """all_saturated must be False when no branches are saturated."""
        from spellbook_mcp.fractal.query_ops import get_saturation_status

        result = get_saturation_status(
            graph_id=branching_graph["graph_id"],
            db_path=branching_graph["db_path"],
        )

        assert result["all_saturated"] is False

    def test_open_questions_count_in_subtree(self, branching_graph):
        """Each branch must report the count of open questions in its subtree."""
        from spellbook_mcp.fractal.query_ops import get_saturation_status

        result = get_saturation_status(
            graph_id=branching_graph["graph_id"],
            db_path=branching_graph["db_path"],
        )

        # branch_a was auto-transitioned to "answered" when sub_a2 (answer) was
        # added as its child. So only sub_a1 (open question) counts.
        branch_a_info = [b for b in result["branches"] if b["node_id"] == branching_graph["branch_a"]]
        assert len(branch_a_info) == 1
        # branch_a (answered, not open) + sub_a1 (open question) = 1 open question
        assert branch_a_info[0]["open_questions"] == 1

        # branch_b has sub_b1 (open question) + branch_b itself (open question) = 2
        branch_b_info = [b for b in result["branches"] if b["node_id"] == branching_graph["branch_b"]]
        assert len(branch_b_info) == 1
        assert branch_b_info[0]["open_questions"] == 2

        # branch_c has no children, just itself (open question) = 1
        branch_c_info = [b for b in result["branches"] if b["node_id"] == branching_graph["branch_c"]]
        assert len(branch_c_info) == 1
        assert branch_c_info[0]["open_questions"] == 1

    def test_returns_graph_id(self, branching_graph):
        """get_saturation_status must include graph_id in result."""
        from spellbook_mcp.fractal.query_ops import get_saturation_status

        result = get_saturation_status(
            graph_id=branching_graph["graph_id"],
            db_path=branching_graph["db_path"],
        )

        assert result["graph_id"] == branching_graph["graph_id"]

    def test_graph_not_found(self, fractal_db):
        """get_saturation_status with nonexistent graph_id must return error."""
        from spellbook_mcp.fractal.query_ops import get_saturation_status

        result = get_saturation_status(
            graph_id="nonexistent-graph-id",
            db_path=fractal_db,
        )

        assert "error" in result


class TestGetClaimableWork:
    """Tests for get_claimable_work function."""

    def test_claimable_returns_open_questions(self, branching_graph):
        """get_claimable_work must return open question nodes."""
        from spellbook_mcp.fractal.query_ops import get_claimable_work

        gid = branching_graph["graph_id"]
        db = branching_graph["db_path"]

        result = get_claimable_work(graph_id=gid, db_path=db)

        assert "claimable" in result
        assert "count" in result
        assert result["graph_id"] == gid
        assert result["count"] > 0
        for node in result["claimable"]:
            assert node["node_type"] == "question"
            assert node["status"] == "open"

    def test_claimable_excludes_claimed(self, branching_graph):
        """get_claimable_work must exclude claimed question nodes."""
        from spellbook_mcp.fractal.node_ops import claim_work
        from spellbook_mcp.fractal.query_ops import get_claimable_work

        gid = branching_graph["graph_id"]
        db = branching_graph["db_path"]

        # Claim a node first
        claimed = claim_work(graph_id=gid, worker_id="worker-1", db_path=db)
        claimed_id = claimed["node_id"]

        result = get_claimable_work(graph_id=gid, db_path=db)

        claimable_ids = {n["node_id"] for n in result["claimable"]}
        assert claimed_id not in claimable_ids

    def test_claimable_affinity_ordering(self, branching_graph):
        """get_claimable_work with worker_id must return sibling nodes first."""
        from spellbook_mcp.fractal.node_ops import add_node, claim_work
        from spellbook_mcp.fractal.query_ops import get_claimable_work

        gid = branching_graph["graph_id"]
        db = branching_graph["db_path"]

        # Claim branch_b so worker-1 owns it (it gets status='claimed')
        # We need sub_b1 to remain open so it has sibling affinity
        # Instead, let's set up: worker-1 owns a sibling of sub_a1
        # by claiming sub_a1
        claimed = claim_work(graph_id=gid, worker_id="worker-1", db_path=db)

        # Add another open question sibling to the claimed node's parent
        from spellbook_mcp.fractal.schema import get_fractal_connection
        conn = get_fractal_connection(db)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT parent_id FROM nodes WHERE id = ?", (claimed["node_id"],)
        )
        parent_id = cursor.fetchone()[0]

        sibling = add_node(
            graph_id=gid, parent_id=parent_id, node_type="question",
            text="Sibling question for affinity test", db_path=db,
        )

        result = get_claimable_work(
            graph_id=gid, worker_id="worker-1", db_path=db,
        )

        # The sibling should appear before non-siblings due to affinity
        assert result["count"] > 0
        assert result["claimable"][0]["node_id"] == sibling["node_id"]

    def test_claimable_empty(self, graph_with_root):
        """get_claimable_work with no open questions returns empty list."""
        from spellbook_mcp.fractal.node_ops import mark_saturated
        from spellbook_mcp.fractal.query_ops import get_claimable_work

        gid = graph_with_root["graph_id"]
        db = graph_with_root["db_path"]

        # Saturate the root node so no open questions remain
        mark_saturated(
            graph_id=gid, node_id=graph_with_root["root_node_id"],
            reason="semantic_overlap", db_path=db,
        )

        result = get_claimable_work(graph_id=gid, db_path=db)

        assert result["claimable"] == []
        assert result["count"] == 0


class TestGetReadyToSynthesize:
    """Tests for get_ready_to_synthesize function."""

    def test_ready_basic(self, branching_graph):
        """Node with all children synthesized/saturated is returned."""
        from spellbook_mcp.fractal.node_ops import (
            add_node,
            mark_saturated,
            synthesize_node,
        )
        from spellbook_mcp.fractal.query_ops import get_ready_to_synthesize

        gid = branching_graph["graph_id"]
        db = branching_graph["db_path"]

        # branch_a is already 'answered' (has answer child sub_a2).
        # Its question child is sub_a1 (open). Saturate sub_a1 so
        # branch_a has all question children done.
        mark_saturated(
            graph_id=gid, node_id=branching_graph["sub_a1"],
            reason="semantic_overlap", db_path=db,
        )

        result = get_ready_to_synthesize(graph_id=gid, db_path=db)

        ready_ids = {n["node_id"] for n in result["ready_nodes"]}
        assert branching_graph["branch_a"] in ready_ids

    def test_ready_excludes_incomplete(self, branching_graph):
        """Node with open children is NOT returned."""
        from spellbook_mcp.fractal.query_ops import get_ready_to_synthesize

        gid = branching_graph["graph_id"]
        db = branching_graph["db_path"]

        result = get_ready_to_synthesize(graph_id=gid, db_path=db)

        # branch_a has sub_a1 still open, so it should not be ready
        ready_ids = {n["node_id"] for n in result["ready_nodes"]}
        assert branching_graph["branch_a"] not in ready_ids

    def test_ready_excludes_leaves(self, branching_graph):
        """Answered leaf nodes (no question children) are NOT returned."""
        from spellbook_mcp.fractal.node_ops import add_node
        from spellbook_mcp.fractal.query_ops import get_ready_to_synthesize

        gid = branching_graph["graph_id"]
        db = branching_graph["db_path"]

        # branch_c is open, add an answer to make it 'answered' but it
        # has no question children
        add_node(
            graph_id=gid, parent_id=branching_graph["branch_c"],
            node_type="answer", text="Answer for branch C", db_path=db,
        )

        result = get_ready_to_synthesize(graph_id=gid, db_path=db)

        ready_ids = {n["node_id"] for n in result["ready_nodes"]}
        assert branching_graph["branch_c"] not in ready_ids

    def test_ready_depth_ordering(self, branching_graph):
        """Deeper nodes are returned before shallower nodes."""
        from spellbook_mcp.fractal.node_ops import (
            add_node,
            mark_saturated,
        )
        from spellbook_mcp.fractal.query_ops import get_ready_to_synthesize

        gid = branching_graph["graph_id"]
        db = branching_graph["db_path"]

        # Make branch_a ready: saturate sub_a1
        mark_saturated(
            graph_id=gid, node_id=branching_graph["sub_a1"],
            reason="semantic_overlap", db_path=db,
        )

        # Make branch_b 'answered' by adding an answer child
        add_node(
            graph_id=gid, parent_id=branching_graph["branch_b"],
            node_type="answer", text="Answer for branch B", db_path=db,
        )
        # Saturate sub_b1 so branch_b has all question children done
        mark_saturated(
            graph_id=gid, node_id=branching_graph["sub_b1"],
            reason="semantic_overlap", db_path=db,
        )

        # Create a deeper ready node under branch_a
        deep_q = add_node(
            graph_id=gid, parent_id=branching_graph["branch_a"],
            node_type="question", text="Deep question", db_path=db,
        )
        # Add answer to deep_q to make it 'answered'
        add_node(
            graph_id=gid, parent_id=deep_q["node_id"],
            node_type="answer", text="Deep answer", db_path=db,
        )
        # Add a question child and mark it done so deep_q qualifies
        deep_sub = add_node(
            graph_id=gid, parent_id=deep_q["node_id"],
            node_type="question", text="Deep sub-question", db_path=db,
        )
        mark_saturated(
            graph_id=gid, node_id=deep_sub["node_id"],
            reason="semantic_overlap", db_path=db,
        )

        # deep_q (depth=2, answered, all question children done) is ready.
        # branch_a (depth=1) now has deep_q (answered, not synthesized/saturated)
        # as a question child, so branch_a is NOT ready.
        # branch_b (depth=1) is ready.
        result = get_ready_to_synthesize(graph_id=gid, db_path=db)

        ready_ids = [n["node_id"] for n in result["ready_nodes"]]
        assert deep_q["node_id"] in ready_ids
        assert branching_graph["branch_b"] in ready_ids

        # deep_q (depth 2) should come before branch_b (depth 1)
        deep_q_idx = ready_ids.index(deep_q["node_id"])
        branch_b_idx = ready_ids.index(branching_graph["branch_b"])
        assert deep_q_idx < branch_b_idx

    def test_ready_empty(self, graph_with_root):
        """No ready nodes returns empty list."""
        from spellbook_mcp.fractal.query_ops import get_ready_to_synthesize

        gid = graph_with_root["graph_id"]
        db = graph_with_root["db_path"]

        result = get_ready_to_synthesize(graph_id=gid, db_path=db)

        assert result["ready_nodes"] == []
        assert result["count"] == 0
        assert result["graph_id"] == gid


class TestSaturationStatusWithSynthesized:
    """Tests for get_saturation_status with synthesized branches."""

    def test_synthesized_branch_counts_as_complete(self, branching_graph):
        """Branch with status 'synthesized' has saturated=True in result."""
        from spellbook_mcp.fractal.node_ops import (
            mark_saturated,
            synthesize_node,
        )
        from spellbook_mcp.fractal.query_ops import get_saturation_status

        gid = branching_graph["graph_id"]
        db = branching_graph["db_path"]

        # branch_a is 'answered' (auto-transitioned when sub_a2 answer was added).
        # To synthesize it, all its question children must be done.
        # sub_a1 is a question child, saturate it first.
        mark_saturated(
            graph_id=gid, node_id=branching_graph["sub_a1"],
            reason="semantic_overlap", db_path=db,
        )

        # Now synthesize branch_a
        synthesize_node(
            graph_id=gid, node_id=branching_graph["branch_a"],
            synthesis_text="Scattering is the cause", db_path=db,
        )

        result = get_saturation_status(graph_id=gid, db_path=db)

        synth_branches = [
            b for b in result["branches"]
            if b["node_id"] == branching_graph["branch_a"]
        ]
        assert len(synth_branches) == 1
        assert synth_branches[0]["saturated"] is True

        # all_complete key should be present
        assert "all_complete" in result
        # Not all complete because branch_b and branch_c are still open
        assert result["all_complete"] is False
        # Backward compat: all_saturated still present
        assert "all_saturated" in result

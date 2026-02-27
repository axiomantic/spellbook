"""End-to-end integration test for the fractal thinking MCP tool surface.

Exercises all 13 MCP tool functions in a realistic sequence:
create_graph -> add_node (multiple) -> update_node (convergence + contradiction)
-> mark_saturated -> get_snapshot -> get_branch -> get_open_questions
-> query_convergence -> query_contradictions -> get_saturation_status
-> update_graph_status -> delete_graph
"""

import json


class TestFractalEndToEnd:
    """Exercises the full fractal thinking CRUD pipeline in a realistic sequence."""

    def test_full_lifecycle(self, fractal_db):
        """End-to-end test: create graph, build tree, query, complete, delete."""
        from spellbook_mcp.fractal.graph_ops import (
            create_graph,
            delete_graph,
            update_graph_status,
        )
        from spellbook_mcp.fractal.node_ops import (
            add_node,
            mark_saturated,
            update_node,
        )
        from spellbook_mcp.fractal.query_ops import (
            get_branch,
            get_open_questions,
            get_saturation_status,
            get_snapshot,
            query_contradictions,
            query_convergence,
        )
        from spellbook_mcp.fractal.schema import get_fractal_connection

        # ----------------------------------------------------------------
        # Step 1: create_graph
        # ----------------------------------------------------------------
        graph = create_graph(
            seed="What are the tradeoffs of microservices vs monoliths?",
            intensity="explore",
            checkpoint_mode="autonomous",
            db_path=fractal_db,
        )

        assert "error" not in graph
        assert graph["intensity"] == "explore"
        assert graph["checkpoint_mode"] == "autonomous"
        assert graph["budget"] == {"max_agents": 8, "max_depth": 4}
        assert graph["status"] == "active"

        graph_id = graph["graph_id"]
        root_id = graph["root_node_id"]

        # ----------------------------------------------------------------
        # Step 2: add_node - 3 child question branches off the root
        # ----------------------------------------------------------------
        branch_q1 = add_node(
            graph_id=graph_id,
            parent_id=root_id,
            node_type="question",
            text="How does team autonomy differ between the two?",
            db_path=fractal_db,
        )
        assert branch_q1["depth"] == 1
        assert branch_q1["node_type"] == "question"
        assert branch_q1["status"] == "open"

        branch_q2 = add_node(
            graph_id=graph_id,
            parent_id=root_id,
            node_type="question",
            text="What are the deployment complexity tradeoffs?",
            db_path=fractal_db,
        )
        assert branch_q2["depth"] == 1
        assert branch_q2["node_type"] == "question"

        branch_q3 = add_node(
            graph_id=graph_id,
            parent_id=root_id,
            node_type="question",
            text="How does data consistency change?",
            db_path=fractal_db,
        )
        assert branch_q3["depth"] == 1
        assert branch_q3["node_type"] == "question"

        q1_id = branch_q1["node_id"]
        q2_id = branch_q2["node_id"]
        q3_id = branch_q3["node_id"]

        # ----------------------------------------------------------------
        # Step 3: add_node - answer nodes to questions 1 and 2
        #   Verifies auto-transition: parent question status -> "answered"
        # ----------------------------------------------------------------
        answer_a1 = add_node(
            graph_id=graph_id,
            parent_id=q1_id,
            node_type="answer",
            text="Microservices give teams ownership of bounded contexts.",
            db_path=fractal_db,
        )
        assert answer_a1["depth"] == 2
        assert answer_a1["node_type"] == "answer"
        assert answer_a1["status"] == "open"

        # Verify parent question auto-transitioned to "answered"
        conn = get_fractal_connection(fractal_db)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT status FROM nodes WHERE id = ?", (q1_id,)
        )
        assert cursor.fetchone()[0] == "answered"

        answer_a2 = add_node(
            graph_id=graph_id,
            parent_id=q2_id,
            node_type="answer",
            text="Monoliths have simpler deployment but harder scaling.",
            db_path=fractal_db,
        )
        assert answer_a2["depth"] == 2

        # Verify second parent also auto-transitioned
        cursor.execute(
            "SELECT status FROM nodes WHERE id = ?", (q2_id,)
        )
        assert cursor.fetchone()[0] == "answered"

        a1_id = answer_a1["node_id"]
        a2_id = answer_a2["node_id"]

        # ----------------------------------------------------------------
        # Step 4: add_node - sub-questions branching from answers
        # ----------------------------------------------------------------
        sub_q1 = add_node(
            graph_id=graph_id,
            parent_id=a1_id,
            node_type="question",
            text="Does bounded context ownership lead to data silos?",
            db_path=fractal_db,
        )
        assert sub_q1["depth"] == 3
        assert sub_q1["node_type"] == "question"

        sub_q2 = add_node(
            graph_id=graph_id,
            parent_id=a2_id,
            node_type="question",
            text="Can monolith scaling be improved with vertical sharding?",
            db_path=fractal_db,
        )
        assert sub_q2["depth"] == 3

        # ----------------------------------------------------------------
        # Step 5: update_node - convergence metadata between two answers
        # ----------------------------------------------------------------
        convergence_result = update_node(
            graph_id=graph_id,
            node_id=a1_id,
            metadata_json=json.dumps({
                "convergence_with": [a2_id],
                "convergence_insight": "Both approaches require clear API boundaries.",
            }),
            db_path=fractal_db,
        )
        assert convergence_result["node_id"] == a1_id
        assert convergence_result["edges_created"] == 1
        assert "convergence_with" in convergence_result["metadata"]
        assert "convergence_insight" in convergence_result["metadata"]

        # ----------------------------------------------------------------
        # Step 6: update_node - contradiction metadata between two answers
        # ----------------------------------------------------------------
        contradiction_result = update_node(
            graph_id=graph_id,
            node_id=a2_id,
            metadata_json=json.dumps({
                "contradiction_with": [a1_id],
                "contradiction_tension": "Team autonomy vs deployment simplicity.",
            }),
            db_path=fractal_db,
        )
        assert contradiction_result["node_id"] == a2_id
        assert contradiction_result["edges_created"] == 1
        assert "contradiction_with" in contradiction_result["metadata"]
        assert "contradiction_tension" in contradiction_result["metadata"]

        # ----------------------------------------------------------------
        # Step 7: mark_saturated - mark branch q1 as saturated
        # ----------------------------------------------------------------
        # q1 is currently "answered"; mark_saturated allows "answered" status
        saturate_result = mark_saturated(
            graph_id=graph_id,
            node_id=q1_id,
            reason="semantic_overlap",
            db_path=fractal_db,
        )
        assert saturate_result["node_id"] == q1_id
        assert saturate_result["status"] == "saturated"
        assert saturate_result["reason"] == "semantic_overlap"

        # Verify in DB
        cursor.execute(
            "SELECT status FROM nodes WHERE id = ?", (q1_id,)
        )
        assert cursor.fetchone()[0] == "saturated"

        # ----------------------------------------------------------------
        # Step 8: get_snapshot - verify full graph structure
        # ----------------------------------------------------------------
        snapshot = get_snapshot(graph_id, db_path=fractal_db)

        assert "error" not in snapshot
        assert snapshot["graph_id"] == graph_id
        assert snapshot["seed"] == "What are the tradeoffs of microservices vs monoliths?"
        assert snapshot["intensity"] == "explore"
        assert snapshot["status"] == "active"

        # Count nodes: root + 3 branches + 2 answers + 2 sub-questions = 8
        assert len(snapshot["nodes"]) == 8

        # Count edges: 3 parent_child (root->branches) + 2 parent_child (branch->answer)
        #   + 2 parent_child (answer->sub-question) + 1 convergence + 1 contradiction = 9
        assert len(snapshot["edges"]) == 9

        # Verify edge types present
        edge_types = {e["edge_type"] for e in snapshot["edges"]}
        assert "parent_child" in edge_types
        assert "convergence" in edge_types
        assert "contradiction" in edge_types

        # ----------------------------------------------------------------
        # Step 9: get_branch - subtree rooted at branch q2
        # ----------------------------------------------------------------
        branch = get_branch(graph_id, q2_id, db_path=fractal_db)

        assert "error" not in branch
        assert branch["graph_id"] == graph_id

        # Branch q2 subtree: q2 + answer_a2 + sub_q2 = 3 nodes
        assert len(branch["nodes"]) == 3

        # Edges within subtree: q2->a2 (parent_child), a2->sub_q2 (parent_child) = 2
        # The convergence/contradiction edges connect to a1_id which is outside
        # this subtree, so they should NOT appear
        subtree_edge_types = [e["edge_type"] for e in branch["edges"]]
        assert subtree_edge_types.count("parent_child") == 2

        # ----------------------------------------------------------------
        # Step 10: get_open_questions - only unanswered questions
        # ----------------------------------------------------------------
        open_qs = get_open_questions(graph_id, db_path=fractal_db)

        assert "error" not in open_qs
        assert open_qs["graph_id"] == graph_id

        # Open questions: root (open), q3 (open, never answered),
        #   sub_q1 (open), sub_q2 (open) = 4
        # q1 is saturated, q2 is answered -- neither is "open"
        assert open_qs["count"] == 4

        open_ids = {q["node_id"] for q in open_qs["open_questions"]}
        assert root_id in open_ids
        assert q3_id in open_ids
        assert sub_q1["node_id"] in open_ids
        assert sub_q2["node_id"] in open_ids
        assert q1_id not in open_ids  # saturated
        assert q2_id not in open_ids  # answered

        # ----------------------------------------------------------------
        # Step 11: query_convergence - verify convergence points
        # ----------------------------------------------------------------
        convergence = query_convergence(graph_id, db_path=fractal_db)

        assert "error" not in convergence
        assert convergence["graph_id"] == graph_id
        assert convergence["count"] >= 1

        # Should find a cluster containing a1_id and a2_id
        found_cluster = False
        for point in convergence["convergence_points"]:
            if a1_id in point["nodes"] and a2_id in point["nodes"]:
                found_cluster = True
                assert point["insight"] == "Both approaches require clear API boundaries."
                break
        assert found_cluster, "Expected convergence cluster with a1 and a2 not found"

        # ----------------------------------------------------------------
        # Step 12: query_contradictions - verify contradiction points
        # ----------------------------------------------------------------
        contradictions = query_contradictions(graph_id, db_path=fractal_db)

        assert "error" not in contradictions
        assert contradictions["graph_id"] == graph_id
        assert contradictions["count"] >= 1

        # Should find a contradiction between a2 and a1
        found_contradiction = False
        for item in contradictions["contradictions"]:
            if a1_id in item["nodes"] and a2_id in item["nodes"]:
                found_contradiction = True
                assert item["tension"] == "Team autonomy vs deployment simplicity."
                break
        assert found_contradiction, (
            "Expected contradiction between a1 and a2 not found"
        )

        # ----------------------------------------------------------------
        # Step 13: get_saturation_status - per-branch saturation
        # ----------------------------------------------------------------
        sat_status = get_saturation_status(graph_id, db_path=fractal_db)

        assert "error" not in sat_status
        assert sat_status["graph_id"] == graph_id

        # 3 depth-1 branches: q1, q2, q3
        assert len(sat_status["branches"]) == 3

        # q1 is saturated, q2 and q3 are not
        assert sat_status["all_saturated"] is False

        branch_map = {b["node_id"]: b for b in sat_status["branches"]}

        assert branch_map[q1_id]["saturated"] is True
        assert branch_map[q1_id]["saturation_reason"] == "semantic_overlap"

        assert branch_map[q2_id]["saturated"] is False
        assert branch_map[q2_id]["saturation_reason"] is None

        assert branch_map[q3_id]["saturated"] is False
        assert branch_map[q3_id]["saturation_reason"] is None

        # q3 is open and has no children, so it has 1 open question (itself)
        assert branch_map[q3_id]["open_questions"] == 1

        # q2 branch: q2 is answered (not open), but sub_q2 is open = 1 open
        assert branch_map[q2_id]["open_questions"] == 1

        # q1 branch: q1 is saturated (not open), sub_q1 is open = 1 open
        assert branch_map[q1_id]["open_questions"] == 1

        # ----------------------------------------------------------------
        # Step 14: update_graph_status - transition to "completed"
        # ----------------------------------------------------------------
        status_result = update_graph_status(
            graph_id,
            "completed",
            reason="All branches explored to satisfaction.",
            db_path=fractal_db,
        )

        assert "error" not in status_result
        assert status_result["graph_id"] == graph_id
        assert status_result["status"] == "completed"
        assert status_result["previous_status"] == "active"

        # Verify reason persisted in metadata_json
        cursor.execute(
            "SELECT metadata_json FROM graphs WHERE id = ?", (graph_id,)
        )
        graph_meta = json.loads(cursor.fetchone()[0])
        assert graph_meta["status_reason"] == "All branches explored to satisfaction."

        # ----------------------------------------------------------------
        # Step 15: delete_graph - cleanup and verify cascade
        # ----------------------------------------------------------------
        delete_result = delete_graph(graph_id, db_path=fractal_db)

        assert delete_result["deleted"] is True
        assert delete_result["graph_id"] == graph_id

        # Verify graph row is gone
        cursor.execute(
            "SELECT COUNT(*) FROM graphs WHERE id = ?", (graph_id,)
        )
        assert cursor.fetchone()[0] == 0

        # Verify all nodes cascade-deleted
        cursor.execute(
            "SELECT COUNT(*) FROM nodes WHERE graph_id = ?", (graph_id,)
        )
        assert cursor.fetchone()[0] == 0

        # Verify all edges cascade-deleted
        cursor.execute(
            "SELECT COUNT(*) FROM edges WHERE graph_id = ?", (graph_id,)
        )
        assert cursor.fetchone()[0] == 0

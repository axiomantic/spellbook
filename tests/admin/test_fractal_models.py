"""Tests for fractal.db ORM model definitions.

Verifies that SQLAlchemy models match the actual fractal.db schema
defined in spellbook/fractal/schema.py:init_fractal_schema().
"""

import json

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from spellbook.db.base import FractalBase


class TestFractalModelTables:
    """Verify all expected tables are created with correct columns."""

    @pytest.fixture
    def engine(self):
        from spellbook.db.fractal_models import (  # noqa: F401
            FractalEdge,
            FractalGraph,
            FractalNode,
        )

        engine = create_engine("sqlite:///:memory:")
        FractalBase.metadata.create_all(engine)
        return engine

    def test_all_tables_created(self, engine):
        inspector = inspect(engine)
        table_names = set(inspector.get_table_names())
        expected = {"graphs", "nodes", "edges"}
        missing = expected - table_names
        extra = table_names - expected
        assert missing == set(), f"Missing tables: {missing}"
        assert extra == set(), f"Unexpected tables: {extra}"

    def test_graphs_columns(self, engine):
        inspector = inspect(engine)
        columns = {col["name"] for col in inspector.get_columns("graphs")}
        expected = {
            "id",
            "seed",
            "intensity",
            "checkpoint_mode",
            "status",
            "metadata_json",
            "project_dir",
            "created_at",
            "updated_at",
        }
        assert columns == expected

    def test_nodes_columns(self, engine):
        inspector = inspect(engine)
        columns = {col["name"] for col in inspector.get_columns("nodes")}
        expected = {
            "id",
            "graph_id",
            "parent_id",
            "node_type",
            "text",
            "owner",
            "depth",
            "status",
            "metadata_json",
            "created_at",
            "claimed_at",
            "answered_at",
            "synthesized_at",
            "session_id",
        }
        assert columns == expected

    def test_edges_columns(self, engine):
        inspector = inspect(engine)
        columns = {col["name"] for col in inspector.get_columns("edges")}
        expected = {
            "id",
            "graph_id",
            "from_node",
            "to_node",
            "edge_type",
            "metadata_json",
            "created_at",
        }
        assert columns == expected

    def test_nodes_has_no_content_column(self, engine):
        """The column is 'text', NOT 'content' -- verify absence."""
        inspector = inspect(engine)
        columns = {col["name"] for col in inspector.get_columns("nodes")}
        assert "content" not in columns
        assert "text" in columns


class TestFractalGraphModel:
    """Verify FractalGraph model behavior."""

    @pytest.fixture
    def engine(self):
        from spellbook.db.fractal_models import (  # noqa: F401
            FractalEdge,
            FractalGraph,
            FractalNode,
        )

        engine = create_engine("sqlite:///:memory:")
        FractalBase.metadata.create_all(engine)
        return engine

    def test_graph_creation_and_to_dict(self, engine):
        from spellbook.db.fractal_models import FractalGraph

        g = FractalGraph(
            id="g-1",
            seed="test seed",
            intensity="explore",
            checkpoint_mode="auto",
            status="active",
            metadata_json='{"key": "val"}',
            project_dir="/test/project",
            created_at="2026-03-20T00:00:00",
            updated_at="2026-03-20T00:00:00",
        )
        d = g.to_dict()
        assert d == {
            "id": "g-1",
            "seed": "test seed",
            "intensity": "explore",
            "checkpoint_mode": "auto",
            "status": "active",
            "metadata": {"key": "val"},
            "project_dir": "/test/project",
            "created_at": "2026-03-20T00:00:00",
            "updated_at": "2026-03-20T00:00:00",
        }

    def test_graph_to_dict_excludes_metadata_json_key(self, engine):
        from spellbook.db.fractal_models import FractalGraph

        g = FractalGraph(
            id="g-2",
            seed="s",
            intensity="pulse",
            checkpoint_mode="manual",
        )
        d = g.to_dict()
        assert "metadata_json" not in d
        assert "metadata" in d

    def test_graph_to_dict_handles_empty_metadata(self, engine):
        from spellbook.db.fractal_models import FractalGraph

        g = FractalGraph(
            id="g-3",
            seed="s",
            intensity="deep",
            checkpoint_mode="manual",
            metadata_json="{}",
        )
        d = g.to_dict()
        assert d["metadata"] == {}

    def test_graph_to_dict_handles_none_metadata(self, engine):
        from spellbook.db.fractal_models import FractalGraph

        g = FractalGraph(
            id="g-4",
            seed="s",
            intensity="pulse",
            checkpoint_mode="manual",
            metadata_json=None,
        )
        d = g.to_dict()
        assert d["metadata"] == {}

    def test_graph_roundtrip_persistence(self, engine):
        from spellbook.db.fractal_models import FractalGraph

        with Session(engine) as session:
            graph = FractalGraph(
                id="g-rt",
                seed="roundtrip",
                intensity="explore",
                checkpoint_mode="auto",
                status="active",
                metadata_json='{"round": "trip"}',
                project_dir="/rt",
            )
            session.add(graph)
            session.commit()

            loaded = session.get(FractalGraph, "g-rt")
            assert loaded is not None
            d = loaded.to_dict()
            assert d == {
                "id": "g-rt",
                "seed": "roundtrip",
                "intensity": "explore",
                "checkpoint_mode": "auto",
                "status": "active",
                "metadata": {"round": "trip"},
                "project_dir": "/rt",
                "created_at": d["created_at"],
                "updated_at": d["updated_at"],
            }


class TestFractalNodeModel:
    """Verify FractalNode model behavior."""

    @pytest.fixture
    def engine(self):
        from spellbook.db.fractal_models import (  # noqa: F401
            FractalEdge,
            FractalGraph,
            FractalNode,
        )

        engine = create_engine("sqlite:///:memory:")
        FractalBase.metadata.create_all(engine)
        return engine

    def test_node_creation_and_to_dict(self, engine):
        from spellbook.db.fractal_models import FractalNode

        n = FractalNode(
            id="n-1",
            graph_id="g-1",
            parent_id=None,
            node_type="question",
            text="What is X?",
            owner="agent-1",
            depth=0,
            status="open",
            metadata_json='{"importance": "high"}',
            created_at="2026-03-20T00:00:00",
            claimed_at=None,
            answered_at=None,
            synthesized_at=None,
            session_id="sess-1",
        )
        d = n.to_dict()
        assert d == {
            "id": "n-1",
            "graph_id": "g-1",
            "parent_id": None,
            "node_type": "question",
            "text": "What is X?",
            "owner": "agent-1",
            "depth": 0,
            "status": "open",
            "metadata": {"importance": "high"},
            "created_at": "2026-03-20T00:00:00",
            "claimed_at": None,
            "answered_at": None,
            "synthesized_at": None,
            "session_id": "sess-1",
        }

    def test_node_to_dict_excludes_metadata_json_key(self, engine):
        from spellbook.db.fractal_models import FractalNode

        n = FractalNode(
            id="n-2",
            graph_id="g-1",
            node_type="answer",
            text="X is Y",
        )
        d = n.to_dict()
        assert "metadata_json" not in d
        assert "metadata" in d
        assert "content" not in d

    def test_node_uses_text_not_content(self, engine):
        from spellbook.db.fractal_models import FractalNode

        n = FractalNode(
            id="n-3",
            graph_id="g-1",
            node_type="question",
            text="A question",
        )
        d = n.to_dict()
        assert d["text"] == "A question"
        assert "content" not in d

    def test_node_roundtrip_with_graph_fk(self, engine):
        from spellbook.db.fractal_models import FractalGraph, FractalNode

        with Session(engine) as session:
            graph = FractalGraph(
                id="g-fk",
                seed="fk test",
                intensity="pulse",
                checkpoint_mode="manual",
            )
            node = FractalNode(
                id="n-fk",
                graph_id="g-fk",
                node_type="question",
                text="FK question",
                depth=0,
            )
            session.add_all([graph, node])
            session.commit()

            loaded = session.get(FractalNode, "n-fk")
            assert loaded is not None
            assert loaded.graph_id == "g-fk"
            assert loaded.text == "FK question"

    def test_node_parent_self_reference(self, engine):
        from spellbook.db.fractal_models import FractalGraph, FractalNode

        with Session(engine) as session:
            graph = FractalGraph(
                id="g-sr",
                seed="self-ref",
                intensity="explore",
                checkpoint_mode="auto",
            )
            parent = FractalNode(
                id="n-parent",
                graph_id="g-sr",
                node_type="question",
                text="Parent Q",
                depth=0,
            )
            child = FractalNode(
                id="n-child",
                graph_id="g-sr",
                parent_id="n-parent",
                node_type="answer",
                text="Child A",
                depth=1,
            )
            session.add_all([graph, parent, child])
            session.commit()

            loaded_child = session.get(FractalNode, "n-child")
            assert loaded_child is not None
            assert loaded_child.parent_id == "n-parent"

            loaded_parent = session.get(FractalNode, "n-parent")
            assert loaded_parent is not None
            assert len(loaded_parent.children) == 1
            assert loaded_parent.children[0].id == "n-child"


class TestFractalEdgeModel:
    """Verify FractalEdge model behavior."""

    @pytest.fixture
    def engine(self):
        from spellbook.db.fractal_models import (  # noqa: F401
            FractalEdge,
            FractalGraph,
            FractalNode,
        )

        engine = create_engine("sqlite:///:memory:")
        FractalBase.metadata.create_all(engine)
        return engine

    def test_edge_creation_and_to_dict(self, engine):
        from spellbook.db.fractal_models import FractalEdge

        e = FractalEdge(
            graph_id="g-1",
            from_node="n-1",
            to_node="n-2",
            edge_type="parent_child",
            metadata_json='{"weight": 1.0}',
            created_at="2026-03-20T00:00:00",
        )
        d = e.to_dict()
        assert d == {
            "id": None,
            "graph_id": "g-1",
            "from_node": "n-1",
            "to_node": "n-2",
            "edge_type": "parent_child",
            "metadata": {"weight": 1.0},
            "created_at": "2026-03-20T00:00:00",
        }

    def test_edge_to_dict_excludes_metadata_json_key(self, engine):
        from spellbook.db.fractal_models import FractalEdge

        e = FractalEdge(
            graph_id="g-1",
            from_node="n-1",
            to_node="n-2",
            edge_type="convergence",
        )
        d = e.to_dict()
        assert "metadata_json" not in d
        assert "metadata" in d

    def test_edge_roundtrip_persistence(self, engine):
        from spellbook.db.fractal_models import (
            FractalEdge,
            FractalGraph,
            FractalNode,
        )

        with Session(engine) as session:
            graph = FractalGraph(
                id="g-edge",
                seed="edge test",
                intensity="deep",
                checkpoint_mode="auto",
            )
            n1 = FractalNode(
                id="n-e1",
                graph_id="g-edge",
                node_type="question",
                text="Q1",
                depth=0,
            )
            n2 = FractalNode(
                id="n-e2",
                graph_id="g-edge",
                node_type="answer",
                text="A1",
                depth=1,
            )
            edge = FractalEdge(
                graph_id="g-edge",
                from_node="n-e1",
                to_node="n-e2",
                edge_type="parent_child",
                metadata_json='{"test": true}',
            )
            session.add_all([graph, n1, n2, edge])
            session.commit()

            loaded = session.query(FractalEdge).first()
            assert loaded is not None
            assert loaded.id is not None  # autoincrement assigned
            d = loaded.to_dict()
            assert d == {
                "id": loaded.id,
                "graph_id": "g-edge",
                "from_node": "n-e1",
                "to_node": "n-e2",
                "edge_type": "parent_child",
                "metadata": {"test": True},
                "created_at": d["created_at"],
            }

    def test_edge_unique_constraint(self, engine):
        from spellbook.db.fractal_models import (
            FractalEdge,
            FractalGraph,
            FractalNode,
        )
        from sqlalchemy.exc import IntegrityError

        with Session(engine) as session:
            graph = FractalGraph(
                id="g-uniq",
                seed="uniq",
                intensity="pulse",
                checkpoint_mode="manual",
            )
            n1 = FractalNode(
                id="n-u1",
                graph_id="g-uniq",
                node_type="question",
                text="Q",
                depth=0,
            )
            n2 = FractalNode(
                id="n-u2",
                graph_id="g-uniq",
                node_type="answer",
                text="A",
                depth=1,
            )
            e1 = FractalEdge(
                graph_id="g-uniq",
                from_node="n-u1",
                to_node="n-u2",
                edge_type="parent_child",
            )
            session.add_all([graph, n1, n2, e1])
            session.commit()

            # Duplicate should raise IntegrityError
            e2 = FractalEdge(
                graph_id="g-uniq",
                from_node="n-u1",
                to_node="n-u2",
                edge_type="parent_child",
            )
            session.add(e2)
            with pytest.raises(IntegrityError):
                session.commit()


class TestFractalRelationships:
    """Verify ORM relationships between models."""

    @pytest.fixture
    def engine(self):
        from spellbook.db.fractal_models import (  # noqa: F401
            FractalEdge,
            FractalGraph,
            FractalNode,
        )

        engine = create_engine("sqlite:///:memory:")
        FractalBase.metadata.create_all(engine)
        return engine

    def test_graph_nodes_relationship(self, engine):
        from spellbook.db.fractal_models import FractalGraph, FractalNode

        with Session(engine) as session:
            graph = FractalGraph(
                id="g-rel",
                seed="rel test",
                intensity="pulse",
                checkpoint_mode="manual",
            )
            n1 = FractalNode(
                id="n-r1",
                graph_id="g-rel",
                node_type="question",
                text="Q1",
                depth=0,
            )
            n2 = FractalNode(
                id="n-r2",
                graph_id="g-rel",
                node_type="answer",
                text="A1",
                depth=1,
            )
            session.add_all([graph, n1, n2])
            session.commit()

            loaded = session.get(FractalGraph, "g-rel")
            assert len(loaded.nodes) == 2
            node_ids = {n.id for n in loaded.nodes}
            assert node_ids == {"n-r1", "n-r2"}

    def test_graph_edges_relationship(self, engine):
        from spellbook.db.fractal_models import (
            FractalEdge,
            FractalGraph,
            FractalNode,
        )

        with Session(engine) as session:
            graph = FractalGraph(
                id="g-er",
                seed="edge rel",
                intensity="explore",
                checkpoint_mode="auto",
            )
            n1 = FractalNode(
                id="n-er1",
                graph_id="g-er",
                node_type="question",
                text="Q",
                depth=0,
            )
            n2 = FractalNode(
                id="n-er2",
                graph_id="g-er",
                node_type="answer",
                text="A",
                depth=1,
            )
            edge = FractalEdge(
                graph_id="g-er",
                from_node="n-er1",
                to_node="n-er2",
                edge_type="contradiction",
            )
            session.add_all([graph, n1, n2, edge])
            session.commit()

            loaded = session.get(FractalGraph, "g-er")
            assert len(loaded.edges) == 1
            assert loaded.edges[0].edge_type == "contradiction"

    def test_node_graph_backref(self, engine):
        from spellbook.db.fractal_models import FractalGraph, FractalNode

        with Session(engine) as session:
            graph = FractalGraph(
                id="g-br",
                seed="backref",
                intensity="deep",
                checkpoint_mode="manual",
            )
            node = FractalNode(
                id="n-br",
                graph_id="g-br",
                node_type="question",
                text="Q",
                depth=0,
            )
            session.add_all([graph, node])
            session.commit()

            loaded_node = session.get(FractalNode, "n-br")
            assert loaded_node.graph is not None
            assert loaded_node.graph.id == "g-br"

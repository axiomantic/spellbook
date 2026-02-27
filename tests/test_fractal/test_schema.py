"""Tests for fractal thinking database schema."""

import sqlite3

import pytest


class TestSchemaInit:
    """Tests for init_fractal_schema creating all tables."""

    def test_init_creates_schema_version_table(self, fractal_db):
        """schema_version table must exist after initialization."""
        from spellbook_mcp.fractal.schema import get_fractal_connection

        conn = get_fractal_connection(fractal_db)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
        )
        assert cursor.fetchone() is not None

    def test_init_creates_graphs_table(self, fractal_db):
        """graphs table must exist after initialization."""
        from spellbook_mcp.fractal.schema import get_fractal_connection

        conn = get_fractal_connection(fractal_db)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='graphs'"
        )
        assert cursor.fetchone() is not None

    def test_init_creates_nodes_table(self, fractal_db):
        """nodes table must exist after initialization."""
        from spellbook_mcp.fractal.schema import get_fractal_connection

        conn = get_fractal_connection(fractal_db)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='nodes'"
        )
        assert cursor.fetchone() is not None

    def test_init_creates_edges_table(self, fractal_db):
        """edges table must exist after initialization."""
        from spellbook_mcp.fractal.schema import get_fractal_connection

        conn = get_fractal_connection(fractal_db)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='edges'"
        )
        assert cursor.fetchone() is not None


class TestSchemaVersionTable:
    """Tests for schema_version table structure and content."""

    def test_schema_version_has_correct_columns(self, fractal_db):
        """schema_version table must have version and applied_at columns."""
        from spellbook_mcp.fractal.schema import get_fractal_connection

        conn = get_fractal_connection(fractal_db)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(schema_version)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}

        assert "version" in columns
        assert "INTEGER" in columns["version"].upper()
        assert "applied_at" in columns
        assert "TEXT" in columns["applied_at"].upper()

    def test_schema_version_recorded(self, fractal_db):
        """Schema version must be recorded during initialization."""
        from spellbook_mcp.fractal.models import SCHEMA_VERSION
        from spellbook_mcp.fractal.schema import get_fractal_connection

        conn = get_fractal_connection(fractal_db)
        cursor = conn.cursor()
        cursor.execute("SELECT version FROM schema_version ORDER BY version DESC LIMIT 1")
        row = cursor.fetchone()

        assert row is not None
        assert row[0] == SCHEMA_VERSION


class TestGraphsTable:
    """Tests for graphs table structure."""

    def test_graphs_has_required_columns(self, fractal_db):
        """graphs table must have all required columns."""
        from spellbook_mcp.fractal.schema import get_fractal_connection

        conn = get_fractal_connection(fractal_db)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(graphs)")
        columns = {row[1] for row in cursor.fetchall()}

        expected = {
            "id",
            "seed",
            "intensity",
            "checkpoint_mode",
            "status",
            "metadata_json",
            "created_at",
            "updated_at",
        }
        assert expected.issubset(columns)

    def test_graphs_id_is_primary_key(self, fractal_db):
        """graphs.id must be the primary key."""
        from spellbook_mcp.fractal.schema import get_fractal_connection

        conn = get_fractal_connection(fractal_db)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(graphs)")
        pk_cols = {row[1]: row[5] for row in cursor.fetchall()}

        assert pk_cols["id"] == 1

    def test_graphs_status_default_is_active(self, fractal_db):
        """graphs.status must default to 'active'."""
        from spellbook_mcp.fractal.schema import get_fractal_connection

        conn = get_fractal_connection(fractal_db)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO graphs (id, seed, intensity, checkpoint_mode)
            VALUES ('g1', 'test seed', 'pulse', 'autonomous')
        """)
        cursor.execute("SELECT status FROM graphs WHERE id = 'g1'")
        assert cursor.fetchone()[0] == "active"

    def test_graphs_intensity_check_constraint(self, fractal_db):
        """graphs.intensity must only accept valid intensities."""
        from spellbook_mcp.fractal.schema import get_fractal_connection

        conn = get_fractal_connection(fractal_db)
        cursor = conn.cursor()
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO graphs (id, seed, intensity, checkpoint_mode)
                VALUES ('g-bad', 'test', 'invalid_intensity', 'autonomous')
            """)

    def test_graphs_status_check_constraint(self, fractal_db):
        """graphs.status must only accept valid statuses."""
        from spellbook_mcp.fractal.schema import get_fractal_connection

        conn = get_fractal_connection(fractal_db)
        cursor = conn.cursor()
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO graphs (id, seed, intensity, checkpoint_mode, status)
                VALUES ('g-bad', 'test', 'pulse', 'autonomous', 'invalid_status')
            """)

    def test_graphs_metadata_json_default(self, fractal_db):
        """graphs.metadata_json must default to '{}'."""
        from spellbook_mcp.fractal.schema import get_fractal_connection

        conn = get_fractal_connection(fractal_db)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO graphs (id, seed, intensity, checkpoint_mode)
            VALUES ('g2', 'test seed', 'explore', 'convergence')
        """)
        cursor.execute("SELECT metadata_json FROM graphs WHERE id = 'g2'")
        assert cursor.fetchone()[0] == "{}"


class TestNodesTable:
    """Tests for nodes table structure."""

    def test_nodes_has_required_columns(self, fractal_db):
        """nodes table must have all required columns."""
        from spellbook_mcp.fractal.schema import get_fractal_connection

        conn = get_fractal_connection(fractal_db)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(nodes)")
        columns = {row[1] for row in cursor.fetchall()}

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
        }
        assert expected.issubset(columns)

    def test_nodes_id_is_primary_key(self, fractal_db):
        """nodes.id must be the primary key."""
        from spellbook_mcp.fractal.schema import get_fractal_connection

        conn = get_fractal_connection(fractal_db)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(nodes)")
        pk_cols = {row[1]: row[5] for row in cursor.fetchall()}

        assert pk_cols["id"] == 1

    def test_nodes_graph_id_foreign_key(self, fractal_db):
        """nodes.graph_id must reference graphs(id)."""
        from spellbook_mcp.fractal.schema import get_fractal_connection

        conn = get_fractal_connection(fractal_db)
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_key_list(nodes)")
        fks = cursor.fetchall()
        graph_fk = [fk for fk in fks if fk[2] == "graphs" and fk[3] == "graph_id"]
        assert len(graph_fk) > 0

    def test_nodes_node_type_check_constraint(self, fractal_db):
        """nodes.node_type must only accept valid types."""
        from spellbook_mcp.fractal.schema import get_fractal_connection

        conn = get_fractal_connection(fractal_db)
        cursor = conn.cursor()
        # First create a graph to satisfy FK
        cursor.execute("""
            INSERT INTO graphs (id, seed, intensity, checkpoint_mode)
            VALUES ('g-for-node', 'test', 'pulse', 'autonomous')
        """)
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO nodes (id, graph_id, node_type, text)
                VALUES ('n-bad', 'g-for-node', 'invalid_type', 'test')
            """)

    def test_nodes_status_check_constraint(self, fractal_db):
        """nodes.status must only accept valid statuses."""
        from spellbook_mcp.fractal.schema import get_fractal_connection

        conn = get_fractal_connection(fractal_db)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO graphs (id, seed, intensity, checkpoint_mode)
            VALUES ('g-for-node2', 'test', 'pulse', 'autonomous')
        """)
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO nodes (id, graph_id, node_type, text, status)
                VALUES ('n-bad2', 'g-for-node2', 'question', 'test', 'invalid_status')
            """)

    def test_nodes_depth_default_is_zero(self, fractal_db):
        """nodes.depth must default to 0."""
        from spellbook_mcp.fractal.schema import get_fractal_connection

        conn = get_fractal_connection(fractal_db)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO graphs (id, seed, intensity, checkpoint_mode)
            VALUES ('g-depth', 'test', 'pulse', 'autonomous')
        """)
        cursor.execute("""
            INSERT INTO nodes (id, graph_id, node_type, text)
            VALUES ('n-depth', 'g-depth', 'question', 'test')
        """)
        cursor.execute("SELECT depth FROM nodes WHERE id = 'n-depth'")
        assert cursor.fetchone()[0] == 0

    def test_nodes_status_default_is_open(self, fractal_db):
        """nodes.status must default to 'open'."""
        from spellbook_mcp.fractal.schema import get_fractal_connection

        conn = get_fractal_connection(fractal_db)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO graphs (id, seed, intensity, checkpoint_mode)
            VALUES ('g-status', 'test', 'pulse', 'autonomous')
        """)
        cursor.execute("""
            INSERT INTO nodes (id, graph_id, node_type, text)
            VALUES ('n-status', 'g-status', 'question', 'test')
        """)
        cursor.execute("SELECT status FROM nodes WHERE id = 'n-status'")
        assert cursor.fetchone()[0] == "open"


class TestEdgesTable:
    """Tests for edges table structure."""

    def test_edges_has_required_columns(self, fractal_db):
        """edges table must have all required columns."""
        from spellbook_mcp.fractal.schema import get_fractal_connection

        conn = get_fractal_connection(fractal_db)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(edges)")
        columns = {row[1] for row in cursor.fetchall()}

        expected = {
            "id",
            "graph_id",
            "from_node",
            "to_node",
            "edge_type",
            "metadata_json",
            "created_at",
        }
        assert expected.issubset(columns)

    def test_edges_id_autoincrement(self, fractal_db):
        """edges.id must autoincrement."""
        from spellbook_mcp.fractal.schema import get_fractal_connection

        conn = get_fractal_connection(fractal_db)
        cursor = conn.cursor()
        # Set up graph and nodes
        cursor.execute("""
            INSERT INTO graphs (id, seed, intensity, checkpoint_mode)
            VALUES ('g-edge', 'test', 'pulse', 'autonomous')
        """)
        cursor.execute("""
            INSERT INTO nodes (id, graph_id, node_type, text)
            VALUES ('n1', 'g-edge', 'question', 'q1')
        """)
        cursor.execute("""
            INSERT INTO nodes (id, graph_id, node_type, text)
            VALUES ('n2', 'g-edge', 'answer', 'a1')
        """)
        cursor.execute("""
            INSERT INTO nodes (id, graph_id, node_type, text)
            VALUES ('n3', 'g-edge', 'question', 'q2')
        """)
        # Insert two edges
        cursor.execute("""
            INSERT INTO edges (graph_id, from_node, to_node, edge_type)
            VALUES ('g-edge', 'n1', 'n2', 'parent_child')
        """)
        cursor.execute("""
            INSERT INTO edges (graph_id, from_node, to_node, edge_type)
            VALUES ('g-edge', 'n2', 'n3', 'parent_child')
        """)
        cursor.execute("SELECT id FROM edges ORDER BY id")
        ids = [row[0] for row in cursor.fetchall()]
        assert ids[0] < ids[1]

    def test_edges_edge_type_check_constraint(self, fractal_db):
        """edges.edge_type must only accept valid types."""
        from spellbook_mcp.fractal.schema import get_fractal_connection

        conn = get_fractal_connection(fractal_db)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO graphs (id, seed, intensity, checkpoint_mode)
            VALUES ('g-edge-ck', 'test', 'pulse', 'autonomous')
        """)
        cursor.execute("""
            INSERT INTO nodes (id, graph_id, node_type, text)
            VALUES ('n-ck1', 'g-edge-ck', 'question', 'q')
        """)
        cursor.execute("""
            INSERT INTO nodes (id, graph_id, node_type, text)
            VALUES ('n-ck2', 'g-edge-ck', 'answer', 'a')
        """)
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO edges (graph_id, from_node, to_node, edge_type)
                VALUES ('g-edge-ck', 'n-ck1', 'n-ck2', 'invalid_type')
            """)

    def test_edges_unique_constraint(self, fractal_db):
        """edges must enforce unique (graph_id, from_node, to_node, edge_type)."""
        from spellbook_mcp.fractal.schema import get_fractal_connection

        conn = get_fractal_connection(fractal_db)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO graphs (id, seed, intensity, checkpoint_mode)
            VALUES ('g-uniq', 'test', 'pulse', 'autonomous')
        """)
        cursor.execute("""
            INSERT INTO nodes (id, graph_id, node_type, text)
            VALUES ('n-u1', 'g-uniq', 'question', 'q')
        """)
        cursor.execute("""
            INSERT INTO nodes (id, graph_id, node_type, text)
            VALUES ('n-u2', 'g-uniq', 'answer', 'a')
        """)
        cursor.execute("""
            INSERT INTO edges (graph_id, from_node, to_node, edge_type)
            VALUES ('g-uniq', 'n-u1', 'n-u2', 'parent_child')
        """)
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO edges (graph_id, from_node, to_node, edge_type)
                VALUES ('g-uniq', 'n-u1', 'n-u2', 'parent_child')
            """)

    def test_edges_foreign_keys_to_graphs(self, fractal_db):
        """edges.graph_id must reference graphs(id)."""
        from spellbook_mcp.fractal.schema import get_fractal_connection

        conn = get_fractal_connection(fractal_db)
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_key_list(edges)")
        fks = cursor.fetchall()
        graph_fk = [fk for fk in fks if fk[2] == "graphs" and fk[3] == "graph_id"]
        assert len(graph_fk) > 0

    def test_edges_foreign_keys_to_nodes(self, fractal_db):
        """edges.from_node and to_node must reference nodes(id)."""
        from spellbook_mcp.fractal.schema import get_fractal_connection

        conn = get_fractal_connection(fractal_db)
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_key_list(edges)")
        fks = cursor.fetchall()
        from_fk = [fk for fk in fks if fk[2] == "nodes" and fk[3] == "from_node"]
        to_fk = [fk for fk in fks if fk[2] == "nodes" and fk[3] == "to_node"]
        assert len(from_fk) > 0
        assert len(to_fk) > 0


class TestIndexes:
    """Tests for database indexes."""

    def test_index_nodes_graph_id(self, fractal_db):
        """Index on nodes(graph_id) must exist."""
        from spellbook_mcp.fractal.schema import get_fractal_connection

        conn = get_fractal_connection(fractal_db)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_nodes_graph_id'"
        )
        assert cursor.fetchone() is not None

    def test_index_nodes_parent_id(self, fractal_db):
        """Index on nodes(parent_id) must exist."""
        from spellbook_mcp.fractal.schema import get_fractal_connection

        conn = get_fractal_connection(fractal_db)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_nodes_parent_id'"
        )
        assert cursor.fetchone() is not None

    def test_index_nodes_graph_status(self, fractal_db):
        """Index on nodes(graph_id, status) must exist."""
        from spellbook_mcp.fractal.schema import get_fractal_connection

        conn = get_fractal_connection(fractal_db)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_nodes_graph_status'"
        )
        assert cursor.fetchone() is not None

    def test_index_edges_graph_id(self, fractal_db):
        """Index on edges(graph_id) must exist."""
        from spellbook_mcp.fractal.schema import get_fractal_connection

        conn = get_fractal_connection(fractal_db)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_edges_graph_id'"
        )
        assert cursor.fetchone() is not None

    def test_index_edges_from_node(self, fractal_db):
        """Index on edges(from_node) must exist."""
        from spellbook_mcp.fractal.schema import get_fractal_connection

        conn = get_fractal_connection(fractal_db)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_edges_from_node'"
        )
        assert cursor.fetchone() is not None

    def test_index_edges_to_node(self, fractal_db):
        """Index on edges(to_node) must exist."""
        from spellbook_mcp.fractal.schema import get_fractal_connection

        conn = get_fractal_connection(fractal_db)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_edges_to_node'"
        )
        assert cursor.fetchone() is not None


class TestWALMode:
    """Tests for WAL mode configuration."""

    def test_wal_mode_enabled(self, fractal_db):
        """WAL mode must be enabled for concurrent access."""
        from spellbook_mcp.fractal.schema import get_fractal_connection

        conn = get_fractal_connection(fractal_db)
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode")
        result = cursor.fetchone()[0]

        assert result.upper() == "WAL"

    def test_foreign_keys_enabled(self, fractal_db):
        """Foreign keys must be enabled."""
        from spellbook_mcp.fractal.schema import get_fractal_connection

        conn = get_fractal_connection(fractal_db)
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys")
        result = cursor.fetchone()[0]

        assert result == 1


class TestIdempotency:
    """Tests for schema initialization idempotency."""

    def test_init_fractal_schema_idempotent(self, tmp_path):
        """Calling init_fractal_schema multiple times should not error."""
        from spellbook_mcp.fractal.schema import (
            close_all_fractal_connections,
            get_fractal_connection,
            init_fractal_schema,
        )

        db_path = str(tmp_path / "fractal.db")

        init_fractal_schema(db_path)
        init_fractal_schema(db_path)
        init_fractal_schema(db_path)

        conn = get_fractal_connection(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM schema_version")
        count = cursor.fetchone()[0]

        assert count == 1
        close_all_fractal_connections()


class TestForeignKeyCascade:
    """Tests for foreign key cascade delete behavior."""

    def test_delete_graph_cascades_to_nodes(self, fractal_db):
        """Deleting a graph must cascade delete its nodes."""
        from spellbook_mcp.fractal.schema import get_fractal_connection

        conn = get_fractal_connection(fractal_db)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO graphs (id, seed, intensity, checkpoint_mode)
            VALUES ('g-cascade', 'test', 'pulse', 'autonomous')
        """)
        cursor.execute("""
            INSERT INTO nodes (id, graph_id, node_type, text)
            VALUES ('n-cascade1', 'g-cascade', 'question', 'q1')
        """)
        cursor.execute("""
            INSERT INTO nodes (id, graph_id, node_type, text)
            VALUES ('n-cascade2', 'g-cascade', 'answer', 'a1')
        """)
        conn.commit()

        # Verify nodes exist
        cursor.execute("SELECT COUNT(*) FROM nodes WHERE graph_id = 'g-cascade'")
        assert cursor.fetchone()[0] == 2

        # Delete graph
        cursor.execute("DELETE FROM graphs WHERE id = 'g-cascade'")
        conn.commit()

        # Nodes should be cascade deleted
        cursor.execute("SELECT COUNT(*) FROM nodes WHERE graph_id = 'g-cascade'")
        assert cursor.fetchone()[0] == 0

    def test_delete_graph_cascades_to_edges(self, fractal_db):
        """Deleting a graph must cascade delete its edges."""
        from spellbook_mcp.fractal.schema import get_fractal_connection

        conn = get_fractal_connection(fractal_db)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO graphs (id, seed, intensity, checkpoint_mode)
            VALUES ('g-cascade-e', 'test', 'pulse', 'autonomous')
        """)
        cursor.execute("""
            INSERT INTO nodes (id, graph_id, node_type, text)
            VALUES ('n-ce1', 'g-cascade-e', 'question', 'q1')
        """)
        cursor.execute("""
            INSERT INTO nodes (id, graph_id, node_type, text)
            VALUES ('n-ce2', 'g-cascade-e', 'answer', 'a1')
        """)
        cursor.execute("""
            INSERT INTO edges (graph_id, from_node, to_node, edge_type)
            VALUES ('g-cascade-e', 'n-ce1', 'n-ce2', 'parent_child')
        """)
        conn.commit()

        # Verify edge exists
        cursor.execute("SELECT COUNT(*) FROM edges WHERE graph_id = 'g-cascade-e'")
        assert cursor.fetchone()[0] == 1

        # Delete graph
        cursor.execute("DELETE FROM graphs WHERE id = 'g-cascade-e'")
        conn.commit()

        # Edge should be cascade deleted
        cursor.execute("SELECT COUNT(*) FROM edges WHERE graph_id = 'g-cascade-e'")
        assert cursor.fetchone()[0] == 0


class TestConnectionCache:
    """Tests for connection caching and cleanup."""

    def test_get_connection_returns_same_connection(self, tmp_path):
        """get_fractal_connection must return cached connection."""
        from spellbook_mcp.fractal.schema import (
            close_all_fractal_connections,
            get_fractal_connection,
            init_fractal_schema,
        )

        db_path = str(tmp_path / "cache-test.db")
        init_fractal_schema(db_path)

        conn1 = get_fractal_connection(db_path)
        conn2 = get_fractal_connection(db_path)

        assert conn1 is conn2
        close_all_fractal_connections()

    def test_close_all_clears_cache(self, tmp_path):
        """close_all_fractal_connections must clear connection cache."""
        from spellbook_mcp.fractal.schema import (
            close_all_fractal_connections,
            get_fractal_connection,
            init_fractal_schema,
        )

        db_path = str(tmp_path / "clear-test.db")
        init_fractal_schema(db_path)

        conn1 = get_fractal_connection(db_path)
        close_all_fractal_connections()

        # After clearing, should get a new connection
        conn2 = get_fractal_connection(db_path)
        assert conn1 is not conn2
        close_all_fractal_connections()


class TestGetFractalDbPath:
    """Tests for get_fractal_db_path function."""

    def test_returns_path_object(self):
        """get_fractal_db_path must return a Path object."""
        from pathlib import Path

        from spellbook_mcp.fractal.schema import get_fractal_db_path

        db_path = get_fractal_db_path()

        assert isinstance(db_path, Path)
        assert db_path.name == "fractal.db"

    def test_path_in_spellbook_dir(self):
        """get_fractal_db_path must be in ~/.local/spellbook/."""
        from spellbook_mcp.fractal.schema import get_fractal_db_path

        db_path = get_fractal_db_path()

        assert db_path.parent.name == "spellbook"
        assert db_path.parent.parent.name == ".local"

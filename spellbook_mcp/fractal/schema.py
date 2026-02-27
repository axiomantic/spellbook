"""Database schema and connection management for fractal thinking.

This module provides SQLite database initialization and connection management
for the fractal thinking system, including schema versioning and WAL mode.
"""

import sqlite3
import threading
from pathlib import Path
from typing import Optional

from spellbook_mcp.fractal.models import SCHEMA_VERSION


def get_fractal_db_path() -> Path:
    """Get path to fractal database file.

    Returns:
        Path to ~/.local/spellbook/fractal.db
    """
    db_dir = Path.home() / ".local" / "spellbook"
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "fractal.db"


_connections: dict = {}
_connections_lock: threading.Lock = threading.Lock()


def get_fractal_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Get database connection with WAL mode enabled.

    Maintains a connection cache to reuse connections efficiently.
    All connections are configured with WAL mode for concurrent access.

    Args:
        db_path: Path to database file (defaults to standard location)

    Returns:
        SQLite connection with WAL mode enabled
    """
    if db_path is None:
        db_path = str(get_fractal_db_path())

    with _connections_lock:
        if db_path in _connections:
            return _connections[db_path]

        conn = sqlite3.connect(db_path, timeout=5.0, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")

        _connections[db_path] = conn
        return conn


def close_all_fractal_connections() -> None:
    """Close all cached fractal database connections.

    Used primarily for cleanup in tests.
    """
    global _connections
    with _connections_lock:
        for conn in _connections.values():
            conn.close()
        _connections = {}


def init_fractal_schema(db_path: Optional[str] = None) -> None:
    """Initialize fractal database schema.

    Creates all required tables with indices. Idempotent - safe to call
    multiple times. Records schema version on first initialization.

    Args:
        db_path: Path to database file (defaults to standard location)
    """
    conn = get_fractal_connection(db_path)
    cursor = conn.cursor()

    # Schema version tracking
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER NOT NULL,
            applied_at TEXT NOT NULL
        )
    """)

    # Check if we need to record the schema version
    cursor.execute(
        "SELECT COUNT(*) FROM schema_version WHERE version = ?",
        (SCHEMA_VERSION,),
    )
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            "INSERT INTO schema_version (version, applied_at) VALUES (?, datetime('now'))",
            (SCHEMA_VERSION,),
        )

    # Graphs - top-level fractal exploration sessions
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS graphs (
            id TEXT PRIMARY KEY,
            seed TEXT NOT NULL,
            intensity TEXT NOT NULL CHECK(intensity IN ('pulse', 'explore', 'deep')),
            checkpoint_mode TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active'
                CHECK(status IN ('active', 'paused', 'completed', 'error', 'budget_exhausted')),
            metadata_json TEXT DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    # Nodes - questions and answers in the fractal graph
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS nodes (
            id TEXT PRIMARY KEY,
            graph_id TEXT NOT NULL REFERENCES graphs(id) ON DELETE CASCADE,
            parent_id TEXT REFERENCES nodes(id) ON DELETE CASCADE,
            node_type TEXT NOT NULL CHECK(node_type IN ('question', 'answer')),
            text TEXT NOT NULL,
            owner TEXT,
            depth INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'open'
                CHECK(status IN ('open', 'answered', 'saturated', 'error', 'budget_exhausted')),
            metadata_json TEXT DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    # Edges - relationships between nodes
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS edges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            graph_id TEXT NOT NULL REFERENCES graphs(id) ON DELETE CASCADE,
            from_node TEXT NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
            to_node TEXT NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
            edge_type TEXT NOT NULL
                CHECK(edge_type IN ('parent_child', 'convergence', 'contradiction')),
            metadata_json TEXT DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(graph_id, from_node, to_node, edge_type)
        )
    """)

    # Indexes on nodes
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_nodes_graph_id ON nodes(graph_id)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_nodes_parent_id ON nodes(parent_id)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_nodes_graph_status ON nodes(graph_id, status)
    """)

    # Indexes on edges
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_edges_graph_id ON edges(graph_id)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_edges_from_node ON edges(from_node)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_edges_to_node ON edges(to_node)
    """)

    conn.commit()

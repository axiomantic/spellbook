"""Database schema and connection management for Forged autonomous development.

This module provides SQLite database initialization and connection management
for the Forged workflow system, including schema versioning and WAL mode.
"""

import sqlite3
import threading
from pathlib import Path
from typing import Optional

from spellbook_mcp.forged.models import SCHEMA_VERSION


def get_forged_db_path() -> Path:
    """Get path to Forged database file.

    Returns:
        Path to ~/.local/spellbook/forged.db
    """
    db_dir = Path.home() / ".local" / "spellbook"
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "forged.db"


_connections: dict = {}
_connections_lock: threading.Lock = threading.Lock()


def get_forged_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Get database connection with WAL mode enabled.

    Maintains a connection cache to reuse connections efficiently.
    All connections are configured with WAL mode for concurrent access.

    Args:
        db_path: Path to database file (defaults to standard location)

    Returns:
        SQLite connection with WAL mode enabled
    """
    if db_path is None:
        db_path = str(get_forged_db_path())

    with _connections_lock:
        if db_path in _connections:
            return _connections[db_path]

        conn = sqlite3.connect(db_path, timeout=5.0, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")

        _connections[db_path] = conn
        return conn


def init_forged_schema(db_path: Optional[str] = None) -> None:
    """Initialize Forged database schema.

    Creates all required tables with indices. Idempotent - safe to call
    multiple times. Records schema version on first initialization.

    Args:
        db_path: Path to database file (defaults to standard location)
    """
    conn = get_forged_connection(db_path)
    cursor = conn.cursor()

    # Schema version tracking
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER NOT NULL,
            applied_at TEXT NOT NULL
        )
    """)

    # Check if we need to record the schema version
    cursor.execute("SELECT COUNT(*) FROM schema_version WHERE version = ?", (SCHEMA_VERSION,))
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            "INSERT INTO schema_version (version, applied_at) VALUES (?, datetime('now'))",
            (SCHEMA_VERSION,)
        )

    # Forge tokens - workflow enforcement
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS forge_tokens (
            id TEXT PRIMARY KEY,
            feature_name TEXT NOT NULL,
            stage TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            invalidated_at TEXT
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_forge_tokens_feature ON forge_tokens(feature_name)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_forge_tokens_stage ON forge_tokens(stage)
    """)

    # Iteration state - core state tracking
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS iteration_state (
            project_path TEXT NOT NULL,
            feature_name TEXT NOT NULL,
            iteration_number INTEGER NOT NULL,
            current_stage TEXT NOT NULL,
            accumulated_knowledge TEXT,
            feedback_history TEXT,
            artifacts_produced TEXT,
            preferences TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY (project_path, feature_name)
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_iteration_state_stage ON iteration_state(current_stage)
    """)

    # Reflections - learning from failures
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reflections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            feature_name TEXT NOT NULL,
            validator TEXT NOT NULL,
            iteration INTEGER NOT NULL,
            failure_description TEXT,
            root_cause TEXT,
            lesson_learned TEXT,
            status TEXT NOT NULL DEFAULT 'PENDING',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            resolved_at TEXT
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_reflections_feature ON reflections(feature_name)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_reflections_status ON reflections(status)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_reflections_validator ON reflections(validator)
    """)

    # Tool analytics - usage tracking
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tool_analytics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tool_name TEXT NOT NULL,
            project_path TEXT NOT NULL,
            feature_name TEXT,
            stage TEXT,
            iteration INTEGER,
            input_tokens INTEGER,
            output_tokens INTEGER,
            duration_ms INTEGER,
            success INTEGER NOT NULL DEFAULT 1,
            called_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_tool_analytics_tool ON tool_analytics(tool_name)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_tool_analytics_project ON tool_analytics(project_path)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_tool_analytics_called ON tool_analytics(called_at)
    """)

    conn.commit()


def close_forged_connections() -> None:
    """Close all cached Forged database connections.

    Used primarily for cleanup in tests.
    """
    global _connections
    with _connections_lock:
        for conn in _connections.values():
            conn.close()
        _connections = {}

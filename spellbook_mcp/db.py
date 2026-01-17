"""Database schema and connection management for session recovery."""

import sqlite3
import threading
from pathlib import Path
from typing import Optional


def get_db_path() -> Path:
    """Get path to spellbook database file.

    Returns:
        Path to ~/.local/spellbook/spellbook.db
    """
    db_dir = Path.home() / ".local" / "spellbook"
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "spellbook.db"


_connections = {}  # Cache connections by path
_connections_lock: threading.Lock = threading.Lock()


def get_connection(db_path: str = None) -> sqlite3.Connection:
    """Get database connection with WAL mode enabled.

    Args:
        db_path: Path to database file (defaults to standard location)

    Returns:
        SQLite connection with WAL mode enabled
    """
    if db_path is None:
        db_path = str(get_db_path())

    with _connections_lock:
        # Return cached connection if exists
        if db_path in _connections:
            return _connections[db_path]

        conn = sqlite3.connect(db_path, timeout=5.0, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")

        _connections[db_path] = conn
        return conn


def init_db(db_path: str = None) -> None:
    """Initialize database schema.

    Creates all required tables with indices. Idempotent - safe to call multiple times.

    Args:
        db_path: Path to database file (defaults to standard location)
    """
    conn = get_connection(db_path)
    cursor = conn.cursor()

    # Main soul state
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS souls (
            id TEXT PRIMARY KEY,
            project_path TEXT NOT NULL,
            session_id TEXT,
            bound_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            -- Extracted state (JSON)
            persona TEXT,
            active_skill TEXT,
            skill_phase TEXT,
            todos TEXT,
            recent_files TEXT,
            exact_position TEXT,
            workflow_pattern TEXT,

            -- Metadata
            summoned_at TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_souls_project ON souls(project_path)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_souls_session ON souls(session_id)
    """)

    # Subagent tracking
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS subagents (
            id TEXT PRIMARY KEY,
            soul_id TEXT,
            project_path TEXT NOT NULL,
            spawned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            -- Subagent details
            prompt_summary TEXT,
            persona TEXT,
            status TEXT,
            last_output TEXT,

            FOREIGN KEY (soul_id) REFERENCES souls(id)
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_subagents_project ON subagents(project_path)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_subagents_spawned ON subagents(spawned_at)
    """)

    # Decision memory
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_path TEXT NOT NULL,
            decision TEXT NOT NULL,
            rationale TEXT,
            decided_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_decisions_project ON decisions(project_path)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_decisions_decided ON decisions(decided_at)
    """)

    # Correction memory
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS corrections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_path TEXT NOT NULL,
            constraint_type TEXT,
            constraint_text TEXT NOT NULL,
            recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_corrections_project ON corrections(project_path)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_corrections_recorded ON corrections(recorded_at)
    """)

    # Watcher heartbeat
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS heartbeat (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()


def close_all_connections():
    """Close all cached database connections.

    Used primarily for cleanup in tests.
    """
    global _connections
    with _connections_lock:
        for conn in _connections.values():
            conn.close()
        _connections = {}

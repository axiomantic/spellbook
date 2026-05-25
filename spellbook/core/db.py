"""Database schema and connection management for session recovery.

Canonical location for database utilities. This module was migrated from
spellbook.core.db as part of the three-layer architecture reorganization.
"""

import logging
import os
import sqlite3
import threading
import time
from pathlib import Path

logger = logging.getLogger(__name__)



def get_db_path() -> Path:
    """Get path to spellbook database file.

    Returns:
        Path to ~/.local/spellbook/spellbook.db
    """
    db_dir = Path.home() / ".local" / "spellbook"
    db_dir.mkdir(parents=True, exist_ok=True)

    # Restrict directory permissions (owner-only)
    try:
        os.chmod(str(db_dir), 0o700)
    except OSError:
        pass  # May fail on Windows or special filesystems

    return db_dir / "spellbook.db"


_connections: dict[str, tuple[sqlite3.Connection, float]] = {}  # Cache: path -> (conn, created_at)
_connections_lock: threading.Lock = threading.Lock()
_CONNECTION_TTL = 3600  # 1 hour


def get_connection(db_path: str = None) -> sqlite3.Connection:
    """Get database connection with WAL mode enabled.

    Connections are cached by path. Cached connections are health-checked
    (SELECT 1) before reuse and replaced if broken or past TTL.

    Args:
        db_path: Path to database file (defaults to standard location)

    Returns:
        SQLite connection with WAL mode enabled
    """
    if db_path is None:
        db_path = str(get_db_path())

    with _connections_lock:
        if db_path in _connections:
            conn, created_at = _connections[db_path]

            # Check TTL
            if time.time() - created_at > _CONNECTION_TTL:
                try:
                    conn.close()
                except Exception:
                    pass
                del _connections[db_path]
            else:
                # Health check
                try:
                    conn.execute("SELECT 1")
                    return conn
                except sqlite3.Error:
                    try:
                        conn.close()
                    except Exception:
                        pass
                    del _connections[db_path]

        conn = sqlite3.connect(db_path, timeout=5.0, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")

        # Set file permissions (owner-only read/write)
        try:
            os.chmod(db_path, 0o600)
        except OSError:
            pass  # May fail on Windows, non-critical

        _connections[db_path] = (conn, time.time())
        return conn


def _migrate_stint_stack_schema(cursor):
    """Ensure stint_stack has NOT NULL on session_id and UNIQUE constraint (idempotent).

    SQLite doesn't support ALTER TABLE ADD CONSTRAINT or ALTER COLUMN, so we
    must recreate the table if the schema doesn't match. Checks both conditions
    in a single pass and rebuilds only if needed.
    """
    # Check if table exists
    if not cursor.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='stint_stack'"
    ).fetchone():
        return  # Table doesn't exist yet; CREATE TABLE will handle it

    # Check NOT NULL on session_id via PRAGMA
    columns = cursor.execute("PRAGMA table_info(stint_stack)").fetchall()
    session_col = next((c for c in columns if c[1] == "session_id"), None)
    has_not_null = session_col is not None and session_col[3] == 1  # notnull flag

    # Check for UNIQUE(project_path, session_id) via PRAGMA
    has_correct_unique = False
    for idx in cursor.execute("PRAGMA index_list(stint_stack)").fetchall():
        if idx[2]:  # unique flag
            idx_cols = [
                r[2] for r in cursor.execute(f"PRAGMA index_info({idx[1]})").fetchall()
            ]
            if idx_cols == ["project_path", "session_id"]:
                has_correct_unique = True
                break

    if has_not_null and has_correct_unique:
        return  # Schema already matches target

    cursor.execute("ALTER TABLE stint_stack RENAME TO _stint_stack_old")
    cursor.execute("""
        CREATE TABLE stint_stack (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_path TEXT NOT NULL,
            session_id TEXT NOT NULL,
            stack_json TEXT NOT NULL DEFAULT '[]',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(project_path, session_id)
        )
    """)
    # Migrate legacy rows with NULL session_id to a default value
    migrated = cursor.execute("SELECT COUNT(*) FROM _stint_stack_old WHERE session_id IS NULL").fetchone()[0]
    if migrated:
        logger.info("Migrating %d legacy stint_stack rows with NULL session_id to 'legacy'", migrated)
    cursor.execute("UPDATE _stint_stack_old SET session_id = 'legacy' WHERE session_id IS NULL")
    cursor.execute("""
        INSERT INTO stint_stack (id, project_path, session_id, stack_json, updated_at)
        SELECT id, project_path, session_id, stack_json, updated_at
        FROM _stint_stack_old
    """)
    cursor.execute("DROP TABLE _stint_stack_old")


def _drop_deleted_security_tables(cursor):
    """Drop security tables removed in the nuclear security cleanup.

    These tables used to back the sleuth/crypto/canary/trust-registry
    feature set and no longer exist in the ORM. Dropping them is idempotent.
    """
    for table_name in (
        "intent_checks",
        "sleuth_budget",
        "sleuth_cache",
        "canary_tokens",
        "session_content_accumulator",
        "trust_registry",
        "security_events",
        "security_mode",
    ):
        try:
            cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
        except sqlite3.Error:
            pass


def _drop_deleted_memory_tables(cursor):
    """Drop memory-system + session-soul tables removed in 0.68.0.

    Idempotent: DROP TABLE IF EXISTS, safe on fresh and existing DBs.
    Child-first FK order. Each DROP individually guarded so a residual
    index/lock on one table cannot abort init_db for every user on upgrade.
    """
    for table_name in (
        "memory_audit_log",
        "memory_branches",
        "memory_links",
        "memory_citations",
        "raw_events",
        "memories_fts",
        "memories",
        "souls",
    ):
        try:
            cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
        except sqlite3.Error:
            pass


def init_db(db_path: str = None) -> None:
    """Initialize database schema.

    Creates all required tables with indices. Idempotent - safe to call multiple times.

    Args:
        db_path: Path to database file (defaults to standard location)
    """
    conn = get_connection(db_path)
    cursor = conn.cursor()

    # Subagent tracking
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS subagents (
            id TEXT PRIMARY KEY,
            project_path TEXT NOT NULL,
            spawned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            -- Subagent details
            prompt_summary TEXT,
            persona TEXT,
            status TEXT,
            last_output TEXT
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

    # Skill outcomes table for analytics persistence
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS skill_outcomes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            skill_name TEXT NOT NULL,
            skill_version TEXT,
            session_id TEXT NOT NULL,
            project_encoded TEXT NOT NULL,
            start_time TIMESTAMP NOT NULL,
            end_time TIMESTAMP,
            duration_seconds REAL,
            outcome TEXT NOT NULL,
            tokens_used INTEGER DEFAULT 0,
            corrections INTEGER DEFAULT 0,
            retries INTEGER DEFAULT 0,
            experiment_variant_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(session_id, skill_name, start_time)
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_skill_outcomes_name
        ON skill_outcomes(skill_name)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_skill_outcomes_version
        ON skill_outcomes(skill_name, skill_version)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_skill_outcomes_time
        ON skill_outcomes(created_at)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_skill_outcomes_project
        ON skill_outcomes(project_encoded)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_skill_outcomes_session_id
        ON skill_outcomes(session_id)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_skill_outcomes_experiment_variant_id
        ON skill_outcomes(experiment_variant_id)
    """)

    # Telemetry config table (singleton)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS telemetry_config (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            enabled INTEGER DEFAULT 0,
            endpoint_url TEXT,
            last_sync TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Workflow state for automatic session recovery
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS workflow_state (
            id INTEGER PRIMARY KEY,
            project_path TEXT NOT NULL UNIQUE,
            state_json TEXT NOT NULL,
            trigger TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_workflow_state_project
        ON workflow_state(project_path)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_workflow_state_updated
        ON workflow_state(updated_at)
    """)

    # A/B Test Management tables
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS experiments (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            skill_name TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'created',
            description TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            started_at TIMESTAMP,
            completed_at TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_experiments_skill_name
        ON experiments(skill_name)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_experiments_status
        ON experiments(status)
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS experiment_variants (
            id TEXT PRIMARY KEY,
            experiment_id TEXT NOT NULL,
            variant_name TEXT NOT NULL,
            skill_version TEXT,
            weight INTEGER NOT NULL DEFAULT 50,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (experiment_id) REFERENCES experiments(id) ON DELETE CASCADE,
            UNIQUE(experiment_id, variant_name)
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_experiment_variants_experiment_id
        ON experiment_variants(experiment_id)
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS variant_assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            experiment_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            variant_id TEXT NOT NULL,
            assigned_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (experiment_id) REFERENCES experiments(id) ON DELETE CASCADE,
            FOREIGN KEY (variant_id) REFERENCES experiment_variants(id) ON DELETE CASCADE,
            UNIQUE(experiment_id, session_id)
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_variant_assignments_experiment_id
        ON variant_assignments(experiment_id)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_variant_assignments_session_id
        ON variant_assignments(session_id)
    """)

    # Drop legacy security tables removed in the nuclear security cleanup.
    _drop_deleted_security_tables(cursor)

    # Drop memory-system + session-soul tables removed in 0.68.0.
    _drop_deleted_memory_tables(cursor)

    # Spawn rate limiting for spawn_claude_session
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS spawn_rate_limit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp REAL NOT NULL,
            session_id TEXT
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_spawn_rate_limit_timestamp
        ON spawn_rate_limit(timestamp)
    """)

    # --- Stint Stack Tables (Zeigarnik focus tracking) ---

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stint_stack (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_path TEXT NOT NULL,
            session_id TEXT NOT NULL,
            stack_json TEXT NOT NULL DEFAULT '[]',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(project_path, session_id)
        )
    """)

    # idx_stint_stack_project and idx_stint_stack_project_session are redundant
    # with the UNIQUE(project_path, session_id) implicit index. Only session_id
    # alone needs an explicit index for session-scoped lookups.
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_stint_stack_session
        ON stint_stack(session_id)
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stint_correction_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_path TEXT NOT NULL,
            session_id TEXT,
            correction_type TEXT NOT NULL,
            old_stack_json TEXT NOT NULL,
            new_stack_json TEXT NOT NULL,
            diff_summary TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_stint_corrections_project
        ON stint_correction_events(project_path)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_stint_corrections_type
        ON stint_correction_events(correction_type)
    """)

    # Migrate stint_stack: ensure NOT NULL + UNIQUE constraint on session_id
    _migrate_stint_stack_schema(cursor)

    conn.commit()


def close_all_connections():
    """Close all cached database connections.

    Used primarily for cleanup in tests.
    """
    global _connections
    with _connections_lock:
        for conn, _created_at in _connections.values():
            conn.close()
        _connections = {}

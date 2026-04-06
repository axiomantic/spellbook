"""Database schema and connection management for session recovery.

Canonical location for database utilities. This module was migrated from
spellbook.core.db as part of the three-layer architecture reorganization.
"""

import logging
import os
import sqlite3
import time
import threading

logger = logging.getLogger(__name__)
from pathlib import Path



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
    row = cursor.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='stint_stack'"
    ).fetchone()
    if row is None:
        return  # Table doesn't exist yet; CREATE TABLE will handle it
    create_sql = row[0]
    has_not_null = "session_id TEXT NOT NULL" in create_sql
    normalized_sql = " ".join(create_sql.upper().split())
    has_correct_unique = "UNIQUE(PROJECT_PATH, SESSION_ID)" in normalized_sql.replace("UNIQUE (", "UNIQUE(")
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
    # Delete legacy rows with NULL session_id (no longer valid with mandatory sessions)
    deleted = cursor.execute("SELECT COUNT(*) FROM _stint_stack_old WHERE session_id IS NULL").fetchone()[0]
    if deleted:
        logger.info("Dropping %d legacy stint_stack rows with NULL session_id", deleted)
    cursor.execute("DELETE FROM _stint_stack_old WHERE session_id IS NULL")
    cursor.execute("""
        INSERT INTO stint_stack (id, project_path, session_id, stack_json, updated_at)
        SELECT id, project_path, session_id, stack_json, updated_at
        FROM _stint_stack_old
    """)
    cursor.execute("DROP TABLE _stint_stack_old")


def _migrate_trust_registry_v2(cursor):
    """Add crypto provenance columns to trust_registry (idempotent)."""
    existing = {row[1] for row in cursor.execute("PRAGMA table_info(trust_registry)").fetchall()}
    for col, typedef in [
        ("signature", "TEXT"),
        ("signing_key_id", "TEXT"),
        ("analysis_status", "TEXT"),
        ("analysis_at", "TEXT"),
    ]:
        if col not in existing:
            cursor.execute(f"ALTER TABLE trust_registry ADD COLUMN {col} {typedef}")


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

    # Security: trust registry for content verification
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trust_registry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content_hash TEXT NOT NULL,
            source TEXT NOT NULL,
            trust_level TEXT NOT NULL,
            registered_at TEXT DEFAULT (datetime('now')),
            expires_at TEXT,
            registered_by TEXT
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_trust_content_hash
        ON trust_registry(content_hash)
    """)

    # Security: event log for audit trail
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS security_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            severity TEXT NOT NULL,
            source TEXT,
            detail TEXT,
            session_id TEXT,
            tool_name TEXT,
            action_taken TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_security_events_type
        ON security_events(event_type)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_security_events_severity
        ON security_events(severity)
    """)

    # Security: canary tokens for injection detection
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS canary_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token TEXT NOT NULL UNIQUE,
            token_type TEXT NOT NULL,
            context TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            triggered_at TEXT,
            triggered_by TEXT
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_canary_token
        ON canary_tokens(token)
    """)

    # Security: singleton security mode
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS security_mode (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            mode TEXT NOT NULL DEFAULT 'standard',
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_by TEXT,
            auto_restore_at TEXT
        )
    """)

    cursor.execute("""
        INSERT OR IGNORE INTO security_mode (id, mode) VALUES (1, 'standard')
    """)

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

    # --- Memory System Tables ---

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id TEXT PRIMARY KEY,
            content TEXT NOT NULL,
            memory_type TEXT,
            namespace TEXT NOT NULL,
            branch TEXT DEFAULT '',
            scope TEXT NOT NULL DEFAULT 'project',
            importance REAL DEFAULT 1.0,
            created_at TEXT NOT NULL,
            accessed_at TEXT,
            status TEXT DEFAULT 'active',
            deleted_at TEXT,
            content_hash TEXT NOT NULL,
            meta TEXT DEFAULT '{}'
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_memories_namespace
        ON memories(namespace)
    """)

    # Migration: add branch column to existing memories tables
    existing_cols = {
        row[1] for row in cursor.execute("PRAGMA table_info(memories)").fetchall()
    }
    if "branch" not in existing_cols:
        cursor.execute("ALTER TABLE memories ADD COLUMN branch TEXT DEFAULT ''")

    # Migration: add scope column to existing memories tables
    if "scope" not in existing_cols:
        cursor.execute("ALTER TABLE memories ADD COLUMN scope TEXT NOT NULL DEFAULT 'project'")

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_memories_branch
        ON memories(branch)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_memories_scope
        ON memories(scope)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_memories_content_hash
        ON memories(content_hash)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_memories_status
        ON memories(status)
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS memory_citations (
            id INTEGER PRIMARY KEY,
            memory_id TEXT NOT NULL REFERENCES memories(id),
            file_path TEXT NOT NULL,
            line_range TEXT,
            content_snippet TEXT,
            UNIQUE(memory_id, file_path, line_range)
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_citations_file
        ON memory_citations(file_path)
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS memory_links (
            memory_a TEXT NOT NULL,
            memory_b TEXT NOT NULL,
            link_type TEXT NOT NULL,
            weight REAL DEFAULT 1.0,
            last_seen TEXT,
            PRIMARY KEY (memory_a, memory_b, link_type)
        )
    """)

    # Junction table for M:N branch-to-memory associations.
    # A memory can be associated with multiple branches (origin, ancestor, manual).
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS memory_branches (
            memory_id TEXT NOT NULL REFERENCES memories(id),
            branch_name TEXT NOT NULL,
            association_type TEXT NOT NULL DEFAULT 'origin',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY (memory_id, branch_name)
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_memory_branches_branch
        ON memory_branches(branch_name)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_memory_branches_memory
        ON memory_branches(memory_id)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_memory_branches_type
        ON memory_branches(association_type)
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS raw_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            timestamp TEXT NOT NULL,
            project TEXT NOT NULL,
            branch TEXT DEFAULT '',
            event_type TEXT,
            tool_name TEXT,
            subject TEXT,
            summary TEXT,
            tags TEXT,
            consolidated INTEGER DEFAULT 0,
            batch_id TEXT
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_raw_events_consolidated
        ON raw_events(consolidated)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_raw_events_project
        ON raw_events(project)
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS memory_audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            action TEXT NOT NULL,
            memory_id TEXT,
            details TEXT
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_memory_audit_action
        ON memory_audit_log(action)
    """)

    # FTS5 for BM25 retrieval (standalone table, manually synced)
    # Note: Using IF NOT EXISTS is not directly supported by FTS5 CREATE VIRTUAL TABLE.
    # Check if the table exists first.
    # This is a standalone FTS5 table (not an external content table). The
    # application manually inserts/deletes rows in memories_fts whenever
    # memories are created or soft-deleted. A standalone table avoids the
    # column-name-mismatch issues that external content tables cause (the
    # FTS columns tags/citations do not exist on the memories table).
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='memories_fts'"
    )
    if cursor.fetchone() is None:
        cursor.execute("""
            CREATE VIRTUAL TABLE memories_fts USING fts5(
                content, tags, citations,
                tokenize="unicode61 tokenchars '_.' "
            )
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

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_stint_stack_project
        ON stint_stack(project_path)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_stint_stack_session
        ON stint_stack(session_id)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_stint_stack_project_session
        ON stint_stack(project_path, session_id)
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

    # --- Injection Defense Tables (v2) ---

    # Intent checks (PromptSleuth results)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS intent_checks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            source_tool TEXT NOT NULL,
            classification TEXT NOT NULL,
            confidence REAL NOT NULL,
            evidence TEXT,
            checked_at TEXT DEFAULT (datetime('now')),
            latency_ms INTEGER,
            cached INTEGER DEFAULT 0
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_intent_session ON intent_checks(session_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_intent_hash ON intent_checks(content_hash)")

    # Session content accumulator (split injection detection)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS session_content_accumulator (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            source_tool TEXT NOT NULL,
            content_summary TEXT,
            content_size INTEGER NOT NULL,
            received_at TEXT DEFAULT (datetime('now')),
            expires_at TEXT DEFAULT (datetime('now', '+1 hour'))
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_accum_session ON session_content_accumulator(session_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_accum_session_time ON session_content_accumulator(session_id, received_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_accum_expires ON session_content_accumulator(expires_at)")

    # PromptSleuth budget tracking
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sleuth_budget (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL UNIQUE,
            calls_remaining INTEGER NOT NULL DEFAULT 50,
            reset_at TEXT NOT NULL
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sleuth_budget_session ON sleuth_budget(session_id)")

    # PromptSleuth classification cache
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sleuth_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content_hash TEXT NOT NULL UNIQUE,
            classification TEXT NOT NULL,
            confidence REAL NOT NULL,
            cached_at TEXT DEFAULT (datetime('now')),
            expires_at TEXT DEFAULT (datetime('now', '+1 hour'))
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sleuth_cache_hash ON sleuth_cache(content_hash)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sleuth_cache_expires ON sleuth_cache(expires_at)")

    # Migrate stint_stack: ensure NOT NULL + UNIQUE constraint on session_id
    _migrate_stint_stack_schema(cursor)

    # Migrate trust_registry: add signature columns if missing
    _migrate_trust_registry_v2(cursor)

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

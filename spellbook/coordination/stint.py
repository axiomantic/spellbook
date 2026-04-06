"""Zeigarnik focus tracking: stint stack helper logic.

Provides push/pop/check/replace operations on the stint stack,
correction classification heuristics, and entry validation.

The stint stack is stored as a JSON array in a single SQLite row
per project. All read-modify-write operations use BEGIN IMMEDIATE
transactions for atomicity.

Entry schema: name, purpose, behavioral_mode, metadata, entered_at.
Old entries with extra fields (type, parent, exited_at, success_criteria)
are read fine -- Python dict access ignores extra keys.
"""

import json
import logging
import sqlite3
import time
from datetime import datetime, timezone
from typing import Callable, Optional

logger = logging.getLogger(__name__)

from spellbook.core.db import get_connection

MAX_STINT_DEPTH = 6


def _is_ordered_subsequence(shorter: list[str], longer: list[str]) -> bool:
    """Check if shorter is an ordered subsequence of longer.

    Each element in shorter must appear in longer in the same relative
    order, but not necessarily contiguously. Works correctly with
    duplicate names.

    PROTECTION: The `item in it` expression uses Python's iterator
    protocol (falling back to `__next__` since iterators lack
    `__contains__`), which advances the iterator past the matched
    element. This is NOT the same as `item in list` (which scans from
    the start). The iterator trick ensures each match consumes elements
    up to and including the match point, so subsequent matches must occur
    AFTER that position. Do NOT "simplify" this to use list indexing or
    set membership -- that would break ordered subsequence semantics and
    fail silently on duplicate names.
    """
    it = iter(longer)
    return all(item in it for item in shorter)


def classify_correction(old_stack: list, new_stack: list) -> str:
    """Classify a correction event as mcp_wrong or llm_wrong.

    Uses index-based ordered comparison, not set-based. Set comparison
    fails with duplicate stint names (e.g., two "explore" stints).

    Returns:
        "llm_wrong" if new is an ordered subsequence of old (LLM
        is removing entries it forgot to pop).
        "mcp_wrong" otherwise (MCP tracking diverged).
    """
    old_names = [e["name"] for e in old_stack]
    new_names = [e["name"] for e in new_stack]

    # No actual change: not a correction at all. Default to "mcp_wrong"
    # since the LLM explicitly called replace, implying it thought tracking
    # was wrong even if the stacks happen to match.
    if old_names == new_names:
        return "mcp_wrong"

    if len(new_names) < len(old_names) and _is_ordered_subsequence(new_names, old_names):
        return "llm_wrong"
    elif len(old_names) < len(new_names) and _is_ordered_subsequence(old_names, new_names):
        return "mcp_wrong"
    else:
        # Structural divergence (different names, not a subsequence relationship).
        # Default to "mcp_wrong" because the LLM is the authority over its own
        # focus state. If it says the stack should look different, the MCP
        # tracking was wrong.
        return "mcp_wrong"


def _validate_stint_entry(entry: dict) -> tuple[bool, str]:
    """Validate a stint entry for injection patterns.

    Checks name, purpose, and behavioral_mode fields against injection
    detection rules from spellbook.sessions.injection.

    Side effect: truncated values from _sanitize_field are persisted
    back into the entry dict, so the stored entry respects length limits.

    Returns:
        (True, "") if valid, (False, error_message) if invalid.
    """
    from spellbook.sessions.injection import _sanitize_field

    for field in ("name", "purpose", "behavioral_mode"):
        value = entry.get(field, "")
        if value:
            sanitized = _sanitize_field(field, value, max_length=500)
            if sanitized is None:
                return False, f"Injection pattern detected in '{field}'"
            entry[field] = sanitized
    return True, ""


def _log_correction_event(
    project_path: str,
    correction_type: str,
    old_stack: list,
    new_stack: list,
    diff_summary: str = "",
    db_path: Optional[str] = None,
    session_id: str = "",
) -> None:
    """Log a correction event to the stint_correction_events table.

    Uses the shared connection from get_connection(). Errors are caught
    and silently ignored because correction logging is observational and
    must never block or crash the caller.
    """
    try:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO stint_correction_events
                (project_path, session_id, correction_type, old_stack_json, new_stack_json, diff_summary)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                project_path,
                session_id,
                correction_type,
                json.dumps(old_stack),
                json.dumps(new_stack),
                diff_summary,
            ),
        )
        conn.commit()
    except Exception:
        logger.error("Failed to log stint correction event", exc_info=True)


def _update_stack(project_path: str, mutate_fn: Callable[[list], list], db_path: Optional[str] = None, session_id: str = "") -> dict:
    """Read-modify-write the stint stack atomically.

    Uses a dedicated connection with BEGIN IMMEDIATE to acquire a write
    lock at transaction start, preventing concurrent read-modify-write
    races. A dedicated (non-cached) connection is required because the
    shared connection from get_connection() cannot handle concurrent
    BEGIN IMMEDIATE calls from multiple threads (SQLite does not allow
    nested transactions on a single connection).

    Retries up to 10 times with exponential backoff when the database
    is locked by another thread's transaction.

    Args:
        project_path: Project key for the stack row.
        mutate_fn: Callable(stack, cursor) -> (result_dict, new_stack).
            Receives the current stack and cursor for additional SQL
            within the same transaction. Returns the tool result and
            the new stack to persist. If new_stack is None, no write.
        db_path: Optional database path (for testing).
        session_id: Session identifier for session-scoped stints.
    """
    from spellbook.core.db import get_db_path

    actual_path = db_path if db_path else str(get_db_path())
    max_retries = 10
    base_delay = 0.01  # 10ms

    for attempt in range(max_retries):
        conn = sqlite3.connect(actual_path, timeout=5.0)
        conn.execute("PRAGMA journal_mode=WAL")
        try:
            conn.execute("BEGIN IMMEDIATE")
            cursor = conn.cursor()
            cursor.execute(
                "SELECT stack_json FROM stint_stack WHERE project_path = ? AND session_id = ?",
                (project_path, session_id),
            )
            row = cursor.fetchone()
            stack = json.loads(row[0]) if row else []

            result, new_stack = mutate_fn(stack, cursor)

            if new_stack is not None:
                cursor.execute(
                    """
                    UPDATE stint_stack
                    SET stack_json = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE project_path = ? AND session_id = ?
                    """,
                    (json.dumps(new_stack), project_path, session_id),
                )
                if cursor.rowcount == 0:
                    cursor.execute(
                        """
                        INSERT INTO stint_stack (project_path, session_id, stack_json, updated_at)
                        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                        """,
                        (project_path, session_id, json.dumps(new_stack)),
                    )
            conn.commit()
            return result
        except sqlite3.OperationalError as e:
            try:
                conn.rollback()
            except Exception:
                pass
            if "database is locked" in str(e) and attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                time.sleep(delay)
                continue
            raise
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            raise
        finally:
            conn.close()

    raise sqlite3.OperationalError("Failed to acquire lock after max retries")


def push_stint(
    project_path: str,
    name: str,
    purpose: str = "",
    behavioral_mode: str = "",
    metadata: Optional[dict] = None,
    db_path: Optional[str] = None,
    *,
    session_id: str,
    # Deprecated parameters (accepted but ignored for backward compatibility)
    stint_type: str = "",
    success_criteria: str = "",
) -> dict:
    """Push a new stint onto the focus stack.

    Returns:
        {"success": True, "depth": int, "stack": list} on success.
        {"success": False, "error": str} on validation failure or depth cap.
    """
    entry = {
        "name": name,
        "purpose": purpose,
        "behavioral_mode": behavioral_mode,
        "metadata": metadata or {},
        "entered_at": datetime.now(timezone.utc).isoformat(),
    }

    # Validate for injection
    valid, msg = _validate_stint_entry(entry)
    if not valid:
        return {"success": False, "error": msg}

    def mutate(stack: list, cursor) -> tuple[dict, list]:
        if len(stack) >= MAX_STINT_DEPTH:
            return {
                "success": False,
                "error": f"Depth cap ({MAX_STINT_DEPTH}) reached. Use stint_replace to restructure, or stint_pop to close completed work.",
            }, None
        stack.append(entry)
        return {"success": True, "depth": len(stack), "stack": list(stack)}, stack

    return _update_stack(project_path, mutate, db_path, session_id)


def pop_stint(
    project_path: str,
    name: Optional[str] = None,
    db_path: Optional[str] = None,
    *,
    session_id: str,
) -> dict:
    """Pop the top stint from the focus stack.

    If name is provided and does not match, logs a correction event
    but still pops (LLM intent takes priority).

    Returns:
        {"success": True, "popped": dict, "depth": int, "mismatch": bool}
        {"success": False, "error": str} if stack is empty.
    """
    def mutate(stack: list, cursor) -> tuple[dict, list | None]:
        if not stack:
            return {"success": False, "error": "stack empty"}, None

        top = stack[-1]
        mismatch = False
        if name is not None and top["name"] != name:
            mismatch = True

        popped = stack.pop()
        return {
            "success": True,
            "popped": popped,
            "depth": len(stack),
            "mismatch": mismatch,
        }, stack

    result = _update_stack(project_path, mutate, db_path, session_id)

    # Log correction event for mismatches (outside the transaction).
    # Classification is "llm_wrong": the LLM asked to pop a name that
    # doesn't match the top of stack, meaning its mental model of the
    # stack was incorrect (it forgot to pop an intervening stint).
    if result.get("success") and result.get("mismatch"):
        _log_correction_event(
            project_path=project_path,
            correction_type="llm_wrong",
            old_stack=[result["popped"]],
            new_stack=[],
            diff_summary=f"Pop name mismatch: expected '{name}', found '{result['popped']['name']}'",
            db_path=db_path,
            session_id=session_id,
        )

    return result


def check_stint(
    project_path: str,
    db_path: Optional[str] = None,
    *,
    session_id: str,
) -> dict:
    """Return the current stint stack. Read-only (no data mutation). Briefly acquires a write lock via BEGIN IMMEDIATE.

    Returns:
        {"success": True, "depth": int, "stack": list}
    """
    def mutate(stack: list, cursor) -> tuple[dict, list | None]:
        return {"success": True, "depth": len(stack), "stack": list(stack)}, None

    return _update_stack(project_path, mutate, db_path, session_id)


def replace_stint(
    project_path: str,
    stack: list[dict],
    reason: str = "",
    db_path: Optional[str] = None,
    *,
    session_id: str,
) -> dict:
    """Replace the entire stint stack with a corrected version.

    Logs a correction event with classification.

    Returns:
        {"success": True, "depth": int, "correction_logged": True}
        {"success": False, "error": str} on validation failure.
    """
    # Validate all entries
    for entry in stack:
        valid, msg = _validate_stint_entry(entry)
        if not valid:
            return {"success": False, "error": msg}

    def mutate(old_stack: list, cursor) -> tuple[dict, list]:
        # Classify correction
        correction_type = classify_correction(old_stack, stack)

        # Log correction event (inside transaction for consistency)
        cursor.execute(
            """
            INSERT INTO stint_correction_events
                (project_path, session_id, correction_type, old_stack_json, new_stack_json, diff_summary)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                project_path,
                session_id,
                correction_type,
                json.dumps(old_stack),
                json.dumps(stack),
                reason,
            ),
        )

        return {
            "success": True,
            "depth": len(stack),
            "correction_logged": True,
        }, stack

    return _update_stack(project_path, mutate, db_path, session_id)

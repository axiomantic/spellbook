"""Configuration management and session initialization for spellbook."""

import json
import logging
import os
import random
import sqlite3
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from installer.compat import CrossPlatformLock, LockHeldError, get_config_dir

logger = logging.getLogger(__name__)

# Session-specific state keyed by session_id (in-memory, resets on MCP server restart)
# This allows session-only mode changes that don't persist to config
# Each session gets its own state dict to support multi-session HTTP daemon mode
_session_states: dict[str, dict] = {}

# Track last activity per session for cleanup
_session_activity: dict[str, datetime] = {}

# Session TTL for garbage collection
SESSION_TTL_DAYS = 3

# Default session ID for backward compatibility (when session_id is not provided)
DEFAULT_SESSION_ID = "__default__"

# File-level lock for thread-safe config access
CONFIG_LOCK_PATH = get_config_dir() / "config.lock"


def _cleanup_stale_sessions() -> None:
    """Remove sessions with no activity for SESSION_TTL_DAYS.

    Called on each state access to garbage collect old sessions.
    """
    cutoff = datetime.now() - timedelta(days=SESSION_TTL_DAYS)
    stale = [sid for sid, ts in _session_activity.items() if ts < cutoff]
    for sid in stale:
        _session_states.pop(sid, None)
        _session_activity.pop(sid, None)


def _get_session_state(session_id: Optional[str] = None) -> dict:
    """Get or create session state, update activity timestamp.

    Args:
        session_id: Session identifier. If None, uses DEFAULT_SESSION_ID
                    for backward compatibility.

    Returns:
        Session state dict with "mode" and "tts" keys.
    """
    _cleanup_stale_sessions()  # Run cleanup on each access
    sid = session_id or DEFAULT_SESSION_ID
    _session_activity[sid] = datetime.now()
    if sid not in _session_states:
        _session_states[sid] = {"mode": None, "tts": {}}
    # Ensure tts key exists for sessions created before TTS feature
    state = _session_states[sid]
    if "tts" not in state:
        state["tts"] = {}
    return state


def _get_default_session_state() -> dict:
    """Get the default session state for backward compatibility.

    Used by existing code and tests that don't pass session_id.
    """
    return _get_session_state(DEFAULT_SESSION_ID)


def get_config_path() -> Path:
    """Get path to spellbook config file."""
    return get_config_dir() / "spellbook.json"


def _is_spellbook_root(path: Path) -> bool:
    """Check if a directory is the spellbook root by looking for key indicators.

    Args:
        path: Directory to check

    Returns:
        True if the directory contains spellbook indicators
    """
    # Key indicators: skills/ directory and CLAUDE.spellbook.md file
    skills_dir = path / "skills"
    spellbook_md = path / "CLAUDE.spellbook.md"
    return skills_dir.is_dir() and spellbook_md.is_file()


def _find_spellbook_root_from_file() -> Optional[Path]:
    """Find spellbook root by walking up from this file's directory.

    Returns:
        Path to spellbook root if found, None otherwise
    """
    # Start from this file's directory (spellbook_mcp/)
    current = Path(__file__).resolve().parent

    # Walk up the directory tree looking for spellbook indicators
    # Limit to reasonable depth to avoid infinite loops
    for _ in range(10):
        if _is_spellbook_root(current):
            return current
        parent = current.parent
        if parent == current:
            # Reached filesystem root
            break
        current = parent

    return None


def get_spellbook_dir() -> Path:
    """Get spellbook source directory.

    Resolution order:
    1. SPELLBOOK_DIR environment variable (if set)
    2. Derive from __file__ by walking up to find spellbook root
    3. Default to ~/.local/spellbook

    Returns:
        Path to the spellbook directory
    """
    # 1. Check environment variable first
    spellbook_dir = os.environ.get("SPELLBOOK_DIR")
    if spellbook_dir:
        return Path(spellbook_dir)

    # 2. Try to find by walking up from this file
    found_root = _find_spellbook_root_from_file()
    if found_root:
        return found_root

    # 3. Default to ~/.local/spellbook
    return Path.home() / ".local" / "spellbook"


def config_get(key: str) -> Optional[Any]:
    """Read a config value from spellbook.json with file-level locking.

    Uses CrossPlatformLock for thread-safe and cross-process-safe reads.
    Falls back to unlocked read if lock acquisition fails (preserves existing
    error contract: returns None on failure).

    Args:
        key: The config key to read

    Returns:
        The value for the key, or None if not set or file missing
    """
    config_path = get_config_path()
    if not config_path.exists():
        return None

    try:
        with CrossPlatformLock(CONFIG_LOCK_PATH, shared=True, blocking=True):
            config = json.loads(config_path.read_text(encoding="utf-8"))
            return config.get(key)
    except LockHeldError:
        # Fall back to unlocked read
        logger.warning("Could not acquire config read lock. Falling back to unlocked read.")
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
            return config.get(key)
        except (json.JSONDecodeError, OSError):
            return None
    except (json.JSONDecodeError, OSError):
        return None


def config_set(key: str, value: Any) -> dict:
    """Write a config value to spellbook.json with file-level locking.

    Uses CrossPlatformLock for thread-safe and cross-process-safe writes.
    Creates the config file and parent directories if they don't exist.
    Preserves other config values (read-modify-write). Falls back to unlocked
    write if lock acquisition fails (preserves existing error contract:
    returns {"status": "ok", ...}).

    Args:
        key: The config key to set
        value: The value to set (must be JSON-serializable)

    Returns:
        Dict with status and the updated config
    """
    config_path = get_config_path()

    try:
        with CrossPlatformLock(CONFIG_LOCK_PATH, blocking=True):
            config = {}
            if config_path.exists():
                try:
                    config = json.loads(config_path.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    config = {}

            config[key] = value
            config_path.parent.mkdir(parents=True, exist_ok=True)

            # Write atomically: write to temp file in same directory, then replace
            fd_tmp, tmp_path = tempfile.mkstemp(
                dir=str(config_path.parent), suffix=".tmp"
            )
            fd_tmp_closed = False
            try:
                os.write(fd_tmp, (json.dumps(config, indent=2) + "\n").encode("utf-8"))
                os.close(fd_tmp)
                fd_tmp_closed = True
                os.replace(tmp_path, str(config_path))
            except BaseException:
                if not fd_tmp_closed:
                    os.close(fd_tmp)
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise

            return {"status": "ok", "config": config}
    except LockHeldError:
        logger.warning("Could not acquire config write lock. Falling back to unlocked write.")
        # Fall through to unlocked atomic write
        config = {}
        if config_path.exists():
            try:
                config = json.loads(config_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                config = {}
        config[key] = value
        config_path.parent.mkdir(parents=True, exist_ok=True)
        fd_tmp, tmp_path = tempfile.mkstemp(
            dir=str(config_path.parent), suffix=".tmp"
        )
        fd_tmp_closed = False
        try:
            os.write(fd_tmp, (json.dumps(config, indent=2) + "\n").encode("utf-8"))
            os.close(fd_tmp)
            fd_tmp_closed = True
            os.replace(tmp_path, str(config_path))
        except BaseException:
            if not fd_tmp_closed:
                os.close(fd_tmp)
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
        return {"status": "ok", "config": config}


def config_set_many(updates: dict[str, Any]) -> dict:
    """Write multiple config values to spellbook.json in a single pass.

    Behaves identically to config_set but applies all key-value pairs from
    *updates* in one atomic read-modify-write cycle, avoiding redundant
    file I/O when several keys are changed together.

    Args:
        updates: Mapping of config keys to values (must be JSON-serializable).

    Returns:
        Dict with status and the updated config.
    """
    if not updates:
        # Nothing to write; return current config
        config_path = get_config_path()
        config = {}
        if config_path.exists():
            try:
                config = json.loads(config_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        return {"status": "ok", "config": config}

    config_path = get_config_path()

    def _atomic_write(config: dict, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd_tmp, tmp_path = tempfile.mkstemp(
            dir=str(path.parent), suffix=".tmp"
        )
        fd_tmp_closed = False
        try:
            os.write(fd_tmp, (json.dumps(config, indent=2) + "\n").encode("utf-8"))
            os.close(fd_tmp)
            fd_tmp_closed = True
            os.replace(tmp_path, str(path))
        except BaseException:
            if not fd_tmp_closed:
                os.close(fd_tmp)
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    def _read_config() -> dict:
        if not config_path.exists():
            return {}
        try:
            return json.loads(config_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def _apply_and_write() -> dict:
        config = _read_config()
        config.update(updates)
        _atomic_write(config, config_path)
        return {"status": "ok", "config": config}

    try:
        with CrossPlatformLock(CONFIG_LOCK_PATH, blocking=True):
            return _apply_and_write()
    except LockHeldError:
        logger.warning("Could not acquire config write lock. Falling back to unlocked write.")
        return _apply_and_write()


def session_mode_set(
    mode: str, permanent: bool = False, session_id: Optional[str] = None
) -> dict:
    """Set session mode, optionally persisting to config.

    Args:
        mode: Mode to set ("fun", "tarot", "none")
        permanent: If True, save to config file. If False, session-only.
        session_id: Session identifier for multi-session isolation.
                    If None, uses default session for backward compatibility.

    Returns:
        Dict with status and current mode state
    """
    if mode not in ("fun", "tarot", "none"):
        return {"status": "error", "message": f"Invalid mode: {mode}. Use 'fun', 'tarot', or 'none'."}

    session_state = _get_session_state(session_id)

    if permanent:
        # Save to config file
        config_set("session_mode", mode)
        # Clear session override so config takes effect
        session_state["mode"] = None
        return {"status": "ok", "mode": mode, "permanent": True}
    else:
        # Session-only: store in memory
        session_state["mode"] = mode
        return {"status": "ok", "mode": mode, "permanent": False}


def session_mode_get(session_id: Optional[str] = None) -> dict:
    """Get current session mode state.

    Args:
        session_id: Session identifier for multi-session isolation.
                    If None, uses default session for backward compatibility.

    Returns:
        Dict with mode, source (session or config), and permanent flag
    """
    session_state = _get_session_state(session_id)

    if session_state["mode"] is not None:
        return {
            "mode": session_state["mode"],
            "source": "session",
            "permanent": False,
        }

    config_mode = config_get("session_mode")
    legacy_mode = config_get("fun_mode")

    if config_mode is not None:
        return {"mode": config_mode, "source": "config", "permanent": True}
    elif legacy_mode is not None:
        return {"mode": "fun" if legacy_mode else "none", "source": "config_legacy", "permanent": True}
    else:
        return {"mode": None, "source": "unset", "permanent": False}


# TTS defaults (used when neither session nor config has a value)
TTS_DEFAULT_ENABLED = True
TTS_DEFAULT_VOICE = "af_heart"
TTS_DEFAULT_VOLUME = 0.3


def tts_session_set(
    enabled: bool = None,
    voice: str = None,
    volume: float = None,
    session_id: Optional[str] = None,
) -> dict:
    """Set TTS overrides for this session (not persisted to config).

    Pass only the settings you want to change. Omitted settings keep
    their current value.

    Args:
        enabled: Enable/disable TTS for this session
        voice: Override voice for this session
        volume: Override volume for this session (0.0-1.0)
        session_id: Session identifier for multi-session isolation.
                    If None, uses default session for backward compatibility.

    Returns:
        Dict with status and current session TTS overrides
    """
    session_state = _get_session_state(session_id)
    tts_state = session_state["tts"]

    if enabled is not None:
        tts_state["enabled"] = enabled
    if voice is not None:
        tts_state["voice"] = voice
    if volume is not None:
        tts_state["volume"] = volume

    return {"status": "ok", "session_tts": dict(tts_state)}


def tts_session_get(session_id: Optional[str] = None) -> dict:
    """Get effective TTS settings with resolution: session > config > defaults.

    Each setting is resolved independently. For example, voice may come
    from session while volume comes from config and enabled from defaults.

    Does NOT check kokoro availability. This is the settings layer only.

    Args:
        session_id: Session identifier for multi-session isolation.
                    If None, uses default session for backward compatibility.

    Returns:
        Dict with effective enabled, voice, volume and their sources
    """
    session_state = _get_session_state(session_id)
    tts_state = session_state["tts"]

    # Resolve each setting: session > config > default
    result = {}

    # enabled
    if "enabled" in tts_state:
        result["enabled"] = tts_state["enabled"]
        result["source_enabled"] = "session"
    else:
        config_val = config_get("tts_enabled")
        if config_val is not None:
            result["enabled"] = config_val
            result["source_enabled"] = "config"
        else:
            result["enabled"] = TTS_DEFAULT_ENABLED
            result["source_enabled"] = "default"

    # voice
    if "voice" in tts_state:
        result["voice"] = tts_state["voice"]
        result["source_voice"] = "session"
    else:
        config_val = config_get("tts_voice")
        if config_val is not None:
            result["voice"] = config_val
            result["source_voice"] = "config"
        else:
            result["voice"] = TTS_DEFAULT_VOICE
            result["source_voice"] = "default"

    # volume
    if "volume" in tts_state:
        result["volume"] = tts_state["volume"]
        result["source_volume"] = "session"
    else:
        config_val = config_get("tts_volume")
        if config_val is not None:
            result["volume"] = config_val
            result["source_volume"] = "config"
        else:
            result["volume"] = TTS_DEFAULT_VOLUME
            result["source_volume"] = "default"

    return result


def random_line(file_path: Path) -> str:
    """Select a random non-empty line from a file.

    Args:
        file_path: Path to the file to read

    Returns:
        A random line from the file, or empty string if file missing/empty
    """
    try:
        lines = [line.strip() for line in file_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        return random.choice(lines) if lines else ""
    except OSError:
        return ""


def _is_recent(iso_timestamp: str, hours: float = 24.0) -> bool:
    """Check if an ISO timestamp is within the given hours from now.

    Args:
        iso_timestamp: ISO format timestamp string
        hours: Maximum age in hours

    Returns:
        True if the timestamp is within the time window
    """
    try:
        ts = datetime.fromisoformat(iso_timestamp)
        age = (datetime.now() - ts).total_seconds() / 3600.0
        return age < hours
    except (ValueError, TypeError):
        return False


def _add_update_notification(result: dict) -> None:
    """Add update notification to session_init result if applicable.

    Checks config for recent auto-update, pending major update, available
    update, and paused state. Adds an ``update_notification`` key to result.

    **Intentional write side-effect:** When a recent auto-update notification
    is shown, this function clears ``last_auto_update`` via ``config_set()``
    to implement show-once behavior. For HTTP daemon mode (multiple
    concurrent sessions), the first session to call ``session_init``
    will consume the notification.

    Args:
        result: The session_init result dict to modify in-place
    """
    last_auto_update = config_get("last_auto_update")
    pending_major = config_get("pending_major_update")
    available = config_get("available_update")

    if last_auto_update:
        applied_at = last_auto_update.get("applied_at", "")
        if _is_recent(applied_at, hours=24):
            result["update_notification"] = {
                "type": "applied",
                "version": last_auto_update["version"],
                "from_version": last_auto_update.get("from_version"),
            }
            # Clear after showing once
            config_set("last_auto_update", None)

    elif pending_major:
        result["update_notification"] = {
            "type": "major_pending",
            "version": pending_major["version"],
            "message": (
                f"Major update {pending_major['version']} available. "
                "Run check_for_updates with auto_apply=True to install."
            ),
        }

    elif available:
        result["update_notification"] = {
            "type": "available",
            "version": available["version"],
        }

    # Always surface paused state if set
    if config_get("auto_update_paused"):
        result.setdefault("update_notification", {})
        result["update_notification"]["paused"] = True
        result["update_notification"]["paused_message"] = (
            "Auto-update is paused (after rollback). "
            "Run check_for_updates(auto_apply=True) or set "
            "auto_update_paused=False to resume."
        )


def _get_repairs() -> list[dict]:
    """Check for known fixable issues and return repair suggestions.

    Each repair is a dict with:
        id: Unique repair identifier
        severity: "warning" or "error"
        message: Human-readable description
        fix_command: Command the user can run to fix the issue

    Uses importlib.util.find_spec for dependency checks instead of
    full imports. Full imports (e.g. kokoro -> spacy -> thinc) can
    take 30+ seconds and should only happen when TTS is actually used.
    """
    import importlib.util

    repairs = []

    # Check TTS: enabled but dependencies missing
    tts_enabled = config_get("tts_enabled")
    if tts_enabled is True:
        try:
            kokoro_installed = importlib.util.find_spec("kokoro") is not None
            soundfile_installed = importlib.util.find_spec("soundfile") is not None
            if not (kokoro_installed and soundfile_installed):
                repairs.append({
                    "id": "tts-deps-missing",
                    "severity": "warning",
                    "message": "TTS is enabled but kokoro is not installed",
                    "fix_command": "uv pip install 'spellbook[tts]'",
                })
        except Exception:
            pass

    # Check TTS: kokoro installed but pip missing (spaCy#13747 workaround)
    if tts_enabled is True and not repairs:
        try:
            if importlib.util.find_spec("kokoro") and not importlib.util.find_spec("pip"):
                repairs.append({
                    "id": "tts-pip-missing",
                    "severity": "warning",
                    "message": "TTS requires pip in the venv (spaCy workaround). TTS will hang without it",
                    "fix_command": "uv pip install pip",
                })
        except Exception:
            pass

    return repairs


def session_init(
    session_id: Optional[str] = None,
    continuation_message: Optional[str] = None,
    project_path: Optional[str] = None
) -> dict:
    """Initialize a spellbook session with optional continuation detection.

    Resolution order for mode:
    1. Session state (in-memory, session-only override)
    2. session_mode config key
    3. fun_mode legacy config key
    4. Unset

    When continuation_message is provided:
    1. Queries for recent resumable session (<24h)
    2. Detects continuation intent from message
    3. Returns resume fields if "continue" or "neutral" intent
    4. Returns resume_available=False if "fresh_start" intent

    Args:
        session_id: Session identifier for multi-session isolation.
                    If None, uses default session for backward compatibility.
        continuation_message: User's first message for resume detection (optional).
                            Pass the raw first message to enable continuation detection.
        project_path: Project path for resume detection. If None, falls back to os.getcwd().

    Returns:
        Dict with:
        - mode: {"type": "fun"|"tarot"|"none"|"unset", ...mode-specific data}
        - fun_mode: "yes"|"no"|"unset" (legacy key for backward compatibility)
        - resume_available: bool
        - resume_* fields if resume is available
    """
    # Check session state first (in-memory override)
    session_state = _get_session_state(session_id)
    session_override = session_state.get("mode")

    # Then check config
    config_mode = config_get("session_mode")
    legacy_fun_mode = config_get("fun_mode")

    # Resolve effective mode with priority: session > config > legacy > unset
    effective_mode: Optional[str] = None

    if session_override is not None:
        # Session override takes highest priority
        effective_mode = session_override if session_override in ("fun", "tarot", "none") else None
    elif config_mode is not None:
        # New config key
        effective_mode = config_mode if config_mode in ("fun", "tarot", "none") else None
    elif legacy_fun_mode is not None:
        # Fall back to legacy boolean
        effective_mode = "fun" if legacy_fun_mode else "none"

    # Build mode result
    result: dict = {}

    # Handle unset
    if effective_mode is None:
        result = {
            "mode": {"type": "unset"},
            "fun_mode": "unset",  # Legacy key
        }
    # Handle explicitly disabled
    elif effective_mode == "none":
        result = {
            "mode": {"type": "none"},
            "fun_mode": "no",  # Legacy key
        }
    # Handle tarot mode
    elif effective_mode == "tarot":
        result = {
            "mode": {"type": "tarot"},
            "fun_mode": "no",  # Legacy key - tarot is not fun-mode
        }
    # Handle fun mode
    else:
        spellbook_dir = get_spellbook_dir()
        fun_assets = spellbook_dir / "skills" / "fun-mode"

        # Verify the assets directory exists
        if not fun_assets.is_dir():
            result = {
                "mode": {"type": "fun", "error": f"fun-mode assets not found at {fun_assets}"},
                "fun_mode": "yes",
                "error": f"fun-mode assets not found at {fun_assets}",
            }
        else:
            # Select random values once to ensure consistency
            persona = random_line(fun_assets / "personas.txt")
            context = random_line(fun_assets / "contexts.txt")
            undertow = random_line(fun_assets / "undertows.txt")

            result = {
                "mode": {
                    "type": "fun",
                    "persona": persona,
                    "context": context,
                    "undertow": undertow,
                },
                # Legacy keys for backward compatibility
                "fun_mode": "yes",
                "persona": persona,
                "context": context,
                "undertow": undertow,
            }

    # Add update notification (if any)
    _add_update_notification(result)

    # Add resume fields
    result.update(_get_resume_context(continuation_message, project_path))

    # Add repair suggestions
    repairs = _get_repairs()
    if repairs:
        result["repairs"] = repairs

    return result


def _get_resume_context(
    continuation_message: Optional[str],
    project_path: Optional[str] = None
) -> dict:
    """Get resume context based on continuation message.

    Args:
        continuation_message: User's first message (optional)
        project_path: Project path (defaults to os.getcwd() if not provided)

    Returns:
        Dict with resume_available and optional resume_* fields
    """
    from spellbook_mcp.db import get_db_path
    from spellbook_mcp.resume import (
        detect_continuation_intent,
        get_resume_fields,
    )

    # Get project path - use provided path or fall back to cwd
    if project_path is None:
        project_path = os.getcwd()

    # Get database path
    try:
        db_path = str(get_db_path())
    except Exception:
        # If no database, no resume available
        return {"resume_available": False}

    # Query for recent session
    resume_fields = get_resume_fields(project_path, db_path)

    # If no recent session available, return early
    if not resume_fields.get("resume_available"):
        return {"resume_available": False}

    # If no continuation message provided, return resume fields unchanged
    if not continuation_message:
        return dict(resume_fields)

    # Detect user intent
    intent = detect_continuation_intent(
        continuation_message,
        has_recent_session=True  # We know there's a recent session
    )

    # Fresh start overrides resume
    if intent["intent"] == "fresh_start":
        return {"resume_available": False}

    # Return resume fields for continue or neutral intent
    return dict(resume_fields)


def telemetry_enable(endpoint_url: str = None, db_path: str = None) -> dict:
    """Enable anonymous telemetry aggregation.

    Args:
        endpoint_url: Optional custom endpoint (default: future Anthropic endpoint)
        db_path: Path to database (defaults to standard location)

    Returns:
        {"status": "enabled", "endpoint_url": str|None} or {"status": "error", "message": str}
    """
    from spellbook_mcp.db import get_connection, get_db_path

    if db_path is None:
        db_path = str(get_db_path())

    try:
        conn = get_connection(db_path)
        conn.execute("""
            INSERT INTO telemetry_config (id, enabled, endpoint_url, updated_at)
            VALUES (1, 1, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(id) DO UPDATE SET
                enabled = 1,
                endpoint_url = COALESCE(excluded.endpoint_url, endpoint_url),
                updated_at = CURRENT_TIMESTAMP
        """, (endpoint_url,))
        conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Database error enabling telemetry: {e}")
        return {"status": "error", "message": str(e)}

    return {"status": "enabled", "endpoint_url": endpoint_url}


def telemetry_disable(db_path: str = None) -> dict:
    """Disable telemetry. Local persistence continues.

    Args:
        db_path: Path to database (defaults to standard location)

    Returns:
        {"status": "disabled"} or {"status": "error", "message": str}
    """
    from spellbook_mcp.db import get_connection, get_db_path

    if db_path is None:
        db_path = str(get_db_path())

    try:
        conn = get_connection(db_path)
        conn.execute("""
            INSERT INTO telemetry_config (id, enabled, updated_at)
            VALUES (1, 0, CURRENT_TIMESTAMP)
            ON CONFLICT(id) DO UPDATE SET
                enabled = 0,
                updated_at = CURRENT_TIMESTAMP
        """)
        conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Database error disabling telemetry: {e}")
        return {"status": "error", "message": str(e)}

    return {"status": "disabled"}


def telemetry_status(db_path: str = None) -> dict:
    """Get current telemetry configuration.

    Args:
        db_path: Path to database (defaults to standard location)

    Returns:
        {"enabled": bool, "endpoint_url": str|None, "last_sync": str|None}
        or includes "status": "error", "message": str on failure
    """
    from spellbook_mcp.db import get_connection, get_db_path

    if db_path is None:
        db_path = str(get_db_path())

    try:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT enabled, endpoint_url, last_sync FROM telemetry_config WHERE id = 1
        """)
        row = cursor.fetchone()
    except sqlite3.Error as e:
        logger.error(f"Database error getting telemetry status: {e}")
        return {
            "enabled": False,
            "endpoint_url": None,
            "last_sync": None,
            "status": "error",
            "message": str(e),
        }

    if row is None:
        return {
            "enabled": False,
            "endpoint_url": None,
            "last_sync": None,
        }

    return {
        "enabled": bool(row[0]),
        "endpoint_url": row[1],
        "last_sync": row[2],
    }

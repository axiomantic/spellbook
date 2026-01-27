"""Configuration management and session initialization for spellbook."""

import json
import os
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

# Session-specific state keyed by session_id (in-memory, resets on MCP server restart)
# This allows session-only mode changes that don't persist to config
# Each session gets its own state dict to support multi-session HTTP daemon mode
_session_states: dict[str, dict] = {}

# Track last activity per session for cleanup
_session_activity: dict[str, datetime] = {}

# Session TTL for garbage collection
SESSION_TTL_DAYS = 3

# Default session ID for backward compatibility (stdio single-session mode)
DEFAULT_SESSION_ID = "__default__"


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
                    for backward compatibility with stdio transport.

    Returns:
        Session state dict with "mode" key.
    """
    _cleanup_stale_sessions()  # Run cleanup on each access
    sid = session_id or DEFAULT_SESSION_ID
    _session_activity[sid] = datetime.now()
    if sid not in _session_states:
        _session_states[sid] = {"mode": None}
    return _session_states[sid]


def _get_default_session_state() -> dict:
    """Get the default session state for backward compatibility.

    Used by existing code and tests that don't pass session_id.
    """
    return _get_session_state(DEFAULT_SESSION_ID)


def get_config_path() -> Path:
    """Get path to spellbook config file."""
    return Path.home() / ".config" / "spellbook" / "spellbook.json"


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
    """Read a config value from spellbook.json.

    Args:
        key: The config key to read

    Returns:
        The value for the key, or None if not set or file missing
    """
    config_path = get_config_path()
    if not config_path.exists():
        return None
    try:
        config = json.loads(config_path.read_text())
        return config.get(key)
    except (json.JSONDecodeError, OSError):
        return None


def config_set(key: str, value: Any) -> dict:
    """Write a config value to spellbook.json.

    Creates the config file and parent directories if they don't exist.
    Preserves other config values (read-modify-write).

    Args:
        key: The config key to set
        value: The value to set (must be JSON-serializable)

    Returns:
        Dict with status and the updated config
    """
    config_path = get_config_path()

    # Read existing config or start fresh
    config = {}
    if config_path.exists():
        try:
            config = json.loads(config_path.read_text())
        except (json.JSONDecodeError, OSError):
            config = {}

    # Update the value
    config[key] = value

    # Ensure parent directory exists
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Write back
    config_path.write_text(json.dumps(config, indent=2) + "\n")

    return {"status": "ok", "config": config}


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


def random_line(file_path: Path) -> str:
    """Select a random non-empty line from a file.

    Args:
        file_path: Path to the file to read

    Returns:
        A random line from the file, or empty string if file missing/empty
    """
    try:
        lines = [line.strip() for line in file_path.read_text().splitlines() if line.strip()]
        return random.choice(lines) if lines else ""
    except OSError:
        return ""


def session_init(
    session_id: Optional[str] = None,
    continuation_message: Optional[str] = None
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

    # Add resume fields
    result.update(_get_resume_context(continuation_message))

    return result


def _get_resume_context(continuation_message: Optional[str]) -> dict:
    """Get resume context based on continuation message.

    Args:
        continuation_message: User's first message (optional)

    Returns:
        Dict with resume_available and optional resume_* fields
    """
    from spellbook_mcp.db import get_db_path
    from spellbook_mcp.resume import (
        detect_continuation_intent,
        get_resume_fields,
    )

    # Get project path
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

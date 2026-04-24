"""Runtime state management for spellbook.

Spellbook separates user **configuration** (intent) from runtime **state**
(machine-written facts). Configuration lives in ``~/.config/spellbook/spellbook.json``
and is owned by ``spellbook.core.config``. State lives in
``~/.local/spellbook/state.json`` and is owned by this module.

The distinction:
    * Config: things the user chose (``auto_update: true``, ``session_mode: fun``).
    * State: things the code wrote for itself (``update_check_failures: 2``,
      ``auto_update_branch: "main"`` once auto-detected).

Keeping them in separate files means a fresh checkout of spellbook.json -- or
an accidental commit of it -- never carries over transient machine state that
was never the user's to edit.

Atomic writes are used to prevent partial-write corruption if the process is
interrupted mid-write.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Optional

from spellbook.core.command_utils import atomic_replace
from spellbook.core.paths import get_data_dir

logger = logging.getLogger(__name__)


def get_state_path() -> Path:
    """Return the path to the runtime state file."""
    return get_data_dir() / "state.json"


def read_state() -> dict[str, Any]:
    """Return the full state dict.

    Returns an empty dict if the file does not yet exist or cannot be parsed.
    Malformed state is treated as empty rather than crashing callers; state is
    recoverable by the code that writes it.
    """
    state_path = get_state_path()
    if not state_path.exists():
        return {}
    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Could not read state file %s: %s", state_path, exc)
        return {}


def write_state(state: dict[str, Any]) -> None:
    """Atomically replace the state file with ``state``.

    Writes to a temp file in the same directory, then ``os.replace()`` to
    swap it into place. This guarantees that readers never see a partial
    write even if the process dies mid-write.

    The parent directory is created if it does not already exist.
    """
    state_path = get_state_path()
    state_path.parent.mkdir(parents=True, exist_ok=True)

    fd_tmp, tmp_path = tempfile.mkstemp(
        dir=str(state_path.parent), suffix=".tmp"
    )
    fd_tmp_closed = False
    try:
        os.write(fd_tmp, (json.dumps(state, indent=2) + "\n").encode("utf-8"))
        os.close(fd_tmp)
        fd_tmp_closed = True
        atomic_replace(tmp_path, str(state_path))
    except BaseException:
        if not fd_tmp_closed:
            try:
                os.close(fd_tmp)
            except OSError:
                pass
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def get_state(key: str, default: Optional[Any] = None) -> Any:
    """Return ``state[key]`` or ``default`` if absent."""
    return read_state().get(key, default)


def set_state(key: str, value: Any) -> None:
    """Write a single key into the state file, preserving other keys.

    Performs a read-modify-write. Callers that need to update several keys at
    once should read via :func:`read_state`, mutate, then :func:`write_state`
    rather than calling this repeatedly.
    """
    state = read_state()
    state[key] = value
    write_state(state)


# ---------------------------------------------------------------------------
# One-shot migration: spellbook.json -> spellbook.json + state.json
# ---------------------------------------------------------------------------

# Keys that reference subsystems removed from spellbook. Stripped unconditionally
# -- they are never re-added, and any value they held was dead weight.
_DEAD_CONFIG_KEYS: tuple[str, ...] = (
    "tts_enabled",
    "tts_volume",
    "telemetry_enabled",
)

# Keys that are runtime state, not user intent. Moved from spellbook.json to
# state.json on first session_init after upgrade. The value carries over so an
# in-flight failure counter or previously-detected branch is not lost.
_STATE_KEYS_TO_MIGRATE: tuple[str, ...] = (
    "update_check_failures",
    "auto_update_branch",
)


def migrate_config_to_state() -> dict[str, Any]:
    """Strip dead keys and move runtime state out of ``spellbook.json``.

    This is a one-shot migration but safe to run on every session_init: it is
    a no-op once the user's spellbook.json contains none of the five relevant
    keys.

    Behaviour:
        * Dead keys (``tts_enabled``, ``tts_volume``, ``telemetry_enabled``)
          are removed from spellbook.json. Their values are discarded.
        * State keys (``update_check_failures``, ``auto_update_branch``) are
          moved to state.json. Existing state.json values are preserved unless
          the key is absent there, in which case the config.json value wins.
        * If nothing needs to change, the config file is not rewritten (no
          touch of mtime, no needless I/O).

    Returns a summary dict: ``{"migrated": bool, "removed": [...], "moved": {...}}``.
    Failures are logged and surfaced via the return value; the function never
    raises, so a broken config file cannot block session_init.
    """
    # Local import to avoid a circular dep: config imports nothing from state,
    # but state's migration *does* need config's path helper.
    from spellbook.core.config import get_config_path

    summary: dict[str, Any] = {"migrated": False, "removed": [], "moved": {}}
    config_path = get_config_path()

    if not config_path.exists():
        return summary

    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Could not read config during migration: %s", exc)
        return summary

    if not isinstance(config, dict):
        return summary

    # Detect what needs to move
    dead_present = [k for k in _DEAD_CONFIG_KEYS if k in config]
    state_present = {k: config[k] for k in _STATE_KEYS_TO_MIGRATE if k in config}

    if not dead_present and not state_present:
        return summary

    # Move state keys to state.json. Preserve pre-existing state.json values
    # so concurrent writes from a running watcher are not clobbered.
    if state_present:
        current_state = read_state()
        for key, value in state_present.items():
            current_state.setdefault(key, value)
            summary["moved"][key] = value
        write_state(current_state)

    # Strip the migrated keys from spellbook.json. A direct read-modify-write
    # (rather than ``config_set_many``) is required because we need to *delete*
    # keys, which ``config_set_many`` does not support.
    new_config = {
        k: v
        for k, v in config.items()
        if k not in _DEAD_CONFIG_KEYS and k not in _STATE_KEYS_TO_MIGRATE
    }

    # Atomic write of the cleaned config (same pattern as write_state).
    fd_tmp, tmp_path = tempfile.mkstemp(
        dir=str(config_path.parent), suffix=".tmp"
    )
    fd_tmp_closed = False
    try:
        os.write(fd_tmp, (json.dumps(new_config, indent=2) + "\n").encode("utf-8"))
        os.close(fd_tmp)
        fd_tmp_closed = True
        atomic_replace(tmp_path, str(config_path))
    except BaseException as exc:
        logger.warning("Could not rewrite config during migration: %s", exc)
        if not fd_tmp_closed:
            try:
                os.close(fd_tmp)
            except OSError:
                pass
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        return summary

    summary["migrated"] = True
    summary["removed"] = dead_present
    return summary

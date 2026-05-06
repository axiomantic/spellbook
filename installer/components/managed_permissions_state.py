"""Managed permissions state file.

Tracks which permission entries (``allow``/``deny``/``ask``) and which
``defaultMode`` value(s) are currently *managed by spellbook* on a per-config-dir
basis. Used by ``install_default_mode`` and ``install_permissions`` (WI-0) to
distinguish entries the installer owns from entries the user added by hand,
so reconciliation can remove stale managed entries without trampling on
user-added ones.

Schema (JSON, on disk at ``~/.local/spellbook/state/managed_permissions.json``):

    {
      "version": 1,
      "config_dirs": {
        "<absolute config_dir path>": {
          "allow": ["Bash(git status:*)", ...],
          "deny": [...],
          "ask": [...]
        }
      }
    }

All read-modify-write operations acquire a ``CrossPlatformLock`` (blocking) on
the state file's ``.lock`` sibling so concurrent installer invocations are
serialized. Writes go through ``atomic_write_json`` so partial writes cannot
leave the file corrupt; corrupt files are treated as empty (recovery path).
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from spellbook.core.command_utils import atomic_write_json, read_json_safe
from spellbook.core.compat import CrossPlatformLock

# Resolved at import time. Tests monkeypatch this attribute to redirect to a
# pytest tmp_path. See ``tests/installer/test_managed_permissions_state.py``.
_STATE_FILE_PATH: Path = Path.home() / ".local" / "spellbook" / "state" / "managed_permissions.json"

_SCHEMA_VERSION = 1


def _empty_schema() -> Dict:
    return {"version": _SCHEMA_VERSION, "config_dirs": {}}


def _empty_per_dir() -> Dict[str, List[str]]:
    return {"allow": [], "deny": [], "ask": []}


def read_state() -> Dict:
    """Return the current state file contents, or the empty schema.

    Missing file or corrupt JSON both return the empty schema; this is the
    recovery path. Callers do not need to handle ``FileNotFoundError`` or
    ``json.JSONDecodeError`` themselves.
    """
    path = _STATE_FILE_PATH
    if not path.exists():
        return _empty_schema()
    try:
        data = read_json_safe(str(path))
    except (ValueError, OSError):
        return _empty_schema()
    if not isinstance(data, dict) or "config_dirs" not in data:
        return _empty_schema()
    return data


def update_managed_set(
    config_dir: Path,
    allow: Optional[List[str]] = None,
    deny: Optional[List[str]] = None,
    ask: Optional[List[str]] = None,
) -> Dict[str, Dict[str, List[str]]]:
    """Replace the managed entries for ``config_dir`` and return a diff.

    Reads the current managed set for ``config_dir``, writes the desired set
    in its place, and returns the add/remove diff so callers (e.g.
    ``install_permissions``) can apply the same delta to ``settings.json``.

    Args:
        config_dir: Absolute path to the platform config directory (e.g.
            ``~/.claude``). Used as the dict key in the state file.
        allow: Desired managed ``allow`` entries. ``None`` -> empty list.
        deny: Desired managed ``deny`` entries. ``None`` -> empty list.
        ask: Desired managed ``ask`` entries. ``None`` -> empty list.

    Returns:
        Diff dict of the form::

            {
              "added":   {"allow": [...], "deny": [...], "ask": [...]},
              "removed": {"allow": [...], "deny": [...], "ask": [...]},
            }

        Lists in the diff are sorted in the order they appear in the input
        (added) or in the prior state (removed).
    """
    desired = {
        "allow": list(allow or []),
        "deny": list(deny or []),
        "ask": list(ask or []),
    }
    key = str(config_dir)

    lock_path = _state_lock_path()
    with CrossPlatformLock(lock_path, blocking=True):
        state = read_state()
        config_dirs = state.setdefault("config_dirs", {})
        prior = config_dirs.get(key, _empty_per_dir())

        diff: Dict[str, Dict[str, List[str]]] = {
            "added": {"allow": [], "deny": [], "ask": []},
            "removed": {"allow": [], "deny": [], "ask": []},
        }
        for bucket in ("allow", "deny", "ask"):
            prior_set = set(prior.get(bucket, []))
            desired_set = set(desired[bucket])
            diff["added"][bucket] = [e for e in desired[bucket] if e not in prior_set]
            diff["removed"][bucket] = [
                e for e in prior.get(bucket, []) if e not in desired_set
            ]

        # Preserve any sibling fields (currently just ``default_mode``) that
        # ``set_managed_default_mode`` may have written. update_managed_set
        # only owns the allow/deny/ask buckets, never the default_mode.
        new_entry = dict(prior)
        new_entry["allow"] = desired["allow"]
        new_entry["deny"] = desired["deny"]
        new_entry["ask"] = desired["ask"]
        config_dirs[key] = new_entry
        state["version"] = _SCHEMA_VERSION
        atomic_write_json(str(_STATE_FILE_PATH), state)

    return diff


def get_managed_default_mode(config_dir: Path) -> Optional[str]:
    """Return the previously-managed ``defaultMode`` for ``config_dir``, or None.

    Used by ``install_default_mode`` to detect whether the value currently in
    ``settings.json`` was last set by spellbook (safe to overwrite) or by the
    user (must be preserved).
    """
    key = str(config_dir)
    state = read_state()
    return state.get("config_dirs", {}).get(key, {}).get("default_mode")


def set_managed_default_mode(config_dir: Path, mode: Optional[str]) -> None:
    """Record (or clear, when ``mode`` is None) the managed ``defaultMode``.

    Acquires the coord lock, reads the state, mutates only the
    ``default_mode`` field for ``config_dir`` (preserving allow/deny/ask),
    and atomically writes the result back.
    """
    key = str(config_dir)
    lock_path = _state_lock_path()
    with CrossPlatformLock(lock_path, blocking=True):
        state = read_state()
        config_dirs = state.setdefault("config_dirs", {})
        per_dir = config_dirs.setdefault(key, _empty_per_dir())
        if mode is None:
            per_dir.pop("default_mode", None)
        else:
            per_dir["default_mode"] = mode
        state["version"] = _SCHEMA_VERSION
        atomic_write_json(str(_STATE_FILE_PATH), state)


def reconcile(config_dir: Path) -> Dict[str, List[str]]:
    """Return the current managed entries for ``config_dir``.

    Acquires the lock, reads the state file, and returns a copy of the
    managed-set entries for the given config directory (or an empty
    per-dir struct if the directory has no entry yet).

    Used by ``install_permissions`` to discover which entries it owned
    on the previous run before computing the new desired set.
    """
    key = str(config_dir)
    lock_path = _state_lock_path()
    with CrossPlatformLock(lock_path, blocking=True):
        state = read_state()
        prior = state.get("config_dirs", {}).get(key, _empty_per_dir())
        return {bucket: list(prior.get(bucket, [])) for bucket in ("allow", "deny", "ask")}


def _state_lock_path() -> Path:
    """Return the lock file used to serialize state-file mutations.

    Distinct suffix from ``atomic_write_json``'s internal ``.lock`` sibling so
    the two locks do not collide on the same name during a write.
    """
    return _STATE_FILE_PATH.with_suffix(_STATE_FILE_PATH.suffix + ".coordlock")

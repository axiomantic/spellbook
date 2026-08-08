"""Configuration management for spellbook.

Canonical location for configuration utilities. This module was migrated from
spellbook.core.config as part of the three-layer architecture reorganization.
"""

import json
import logging
import os
import tempfile
import warnings
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from spellbook.core.compat import CrossPlatformLock, LockHeldError, get_config_dir

logger = logging.getLogger(__name__)

# Prefix for the per-rule-module opt-in keys. Their defaults are resolved
# lazily (see rule_module_config_defaults) rather than registered at import.
RULE_MODULE_KEY_PREFIX = "rules.module."

# Built-in defaults for config keys. config_get returns these when a key is
# absent from the user's spellbook.json config file. Adding an entry here
# means the key has a well-known default that callers can rely on.
CONFIG_DEFAULTS: dict[str, Any] = {
    # Hook observability. Consumed by the purge loop via single-arg
    # config_get(key); missing defaults would make config_get return None and
    # crash the int casts in spellbook/hooks/observability.py.
    "hook_observability_retention_hours": 24,
    "hook_observability_max_rows": 50000,
    "hook_observability_purge_interval_seconds": 300,
    # PreToolUse security gates (bash/spawn/state-sanitize + tool-safety sniff).
    # Disabled by default (opt-in); the installer defaults wizard asks about it.
    # Read live by hooks/spellbook_hook.py::_gates_disabled. Matches CONFIG_SCHEMA
    # in the config schema.
    "security_gates_enabled": False,
}


def _rule_module_defaults() -> dict[str, Any]:
    """One boolean default per preference rule module, read from ``rules/``.

    Generated rather than typed, so adding a module cannot leave a key
    unregistered. Mandatory modules get no key: they install unconditionally
    and are never consulted against config.

    A key's *absence* from the user's config file remains meaningful (it means
    "never offered"), so these entries are defaults for ``config_get`` only --
    ``config_is_explicitly_set`` still distinguishes an answered module from an
    unanswered one.
    """
    try:
        from installer.components.rule_modules import (
            get_rules_dir,
            load_rule_modules,
            preference_modules,
        )

        modules = load_rule_modules(get_rules_dir(get_spellbook_dir()))
    except Exception:  # pragma: no cover - a partial checkout must not break config
        logger.debug("Rule modules unavailable; no rules.module.* defaults registered")
        return {}

    return {module.config_key: module.default_on for module in preference_modules(modules)}


@lru_cache(maxsize=4)
def _rule_module_defaults_for_dir(spellbook_dir: str) -> dict[str, Any]:
    return _rule_module_defaults()


def rule_module_config_defaults() -> dict[str, Any]:
    """Memoized ``rules.module.*`` defaults, resolved on first use.

    Deliberately NOT folded into ``CONFIG_DEFAULTS`` at import time. Doing that
    globbed and parsed every file in ``rules/`` on every import of this module
    -- including from the PreToolUse bash gate, which runs on every single Bash
    call. Resolution now happens only when a ``rules.module.*`` default is
    actually requested, and only once per checkout.

    Keyed on the resolved checkout path rather than memoized outright. The MCP
    server is a long-lived process; a ``SPELLBOOK_DIR`` change under it left a
    single-slot cache serving the defaults of the previous checkout forever,
    and a ``cache_clear`` nobody called cannot fix that. Keying makes the stale
    read impossible instead of merely recoverable.
    """
    return _rule_module_defaults_for_dir(str(get_spellbook_dir()))


def config_default_for(key: str) -> Any:
    """Built-in default for a config key, including the lazy rule-module keys."""
    if key in CONFIG_DEFAULTS:
        return CONFIG_DEFAULTS[key]
    if key.startswith(RULE_MODULE_KEY_PREFIX):
        return rule_module_config_defaults().get(key)
    return None


def config_is_explicitly_set(key: str) -> bool:
    """Return True if key exists in spellbook.json (not just in CONFIG_DEFAULTS).

    Reads the config file directly without applying CONFIG_DEFAULTS, so a key
    that has a default but has never been written to disk returns False.

    Args:
        key: Dotted config key string (e.g. "security.spotlighting.enabled")

    Returns:
        True if the key is present as a top-level key in spellbook.json,
        False if the file is missing, unreadable, malformed, or the key is absent.
    """
    config_path = get_config_dir() / "spellbook.json"
    if not config_path.exists():
        return False
    try:
        return key in json.loads(config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False


def get_unset_config_keys(keys: list[str]) -> list[str]:
    """Return the subset of keys not yet explicitly set in spellbook.json.

    Preserves input order. This is a generic helper consumed by callers
    that know which keys they care about; it does not carry an opinion
    about the "install wizard key set" (that lived in the previous
    ``WIZARD_CONFIG_KEYS`` constant, which was removed in favor of
    per-wizard opinions in ``installer/wizards/*``).

    Args:
        keys: List of config key strings to check.

    Returns:
        Keys from the input list for which config_is_explicitly_set() is False.
    """
    return [k for k in keys if not config_is_explicitly_set(k)]


# File-level lock for thread-safe config access
CONFIG_LOCK_PATH = get_config_dir() / "config.lock"


def _config_lock_path() -> Path:
    """Return the path of the config file-level lock.

    Internal callers use this indirection so tests can redirect the lock path
    via ``tripwire.mock("spellbook.core.config:_config_lock_path")`` instead of
    monkey-patching the module-level ``CONFIG_LOCK_PATH`` constant.
    """
    return CONFIG_LOCK_PATH

# Environment variable aliases for backward compatibility.
# Maps short key names to their old SPELLBOOK_MCP_* env var names.
# New canonical names use the SPELLBOOK_* prefix (e.g., SPELLBOOK_PORT).
_ENV_ALIASES: dict[str, str] = {
    "PORT": "SPELLBOOK_MCP_PORT",
    "HOST": "SPELLBOOK_MCP_HOST",
    "DB_PATH": "SPELLBOOK_MCP_DB_PATH",
    "TOKEN": "SPELLBOOK_MCP_TOKEN",
    "AUTH": "SPELLBOOK_MCP_AUTH",
    "TRANSPORT": "SPELLBOOK_MCP_TRANSPORT",
}


def get_env(key: str, default: Optional[str] = None) -> Optional[str]:
    """Get a spellbook environment variable with backward compatibility.

    Checks the new canonical name (SPELLBOOK_{key}) first. If not found,
    falls back to the old SPELLBOOK_MCP_* name (if one exists in _ENV_ALIASES)
    and emits a deprecation warning.

    Args:
        key: Short key name (e.g., "PORT", "HOST", "DB_PATH")
        default: Default value if neither new nor old name is set

    Returns:
        The environment variable value, or default if not set
    """
    # Try new canonical name first
    new_name = f"SPELLBOOK_{key}"
    value = os.environ.get(new_name)
    if value is not None:
        return value

    # Try old name with deprecation warning
    old_name = _ENV_ALIASES.get(key)
    if old_name is not None:
        value = os.environ.get(old_name)
        if value is not None:
            warnings.warn(
                f"Environment variable {old_name} is deprecated. "
                f"Use {new_name} instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            return value

    return default



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
    # Key indicators: skills/ directory and the rules/ module directory.
    # The AGENTS.spellbook.md alternative is retained for one minor release so a
    # checkout predating the rules/ split is still recognized. This predicate must
    # stay byte-equivalent to install.py::is_spellbook_repo.
    skills_dir = path / "skills"
    rules_dir = path / "rules"
    legacy_md = path / "AGENTS.spellbook.md"
    return skills_dir.is_dir() and (rules_dir.is_dir() or legacy_md.is_file())


def _find_spellbook_root_from_file() -> Optional[Path]:
    """Find spellbook root by walking up from this file's directory.

    Returns:
        Path to spellbook root if found, None otherwise
    """
    # Start from this file's directory (spellbook/core/)
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
        The value for the key, built-in default from CONFIG_DEFAULTS, or None
    """
    default = config_default_for(key)
    config_path = get_config_path()
    if not config_path.exists():
        return default

    try:
        with CrossPlatformLock(_config_lock_path(), shared=True, blocking=True):
            config = json.loads(config_path.read_text(encoding="utf-8"))
            return config.get(key, default)
    except LockHeldError:
        # Fall back to unlocked read
        logger.warning("Could not acquire config read lock. Falling back to unlocked read.")
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
            return config.get(key, default)
        except (json.JSONDecodeError, OSError):
            return default
    except (json.JSONDecodeError, OSError):
        return default


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
        with CrossPlatformLock(_config_lock_path(), blocking=True):
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
        with CrossPlatformLock(_config_lock_path(), blocking=True):
            return _apply_and_write()
    except LockHeldError:
        logger.warning("Could not acquire config write lock. Falling back to unlocked write.")
        return _apply_and_write()


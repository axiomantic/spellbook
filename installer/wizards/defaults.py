"""Shared defaults wizard for previously never-prompted config keys.

Several keys have a runtime default but no installer prompt:
``security_gates_enabled``, ``notify_enabled``, ``notify_title``,
``auto_update``. Without a prompt users discover them only by reading
source.

This wizard closes the gap by walking the user through each key on
fresh installs. It respects the idempotency rule defined in AGENTS.md:
keys already explicitly set in ``spellbook.json`` are skipped unless
``--reconfigure`` is active. Bare Enter accepts the current default.

Invoked from both the root ``install.py`` entry path and
``spellbook.cli.commands.install`` so every install flow offers the
same prompts.
"""

from __future__ import annotations

import sys as _sys
from typing import Any, Optional


def _is_explicit(key: str) -> bool:
    """Return True if ``key`` has been explicitly written to spellbook.json."""
    try:
        from spellbook.core.config import config_is_explicitly_set
    except ImportError:
        return False
    return config_is_explicitly_set(key)


def _config_get(key: str, default: Any) -> Any:
    """Return the current config value, falling back to ``default``."""
    try:
        from spellbook.core.config import config_get
    except ImportError:
        return default
    value = config_get(key)
    return default if value is None else value


def _prompt_bool(prompt: str, current: bool) -> bool:
    suffix = "[Y/n]" if current else "[y/N]"
    raw = input(f"{prompt} {suffix}: ").strip().lower()
    if not raw:
        return current
    return raw in ("y", "yes")


def _prompt_string(prompt: str, current: str) -> str:
    shown = current if current else "(empty)"
    raw = input(f"{prompt} [{shown}]: ").strip()
    return current if not raw else raw


def _write(key: str, value: Any) -> None:
    """Write a single config key, catching import/IO errors."""
    try:
        from spellbook.core.config import config_set
    except ImportError:
        return
    try:
        config_set(key, value)
    except Exception as e:  # noqa: BLE001
        print(f"  Error writing {key}: {type(e).__name__}: {e}")


def run_defaults_wizard(args: Optional[Any] = None) -> None:
    """Prompt the user for the never-prompted config keys.

    Skipped when stdin is not a tty or ``args.dry_run`` is True. Each key
    is skipped when already explicitly set unless ``args.reconfigure`` is
    truthy.

    Args:
        args: Optional argparse ``Namespace``. Checked for ``dry_run``
            and ``reconfigure``.
    """
    if not _sys.stdin.isatty():
        return
    if getattr(args, "dry_run", False):
        return

    reconfigure = bool(getattr(args, "reconfigure", False))

    # Decide whether to ask about anything at all. If every key is already
    # set and --reconfigure is not active, stay silent.
    candidate_keys = [
        "security_gates_enabled",
        "notify_enabled",
        "notify_title",
        "auto_update",
    ]
    if not reconfigure and all(_is_explicit(k) for k in candidate_keys):
        return

    print()
    print("Additional defaults (press Enter to keep the current value):")

    # ----- Security gates -----
    if reconfigure or not _is_explicit("security_gates_enabled"):
        current = bool(_config_get("security_gates_enabled", False))
        try:
            value = _prompt_bool(
                "Enable the PreToolUse security gates? They block risky bash "
                "commands (exfiltration / dangerous patterns) and sanitize "
                "spawn/state inputs. Disabled by default",
                current,
            )
        except (EOFError, KeyboardInterrupt):
            print()
            print("  (defaults wizard cancelled)")
            return
        _write("security_gates_enabled", value)

    # ----- Notifications -----
    if reconfigure or not _is_explicit("notify_enabled"):
        current = bool(_config_get("notify_enabled", True))
        try:
            value = _prompt_bool("Enable native OS notifications?", current)
        except (EOFError, KeyboardInterrupt):
            print()
            print("  (defaults wizard cancelled)")
            return
        _write("notify_enabled", value)
    if reconfigure or not _is_explicit("notify_title"):
        current = str(_config_get("notify_title", "Spellbook"))
        try:
            value = _prompt_string("Notification title", current)
        except (EOFError, KeyboardInterrupt):
            print()
            print("  (defaults wizard cancelled)")
            return
        _write("notify_title", value)

    # ----- Auto-update -----
    if reconfigure or not _is_explicit("auto_update"):
        current = bool(_config_get("auto_update", True))
        try:
            value = _prompt_bool(
                "Automatically check for and apply spellbook updates?", current
            )
        except (EOFError, KeyboardInterrupt):
            print()
            print("  (defaults wizard cancelled)")
            return
        _write("auto_update", value)

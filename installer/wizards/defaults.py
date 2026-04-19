"""Shared defaults wizard for previously never-prompted config keys.

Seven keys have entries in ``CONFIG_SCHEMA`` but no installer prompt:
``tts_voice``, ``tts_volume``, ``notify_enabled``, ``notify_title``,
``telemetry_enabled``, ``auto_update``, ``session_mode``. Without a prompt
users discover them only via the admin UI or by reading source.

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


# Session mode enum mirrors the validator in
# ``spellbook.core.config.session_mode_set``.
_SESSION_MODE_OPTIONS: tuple[str, ...] = ("none", "fun", "tarot")


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


def _prompt_float(prompt: str, current: float, lo: float, hi: float) -> float:
    """Prompt for a float in [lo, hi] with enter-to-keep-default."""
    while True:
        raw = input(f"{prompt} [{current}]: ").strip()
        if not raw:
            return current
        try:
            value = float(raw)
        except ValueError:
            print("  Please enter a number.")
            continue
        if value < lo or value > hi:
            print(f"  Must be between {lo} and {hi}.")
            continue
        return value


def _prompt_choice(prompt: str, current: str, options: tuple[str, ...]) -> str:
    """Numbered-list prompt for a string enum. Enter keeps current."""
    print()
    print(f"{prompt} (current: {current}):")
    for i, opt in enumerate(options, start=1):
        print(f"  {i}. {opt}")
    while True:
        raw = input(f"Select [1-{len(options)}] (Enter to keep {current}): ").strip()
        if not raw:
            return current
        try:
            idx = int(raw)
        except ValueError:
            print("  Please enter a number.")
            continue
        if 1 <= idx <= len(options):
            return options[idx - 1]
        print("  Out of range.")


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
    """Prompt the user for the seven never-prompted config keys.

    Skipped when stdin is not a tty or ``args.dry_run`` is True. Each key
    is skipped when already explicitly set unless ``args.reconfigure`` is
    truthy. The ``tts_voice`` prompt is conditional on ``tts_enabled``
    being True (we do not ask about voice when TTS is off).

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
    tts_enabled = _config_get("tts_enabled", True)
    candidate_keys = [
        "tts_voice",
        "tts_volume",
        "notify_enabled",
        "notify_title",
        "telemetry_enabled",
        "auto_update",
        "session_mode",
    ]
    if not reconfigure and all(_is_explicit(k) for k in candidate_keys):
        return

    print()
    print("Additional defaults (press Enter to keep the current value):")

    # ----- TTS voice / volume (voice gated on tts_enabled) -----
    if reconfigure or not _is_explicit("tts_voice"):
        if tts_enabled:
            current = _config_get("tts_voice", "")
            try:
                value = _prompt_string(
                    "TTS voice (Wyoming server-specific; blank = server default)",
                    str(current),
                )
            except (EOFError, KeyboardInterrupt):
                print()
                print("  (defaults wizard cancelled)")
                return
            _write("tts_voice", value)
        # else: TTS is off; silently skip voice prompt.
    if reconfigure or not _is_explicit("tts_volume"):
        current = _config_get("tts_volume", 0.3)
        try:
            value = _prompt_float(
                "TTS volume (0.0 to 1.0)", float(current), 0.0, 1.0
            )
        except (EOFError, KeyboardInterrupt):
            print()
            print("  (defaults wizard cancelled)")
            return
        _write("tts_volume", value)

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

    # ----- Telemetry -----
    if reconfigure or not _is_explicit("telemetry_enabled"):
        current = bool(_config_get("telemetry_enabled", False))
        try:
            value = _prompt_bool("Enable anonymous usage telemetry?", current)
        except (EOFError, KeyboardInterrupt):
            print()
            print("  (defaults wizard cancelled)")
            return
        _write("telemetry_enabled", value)

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

    # ----- Session mode (none / fun / tarot) -----
    if reconfigure or not _is_explicit("session_mode"):
        current = str(_config_get("session_mode", "none"))
        if current not in _SESSION_MODE_OPTIONS:
            current = "none"
        try:
            value = _prompt_choice(
                "Default session mode", current, _SESSION_MODE_OPTIONS
            )
        except (EOFError, KeyboardInterrupt):
            print()
            print("  (defaults wizard cancelled)")
            return
        _write("session_mode", value)

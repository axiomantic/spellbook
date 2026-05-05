"""Install / uninstall the spellbook-managed ``defaultMode`` key.

WI-0 deliverable: a single, idempotent function that sets
``settings["defaultMode"] = mode`` in a Claude Code settings file, atomically,
and records the managed value in the per-config-dir state file so subsequent
re-runs (or uninstalls) can distinguish spellbook-managed values from
user-set values.

If the settings file already contains a ``defaultMode`` whose value is NOT
the one we last set (per the state file), the user is assumed to have set it
manually -- we leave it alone and return a ``HookResult`` with
``action="skipped"`` and a warning message.

Errors during read/parse/write are wrapped into a ``HookResult`` with
``success=False`` and ``action="failed"``, mirroring the contract of
``installer.components.hooks.install_hooks``.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from spellbook.core.command_utils import atomic_write_json

from . import managed_permissions_state as _mps
from .hooks import HookResult

logger = logging.getLogger(__name__)


def install_default_mode(
    settings_path: Path,
    mode: str,
    spellbook_dir: Path,
    dry_run: bool,
) -> HookResult:
    """Install the spellbook-managed ``defaultMode`` into a settings file.

    Args:
        settings_path: Path to the Claude Code settings file (e.g.
            ``~/.claude/settings.json``).
        mode: Desired ``defaultMode`` value (e.g. ``"acceptEdits"``).
        spellbook_dir: Reserved for future use (parity with ``install_hooks``).
        dry_run: If True, no files are written; returns success without I/O.

    Returns:
        ``HookResult`` with ``component="default_mode"``. ``action`` is one of:
            - ``"installed"``: settings.json was written (or would be in dry run)
            - ``"unchanged"``: file already had the desired mode (idempotent no-op)
            - ``"skipped"``: settings.json had a user-set value not managed by us
            - ``"failed"``: an error occurred while reading or writing
    """
    if dry_run:
        return HookResult(
            component="default_mode",
            success=True,
            action="installed",
            message=f"default_mode: would install defaultMode={mode!r} (dry run)",
        )

    config_dir = settings_path.parent
    try:
        existing_settings = _read_settings(settings_path)
    except json.JSONDecodeError as e:
        return HookResult(
            component="default_mode",
            success=False,
            action="failed",
            message=(
                f"default_mode: failed to parse {settings_path.name} - "
                f"JSON decode error: {e}"
            ),
        )
    except OSError as e:
        return HookResult(
            component="default_mode",
            success=False,
            action="failed",
            message=f"default_mode: failed to read {settings_path.name}: {e}",
        )

    current_mode = existing_settings.get("defaultMode")
    managed_mode = _mps.get_managed_default_mode(config_dir)

    if current_mode is not None and current_mode != managed_mode and current_mode != mode:
        # User manually set defaultMode and we don't own that value. Leave alone.
        logger.warning(
            "default_mode: user-set defaultMode=%r in %s; not overwriting "
            "with managed value %r",
            current_mode,
            settings_path,
            mode,
        )
        return HookResult(
            component="default_mode",
            success=True,
            action="skipped",
            message=(
                f"default_mode: user-set defaultMode={current_mode!r} in "
                f"{settings_path.name}; not overwriting with managed value {mode!r}"
            ),
        )

    if current_mode == mode and managed_mode == mode:
        return HookResult(
            component="default_mode",
            success=True,
            action="unchanged",
            message=f"default_mode: defaultMode already set to {mode!r}",
        )

    new_settings = dict(existing_settings)
    new_settings["defaultMode"] = mode

    try:
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(str(settings_path), new_settings)
    except (ValueError, OSError) as e:
        return HookResult(
            component="default_mode",
            success=False,
            action="failed",
            message=f"default_mode: write to {settings_path.name} failed: {e}",
        )

    # Record the managed value AFTER the settings.json write succeeds. If the
    # state-file write fails, the next run will see "user set" mode==state and
    # treat it as user-managed -- failing safe (preserves the user's intent).
    try:
        _mps.set_managed_default_mode(config_dir, mode)
    except (ValueError, OSError) as e:
        logger.warning(
            "default_mode: settings.json updated but state-file write failed: %s",
            e,
        )

    return HookResult(
        component="default_mode",
        success=True,
        action="installed",
        message=f"default_mode: defaultMode={mode!r} installed in {settings_path.name}",
    )


def _read_settings(settings_path: Path) -> dict:
    """Read settings.json; return {} when file is absent."""
    if not settings_path.exists():
        return {}
    text = settings_path.read_text(encoding="utf-8")
    if not text.strip():
        return {}
    return json.loads(text)

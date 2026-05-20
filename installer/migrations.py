"""
One-shot migrations run during install/upgrade and uninstall.

Each function is idempotent and safe to run on machines that have never
had the affected artifact. Migrations should be deletable once they've
been in the wild long enough that no plausible user is still on the
pre-migration version.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Markers historically written by the now-removed
# installer/components/aliases.py (claude/opencode -> spellbook-sandbox).
# Safe to remove this migration after a few releases.
_LEGACY_ALIAS_START = "# SPELLBOOK_ALIASES:START"
_LEGACY_ALIAS_END = "# SPELLBOOK_ALIASES:END"


def _candidate_rc_files() -> list[Path]:
    home = Path.home()
    return [
        home / ".zshrc",
        home / ".bashrc",
        home / ".config" / "fish" / "config.fish",
    ]


def cleanup_legacy_alias_block(rc_path: Path) -> bool:
    """Strip the SPELLBOOK_ALIASES marker block from *rc_path*.

    Returns True if the file was modified, False otherwise.
    Idempotent: no-ops when no markers are present.
    """
    if not rc_path.exists():
        return False
    try:
        original = rc_path.read_text()
    except OSError:
        logger.debug("cleanup_legacy_alias_block: unreadable %s", rc_path)
        return False

    if _LEGACY_ALIAS_START not in original or _LEGACY_ALIAS_END not in original:
        return False

    lines = original.splitlines(keepends=True)
    kept: list[str] = []
    inside = False
    for line in lines:
        if _LEGACY_ALIAS_START in line:
            inside = True
            continue
        if _LEGACY_ALIAS_END in line:
            inside = False
            continue
        if not inside:
            kept.append(line)

    # Collapse a run of blank lines left where the block used to be.
    cleaned: list[str] = []
    prev_blank = False
    for line in kept:
        is_blank = line.strip() == ""
        if is_blank and prev_blank:
            continue
        cleaned.append(line)
        prev_blank = is_blank
    new_text = "".join(cleaned)

    if new_text == original:
        return False
    rc_path.write_text(new_text)
    return True


def run_all_migrations() -> list[Path]:
    """Run every migration in this module. Returns list of modified files.

    Called from install() and uninstall() so both upgrade and removal
    paths clean up legacy state.
    """
    modified: list[Path] = []
    for rc_path in _candidate_rc_files():
        if cleanup_legacy_alias_block(rc_path):
            modified.append(rc_path)
            logger.info("Removed legacy alias block from %s", rc_path)
    return modified

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
        original = rc_path.read_text(encoding="utf-8")
    except OSError:
        logger.debug("cleanup_legacy_alias_block: unreadable %s", rc_path)
        return False

    if _LEGACY_ALIAS_START not in original or _LEGACY_ALIAS_END not in original:
        return False

    # Walk the file and build the output, removing each marker block plus
    # at most one blank line directly adjacent to it on each side. Blank
    # lines elsewhere in the user's rc file (including intentional
    # double-blank-line spacing between unrelated sections) are preserved
    # verbatim.
    lines = original.splitlines(keepends=True)
    final: list[str] = []
    inside = False
    just_closed = False
    for line in lines:
        stripped = line.strip()
        if stripped == _LEGACY_ALIAS_START:
            # Drop one trailing blank line that was paired with the
            # block on its leading side, if present.
            if final and final[-1].strip() == "":
                final.pop()
            inside = True
            continue
        if stripped == _LEGACY_ALIAS_END:
            inside = False
            just_closed = True
            continue
        if inside:
            continue
        # Outside the block. The first blank line immediately after the
        # END marker is the trailing boundary blank -- drop it. Any
        # subsequent blanks (intentional spacing) are preserved.
        if just_closed and stripped == "":
            just_closed = False
            continue
        just_closed = False
        final.append(line)

    new_text = "".join(final)

    if new_text == original:
        return False
    rc_path.write_text(new_text, encoding="utf-8")
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

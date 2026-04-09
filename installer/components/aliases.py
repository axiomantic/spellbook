"""
Shell alias management for spellbook installation.

Installs aliases (claude, opencode) that point to the spellbook-sandbox
launcher into the user's shell rc file. Uses demarcated sections for
idempotent install/uninstall.
"""

import os
import re
import shutil
from pathlib import Path
from typing import Optional

# Demarcation markers for shell rc files (# comment style, matching
# the pattern used by installer/platforms/codex.py for TOML files).
_START_MARKER = "# SPELLBOOK_ALIASES:START"
_END_MARKER = "# SPELLBOOK_ALIASES:END"

# Regex to find existing alias targets
_ALIAS_RE = re.compile(
    r"""alias\s+(claude|opencode)\s*=?\s*['"]([^'"]+)['"]""",
)


def get_shell_rc_path() -> Path | None:
    """Detect user's shell and return rc file path.

    Returns .zshrc for zsh, .bashrc for bash, config.fish for fish,
    None for unknown.  Uses $SHELL env var.
    """
    shell = os.environ.get("SHELL", "")
    shell_name = Path(shell).name if shell else ""

    home = Path.home()
    rc_map: dict[str, Path] = {
        "zsh": home / ".zshrc",
        "bash": home / ".bashrc",
        "fish": home / ".config" / "fish" / "config.fish",
    }

    return rc_map.get(shell_name)


def _is_fish(rc_path: Path) -> bool:
    """Return True if *rc_path* belongs to fish shell."""
    return rc_path.name == "config.fish"


def detect_existing_aliases(rc_path: Path) -> dict[str, str | None]:
    """Check if claude/opencode aliases already exist in rc file.

    Returns dict like ``{"claude": "/path/to/spellbook-sandbox", "opencode": None}``
    where value is the target if alias exists and points to spellbook-sandbox,
    None if not found.
    """
    result: dict[str, str | None] = {"claude": None, "opencode": None}

    if not rc_path.exists():
        return result

    content = rc_path.read_text(encoding="utf-8")
    for match in _ALIAS_RE.finditer(content):
        name, target = match.group(1), match.group(2)
        if name in result and "spellbook-sandbox" in target:
            result[name] = target

    return result


def generate_alias_block(spellbook_dir: Path, fish: bool = False) -> str:
    """Generate the shell alias block for the rc file.

    For bash/zsh::

        alias claude='/path/to/spellbook/scripts/spellbook-sandbox'
        alias opencode='/path/to/spellbook/scripts/spellbook-sandbox opencode'

    For fish::

        alias claude '/path/to/spellbook/scripts/spellbook-sandbox'
        alias opencode '/path/to/spellbook/scripts/spellbook-sandbox opencode'
    """
    launcher = spellbook_dir / "scripts" / "spellbook-sandbox"

    if fish:
        lines = [
            f"alias claude '{launcher}'",
            f"alias opencode '{launcher} opencode'",
        ]
    else:
        lines = [
            f"alias claude='{launcher}'",
            f"alias opencode='{launcher} opencode'",
        ]

    return "\n".join(lines)


def _read_rc(rc_path: Path) -> str:
    """Read rc file content, returning empty string if absent."""
    if rc_path.exists():
        return rc_path.read_text(encoding="utf-8")
    return ""


def _find_demarcated_section(content: str) -> tuple[int, int] | None:
    """Return (start, end) byte offsets of the demarcated block, or None."""
    start = content.find(_START_MARKER)
    if start == -1:
        return None
    end = content.find(_END_MARKER, start)
    if end == -1:
        return None
    return (start, end + len(_END_MARKER))


def _build_block(alias_content: str) -> str:
    """Wrap alias content in demarcation markers."""
    return f"{_START_MARKER}\n{alias_content}\n{_END_MARKER}"


def install_aliases(
    spellbook_dir: Path, dry_run: bool = False
) -> dict:
    """Install shell aliases into the user's rc file.

    Uses demarcated section pattern for idempotency.

    Returns::

        {
            "installed": bool,
            "rc_path": str,
            "aliases": list[str],
            "skipped_reason": str | None,
        }
    """
    rc_path = get_shell_rc_path()
    if rc_path is None:
        return {
            "installed": False,
            "rc_path": None,
            "aliases": [],
            "skipped_reason": "Unknown shell (only zsh, bash, and fish are supported)",
        }

    fish = _is_fish(rc_path)
    alias_block = generate_alias_block(spellbook_dir, fish=fish)
    new_block = _build_block(alias_block)

    content = _read_rc(rc_path)
    span = _find_demarcated_section(content)

    if span is not None:
        # Replace existing block
        new_content = content[: span[0]] + new_block + content[span[1] :]
    else:
        # Append
        if content and not content.endswith("\n"):
            content += "\n"
        new_content = content + "\n" + new_block + "\n"

    if not dry_run:
        rc_path.parent.mkdir(parents=True, exist_ok=True)
        rc_path.write_text(new_content, encoding="utf-8")

    return {
        "installed": True,
        "rc_path": str(rc_path),
        "aliases": ["claude", "opencode"],
        "skipped_reason": None,
    }


def uninstall_aliases() -> dict:
    """Remove the demarcated alias block from the user's rc file.

    Returns::

        {"removed": bool, "rc_path": str | None}
    """
    rc_path = get_shell_rc_path()
    if rc_path is None or not rc_path.exists():
        return {"removed": False, "rc_path": None}

    content = rc_path.read_text(encoding="utf-8")
    span = _find_demarcated_section(content)

    if span is None:
        return {"removed": False, "rc_path": str(rc_path)}

    # Remove the block and any surrounding blank lines
    before = content[: span[0]].rstrip("\n")
    after = content[span[1] :].lstrip("\n")

    if before and after:
        new_content = before + "\n\n" + after
    elif before:
        new_content = before + "\n"
    elif after:
        new_content = after
    else:
        new_content = ""

    rc_path.write_text(new_content, encoding="utf-8")

    return {"removed": True, "rc_path": str(rc_path)}

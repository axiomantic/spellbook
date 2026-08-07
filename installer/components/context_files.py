"""
Context file generation for spellbook installation.
"""

import sys
from pathlib import Path

# Add parent directories to path for imports
_installer_dir = Path(__file__).parent.parent
_spellbook_dir = _installer_dir.parent

if str(_spellbook_dir) not in sys.path:
    sys.path.insert(0, str(_spellbook_dir))


from installer.config import get_spellbook_config_dir  # noqa: E402


def ensure_machine_config_file(spellbook_dir: Path, dry_run: bool = False) -> Path:
    """Ensure ~/.config/spellbook/paths.md exists with machine-specific path definitions."""
    machine_config_dir = Path.home() / ".config" / "spellbook"
    paths_file = machine_config_dir / "paths.md"
    config_dir = get_spellbook_config_dir()

    content = (
        "# Spellbook Machine Configuration\n"
        f"SPELLBOOK_DIR={spellbook_dir.resolve()}\n"
        f"SPELLBOOK_CONFIG_DIR={config_dir.resolve()}\n"
    )

    if not dry_run:
        machine_config_dir.mkdir(parents=True, exist_ok=True)
        paths_file.write_text(content, encoding="utf-8")

    return paths_file


def generate_spellbook_config_section(spellbook_dir: Path) -> str:
    """
    Generate the Spellbook Configuration section with path definitions.

    This section defines variables that are referenced in symlinked skill/command files.
    The AI should substitute these values when interpreting paths.
    """
    config_dir = get_spellbook_config_dir()

    lines = [
        "## Spellbook Configuration",
        "",
        "The following variables are defined for this spellbook installation.",
        "When reading spellbook skills, commands, and documentation, **substitute these values**",
        "for any `$VARIABLE` or `${VARIABLE}` references:",
        "",
        "```",
        f"SPELLBOOK_DIR={spellbook_dir}",
        f"SPELLBOOK_CONFIG_DIR={config_dir}",
        "```",
        "",
        "**CRITICAL:** Treat these as environment variables when interpreting paths in spellbook files.",
        "For example, `$SPELLBOOK_DIR/tests/example.py` means `" + str(spellbook_dir) + "/tests/example.py`.",
        "",
        "---",
        "",
    ]
    return "\n".join(lines)


# The per-platform context generators that once lived here
# (get_spellbook_context_content, generate_codex_context,
# generate_claude_context) are gone. They read a single monolithic template
# that no longer exists; rule content is now assembled per platform by
# installer/components/rule_bundle.py from the rules/ module sources.

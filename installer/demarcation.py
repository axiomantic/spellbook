"""
Demarcated section manipulation for context files.

Handles parsing, writing, updating, and removing demarcated sections
in files like CLAUDE.md, GEMINI.md, and AGENTS.md.

Format:
    {user content}

    <!-- SPELLBOOK:START version=X.X.X -->
    {spellbook content}
    <!-- SPELLBOOK:END -->
"""

import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

# Marker patterns
MARKER_START_PATTERN = re.compile(
    r"^<!-- SPELLBOOK:START version=([0-9]+\.[0-9]+\.[0-9]+) -->$", re.MULTILINE
)
MARKER_END = "<!-- SPELLBOOK:END -->"


@dataclass
class DemarcatedFile:
    """Represents a file with potential demarcated section."""

    path: Path
    user_content: str  # Content before demarcated section
    spellbook_content: str  # Content within markers (empty if none)
    spellbook_version: Optional[str]  # Version from marker (None if no section)
    trailing_content: str  # Content after demarcated section (should be empty)


def parse_demarcated_file(path: Path) -> DemarcatedFile:
    """
    Parse a file to extract user content and demarcated section.

    Returns DemarcatedFile with:
    - user_content: Everything before the SPELLBOOK:START marker
    - spellbook_content: Content between markers (excluding markers)
    - spellbook_version: Version from START marker, or None
    - trailing_content: Anything after END marker (should be empty)
    """
    if not path.exists():
        return DemarcatedFile(
            path=path,
            user_content="",
            spellbook_content="",
            spellbook_version=None,
            trailing_content="",
        )

    content = path.read_text(encoding="utf-8")

    # Find start marker
    start_match = MARKER_START_PATTERN.search(content)
    if not start_match:
        # No demarcated section - entire file is user content
        return DemarcatedFile(
            path=path,
            user_content=content,
            spellbook_content="",
            spellbook_version=None,
            trailing_content="",
        )

    # Extract version and positions
    version = start_match.group(1)
    start_pos = start_match.start()
    marker_end_pos = start_match.end()

    # Find end marker
    end_pos = content.find(MARKER_END, marker_end_pos)
    if end_pos == -1:
        raise ValueError(f"Malformed demarcated section: START without END in {path}")

    user_content = content[:start_pos].rstrip()
    spellbook_content = content[marker_end_pos:end_pos].strip()
    trailing_content = content[end_pos + len(MARKER_END) :].strip()

    return DemarcatedFile(
        path=path,
        user_content=user_content,
        spellbook_content=spellbook_content,
        spellbook_version=version,
        trailing_content=trailing_content,
    )


def write_demarcated_file(
    path: Path,
    user_content: str,
    spellbook_content: str,
    version: str,
    backup: bool = True,
) -> Optional[Path]:
    """
    Write file with demarcated section at END.

    Format:
    {user_content}

    <!-- SPELLBOOK:START version=X.X.X -->
    {spellbook_content}
    <!-- SPELLBOOK:END -->

    Returns backup path if backup was created, None otherwise.
    """
    backup_path = None

    if backup and path.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = path.parent / f"{path.name}.backup.{timestamp}"
        shutil.copy2(path, backup_path)

    # CRITICAL: If path is a symlink, remove it first.
    # Otherwise we'd write through the symlink to the source file!
    if path.is_symlink():
        path.unlink()

    # Build content
    start_marker = f"<!-- SPELLBOOK:START version={version} -->"

    parts = []
    if user_content.strip():
        parts.append(user_content.rstrip())
        parts.append("")  # Blank line separator

    parts.append(start_marker)
    parts.append(spellbook_content)
    parts.append(MARKER_END)

    final_content = "\n".join(parts) + "\n"

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(final_content, encoding="utf-8")

    return backup_path


def update_demarcated_section(
    path: Path, new_content: str, version: str
) -> Tuple[str, Optional[Path]]:
    """
    Update only the demarcated section, preserving user content.

    Returns: (action, backup_path)
    - action: "created", "upgraded", "unchanged"
    - backup_path: Path to backup file if created
    """
    parsed = parse_demarcated_file(path)

    # Check if content changed
    if parsed.spellbook_content == new_content and parsed.spellbook_version == version:
        return ("unchanged", None)

    action = "upgraded" if parsed.spellbook_version else "created"

    # Preserve any trailing content by appending to user content
    user_content = parsed.user_content
    if parsed.trailing_content:
        if user_content:
            user_content = user_content + "\n\n" + parsed.trailing_content
        else:
            user_content = parsed.trailing_content

    # Special case: if this is a fresh install (no existing markers) and the
    # existing content is essentially the same as what we're about to install,
    # don't duplicate it. This handles the case where the file was previously
    # a symlink to spellbook's CLAUDE.md.
    if action == "created" and user_content.strip():
        # Normalize for comparison (strip whitespace, normalize line endings)
        normalized_user = user_content.strip().replace("\r\n", "\n")
        normalized_new = new_content.strip().replace("\r\n", "\n")

        # If existing content is a substring of new content or vice versa,
        # or they're very similar (>90% overlap), skip user content
        if normalized_user == normalized_new:
            user_content = ""
        elif normalized_new.startswith(normalized_user[:500]) and len(normalized_user) > 100:
            # User content looks like the start of spellbook content
            user_content = ""
        elif normalized_user.startswith(normalized_new[:500]) and len(normalized_new) > 100:
            # Spellbook content looks like the start of user content
            user_content = ""

    backup_path = write_demarcated_file(
        path=path,
        user_content=user_content,
        spellbook_content=new_content,
        version=version,
        backup=(action == "upgraded"),  # Only backup on upgrade
    )

    return (action, backup_path)


def remove_demarcated_section(path: Path) -> Tuple[str, Optional[Path]]:
    """
    Remove the demarcated section, preserving user content.

    Returns: (action, backup_path)
    - action: "removed", "unchanged" (if no section existed), "deleted" (empty file removed)
    """
    if not path.exists():
        return ("unchanged", None)

    parsed = parse_demarcated_file(path)

    if not parsed.spellbook_version:
        return ("unchanged", None)

    # Create backup
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = path.parent / f"{path.name}.backup.{timestamp}"
    shutil.copy2(path, backup_path)

    # Combine user content and trailing content
    final_content = parsed.user_content
    if parsed.trailing_content:
        if final_content:
            final_content = final_content + "\n\n" + parsed.trailing_content
        else:
            final_content = parsed.trailing_content

    # Write just user content or delete empty file
    if final_content.strip():
        path.write_text(final_content.rstrip() + "\n", encoding="utf-8")
        return ("removed", backup_path)
    else:
        path.unlink()
        return ("deleted", backup_path)


def get_installed_version(path: Path) -> Optional[str]:
    """Extract version from demarcated section if present."""
    if not path.exists():
        return None
    parsed = parse_demarcated_file(path)
    return parsed.spellbook_version


def has_demarcated_section(path: Path) -> bool:
    """Check if file has a demarcated section."""
    if not path.exists():
        return False
    parsed = parse_demarcated_file(path)
    return parsed.spellbook_version is not None

"""
Version tracking and synchronization for spellbook.
"""

import json
import re
from pathlib import Path
from typing import List, Optional, Tuple

from .demarcation import get_installed_version


def read_version(version_file: Path) -> str:
    """Read version from .version file."""
    if not version_file.exists():
        raise FileNotFoundError(f"Version file not found: {version_file}")
    return version_file.read_text(encoding="utf-8").strip()


def check_upgrade_needed(
    installed_version: Optional[str], current_version: str, force: bool = False
) -> Tuple[bool, str]:
    """
    Determine if upgrade is needed.

    Returns: (needs_upgrade, reason)
    """
    if force:
        return (True, "forced reinstall")

    if installed_version is None:
        return (True, "fresh install")

    if installed_version == current_version:
        return (False, "version unchanged")

    # Parse versions for comparison
    try:
        installed_parts = [int(x) for x in installed_version.split(".")]
        current_parts = [int(x) for x in current_version.split(".")]

        # Pad to same length
        max_len = max(len(installed_parts), len(current_parts))
        installed_parts.extend([0] * (max_len - len(installed_parts)))
        current_parts.extend([0] * (max_len - len(current_parts)))

        if current_parts > installed_parts:
            return (True, f"upgrade from {installed_version}")
        elif current_parts < installed_parts:
            return (True, f"downgrade from {installed_version}")
        else:
            return (False, "version unchanged")
    except ValueError:
        # Fallback to string comparison
        if installed_version != current_version:
            return (True, f"version changed from {installed_version}")
        return (False, "version unchanged")


def sync_version_to_files(spellbook_dir: Path, version: str) -> List[str]:
    """
    Synchronize version across all files that contain it.
    Returns list of updated files.
    """
    updated = []

    # 1. gemini-extension.json
    gemini_ext = spellbook_dir / "extensions" / "gemini" / "gemini-extension.json"
    if gemini_ext.exists():
        try:
            data = json.loads(gemini_ext.read_text(encoding="utf-8"))
            if data.get("version") != version:
                data["version"] = version
                gemini_ext.write_text(
                    json.dumps(data, indent=2) + "\n", encoding="utf-8"
                )
                updated.append(str(gemini_ext))
        except (json.JSONDecodeError, OSError):
            pass

    return updated


def validate_version_consistency(spellbook_dir: Path) -> List[str]:
    """
    Check that all version references are consistent.
    Returns list of inconsistencies.
    """
    issues = []
    version = read_version(spellbook_dir / ".version")

    # Check gemini-extension.json
    gemini_ext = spellbook_dir / "extensions" / "gemini" / "gemini-extension.json"
    if gemini_ext.exists():
        try:
            data = json.loads(gemini_ext.read_text(encoding="utf-8"))
            if data.get("version") != version:
                issues.append(
                    f"gemini-extension.json has {data.get('version')}, expected {version}"
                )
        except (json.JSONDecodeError, OSError):
            issues.append("gemini-extension.json could not be read")

    return issues


def get_changelog_versions(changelog_path: Path) -> List[str]:
    """Extract all version numbers from CHANGELOG.md."""
    if not changelog_path.exists():
        return []
    content = changelog_path.read_text(encoding="utf-8")
    # Match [X.X.X] headers
    return re.findall(r"\[(\d+\.\d+\.\d+)\]", content)


def get_changelog_between_versions(
    changelog_path: Path,
    from_version: Optional[str],
    to_version: Optional[str] = None,
) -> str:
    """Extract changelog entries between two versions.

    Returns the raw markdown text of changelog sections that fall between
    from_version (exclusive) and to_version (inclusive). If from_version
    is None, returns everything up to and including to_version (or all
    [Unreleased] content). If to_version is None, includes [Unreleased].

    Args:
        changelog_path: Path to CHANGELOG.md.
        from_version: The old/installed version (exclusive). None for fresh install.
        to_version: The new version (inclusive). None to include [Unreleased].

    Returns:
        Extracted changelog text, or empty string if nothing found.
    """
    if not changelog_path.exists():
        return ""

    content = changelog_path.read_text(encoding="utf-8")
    lines = content.splitlines()

    # Parse into sections: each section starts with ## [version] or ## [Unreleased]
    sections: List[Tuple[Optional[str], str]] = []  # (version_or_none, text)
    current_version: Optional[str] = None
    current_lines: List[str] = []
    in_section = False  # Don't capture text before the first ## header
    header_pattern = re.compile(r"^## \[([^\]]+)\]")

    for line in lines:
        match = header_pattern.match(line)
        if match:
            # Save previous section
            if in_section and current_lines:
                sections.append((current_version, "\n".join(current_lines)))
            tag = match.group(1)
            current_version = None if tag.lower() == "unreleased" else tag
            current_lines = []
            in_section = True
        elif in_section:
            current_lines.append(line)

    # Save last section
    if in_section and current_lines:
        sections.append((current_version, "\n".join(current_lines)))

    # Filter sections between from_version (exclusive) and to_version (inclusive)
    result_parts: List[str] = []
    for ver, text in sections:
        text = text.strip()
        if not text:
            continue

        # Skip the from_version section itself and anything older
        if from_version and ver is not None:
            try:
                ver_parts = [int(x) for x in ver.split(".")]
                from_parts = [int(x) for x in from_version.split(".")]
                max_len = max(len(ver_parts), len(from_parts))
                ver_parts.extend([0] * (max_len - len(ver_parts)))
                from_parts.extend([0] * (max_len - len(from_parts)))
                if ver_parts <= from_parts:
                    continue
            except ValueError:
                if ver <= from_version:
                    continue

        # Include [Unreleased] only if to_version is None
        if ver is None and to_version is not None:
            continue

        # Skip versions newer than to_version
        if to_version and ver is not None:
            try:
                ver_parts = [int(x) for x in ver.split(".")]
                to_parts = [int(x) for x in to_version.split(".")]
                max_len = max(len(ver_parts), len(to_parts))
                ver_parts.extend([0] * (max_len - len(ver_parts)))
                to_parts.extend([0] * (max_len - len(to_parts)))
                if ver_parts > to_parts:
                    continue
            except ValueError:
                pass

        result_parts.append(text)

    return "\n\n".join(result_parts)

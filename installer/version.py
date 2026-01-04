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

    # 2. spellbook-codex (JS file with VERSION constant)
    codex_cli = spellbook_dir / ".codex" / "spellbook-codex"
    if codex_cli.exists():
        try:
            content = codex_cli.read_text(encoding="utf-8")
            pattern = r"const VERSION = '[^']+'"
            replacement = f"const VERSION = '{version}'"
            new_content = re.sub(pattern, replacement, content)
            if new_content != content:
                codex_cli.write_text(new_content, encoding="utf-8")
                updated.append(str(codex_cli))
        except OSError:
            pass

    # 3. installer/__init__.py
    installer_init = spellbook_dir / "installer" / "__init__.py"
    if installer_init.exists():
        try:
            content = installer_init.read_text(encoding="utf-8")
            pattern = r'__version__ = "[^"]+"'
            replacement = f'__version__ = "{version}"'
            new_content = re.sub(pattern, replacement, content)
            if new_content != content:
                installer_init.write_text(new_content, encoding="utf-8")
                updated.append(str(installer_init))
        except OSError:
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

    # Check spellbook-codex
    codex_cli = spellbook_dir / ".codex" / "spellbook-codex"
    if codex_cli.exists():
        try:
            content = codex_cli.read_text(encoding="utf-8")
            match = re.search(r"const VERSION = '([^']+)'", content)
            if match and match.group(1) != version:
                issues.append(
                    f"spellbook-codex has {match.group(1)}, expected {version}"
                )
        except OSError:
            issues.append("spellbook-codex could not be read")

    return issues


def get_changelog_versions(changelog_path: Path) -> List[str]:
    """Extract all version numbers from CHANGELOG.md."""
    if not changelog_path.exists():
        return []
    content = changelog_path.read_text(encoding="utf-8")
    # Match [X.X.X] headers
    return re.findall(r"\[(\d+\.\d+\.\d+)\]", content)

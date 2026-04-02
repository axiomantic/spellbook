"""Session profile discovery and loading.

Profiles are read-only .md files with minimal frontmatter (name, description)
that provide behavioral instructions for AI sessions. They are discovered from
two directories:

- Bundled: ``profiles/`` relative to the spellbook repo root
- Custom: ``profiles/`` relative to ``~/.local/spellbook/``

Custom profiles with the same filename (slug) as bundled ones take precedence.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from spellbook.core.compat import get_config_dir
from spellbook.core.config import get_spellbook_dir

logger = logging.getLogger(__name__)


@dataclass
class ProfileInfo:
    """Metadata about a discovered profile."""

    slug: str
    name: str
    description: str
    path: Path
    is_custom: bool


def parse_profile_frontmatter(content: str) -> tuple[dict[str, str], str]:
    """Parse minimal frontmatter from profile content.

    Splits on ``---`` markers to extract ``key: value`` metadata lines.
    No YAML library required; only flat string fields are supported.

    Args:
        content: Raw file content.

    Returns:
        Tuple of (metadata_dict, body_content). If no valid frontmatter
        found, returns ({}, full_content).
    """
    if not content.startswith("---"):
        return {}, content
    parts = content.split("---", 2)  # ['', frontmatter, body]
    if len(parts) < 3:
        return {}, content
    meta: dict[str, str] = {}
    for line in parts[1].strip().splitlines():
        if ": " in line:
            key, value = line.split(": ", 1)
            meta[key.strip()] = value.strip()
    return meta, parts[2].strip()


BUNDLED_PROFILES_SUBDIR = "profiles"
CUSTOM_PROFILES_SUBDIR = "profiles"


def _scan_profile_dir(directory: Path, is_custom: bool) -> dict[str, ProfileInfo]:
    """Scan a directory for .md profile files and return a slug -> ProfileInfo map.

    Args:
        directory: Directory to scan for ``*.md`` files.
        is_custom: Whether this is a custom (user) profile directory.

    Returns:
        Dict mapping slug to ProfileInfo. Slug is the filename without ``.md``.
    """
    profiles: dict[str, ProfileInfo] = {}
    if not directory.is_dir():
        return profiles
    for path in sorted(directory.glob("*.md")):
        slug = path.stem
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            logger.warning("Failed to read profile file: %s", path)
            continue
        meta, _body = parse_profile_frontmatter(content)
        profiles[slug] = ProfileInfo(
            slug=slug,
            name=meta.get("name", slug),
            description=meta.get("description", ""),
            path=path,
            is_custom=is_custom,
        )
    return profiles


def discover_profiles() -> list[ProfileInfo]:
    """Find all available profiles from bundled and custom directories.

    Custom profiles with the same slug as bundled ones take precedence.

    Returns:
        List of ProfileInfo sorted by name. Does not include a synthetic
        "None" entry; that is handled by the wizard UI.
    """
    bundled_dir = get_spellbook_dir() / BUNDLED_PROFILES_SUBDIR
    custom_dir = get_config_dir() / CUSTOM_PROFILES_SUBDIR

    # Bundled first, then custom overrides
    profiles = _scan_profile_dir(bundled_dir, is_custom=False)
    profiles.update(_scan_profile_dir(custom_dir, is_custom=True))

    return sorted(profiles.values(), key=lambda p: p.name)


def load_profile(slug: str) -> Optional[str]:
    """Load profile body content by slug (filename without .md extension).

    Resolution order: custom directory first, then bundled directory.

    Args:
        slug: Profile identifier (e.g. ``"radical-collaborator"``).

    Returns:
        Profile body content (without frontmatter), or ``None`` if not
        found or empty.
    """
    custom_dir = get_config_dir() / CUSTOM_PROFILES_SUBDIR
    bundled_dir = get_spellbook_dir() / BUNDLED_PROFILES_SUBDIR

    for directory in [custom_dir, bundled_dir]:
        path = directory / f"{slug}.md"
        if path.is_file():
            try:
                content = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                logger.warning("Failed to read profile '%s' at %s", slug, path)
                continue
            _meta, body = parse_profile_frontmatter(content)
            return body if body else None

    return None

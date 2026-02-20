"""Tests for demarcation system: user content preservation during upgrades.

Verifies that the demarcation system (SPELLBOOK:START/END markers) correctly
preserves user content above and below managed sections when installing,
upgrading, or handling edge cases like corrupt markers and empty files.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from installer.demarcation import (
    parse_demarcated_file,
    update_demarcated_section,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SAMPLE_USER_CONTENT_ABOVE = """\
# My Custom Config

## Project-Specific Rules

### Git Conventions
- Use conventional commits
- Always rebase before merge"""

SAMPLE_USER_CONTENT_BELOW = """\
## My Personal Notes

These are notes I added after the spellbook section.
Do not touch these during upgrades."""

OLD_SPELLBOOK_CONTENT = """\
## Spellbook Configuration

Old spellbook content from version 0.9.0."""

NEW_SPELLBOOK_CONTENT = """\
## Spellbook Configuration

New spellbook content from version 0.10.0.

### New Feature
This section was added in the upgrade."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_demarcated_file(
    path: Path,
    user_content: str = "",
    spellbook_content: str = "",
    version: str = "0.9.0",
    trailing_content: str = "",
) -> None:
    """Create a file with user content, a demarcated spellbook section, and optional trailing content."""
    parts: list[str] = []
    if user_content.strip():
        parts.append(user_content.rstrip())
        parts.append("")  # blank line separator

    parts.append(f"<!-- SPELLBOOK:START version={version} -->")
    parts.append(spellbook_content)
    parts.append("<!-- SPELLBOOK:END -->")

    if trailing_content.strip():
        parts.append("")  # blank line separator
        parts.append(trailing_content.rstrip())

    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestUserContentAbovePreserved:
    """Verify that custom content placed before the SPELLBOOK markers survives updates."""

    def test_user_content_above_preserved_on_upgrade(self, tmp_path: Path) -> None:
        """User content above SPELLBOOK:START markers is unchanged after an upgrade."""
        path = tmp_path / "CLAUDE.md"
        _make_demarcated_file(
            path,
            user_content=SAMPLE_USER_CONTENT_ABOVE,
            spellbook_content=OLD_SPELLBOOK_CONTENT,
            version="0.9.0",
        )

        action, _backup = update_demarcated_section(
            path, NEW_SPELLBOOK_CONTENT, version="0.10.0"
        )

        assert action == "upgraded", f"Expected 'upgraded', got '{action}'"

        content = path.read_text(encoding="utf-8")
        assert "My Custom Config" in content, "User heading was lost"
        assert "Project-Specific Rules" in content, "User section was lost"
        assert "conventional commits" in content, "User detail was lost"
        assert "Always rebase before merge" in content, "User detail was lost"

    def test_user_content_above_not_duplicated(self, tmp_path: Path) -> None:
        """User content above markers appears exactly once after upgrade."""
        path = tmp_path / "CLAUDE.md"
        _make_demarcated_file(
            path,
            user_content=SAMPLE_USER_CONTENT_ABOVE,
            spellbook_content=OLD_SPELLBOOK_CONTENT,
            version="0.9.0",
        )

        update_demarcated_section(path, NEW_SPELLBOOK_CONTENT, version="0.10.0")

        content = path.read_text(encoding="utf-8")
        assert content.count("My Custom Config") == 1, (
            "User content was duplicated during upgrade"
        )


class TestUserContentBelowPreserved:
    """Verify that custom content placed after the SPELLBOOK markers survives updates."""

    def test_user_content_below_preserved_on_upgrade(self, tmp_path: Path) -> None:
        """User content below SPELLBOOK:END markers is preserved after an upgrade.

        The demarcation system captures trailing content and folds it into the
        user-content section above the markers on upgrade.
        """
        path = tmp_path / "CLAUDE.md"
        _make_demarcated_file(
            path,
            user_content=SAMPLE_USER_CONTENT_ABOVE,
            spellbook_content=OLD_SPELLBOOK_CONTENT,
            version="0.9.0",
            trailing_content=SAMPLE_USER_CONTENT_BELOW,
        )

        action, _backup = update_demarcated_section(
            path, NEW_SPELLBOOK_CONTENT, version="0.10.0"
        )

        assert action == "upgraded", f"Expected 'upgraded', got '{action}'"

        content = path.read_text(encoding="utf-8")
        assert "My Personal Notes" in content, "Trailing user content was lost"
        assert "Do not touch these during upgrades" in content, (
            "Trailing user detail was lost"
        )

    def test_trailing_content_merged_above_markers(self, tmp_path: Path) -> None:
        """After upgrade, trailing content is relocated above SPELLBOOK:START.

        The demarcation system merges trailing content into user_content to keep
        all user material above the managed section.
        """
        path = tmp_path / "CLAUDE.md"
        _make_demarcated_file(
            path,
            user_content="",
            spellbook_content=OLD_SPELLBOOK_CONTENT,
            version="0.9.0",
            trailing_content=SAMPLE_USER_CONTENT_BELOW,
        )

        update_demarcated_section(path, NEW_SPELLBOOK_CONTENT, version="0.10.0")

        content = path.read_text(encoding="utf-8")
        start_marker_pos = content.find("<!-- SPELLBOOK:START")
        trailing_pos = content.find("My Personal Notes")

        assert trailing_pos != -1, "Trailing content was lost entirely"
        assert start_marker_pos != -1, "SPELLBOOK:START marker missing"
        assert trailing_pos < start_marker_pos, (
            "Trailing content should be relocated above SPELLBOOK:START marker"
        )


class TestManagedSectionUpdated:
    """Verify that the managed section is correctly replaced during upgrades."""

    def test_version_marker_updated(self, tmp_path: Path) -> None:
        """The version in the SPELLBOOK:START marker is updated on upgrade."""
        path = tmp_path / "CLAUDE.md"
        _make_demarcated_file(
            path,
            user_content=SAMPLE_USER_CONTENT_ABOVE,
            spellbook_content=OLD_SPELLBOOK_CONTENT,
            version="0.9.0",
        )

        update_demarcated_section(path, NEW_SPELLBOOK_CONTENT, version="0.10.0")

        content = path.read_text(encoding="utf-8")
        assert "version=0.10.0" in content, "Version marker was not updated"
        assert "version=0.9.0" not in content, "Old version marker still present"

    def test_managed_content_replaced(self, tmp_path: Path) -> None:
        """Old spellbook content is replaced with new content on upgrade."""
        path = tmp_path / "CLAUDE.md"
        _make_demarcated_file(
            path,
            user_content=SAMPLE_USER_CONTENT_ABOVE,
            spellbook_content=OLD_SPELLBOOK_CONTENT,
            version="0.9.0",
        )

        update_demarcated_section(path, NEW_SPELLBOOK_CONTENT, version="0.10.0")

        content = path.read_text(encoding="utf-8")
        assert "Old spellbook content from version 0.9.0" not in content, (
            "Old managed content was not removed"
        )
        assert "New spellbook content from version 0.10.0" in content, (
            "New managed content was not inserted"
        )
        assert "New Feature" in content, (
            "New section added in upgrade is missing"
        )

    def test_unchanged_content_returns_unchanged(self, tmp_path: Path) -> None:
        """When content and version are identical, action is 'unchanged'."""
        path = tmp_path / "CLAUDE.md"
        _make_demarcated_file(
            path,
            user_content=SAMPLE_USER_CONTENT_ABOVE,
            spellbook_content=OLD_SPELLBOOK_CONTENT,
            version="0.9.0",
        )

        action, backup = update_demarcated_section(
            path, OLD_SPELLBOOK_CONTENT, version="0.9.0"
        )

        assert action == "unchanged", f"Expected 'unchanged', got '{action}'"
        assert backup is None, "No backup should be created for unchanged content"


class TestFirstInstallNoExisting:
    """Verify behavior when installing into a directory with no existing file."""

    def test_file_created_with_markers(self, tmp_path: Path) -> None:
        """A new file is created with full managed section including markers."""
        path = tmp_path / "CLAUDE.md"
        assert not path.exists(), "Precondition: file should not exist"

        action, backup = update_demarcated_section(
            path, NEW_SPELLBOOK_CONTENT, version="0.10.0"
        )

        assert action == "created", f"Expected 'created', got '{action}'"
        assert backup is None, "No backup for fresh install"
        assert path.exists(), "File should be created"

    def test_created_file_has_start_marker(self, tmp_path: Path) -> None:
        """Created file includes SPELLBOOK:START with correct version."""
        path = tmp_path / "CLAUDE.md"
        update_demarcated_section(path, NEW_SPELLBOOK_CONTENT, version="0.10.0")

        content = path.read_text(encoding="utf-8")
        assert "<!-- SPELLBOOK:START version=0.10.0 -->" in content, (
            "START marker with version is missing"
        )

    def test_created_file_has_end_marker(self, tmp_path: Path) -> None:
        """Created file includes SPELLBOOK:END marker."""
        path = tmp_path / "CLAUDE.md"
        update_demarcated_section(path, NEW_SPELLBOOK_CONTENT, version="0.10.0")

        content = path.read_text(encoding="utf-8")
        assert "<!-- SPELLBOOK:END -->" in content, "END marker is missing"

    def test_created_file_has_managed_content(self, tmp_path: Path) -> None:
        """Created file includes the spellbook content between markers."""
        path = tmp_path / "CLAUDE.md"
        update_demarcated_section(path, NEW_SPELLBOOK_CONTENT, version="0.10.0")

        parsed = parse_demarcated_file(path)
        assert parsed.spellbook_content == NEW_SPELLBOOK_CONTENT, (
            "Managed content does not match what was written"
        )
        assert parsed.spellbook_version == "0.10.0", (
            "Parsed version does not match"
        )

    def test_created_file_roundtrips_through_parse(self, tmp_path: Path) -> None:
        """A freshly created file can be parsed and re-updated without data loss."""
        path = tmp_path / "CLAUDE.md"
        update_demarcated_section(path, NEW_SPELLBOOK_CONTENT, version="0.10.0")

        # Re-parse and verify
        parsed = parse_demarcated_file(path)
        assert parsed.user_content == "", "Fresh install should have no user content"
        assert parsed.spellbook_version == "0.10.0"

        # Update again with newer version
        action, _backup = update_demarcated_section(
            path, "Updated content.", version="0.11.0"
        )
        assert action == "upgraded"

        re_parsed = parse_demarcated_file(path)
        assert re_parsed.spellbook_content == "Updated content."
        assert re_parsed.spellbook_version == "0.11.0"


class TestCorruptMarkersHandled:
    """Verify graceful handling of malformed marker scenarios."""

    def test_start_without_end_raises(self, tmp_path: Path) -> None:
        """A START marker without a matching END raises ValueError.

        This is the expected behavior per parse_demarcated_file: malformed
        files with START but no END are treated as errors rather than silently
        losing content.
        """
        path = tmp_path / "CLAUDE.md"
        path.write_text(
            "# User content\n\n"
            "<!-- SPELLBOOK:START version=0.9.0 -->\n"
            "Some spellbook content\n"
            "# No END marker here\n",
            encoding="utf-8",
        )

        with pytest.raises(ValueError, match="START without END"):
            update_demarcated_section(path, NEW_SPELLBOOK_CONTENT, version="0.10.0")

    def test_end_without_start_treated_as_user_content(self, tmp_path: Path) -> None:
        """An END marker without a preceding START is treated as plain user content."""
        path = tmp_path / "CLAUDE.md"
        path.write_text(
            "# User content\n\n"
            "<!-- SPELLBOOK:END -->\n"
            "More user content\n",
            encoding="utf-8",
        )

        action, _backup = update_demarcated_section(
            path, NEW_SPELLBOOK_CONTENT, version="0.10.0"
        )

        assert action == "created", (
            "File with only END marker should be treated as having no managed section"
        )
        content = path.read_text(encoding="utf-8")
        assert "<!-- SPELLBOOK:START version=0.10.0 -->" in content

    def test_garbled_version_in_marker_treated_as_no_section(
        self, tmp_path: Path
    ) -> None:
        """A START marker with a garbled version string is not recognized as a marker."""
        path = tmp_path / "CLAUDE.md"
        path.write_text(
            "# User content\n\n"
            "<!-- SPELLBOOK:START version=GARBLED -->\n"
            "Some content\n"
            "<!-- SPELLBOOK:END -->\n",
            encoding="utf-8",
        )

        action, _backup = update_demarcated_section(
            path, NEW_SPELLBOOK_CONTENT, version="0.10.0"
        )

        # The garbled marker is not recognized by the regex, so the entire
        # file is treated as user content (no existing managed section).
        assert action == "created", (
            "Garbled version marker should not be recognized as a managed section"
        )

    def test_duplicate_sections_first_pair_used(self, tmp_path: Path) -> None:
        """When two START/END pairs exist, the first pair is recognized as the managed section.

        The parser matches the first START marker to the first END marker.
        Content after that first END (including any second START/END pair) is
        treated as trailing content and folded into user content on upgrade.
        """
        path = tmp_path / "CLAUDE.md"
        path.write_text(
            "# User content\n\n"
            "<!-- SPELLBOOK:START version=0.9.0 -->\n"
            "First section\n"
            "<!-- SPELLBOOK:END -->\n"
            "\n"
            "<!-- SPELLBOOK:START version=0.8.0 -->\n"
            "Second section\n"
            "<!-- SPELLBOOK:END -->\n",
            encoding="utf-8",
        )

        action, _backup = update_demarcated_section(
            path, NEW_SPELLBOOK_CONTENT, version="0.10.0"
        )

        assert action == "upgraded"
        content = path.read_text(encoding="utf-8")
        # The second pair's markers are preserved as trailing/user content
        assert "version=0.10.0" in content, "New version marker should be present"
        assert "User content" in content, "Original user content should be preserved"
        assert NEW_SPELLBOOK_CONTENT.splitlines()[0] in content, (
            "New managed content should be present"
        )


class TestEmptyExistingFile:
    """Verify behavior when updating into an existing empty file."""

    def test_empty_file_gets_managed_section(self, tmp_path: Path) -> None:
        """An empty file receives the full managed section with markers."""
        path = tmp_path / "CLAUDE.md"
        path.write_text("", encoding="utf-8")
        assert path.exists(), "Precondition: file should exist"

        action, _backup = update_demarcated_section(
            path, NEW_SPELLBOOK_CONTENT, version="0.10.0"
        )

        assert action == "created", f"Expected 'created', got '{action}'"

        content = path.read_text(encoding="utf-8")
        assert "<!-- SPELLBOOK:START version=0.10.0 -->" in content, (
            "START marker is missing from empty file"
        )
        assert "<!-- SPELLBOOK:END -->" in content, (
            "END marker is missing from empty file"
        )
        assert "New spellbook content from version 0.10.0" in content, (
            "Managed content is missing from empty file"
        )

    def test_empty_file_has_no_user_content_prefix(self, tmp_path: Path) -> None:
        """An empty file should not have spurious content before the START marker."""
        path = tmp_path / "CLAUDE.md"
        path.write_text("", encoding="utf-8")

        update_demarcated_section(path, NEW_SPELLBOOK_CONTENT, version="0.10.0")

        parsed = parse_demarcated_file(path)
        assert parsed.user_content == "", (
            "Empty file should produce no user content prefix"
        )
        assert parsed.spellbook_version == "0.10.0"

    def test_whitespace_only_file_treated_as_empty(self, tmp_path: Path) -> None:
        """A file containing only whitespace is treated as having no user content."""
        path = tmp_path / "CLAUDE.md"
        path.write_text("   \n\n  \n", encoding="utf-8")

        action, _backup = update_demarcated_section(
            path, NEW_SPELLBOOK_CONTENT, version="0.10.0"
        )

        assert action == "created", f"Expected 'created', got '{action}'"

        parsed = parse_demarcated_file(path)
        assert parsed.spellbook_version == "0.10.0"
        assert parsed.spellbook_content == NEW_SPELLBOOK_CONTENT

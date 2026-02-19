"""Tests for installer.demarcation.remove_demarcated_section()."""

import pytest
from pathlib import Path


SAMPLE_SPELLBOOK_CONTENT = """\
## Spellbook Configuration

Some spellbook content here.
"""

SAMPLE_USER_CONTENT = """\
# My Custom Config

This is my personal content.
"""


def _make_demarcated_file(path: Path, user_content: str = "", spellbook_content: str = "", version: str = "0.9.0"):
    """Helper to create a file with a demarcated spellbook section."""
    parts = []
    if user_content.strip():
        parts.append(user_content.rstrip())
        parts.append("")  # blank line separator

    parts.append(f"<!-- SPELLBOOK:START version={version} -->")
    parts.append(spellbook_content)
    parts.append("<!-- SPELLBOOK:END -->")

    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


class TestRemoveDemarcatedSection:
    """Tests for remove_demarcated_section()."""

    def test_no_file_returns_no_file(self, tmp_path):
        """When the file doesn't exist, return 'no_file'."""
        from installer.demarcation import remove_demarcated_section

        path = tmp_path / "nonexistent.md"
        action, backup_path = remove_demarcated_section(path)
        assert action == "no_file"
        assert backup_path is None

    def test_file_without_section_returns_not_found(self, tmp_path):
        """When file exists but has no spellbook section, return 'not_found'."""
        from installer.demarcation import remove_demarcated_section

        path = tmp_path / "CLAUDE.md"
        path.write_text("# Just user content\n\nNo spellbook here.\n", encoding="utf-8")

        action, backup_path = remove_demarcated_section(path)
        assert action == "not_found"
        assert backup_path is None

    def test_file_with_section_returns_removed(self, tmp_path):
        """When file has a spellbook section, remove it and return 'removed'."""
        from installer.demarcation import remove_demarcated_section

        path = tmp_path / "CLAUDE.md"
        _make_demarcated_file(path, user_content=SAMPLE_USER_CONTENT, spellbook_content=SAMPLE_SPELLBOOK_CONTENT)

        action, backup_path = remove_demarcated_section(path)
        assert action == "removed"
        assert backup_path is not None

    def test_removal_preserves_user_content(self, tmp_path):
        """After removal, only user content remains in the file."""
        from installer.demarcation import remove_demarcated_section

        path = tmp_path / "CLAUDE.md"
        _make_demarcated_file(path, user_content=SAMPLE_USER_CONTENT, spellbook_content=SAMPLE_SPELLBOOK_CONTENT)

        remove_demarcated_section(path)

        content = path.read_text(encoding="utf-8")
        assert "My Custom Config" in content
        assert "personal content" in content
        assert "SPELLBOOK:START" not in content
        assert "SPELLBOOK:END" not in content
        assert "Spellbook Configuration" not in content

    def test_removal_file_has_no_markers(self, tmp_path):
        """After removal, no demarcation markers remain."""
        from installer.demarcation import remove_demarcated_section

        path = tmp_path / "CLAUDE.md"
        _make_demarcated_file(path, user_content=SAMPLE_USER_CONTENT, spellbook_content=SAMPLE_SPELLBOOK_CONTENT)

        remove_demarcated_section(path)

        content = path.read_text(encoding="utf-8")
        assert "<!-- SPELLBOOK:START" not in content
        assert "<!-- SPELLBOOK:END -->" not in content

    def test_removal_creates_backup_by_default(self, tmp_path):
        """By default, a backup file is created before removal."""
        from installer.demarcation import remove_demarcated_section

        path = tmp_path / "CLAUDE.md"
        _make_demarcated_file(path, user_content=SAMPLE_USER_CONTENT, spellbook_content=SAMPLE_SPELLBOOK_CONTENT)
        original_content = path.read_text(encoding="utf-8")

        remove_demarcated_section(path)

        # Find backup file
        backups = list(tmp_path.glob("CLAUDE.md.backup.*"))
        assert len(backups) == 1
        assert backups[0].read_text(encoding="utf-8") == original_content

    def test_removal_no_backup_when_disabled(self, tmp_path):
        """When backup=False, no backup file is created."""
        from installer.demarcation import remove_demarcated_section

        path = tmp_path / "CLAUDE.md"
        _make_demarcated_file(path, user_content=SAMPLE_USER_CONTENT, spellbook_content=SAMPLE_SPELLBOOK_CONTENT)

        remove_demarcated_section(path, backup=False)

        backups = list(tmp_path.glob("CLAUDE.md.backup.*"))
        assert len(backups) == 0

    def test_empty_user_content_deletes_file(self, tmp_path):
        """When user content is empty/whitespace, delete the file entirely."""
        from installer.demarcation import remove_demarcated_section

        path = tmp_path / "CLAUDE.md"
        _make_demarcated_file(path, user_content="", spellbook_content=SAMPLE_SPELLBOOK_CONTENT)

        action, backup_path = remove_demarcated_section(path)
        assert action == "removed"
        assert backup_path is not None
        assert not path.exists(), "File should be deleted when user content is empty"

    def test_whitespace_only_user_content_deletes_file(self, tmp_path):
        """When user content is whitespace-only, delete the file entirely."""
        from installer.demarcation import remove_demarcated_section

        path = tmp_path / "CLAUDE.md"
        _make_demarcated_file(path, user_content="   \n\n  \n", spellbook_content=SAMPLE_SPELLBOOK_CONTENT)

        action, backup_path = remove_demarcated_section(path)
        assert action == "removed"
        assert backup_path is not None
        assert not path.exists(), "File should be deleted when user content is whitespace-only"

    def test_backup_created_even_when_file_deleted(self, tmp_path):
        """Backup is created even if the file itself gets deleted (empty user content)."""
        from installer.demarcation import remove_demarcated_section

        path = tmp_path / "CLAUDE.md"
        _make_demarcated_file(path, user_content="", spellbook_content=SAMPLE_SPELLBOOK_CONTENT)
        original_content = path.read_text(encoding="utf-8")

        remove_demarcated_section(path, backup=True)

        assert not path.exists(), "Original file should be deleted"
        backups = list(tmp_path.glob("CLAUDE.md.backup.*"))
        assert len(backups) == 1
        assert backups[0].read_text(encoding="utf-8") == original_content

    def test_no_backup_no_file_deletion_preserves_nothing(self, tmp_path):
        """When backup=False and file gets deleted, no backup exists."""
        from installer.demarcation import remove_demarcated_section

        path = tmp_path / "CLAUDE.md"
        _make_demarcated_file(path, user_content="", spellbook_content=SAMPLE_SPELLBOOK_CONTENT)

        remove_demarcated_section(path, backup=False)

        assert not path.exists()
        backups = list(tmp_path.glob("CLAUDE.md.backup.*"))
        assert len(backups) == 0

    def test_user_content_trailing_newline(self, tmp_path):
        """After removal, user content ends with a single trailing newline."""
        from installer.demarcation import remove_demarcated_section

        path = tmp_path / "CLAUDE.md"
        _make_demarcated_file(path, user_content=SAMPLE_USER_CONTENT, spellbook_content=SAMPLE_SPELLBOOK_CONTENT)

        remove_demarcated_section(path)

        content = path.read_text(encoding="utf-8")
        assert content.endswith("\n"), "File should end with newline"
        assert not content.endswith("\n\n"), "File should not end with double newline"

    def test_file_without_section_unchanged(self, tmp_path):
        """File without spellbook section is not modified."""
        from installer.demarcation import remove_demarcated_section

        path = tmp_path / "CLAUDE.md"
        original = "# Just user content\n\nNo spellbook here.\n"
        path.write_text(original, encoding="utf-8")

        remove_demarcated_section(path)

        assert path.read_text(encoding="utf-8") == original

    def test_no_file_creates_no_backup(self, tmp_path):
        """When file doesn't exist, no backup is created."""
        from installer.demarcation import remove_demarcated_section

        path = tmp_path / "nonexistent.md"
        remove_demarcated_section(path)

        backups = list(tmp_path.glob("*.backup.*"))
        assert len(backups) == 0

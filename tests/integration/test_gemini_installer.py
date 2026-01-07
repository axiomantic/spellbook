"""Integration tests for Gemini installer."""

import pytest
from pathlib import Path
from installer.platforms.gemini import GeminiInstaller


def test_gemini_creates_extension_skill_symlinks(tmp_path):
    """Test that Gemini installer creates skill symlinks in extension."""
    # Setup
    spellbook_dir = tmp_path / "spellbook"
    skills_dir = spellbook_dir / "skills"
    skills_dir.mkdir(parents=True)

    # Create test skills
    (skills_dir / "test-skill-1").mkdir()
    (skills_dir / "test-skill-1" / "SKILL.md").write_text("# Test Skill 1")
    (skills_dir / "test-skill-2").mkdir()
    (skills_dir / "test-skill-2" / "SKILL.md").write_text("# Test Skill 2")

    # Create extension directory (installer expects it at spellbook_dir/extensions/gemini)
    extension_dir = spellbook_dir / "extensions" / "gemini"
    extension_dir.mkdir(parents=True)

    config_dir = tmp_path / "gemini_config"

    installer = GeminiInstaller(
        spellbook_dir=spellbook_dir,
        config_dir=config_dir,
        version="0.1.0",
        dry_run=False
    )

    # Test skill symlink creation
    created, errors = installer._ensure_extension_skills_symlinks()

    assert created == 2
    assert errors == 0

    # Verify symlinks
    skill1_link = installer.extension_dir / "skills" / "test-skill-1"
    skill2_link = installer.extension_dir / "skills" / "test-skill-2"

    assert skill1_link.is_symlink()
    assert skill2_link.is_symlink()
    assert skill1_link.resolve() == (skills_dir / "test-skill-1").resolve()


def test_gemini_install_includes_extension_skills(tmp_path, monkeypatch):
    """Test that install method creates extension skills."""
    # Mock gemini CLI availability
    def mock_check_cli():
        return True

    monkeypatch.setattr("installer.platforms.gemini.check_gemini_cli_available", mock_check_cli)

    # Setup
    spellbook_dir = tmp_path / "spellbook"
    skills_dir = spellbook_dir / "skills"
    skills_dir.mkdir(parents=True)
    (skills_dir / "test-skill").mkdir()
    (skills_dir / "test-skill" / "SKILL.md").write_text("# Test")

    extension_dir = spellbook_dir / "extensions" / "gemini"
    extension_dir.mkdir(parents=True)

    config_dir = tmp_path / "gemini_config"

    installer = GeminiInstaller(
        spellbook_dir=spellbook_dir,
        config_dir=config_dir,
        version="0.1.0",
        dry_run=True  # Use dry_run to avoid actual CLI calls
    )

    results = installer.install()

    # Verify extension_skills component exists
    skill_results = [r for r in results if r.component == "extension_skills"]
    assert len(skill_results) == 1
    assert skill_results[0].success

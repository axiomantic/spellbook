"""Integration tests for Codex installer with skill symlinks."""

import pytest
from pathlib import Path


@pytest.fixture
def spellbook_dir(tmp_path):
    """Create a mock spellbook directory with skills."""
    spellbook = tmp_path / "spellbook"
    spellbook.mkdir()

    # Create version file
    (spellbook / ".version").write_text("0.1.0")

    # Create MCP server path
    mcp_dir = spellbook / "spellbook_mcp"
    mcp_dir.mkdir()
    (mcp_dir / "server.py").write_text("# MCP server stub")

    # Create AGENTS.spellbook.md for context generation
    (spellbook / "AGENTS.spellbook.md").write_text("# Spellbook Context\n\nTest content.")

    # Create test skills
    skills_dir = spellbook / "skills"
    skills_dir.mkdir()

    (skills_dir / "test-skill-1").mkdir()
    (skills_dir / "test-skill-1" / "SKILL.md").write_text("# Test Skill 1")

    (skills_dir / "test-skill-2").mkdir()
    (skills_dir / "test-skill-2" / "SKILL.md").write_text("# Test Skill 2")

    return spellbook


@pytest.fixture
def codex_config_dir(tmp_path):
    """Create a mock Codex config directory."""
    config_dir = tmp_path / ".codex"
    config_dir.mkdir(parents=True)
    return config_dir


def test_codex_creates_skill_symlinks(spellbook_dir, codex_config_dir):
    """Test that Codex installer creates per-skill symlinks."""
    from installer.platforms.codex import CodexInstaller

    installer = CodexInstaller(
        spellbook_dir=spellbook_dir,
        config_dir=codex_config_dir,
        version="0.1.0",
        dry_run=False
    )

    # Install
    results = installer.install()

    # Verify skills component exists
    skills_results = [r for r in results if r.component == "skills"]
    assert len(skills_results) == 1
    assert skills_results[0].success

    # Verify symlinks created
    skills_dir = spellbook_dir / "skills"
    skill1_link = codex_config_dir / "skills" / "test-skill-1"
    skill2_link = codex_config_dir / "skills" / "test-skill-2"

    assert skill1_link.is_symlink()
    assert skill2_link.is_symlink()
    assert skill1_link.resolve() == (skills_dir / "test-skill-1").resolve()
    assert skill2_link.resolve() == (skills_dir / "test-skill-2").resolve()


def test_codex_uninstall_removes_skill_symlinks(spellbook_dir, codex_config_dir):
    """Test that uninstall removes skill symlinks."""
    from installer.platforms.codex import CodexInstaller

    installer = CodexInstaller(
        spellbook_dir=spellbook_dir,
        config_dir=codex_config_dir,
        version="0.1.0",
        dry_run=False
    )

    # Install then uninstall
    installer.install()
    results = installer.uninstall()

    # Verify skills component in uninstall results
    skills_results = [r for r in results if r.component == "skills"]
    assert len(skills_results) == 1
    assert skills_results[0].action == "removed"

    # Verify symlinks removed
    skill1_link = codex_config_dir / "skills" / "test-skill-1"
    skill2_link = codex_config_dir / "skills" / "test-skill-2"

    assert not skill1_link.exists()
    assert not skill2_link.exists()


def test_codex_get_symlinks_includes_skills(spellbook_dir, codex_config_dir):
    """Test that get_symlinks returns skill symlinks."""
    from installer.platforms.codex import CodexInstaller

    installer = CodexInstaller(
        spellbook_dir=spellbook_dir,
        config_dir=codex_config_dir,
        version="0.1.0",
        dry_run=False
    )

    # Install to create symlinks
    installer.install()

    # Get symlinks
    symlinks = installer.get_symlinks()

    # Should include spellbook root link
    spellbook_link = codex_config_dir / "spellbook"
    assert spellbook_link in symlinks

    # Should include skill symlinks
    skill1_link = codex_config_dir / "skills" / "test-skill-1"
    skill2_link = codex_config_dir / "skills" / "test-skill-2"

    assert skill1_link in symlinks
    assert skill2_link in symlinks


def test_codex_dry_run_skill_symlinks(spellbook_dir, codex_config_dir):
    """Test that dry_run=True doesn't create actual skill symlinks."""
    from installer.platforms.codex import CodexInstaller

    installer = CodexInstaller(
        spellbook_dir=spellbook_dir,
        config_dir=codex_config_dir,
        version="0.1.0",
        dry_run=True
    )

    # Install in dry-run mode
    results = installer.install()

    # Verify skills component exists in results
    skills_results = [r for r in results if r.component == "skills"]
    assert len(skills_results) == 1
    assert skills_results[0].success

    # Verify no actual symlinks created
    skill1_link = codex_config_dir / "skills" / "test-skill-1"
    skill2_link = codex_config_dir / "skills" / "test-skill-2"

    assert not skill1_link.exists()
    assert not skill2_link.exists()

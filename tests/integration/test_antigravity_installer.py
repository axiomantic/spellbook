"""
Integration tests for Antigravity installer.
"""

from installer.platforms.antigravity import AntigravityInstaller


def test_antigravity_creates_skill_symlinks(tmp_path):
    """Test that Antigravity installer creates skill symlinks."""
    spellbook_dir = tmp_path / "spellbook"
    skills_dir = spellbook_dir / "skills"
    skills_dir.mkdir(parents=True)

    # Create test skills
    (skills_dir / "test-skill-1").mkdir()
    (skills_dir / "test-skill-1" / "SKILL.md").write_text("# Test Skill 1")
    (skills_dir / "test-skill-2").mkdir()
    (skills_dir / "test-skill-2" / "SKILL.md").write_text("# Test Skill 2")

    config_dir = tmp_path / "antigravity"

    installer = AntigravityInstaller(
        spellbook_dir=spellbook_dir,
        config_dir=config_dir,
        version="0.1.0",
        dry_run=False,
    )

    created, errors = installer._ensure_skill_symlinks()
    assert created == 2
    assert errors == 0

    skill1_link = config_dir / "skills" / "test-skill-1"
    skill2_link = config_dir / "skills" / "test-skill-2"

    assert skill1_link.is_symlink()
    assert skill2_link.is_symlink()


def test_antigravity_full_install_and_uninstall(tmp_path):
    """Test full install and uninstall cycle for Antigravity."""
    spellbook_dir = tmp_path / "spellbook"
    skills_dir = spellbook_dir / "skills"
    skills_dir.mkdir(parents=True)
    (skills_dir / "test-skill").mkdir()
    (skills_dir / "test-skill" / "SKILL.md").write_text("# Test Skill")

    (spellbook_dir / "AGENTS.spellbook.md").write_text("# Test Agents")

    hooks_dir = spellbook_dir / "hooks"
    hooks_dir.mkdir(parents=True)
    (hooks_dir / "bash-policy.toml").write_text("[policy]\nversion = '1.0'\n")

    config_dir = tmp_path / "antigravity"

    installer = AntigravityInstaller(
        spellbook_dir=spellbook_dir,
        config_dir=config_dir,
        version="0.1.0",
        dry_run=False,
    )

    # Install
    results = installer.install()
    assert all(r.success for r in results)

    # Verify rule symlink to AGENTS.spellbook.md
    rule_symlink = config_dir / "rules" / "spellbook.md"
    assert rule_symlink.is_symlink()
    assert rule_symlink.resolve() == (spellbook_dir / "AGENTS.spellbook.md").resolve()

    status = installer.detect()
    assert status.installed is True

    # Uninstall
    un_results = installer.uninstall()
    assert all(r.success for r in un_results)

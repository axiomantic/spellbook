"""
Integration tests for Antigravity installer.
"""

import os

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

    skills_root = config_dir.parent / "config" / "skills"
    skill1_link = skills_root / "test-skill-1"
    skill2_link = skills_root / "test-skill-2"

    assert skill1_link.is_symlink()
    assert skill2_link.is_symlink()


def test_antigravity_full_install_and_uninstall(tmp_path):
    """Test full install and uninstall cycle for Antigravity."""
    spellbook_dir = tmp_path / "spellbook"
    skills_dir = spellbook_dir / "skills"
    skills_dir.mkdir(parents=True)
    (skills_dir / "test-skill").mkdir()
    (skills_dir / "test-skill" / "SKILL.md").write_text("# Test Skill")

    (spellbook_dir / "rules").mkdir(exist_ok=True)
    (spellbook_dir / "rules" / "00-core.md").write_text(
        """---\nid: core\nname: Spellbook Core\nclass: mandatory\ndescription: Test module.\nrelated: []\nrenamed_from: []\nsuperseded_by: null\npaths: []\n---\n\nTest rule module body.\n"""
    )

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

    # One symlink per module, at the corrected global rules root. Antigravity
    # reads ~/.gemini/config/rules, not <config_dir>/rules -- the latter path
    # appears nowhere in the shipped binary, so nothing written there loaded.
    rules_root = config_dir.parent / "config" / "rules"
    module_link = rules_root / "00-spellbook-core.md"
    assert module_link.is_symlink()
    assert module_link.resolve() == (spellbook_dir / "rules" / "00-core.md").resolve()

    # Skills symlink at the corrected global skills root (~/.gemini/config/skills).
    skills_root = config_dir.parent / "config" / "skills"
    skill_link = skills_root / "test-skill"
    assert skill_link.is_symlink()
    assert skill_link.resolve() == (skills_dir / "test-skill").resolve()

    # The retired single sidecar is not created.
    assert not os.path.lexists(config_dir / "rules" / "spellbook.md")

    status = installer.detect()
    assert status.installed is True

    # Also simulate a legacy symlink left behind in <config_dir>/skills to verify cleanup
    legacy_skill_dir = config_dir / "skills"
    legacy_skill_dir.mkdir(parents=True, exist_ok=True)
    legacy_link = legacy_skill_dir / "legacy-skill"
    os.symlink(skills_dir / "test-skill", legacy_link)
    assert legacy_link.is_symlink()

    # Uninstall
    un_results = installer.uninstall()
    assert all(r.success for r in un_results)

    # Uninstall is complete: every module file is gone, skills symlinks (both active
    # and legacy) are gone, and detect() stops reporting the platform installed.
    assert not list(rules_root.glob("??-spellbook-*.md"))
    assert not os.path.lexists(skill_link)
    assert not os.path.lexists(legacy_link)
    assert installer.detect().installed is False

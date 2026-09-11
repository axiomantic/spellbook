"""Integration tests for AionUi installer."""

from pathlib import Path

import pytest


@pytest.fixture
def spellbook_dir(tmp_path):
    """Mock spellbook repo with required layout."""
    spellbook = tmp_path / "spellbook"
    spellbook.mkdir()

    # Required files for installer
    (spellbook / ".version").write_text("0.94.0")
    rules_dir = spellbook / "rules"
    rules_dir.mkdir()
    (rules_dir / "00-core.md").write_text(
        "---\nid: core\n---\n# Test core rule\n"
    )

    # Skills directory with 2 test skills
    skills_dir = spellbook / "skills"
    skills_dir.mkdir()
    for name in ("test-skill-1", "test-skill-2"):
        skill_dir = skills_dir / name
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: A test skill\n---\n# {name}\n"
        )

    return spellbook


@pytest.fixture
def aionui_env(tmp_path, monkeypatch):
    """Isolated config dir so the real AionUi userData is never touched."""
    config_dir = tmp_path / "AionUi"
    monkeypatch.setenv("AIONUI_CONFIG_DIR", str(config_dir))
    return config_dir


def _installer(spellbook_dir: Path, aionui_env: Path, dry_run: bool = False):
    from installer.platforms.aionui import AionUiInstaller

    return AionUiInstaller(
        spellbook_dir=spellbook_dir,
        config_dir=aionui_env,
        version="0.94.0",
        dry_run=dry_run,
    )


# ---------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------


def test_aionui_detect_when_config_dir_missing(spellbook_dir, aionui_env):
    """detect() returns available=False and does NOT create the config dir."""
    installer = _installer(spellbook_dir, aionui_env)

    status = installer.detect()
    assert status.available is False
    assert status.installed is False
    assert status.platform == "aionui"
    # Detect must not have side effects.
    assert not aionui_env.exists()


def test_aionui_detect_when_config_dir_exists(spellbook_dir, aionui_env):
    """detect() returns available=True when the userData root exists."""
    aionui_env.mkdir(parents=True, exist_ok=True)
    status = _installer(spellbook_dir, aionui_env).detect()
    assert status.available is True
    assert status.installed is False


# ---------------------------------------------------------------------
# Install
# ---------------------------------------------------------------------


@pytest.mark.posix_only
def test_aionui_install_creates_skill_symlinks(spellbook_dir, aionui_env):
    """Skills are symlinked into <userData>/config/skills/.

    POSIX-only: creating a symlink on Windows needs SeCreateSymbolicLink
    (Administrator, or Developer Mode) — same constraint as goose.
    """
    aionui_env.mkdir(parents=True, exist_ok=True)

    results = _installer(spellbook_dir, aionui_env).install()

    skills_dir = aionui_env / "config" / "skills"
    assert skills_dir.is_dir()
    for name in ("test-skill-1", "test-skill-2"):
        link = skills_dir / name
        assert link.is_symlink()
        assert link.resolve() == (spellbook_dir / "skills" / name).resolve()

    skills_results = [r for r in results if r.component == "skills"]
    assert len(skills_results) == 1
    assert skills_results[0].success


def test_aionui_install_never_touches_app_database(spellbook_dir, aionui_env):
    """MCP is app-database-managed: the installer must not write any db.

    It reports the manual step instead (action=skipped, success=True).
    """
    aionui_env.mkdir(parents=True, exist_ok=True)
    # A stray sqlite file where the app db would live must stay untouched.
    db = aionui_env / "aionui" / "aionui-backend.db"
    db.parent.mkdir(parents=True, exist_ok=True)
    db.write_bytes(b"not a real db")

    results = _installer(spellbook_dir, aionui_env).install()

    assert db.read_bytes() == b"not a real db", "installer touched the app db"
    mcp = [r for r in results if r.component == "mcp"]
    assert len(mcp) == 1
    assert mcp[0].action == "skipped"
    assert mcp[0].success


def test_aionui_install_reports_rules_as_manual(spellbook_dir, aionui_env):
    """Rules are per-assistant db rows; no rules files are written."""
    aionui_env.mkdir(parents=True, exist_ok=True)
    results = _installer(spellbook_dir, aionui_env).install()

    rules = [r for r in results if r.component == "rules"]
    assert len(rules) == 1
    assert rules[0].action == "skipped"
    assert rules[0].success
    # No rules directory materialized anywhere in the config dir.
    assert not (aionui_env / "assistant-rules").exists()


@pytest.mark.posix_only
def test_aionui_install_preserves_user_skills(spellbook_dir, aionui_env):
    """A real skill dir occupying a name is never clobbered."""
    aionui_env.mkdir(parents=True, exist_ok=True)
    skills_dir = aionui_env / "config" / "skills"
    user_skill = skills_dir / "test-skill-1"
    user_skill.mkdir(parents=True)
    (user_skill / "SKILL.md").write_text("# User's own skill\n")

    # User skill intact, not replaced by a symlink.
    _installer(spellbook_dir, aionui_env).install()
    assert user_skill.is_dir() and not user_skill.is_symlink()
    assert (user_skill / "SKILL.md").read_text() == "# User's own skill\n"
    # The other skill still linked.
    assert (skills_dir / "test-skill-2").is_symlink()


@pytest.mark.posix_only
def test_aionui_install_is_idempotent(spellbook_dir, aionui_env):
    """Re-running install leaves correct symlinks in place, still valid."""
    aionui_env.mkdir(parents=True, exist_ok=True)
    installer = _installer(spellbook_dir, aionui_env)

    installer.install()
    first = installer.detect()
    installer.install()
    second = installer.detect()

    assert first.installed and second.installed
    skills_dir = aionui_env / "config" / "skills"
    for name in ("test-skill-1", "test-skill-2"):
        link = skills_dir / name
        assert link.is_symlink()
        assert link.resolve() == (spellbook_dir / "skills" / name).resolve()
    assert len(list(skills_dir.iterdir())) == 2, "no duplicates"


def test_aionui_install_dry_run_does_not_modify_filesystem(
    spellbook_dir, aionui_env
):
    """dry_run=True reports steps but creates nothing."""
    aionui_env.mkdir(parents=True, exist_ok=True)
    _installer(spellbook_dir, aionui_env, dry_run=True).install()

    assert not (aionui_env / "config" / "skills").exists()


# ---------------------------------------------------------------------
# Uninstall
# ---------------------------------------------------------------------


@pytest.mark.posix_only
def test_aionui_uninstall_removes_spellbook_links_only(
    spellbook_dir, aionui_env
):
    """Uninstall removes spellbook symlinks; user skills stay."""
    aionui_env.mkdir(parents=True, exist_ok=True)
    skills_dir = aionui_env / "config" / "skills"
    user_skill = skills_dir / "user-skill"
    user_skill.mkdir(parents=True)
    (user_skill / "SKILL.md").write_text("# User Skill\n")

    installer = _installer(spellbook_dir, aionui_env)
    installer.install()
    installer.uninstall()

    for name in ("test-skill-1", "test-skill-2"):
        assert not (skills_dir / name).exists()
    assert user_skill.is_dir()
    assert (user_skill / "SKILL.md").exists()


# ---------------------------------------------------------------------
# Sibling-directory prefix safety (startswith regression)
# ---------------------------------------------------------------------


@pytest.mark.posix_only
def test_aionui_detect_ignores_sibling_prefix_link(
    spellbook_dir, aionui_env, tmp_path
):
    """A symlink into ``spellbook-<suffix>`` (sibling dir) is NOT spellbook.

    The old check used a string prefix test: ``.../spellbook-something``
    startswith ``.../spellbook``, so detect() falsely reported installed.
    """
    aionui_env.mkdir(parents=True, exist_ok=True)
    sibling = tmp_path / "spellbook-sibling"
    skill = sibling / "skills" / "fake-skill"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("# Fake\n")

    skills_dir = aionui_env / "config" / "skills"
    skills_dir.mkdir(parents=True)
    (skills_dir / "fake-skill").symlink_to(skill)

    status = _installer(spellbook_dir, aionui_env).detect()
    assert status.installed is False


@pytest.mark.posix_only
def test_aionui_uninstall_keeps_sibling_prefix_link(
    spellbook_dir, aionui_env, tmp_path
):
    """Uninstall must never remove a user's link into a sibling repo."""
    aionui_env.mkdir(parents=True, exist_ok=True)
    sibling = tmp_path / "spellbook-sibling"
    skill = sibling / "skills" / "fake-skill"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("# Fake\n")

    skills_dir = aionui_env / "config" / "skills"
    skills_dir.mkdir(parents=True)
    (skills_dir / "fake-skill").symlink_to(skill)

    _installer(spellbook_dir, aionui_env).uninstall()
    assert (skills_dir / "fake-skill").is_symlink()
    assert (skills_dir / "fake-skill").resolve() == skill.resolve()


# ---------------------------------------------------------------------
# Config dir resolution + registration
# ---------------------------------------------------------------------


def test_aionui_config_dir_env_override(tmp_path, monkeypatch):
    """AIONUI_CONFIG_DIR overrides the OS default for get_platform_config_dir."""
    from installer.config import get_platform_config_dir

    override = tmp_path / "custom" / "AionUi"
    monkeypatch.setenv("AIONUI_CONFIG_DIR", str(override))
    assert get_platform_config_dir("aionui") == override
    monkeypatch.delenv("AIONUI_CONFIG_DIR")
    # Default falls back to the OS-aware userData root, never the real
    # override — just assert it is an absolute path under the user home.
    default = get_platform_config_dir("aionui")
    assert default.is_absolute()


def test_aionui_registered_in_installer_dispatch():
    """AionUiInstaller is registered in installer/core.py dispatch dict."""
    from installer.core import get_platform_installer
    from installer.platforms.aionui import AionUiInstaller

    installer = get_platform_installer(
        "aionui",
        spellbook_dir=Path("/tmp/nonexistent"),
        version="0.94.0",
        dry_run=True,
    )
    assert isinstance(installer, AionUiInstaller)


def test_aionui_in_supported_platforms_and_config():
    """AionUi is registered in the platform registry (config.py)."""
    from installer.config import PLATFORM_CONFIG, SUPPORTED_PLATFORMS

    assert "aionui" in SUPPORTED_PLATFORMS
    entry = PLATFORM_CONFIG["aionui"]
    assert entry["name"] == "AionUi"
    assert entry["config_dir_env"] == "AIONUI_CONFIG_DIR"
    assert entry["mcp_supported"] is False

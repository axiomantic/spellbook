"""Integration tests for Goose installer."""

import pytest


@pytest.fixture
def spellbook_dir(tmp_path):
    """Mock spellbook repo with required layout."""
    spellbook = tmp_path / "spellbook"
    spellbook.mkdir()

    # Required files for installer
    (spellbook / ".version").write_text("0.83.0")
    (spellbook / "AGENTS.spellbook.md").write_text(
        "# Spellbook Behavioral Guidance\n\nTest content."
    )

    # Mock MCP server path (read by core installer)
    mcp_dir = spellbook / "spellbook"
    mcp_dir.mkdir()
    (mcp_dir / "server.py").write_text("# MCP server stub")

    # Skills directory with 2 test skills
    skills_dir = spellbook / "skills"
    skills_dir.mkdir()
    for name in ("test-skill-1", "test-skill-2"):
        skill_dir = skills_dir / name
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: A test skill\n---\n# {name}\n"
        )

    # Extension template
    ext_goose = spellbook / "extensions" / "goose"
    ext_goose.mkdir(parents=True)
    (ext_goose / ".goosehints").write_text("# Spellbook Goose Hints Template")

    return spellbook


@pytest.fixture
def goose_env(tmp_path, monkeypatch):
    """Isolated HOME so ~/.agents and ~/.config/goose don't collide with real user state."""
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    # Prevent GOOSE_PATH_ROOT from being set by parent environment
    monkeypatch.delenv("GOOSE_PATH_ROOT", raising=False)
    # Also override default_config_dir via env
    monkeypatch.setenv("GOOSE_CONFIG_DIR", str(fake_home / ".config" / "goose"))
    return fake_home


@pytest.fixture
def mock_mcp_token():
    """Mock get_mcp_auth_token via tripwire so it returns a deterministic token.

    The installer imports get_mcp_auth_token into installer.platforms.goose at
    module load; tripwire can intercept the bound name. The MCP server URL
    helpers read DEFAULT_HOST/DEFAULT_PORT directly so they don't need mocking.
    """
    import tripwire

    return tripwire.mock("installer.platforms.goose:get_mcp_auth_token").returns(
        "test-token-abc123"
    )


# ---------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------

def test_goose_detect_when_config_dir_missing(spellbook_dir, goose_env):
    """detect() returns available=False when ~/.config/goose/ doesn't exist."""
    from installer.platforms.goose import GooseInstaller

    installer = GooseInstaller(
        spellbook_dir=spellbook_dir,
        config_dir=goose_env / ".config" / "goose",
        version="0.83.0",
        dry_run=False,
    )

    status = installer.detect()
    assert status.available is False
    assert status.installed is False
    assert status.platform == "goose"


def test_goose_detect_when_config_dir_exists(spellbook_dir, goose_env):
    """detect() returns available=True when ~/.config/goose/ exists (even empty)."""
    from installer.platforms.goose import GooseInstaller

    goose_env.mkdir(parents=True, exist_ok=True) if not goose_env.exists() else None
    (goose_env / ".config" / "goose").mkdir(parents=True, exist_ok=True)

    installer = GooseInstaller(
        spellbook_dir=spellbook_dir,
        config_dir=goose_env / ".config" / "goose",
        version="0.83.0",
        dry_run=False,
    )

    status = installer.detect()
    assert status.available is True
    assert status.installed is False


# ---------------------------------------------------------------------
# Install
# ---------------------------------------------------------------------

def test_goose_install_creates_skill_symlinks(spellbook_dir, goose_env):
    """Skills are symlinked into ~/.agents/skills/."""
    from installer.platforms.goose import GooseInstaller

    (goose_env / ".config" / "goose").mkdir(parents=True, exist_ok=True)

    installer = GooseInstaller(
        spellbook_dir=spellbook_dir,
        config_dir=goose_env / ".config" / "goose",
        version="0.83.0",
        dry_run=False,
    )

    results = installer.install()

    skills_dir = goose_env / ".agents" / "skills"
    assert skills_dir.is_dir(), f"Expected {skills_dir} to exist"
    skill1 = skills_dir / "test-skill-1"
    skill2 = skills_dir / "test-skill-2"
    assert skill1.is_symlink()
    assert skill2.is_symlink()
    assert skill1.resolve() == (spellbook_dir / "skills" / "test-skill-1").resolve()
    assert skill2.resolve() == (spellbook_dir / "skills" / "test-skill-2").resolve()

    # Component reported as installed
    skills_results = [r for r in results if r.component == "skills"]
    assert len(skills_results) == 1
    assert skills_results[0].success


def test_goose_install_creates_global_hints_symlink(spellbook_dir, goose_env):
    """~/.agents/AGENTS.md is symlinked to AGENTS.spellbook.md."""
    from installer.platforms.goose import GooseInstaller

    (goose_env / ".config" / "goose").mkdir(parents=True, exist_ok=True)

    installer = GooseInstaller(
        spellbook_dir=spellbook_dir,
        config_dir=goose_env / ".config" / "goose",
        version="0.83.0",
        dry_run=False,
    )

    installer.install()

    hints = goose_env / ".agents" / "AGENTS.md"
    assert hints.is_symlink()
    assert hints.resolve() == (spellbook_dir / "AGENTS.spellbook.md").resolve()


def test_goose_install_registers_mcp_in_config_yaml(spellbook_dir, goose_env, mock_mcp_token):
    """config.yaml gets a spellbook MCP extension block with Bearer header."""
    import tripwire

    from installer.platforms.goose import GooseInstaller

    (goose_env / ".config" / "goose").mkdir(parents=True, exist_ok=True)

    installer = GooseInstaller(
        spellbook_dir=spellbook_dir,
        config_dir=goose_env / ".config" / "goose",
        version="0.83.0",
        dry_run=False,
    )

    with tripwire:
        installer.install()
    mock_mcp_token.assert_call()

    cfg = goose_env / ".config" / "goose" / "config.yaml"
    assert cfg.exists()
    content = cfg.read_text()

    # Has the marker block
    assert "# SPELLBOOK:START" in content
    assert "# SPELLBOOK:END" in content
    assert "extensions:" in content
    assert "name: spellbook" in content
    assert "uri: http://127.0.0.1:8765/mcp" in content
    # Bearer token is inlined
    assert "Bearer test-token-abc123" in content

    # File mode is 0600 (token protection)
    mode = cfg.stat().st_mode & 0o777
    assert mode == 0o600, f"Expected mode 0600, got {oct(mode)}"


def test_goose_install_skipped_when_config_dir_missing(spellbook_dir, goose_env):
    """Install reports skipped platform when ~/.config/goose/ doesn't exist."""
    from installer.platforms.goose import GooseInstaller

    installer = GooseInstaller(
        spellbook_dir=spellbook_dir,
        config_dir=goose_env / ".config" / "goose",
        version="0.83.0",
        dry_run=False,
    )

    results = installer.install()

    # Should report one skipped result
    skipped = [r for r in results if r.action == "skipped"]
    assert len(skipped) == 1
    assert "not found" in skipped[0].message


def test_goose_install_preserves_existing_extensions(spellbook_dir, goose_env, mock_mcp_token):
    """Re-running install preserves user-added extensions in config.yaml."""
    import tripwire

    from installer.platforms.goose import GooseInstaller

    (goose_env / ".config" / "goose").mkdir(parents=True, exist_ok=True)
    # User has another extension defined
    cfg = goose_env / ".config" / "goose" / "config.yaml"
    cfg.write_text(
        "extensions:\n"
        "  - type: stdio\n"
        '    name: filesystem\n'
        '    cmd: filesystem-mcp\n'
        '    enabled: true\n'
    )

    installer = GooseInstaller(
        spellbook_dir=spellbook_dir,
        config_dir=goose_env / ".config" / "goose",
        version="0.83.0",
        dry_run=False,
    )

    with tripwire:
        installer.install()
    mock_mcp_token.assert_call()

    content = cfg.read_text()
    # User extension preserved
    assert "filesystem" in content
    assert "filesystem-mcp" in content
    # Spellbook block added
    assert "# SPELLBOOK:START" in content
    assert "name: spellbook" in content


def test_goose_install_is_idempotent(spellbook_dir, goose_env):
    """Re-running install with no changes produces a valid update (not duplicates)."""
    from installer.platforms.goose import GooseInstaller

    (goose_env / ".config" / "goose").mkdir(parents=True, exist_ok=True)

    installer = GooseInstaller(
        spellbook_dir=spellbook_dir,
        config_dir=goose_env / ".config" / "goose",
        version="0.83.0",
        dry_run=False,
    )

    # Idempotency: install twice; both must succeed without raising.
    # tripwire's strict mock lifecycle is awkward with multiple-install tests
    # that share a single mock target, so this test asserts file content
    # directly without mocking get_mcp_auth_token (the MCP-token-specific
    # behavior is covered by test_goose_install_registers_mcp_in_config_yaml).
    installer.install()
    installer.install()

    cfg = goose_env / ".config" / "goose" / "config.yaml"
    content = cfg.read_text()

    # Exactly one spellbook block (markers appear once)
    assert content.count("# SPELLBOOK:START") == 1
    assert content.count("# SPELLBOOK:END") == 1
    assert content.count("name: spellbook") == 1


# ---------------------------------------------------------------------
# Dry-run
# ---------------------------------------------------------------------

def test_goose_install_dry_run_does_not_modify_filesystem(spellbook_dir, goose_env):
    """dry_run=True reports steps but creates no files or symlinks."""
    from installer.platforms.goose import GooseInstaller

    (goose_env / ".config" / "goose").mkdir(parents=True, exist_ok=True)

    installer = GooseInstaller(
        spellbook_dir=spellbook_dir,
        config_dir=goose_env / ".config" / "goose",
        version="0.83.0",
        dry_run=True,
    )

    installer.install()

    # No skills dir created
    assert not (goose_env / ".agents" / "skills").exists()
    # No global hints symlink
    assert not (goose_env / ".agents" / "AGENTS.md").exists()
    # No config.yaml written
    assert not (goose_env / ".config" / "goose" / "config.yaml").exists()


# ---------------------------------------------------------------------
# Uninstall
# ---------------------------------------------------------------------

def test_goose_uninstall_removes_symlinks_and_mcp_block(spellbook_dir, goose_env, mock_mcp_token):
    """Uninstall reverses install: removes skill symlinks, hints symlink, MCP block."""
    import tripwire

    from installer.platforms.goose import GooseInstaller

    (goose_env / ".config" / "goose").mkdir(parents=True, exist_ok=True)

    installer = GooseInstaller(
        spellbook_dir=spellbook_dir,
        config_dir=goose_env / ".config" / "goose",
        version="0.83.0",
        dry_run=False,
    )

    with tripwire:
        installer.install()
        installer.uninstall()
    mock_mcp_token.assert_call()

    # Skills removed
    skills_dir = goose_env / ".agents" / "skills"
    for skill_name in ("test-skill-1", "test-skill-2"):
        assert not (skills_dir / skill_name).exists()

    # Global hints symlink removed
    hints = goose_env / ".agents" / "AGENTS.md"
    assert not hints.exists() or not hints.is_symlink()

    # MCP block removed from config.yaml
    cfg = goose_env / ".config" / "goose" / "config.yaml"
    content = cfg.read_text()
    assert "# SPELLBOOK:START" not in content
    assert "name: spellbook" not in content


def test_goose_uninstall_preserves_user_skills(spellbook_dir, goose_env):
    """Uninstall only removes spellbook symlinks; user-added skills remain."""
    from installer.platforms.goose import GooseInstaller

    (goose_env / ".config" / "goose").mkdir(parents=True, exist_ok=True)
    skills_dir = goose_env / ".agents" / "skills"
    skills_dir.mkdir(parents=True)

    # Add a user skill (not a symlink)
    user_skill_dir = skills_dir / "user-skill"
    user_skill_dir.mkdir()
    (user_skill_dir / "SKILL.md").write_text("# User Skill")

    installer = GooseInstaller(
        spellbook_dir=spellbook_dir,
        config_dir=goose_env / ".config" / "goose",
        version="0.83.0",
        dry_run=False,
    )

    installer.install()
    installer.uninstall()

    # Spellbook symlinks gone
    assert not (skills_dir / "test-skill-1").exists()
    assert not (skills_dir / "test-skill-2").exists()
    # User skill preserved
    assert (skills_dir / "user-skill").is_dir()
    assert (skills_dir / "user-skill" / "SKILL.md").exists()


# ---------------------------------------------------------------------
# GOOSE_PATH_ROOT handling
# ---------------------------------------------------------------------

def test_goose_path_root_overrides_config_dir(spellbook_dir, goose_env, monkeypatch):
    """When GOOSE_PATH_ROOT is set, installer uses $GOOSE_PATH_ROOT/config/."""
    from installer.platforms.goose import GooseInstaller, _resolve_effective_config_dir

    custom_root = goose_env / "custom_goose"
    monkeypatch.setenv("GOOSE_PATH_ROOT", str(custom_root))

    # No config dir at the default path
    default_dir = goose_env / ".config" / "goose"

    effective = _resolve_effective_config_dir(default_dir)
    assert effective == custom_root / "config"

    installer = GooseInstaller(
        spellbook_dir=spellbook_dir,
        config_dir=default_dir,
        version="0.83.0",
        dry_run=False,
    )

    # effective_config_dir property should also respect the override
    assert installer.effective_config_dir == custom_root / "config"


# ---------------------------------------------------------------------
# Dispatch registration
# ---------------------------------------------------------------------

def test_goose_registered_in_installer_dispatch():
    """GooseInstaller is registered in installer/core.py dispatch dict."""
    from installer.core import get_platform_installer
    from installer.platforms.goose import GooseInstaller

    installer = get_platform_installer(
        "goose",
        spellbook_dir=__import__("pathlib").Path("/tmp/nonexistent"),
        version="0.83.0",
        dry_run=True,
    )
    assert isinstance(installer, GooseInstaller)

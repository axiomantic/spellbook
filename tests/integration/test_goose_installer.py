"""Integration tests for Goose installer."""

import sys

import pytest


@pytest.fixture
def spellbook_dir(tmp_path):
    """Mock spellbook repo with required layout."""
    spellbook = tmp_path / "spellbook"
    spellbook.mkdir()

    # Required files for installer
    (spellbook / ".version").write_text("0.83.0")
    # BOT-D1 fix: AGENTS.spellbook.md was deleted by PR #442. The global hints
    # symlink now points to rules/00-core.md, so the fixture must create that.
    rules_dir = spellbook / "rules"
    rules_dir.mkdir()
    (rules_dir / "00-core.md").write_text(
        "---\nid: core\n---\n# Test core rule\n"
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

@pytest.mark.posix_only
def test_goose_install_creates_skill_symlinks(spellbook_dir, goose_env):
    """Skills are symlinked into ~/.agents/skills/.

    POSIX-only: creating a symlink on Windows needs SeCreateSymbolicLink
    (Administrator, or Developer Mode). The GitHub runner has neither, so
    the installer's symlink step cannot succeed there. The uninstall and
    dry-run tests below assert ABSENCE and so remain valid on Windows.
    """
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


@pytest.mark.posix_only
def test_goose_install_creates_global_hints_symlink(spellbook_dir, goose_env):
    """~/.agents/AGENTS.md is symlinked to AGENTS.spellbook.md.

    POSIX-only for the same reason as the skill-symlink test above.
    """
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
    assert hints.resolve() == (spellbook_dir / "rules" / "00-core.md").resolve()


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

    # File mode is 0600 (token protection). Windows has no POSIX mode bits:
    # os.chmod there only toggles the read-only flag, and stat() reports
    # 0o666 whatever the installer asked for. Asserting 0600 on Windows
    # would be testing the platform, not the installer -- and the token
    # registration above (the part that carries the secret) is still
    # covered there.
    if sys.platform != "win32":
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
# BOT-A3 regression: extensions: as last line with no trailing newline
# ---------------------------------------------------------------------

def test_goose_install_inserts_when_extensions_is_last_line_no_newline(
    spellbook_dir, goose_env, mock_mcp_token
):
    """MCP block is inserted even when extensions: is the last line without \n.

    Regression test for BOT-A1: Path 2 of _insert_spellbook_block requires a
    trailing newline after the ``extensions:`` line for its regex to match.
    If a user's config.yaml ends with bare ``extensions:`` and no newline,
    the installer used to silently fail to register the MCP server.
    """
    import tripwire

    from installer.platforms.goose import GooseInstaller

    (goose_env / ".config" / "goose").mkdir(parents=True, exist_ok=True)
    cfg = goose_env / ".config" / "goose" / "config.yaml"
    # No trailing newline after extensions: -- the edge case.
    cfg.write_text("key: value\nextensions:")

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
    assert "# SPELLBOOK:START" in content, (
        "MCP block not inserted -- BOT-A1 regression"
    )
    assert "name: spellbook" in content


# ---------------------------------------------------------------------

# ---------------------------------------------------------------------
# BOT-B1 regression: extensions: with trailing comment or inline array
# ---------------------------------------------------------------------

def test_goose_install_inserts_when_extensions_has_trailing_comment(
    spellbook_dir, goose_env
):
    r"""MCP block is inserted when `extensions:` line has a trailing YAML comment.

    Regression test for BOT-B1: Path 2's regex `^extensions:\s*$` did NOT
    match `extensions: # comment`, so the function fell through to Path 3
    which appended a NEW `extensions:` section. YAML allows duplicate keys
    (last-wins), which silently DROPPED the user's existing extensions.
    """
    from installer.platforms.goose import _generate_mcp_yaml_list_item, _insert_spellbook_block

    yaml_text = "extensions: # user extensions here\n  - type: stdio\n    name: user-tool\n"
    block = _generate_mcp_yaml_list_item()

    result = _insert_spellbook_block(yaml_text, block)

    # The user's existing extension must still be present.
    assert "name: user-tool" in result, (
        "User's existing extensions were silently dropped (BOT-B1 regression)"
    )
    # The spellbook block must be inserted.
    assert "# SPELLBOOK:START" in result
    assert "name: spellbook" in result
    # There must be exactly one `extensions:` key (no duplicate).
    ext_count = result.count("extensions:")
    assert ext_count == 1, (
        f"Duplicate `extensions:` key created: {ext_count} occurrences\n{result}"
    )


def test_goose_install_inserts_when_extensions_is_inline_array(
    spellbook_dir, goose_env
):
    r"""MCP block is inserted when `extensions:` is an inline flow-style list.

    Regression test for BOT-B1: `extensions: [a, b]` also failed the
    `^extensions:\s*$` regex. The fix expands inline arrays to block style
    and then inserts the spellbook block in the same list.
    """
    from installer.platforms.goose import _generate_mcp_yaml_list_item, _insert_spellbook_block

    yaml_text = "extensions: [type: stdio, type: http]\n"
    block = _generate_mcp_yaml_list_item()

    result = _insert_spellbook_block(yaml_text, block)

    # User's extensions preserved (now in block style)
    assert "type: stdio" in result
    assert "type: http" in result
    # Spellbook block inserted
    assert "# SPELLBOOK:START" in result
    assert "name: spellbook" in result
    # No duplicate extensions: key
    ext_count = result.count("extensions:")
    assert ext_count == 1, (
        f"Duplicate `extensions:` key created: {ext_count} occurrences\n{result}"
    )



def test_goose_install_preserves_inline_array_with_flow_mapping_items(
    spellbook_dir, goose_env
):
    """MCP block is inserted when `extensions:` is an inline array containing
    flow-mapping items with embedded commas (e.g. {name: a, type: b}).

    Regression test for BOT-D4: naive `inner.split(",")` was lossy for these
    cases -- it would split mid-mapping and corrupt the user YAML. The fix
    uses yaml.safe_load to parse items correctly.
    """
    from installer.platforms.goose import _insert_spellbook_block, _generate_mcp_yaml_list_item

    # Embedded comma inside a flow mapping: the original naive split would
    # yield 4 broken items instead of 2 mappings.
    yaml_text = "extensions: [{name: foo, type: bar}, {name: baz, type: qux}]\n"
    block = _generate_mcp_yaml_list_item()

    result = _insert_spellbook_block(yaml_text, block)

    # Both flow-mappings preserved (in block style)
    assert "name: foo" in result
    assert "type: bar" in result
    assert "name: baz" in result
    assert "type: qux" in result
    # Spellbook block inserted
    assert "# SPELLBOOK:START" in result
    assert "name: spellbook" in result
    # No duplicate extensions: key
    ext_count = result.count("extensions:")
    assert ext_count == 1, (
        f"Duplicate `extensions:` key created: {ext_count} occurrences\n{result}"
    )



# ---------------------------------------------------------------------
# BOT-B2 regression: no double-close of fd when f.write() raises
# ---------------------------------------------------------------------

def test_goose_mcp_config_no_double_close_on_write_failure(
    spellbook_dir, goose_env, monkeypatch
):
    """When f.write() raises, the file descriptor is closed exactly once.

    Regression test for BOT-B2: previously, an exception in f.write() caused
    `_os.fdopen()`'s context manager to close `fd`, AND the except handler
    also called `_os.close(fd)`, double-closing the descriptor.
    """
    import os as _os

    from installer.platforms import goose as goose_mod

    close_calls = []

    real_close = _os.close
    real_fdopen = _os.fdopen

    def tracking_close(fd):
        close_calls.append(fd)
        return real_close(fd)

    def fake_fdopen(fd, mode, *args, **kwargs):
        # Wrap fdopen so the resulting file object raises on .write()
        f = real_fdopen(fd, mode, *args, **kwargs)
        original_write = f.write

        def failing_write(data):
            original_write(data)  # write a partial buffer first
            raise OSError("simulated write failure")

        f.write = failing_write
        return f

    monkeypatch.setattr(_os, "close", tracking_close)
    monkeypatch.setattr(_os, "fdopen", fake_fdopen)

    cfg = goose_env / ".config" / "goose" / "config.yaml"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text("extensions:\n  - type: stdio\n    name: existing\n")

    with pytest.raises(OSError, match="simulated write failure"):
        goose_mod._update_goose_mcp_config(cfg, dry_run=False)

    # With the BOT-B2 fix, the except handler does NOT call os.close(fd) anymore.
    # The file object created by os.fdopen() owns the fd; its __exit__ closes
    # the fd via the C extension (NOT via os.close), so close_calls should be 0.
    # The buggy version would have called os.close(fd) explicitly in the except,
    # giving close_calls == 1 (the double-close).
    assert len(close_calls) == 0, (
        f"os.close was called {len(close_calls)} time(s) -- except handler must NOT "
        f"close fd that fdopen already owns (BOT-B2 regression)"
    )

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

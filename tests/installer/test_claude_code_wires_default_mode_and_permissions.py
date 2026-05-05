"""WI-0 wiring: ClaudeCodeInstaller.install() invokes install_default_mode
and install_permissions and surfaces the results as InstallResult entries.
"""

from pathlib import Path

import pytest


@pytest.fixture
def home_dir(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    return home


@pytest.fixture
def spellbook_dir(tmp_path):
    sb = tmp_path / "spellbook_dir"
    sb.mkdir()
    return sb


def _stub_external_calls(monkeypatch, tmp_path):
    """Disable everything that would touch the real network / system."""
    monkeypatch.setattr(
        "installer.platforms.claude_code.check_claude_cli_available", lambda: False
    )
    monkeypatch.setattr(
        "installer.components.mcp.check_claude_cli_available", lambda: False
    )
    monkeypatch.setattr(
        "installer.components.mcp.install_daemon",
        lambda *a, **kw: (True, "ok"),
    )
    # Redirect the managed-permissions state file to tmp_path so we don't
    # mutate the real one under ~/.local/spellbook.
    state_path = tmp_path / "managed_permissions.json"
    from installer.components import managed_permissions_state as mps
    monkeypatch.setattr(mps, "_STATE_FILE_PATH", state_path)


def test_install_emits_default_mode_result(home_dir, spellbook_dir, tmp_path, monkeypatch):
    """install() includes an InstallResult for component='default_mode'."""
    from installer.platforms.claude_code import ClaudeCodeInstaller

    _stub_external_calls(monkeypatch, tmp_path)

    config_dir = home_dir / ".claude"
    installer = ClaudeCodeInstaller(spellbook_dir, config_dir, "0.10.0")
    results = installer.install()

    components = [r.component for r in results]
    assert "default_mode" in components
    dm_result = next(r for r in results if r.component == "default_mode")
    assert dm_result.success is True
    assert dm_result.platform == "claude_code"


def test_install_emits_permissions_result(home_dir, spellbook_dir, tmp_path, monkeypatch):
    """install() includes an InstallResult for component='permissions'."""
    from installer.platforms.claude_code import ClaudeCodeInstaller

    _stub_external_calls(monkeypatch, tmp_path)

    config_dir = home_dir / ".claude"
    installer = ClaudeCodeInstaller(spellbook_dir, config_dir, "0.10.0")
    results = installer.install()

    components = [r.component for r in results]
    assert "permissions" in components
    p_result = next(r for r in results if r.component == "permissions")
    assert p_result.success is True
    assert p_result.platform == "claude_code"


def test_install_writes_acceptedits_default_mode(home_dir, spellbook_dir, tmp_path, monkeypatch):
    """The wired-in mode for Phase 1 is 'acceptEdits'; settings.json reflects it."""
    import json

    from installer.platforms.claude_code import ClaudeCodeInstaller

    _stub_external_calls(monkeypatch, tmp_path)

    config_dir = home_dir / ".claude"
    installer = ClaudeCodeInstaller(spellbook_dir, config_dir, "0.10.0")
    installer.install()

    settings_path = config_dir / "settings.json"
    assert settings_path.exists()
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    assert settings.get("defaultMode") == "acceptEdits"

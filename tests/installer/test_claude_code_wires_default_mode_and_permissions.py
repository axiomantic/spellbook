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
    """install() emits exactly one InstallResult for component='default_mode'.

    Counted-and-extracted (not "in components") so a regression that wires
    install_default_mode twice would fail this test.
    """
    from installer.platforms.claude_code import ClaudeCodeInstaller

    _stub_external_calls(monkeypatch, tmp_path)

    config_dir = home_dir / ".claude"
    installer = ClaudeCodeInstaller(spellbook_dir, config_dir, "0.10.0")
    results = installer.install()

    dm_results = [r for r in results if r.component == "default_mode"]
    assert len(dm_results) == 1
    dm_result = dm_results[0]
    assert dm_result.success is True
    assert dm_result.platform == "claude_code"


def test_install_emits_permissions_result(home_dir, spellbook_dir, tmp_path, monkeypatch):
    """install() emits exactly one InstallResult for component='permissions'."""
    from installer.platforms.claude_code import ClaudeCodeInstaller

    _stub_external_calls(monkeypatch, tmp_path)

    config_dir = home_dir / ".claude"
    installer = ClaudeCodeInstaller(spellbook_dir, config_dir, "0.10.0")
    results = installer.install()

    p_results = [r for r in results if r.component == "permissions"]
    assert len(p_results) == 1
    p_result = p_results[0]
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


def test_uninstall_emits_default_mode_and_permissions_results(
    home_dir, spellbook_dir, tmp_path, monkeypatch
):
    """uninstall() must emit exactly one default_mode and one permissions
    InstallResult, alongside the existing hooks result."""
    from installer.platforms.claude_code import ClaudeCodeInstaller

    _stub_external_calls(monkeypatch, tmp_path)

    config_dir = home_dir / ".claude"
    installer = ClaudeCodeInstaller(spellbook_dir, config_dir, "0.10.0")
    installer.install()

    results = installer.uninstall()

    dm_results = [r for r in results if r.component == "default_mode"]
    p_results = [r for r in results if r.component == "permissions"]
    h_results = [r for r in results if r.component == "hooks"]

    assert len(dm_results) == 1
    assert dm_results[0].success is True
    assert dm_results[0].platform == "claude_code"

    assert len(p_results) == 1
    assert p_results[0].success is True
    assert p_results[0].platform == "claude_code"

    # Hooks uninstall remains wired and emits exactly one result.
    assert len(h_results) == 1


def test_uninstall_clears_managed_default_mode_from_settings(
    home_dir, spellbook_dir, tmp_path, monkeypatch
):
    """install -> uninstall removes the managed defaultMode from settings.json."""
    import json as _json

    from installer.platforms.claude_code import ClaudeCodeInstaller

    _stub_external_calls(monkeypatch, tmp_path)

    config_dir = home_dir / ".claude"
    installer = ClaudeCodeInstaller(spellbook_dir, config_dir, "0.10.0")
    installer.install()

    settings_path = config_dir / "settings.json"
    assert _json.loads(settings_path.read_text(encoding="utf-8")).get("defaultMode") == "acceptEdits"

    installer.uninstall()

    written = _json.loads(settings_path.read_text(encoding="utf-8"))
    assert "defaultMode" not in written

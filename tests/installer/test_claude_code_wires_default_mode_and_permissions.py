"""WI-0 wiring: ClaudeCodeInstaller.install() invokes install_default_mode
and install_permissions and surfaces the results as InstallResult entries.
"""

import pytest
import tripwire
from dirty_equals import AnyThing


@pytest.fixture
def home_dir(tmp_path):
    """Create a fake home directory under tmp_path. Returned for use as the
    Path.home() return value in tripwire mocks registered per test."""
    home = tmp_path / "home"
    home.mkdir()
    return home


@pytest.fixture
def spellbook_dir(tmp_path):
    sb = tmp_path / "spellbook_dir"
    sb.mkdir()
    return sb


def _redirect_state_file(monkeypatch, tmp_path):
    """Redirect the managed-permissions state file to tmp_path so the test
    does not mutate the real one under ~/.local/spellbook.

    NOTE: ``_STATE_FILE_PATH`` is a Path *constant* (not a callable), so
    monkeypatch.setattr is the right tool here. The styleguide prohibition
    on monkeypatch.setattr is specific to callables / methods / classes."""
    state_path = tmp_path / "managed_permissions.json"
    from installer.components import managed_permissions_state as mps
    monkeypatch.setattr(mps, "_STATE_FILE_PATH", state_path)


# Empirical call counts inside the tripwire sandbox per install() / uninstall()
# call. These are measured against the actual SUT via a probe test (not
# guessed); if the SUT changes such that more or fewer calls are made, these
# constants and the matching assert loops below must be updated together.
#
# Probed sequence for install() (sequence numbers 0-N inside the sandbox):
#   0,1,2: pathlib:Path.home() x 3
#   3:     installer.components.mcp:check_claude_cli_available() (via
#          unregister_mcp_server's internal CLI gate)
#   4:     installer.platforms.claude_code:check_claude_cli_available()
#
# Probed sequence for uninstall() (delta after install):
#   5:     installer.platforms.claude_code:uninstall_daemon(dry_run=False)
#   6:     installer.platforms.claude_code:check_claude_cli_available()
_HOME_CALLS_PER_INSTALL = 2
_CC_CLI_CALLS_PER_INSTALL = 1
_MCP_CLI_CALLS_PER_INSTALL = 1
_HOME_CALLS_PER_UNINSTALL = 0
_CC_CLI_CALLS_PER_UNINSTALL = 1
_DAEMON_CALLS_PER_UNINSTALL = 1


def _register_install_mocks(home_dir):
    """Register tripwire mocks for the install() call path.

    Both ``check_claude_cli_available`` import-site mocks are required:
    the ``from ..components.mcp import check_claude_cli_available`` in
    claude_code.py creates a separate binding from the original symbol
    in mcp.py; calls inside mcp use mcp's binding, calls inside
    claude_code use claude_code's. Two bindings, two mocks.
    """
    mock_home = tripwire.mock("pathlib:Path.home")
    for _ in range(_HOME_CALLS_PER_INSTALL):
        mock_home.__call__.required(False).returns(home_dir)

    mock_cc_cli = tripwire.mock(
        "installer.platforms.claude_code:check_claude_cli_available"
    )
    for _ in range(_CC_CLI_CALLS_PER_INSTALL):
        mock_cc_cli.__call__.required(False).returns(False)

    mock_mcp_cli = tripwire.mock(
        "installer.components.mcp:check_claude_cli_available"
    )
    for _ in range(_MCP_CLI_CALLS_PER_INSTALL):
        mock_mcp_cli.__call__.required(False).returns(False)

    return mock_home, mock_cc_cli, mock_mcp_cli


def _register_install_and_uninstall_mocks(home_dir):
    """Register tripwire mocks for the combined install() + uninstall() call
    paths in a single sandbox.

    Tripwire allows each target to be mocked exactly once per sandbox, so
    install + uninstall tests must share registration. The budget is the
    sum of install and uninstall calls.

    Note: Path.home is NOT called from the uninstall path under the test's
    config_dir setup, so no extra home mocks are needed beyond install.
    The daemon mock intercepts ``uninstall_daemon`` so the test never
    actually opens a socket to check the daemon (tripwire's DNS plugin
    would otherwise fail on the unmocked socket call).
    """
    mock_home = tripwire.mock("pathlib:Path.home")
    for _ in range(_HOME_CALLS_PER_INSTALL + _HOME_CALLS_PER_UNINSTALL):
        mock_home.__call__.required(False).returns(home_dir)

    mock_cc_cli = tripwire.mock(
        "installer.platforms.claude_code:check_claude_cli_available"
    )
    for _ in range(_CC_CLI_CALLS_PER_INSTALL + _CC_CLI_CALLS_PER_UNINSTALL):
        mock_cc_cli.__call__.required(False).returns(False)

    mock_mcp_cli = tripwire.mock(
        "installer.components.mcp:check_claude_cli_available"
    )
    for _ in range(_MCP_CLI_CALLS_PER_INSTALL):
        mock_mcp_cli.__call__.required(False).returns(False)

    mock_daemon = tripwire.mock(
        "installer.platforms.claude_code:uninstall_daemon"
    )
    for _ in range(_DAEMON_CALLS_PER_UNINSTALL):
        mock_daemon.__call__.required(False).returns((True, "ok"))

    return mock_home, mock_cc_cli, mock_mcp_cli, mock_daemon


def _assert_install_mocks(mock_home, mock_cc_cli, mock_mcp_cli):
    with tripwire.in_any_order():
        for _ in range(_HOME_CALLS_PER_INSTALL):
            mock_home.assert_call(args=(), kwargs={}, returned=AnyThing)
        for _ in range(_CC_CLI_CALLS_PER_INSTALL):
            mock_cc_cli.assert_call(args=(), kwargs={}, returned=AnyThing)
        for _ in range(_MCP_CLI_CALLS_PER_INSTALL):
            mock_mcp_cli.assert_call(args=(), kwargs={}, returned=AnyThing)


def _assert_install_and_uninstall_mocks(
    mock_home, mock_cc_cli, mock_mcp_cli, mock_daemon
):
    """Combined assertion for tests that exercise install() and uninstall()
    in the same sandbox. Total expected counts = install + uninstall."""
    with tripwire.in_any_order():
        for _ in range(_HOME_CALLS_PER_INSTALL + _HOME_CALLS_PER_UNINSTALL):
            mock_home.assert_call(args=(), kwargs={}, returned=AnyThing)
        for _ in range(_CC_CLI_CALLS_PER_INSTALL + _CC_CLI_CALLS_PER_UNINSTALL):
            mock_cc_cli.assert_call(args=(), kwargs={}, returned=AnyThing)
        for _ in range(_MCP_CLI_CALLS_PER_INSTALL):
            mock_mcp_cli.assert_call(args=(), kwargs={}, returned=AnyThing)
        for _ in range(_DAEMON_CALLS_PER_UNINSTALL):
            mock_daemon.assert_call(
                args=(), kwargs={"dry_run": False}, returned=AnyThing
            )


def test_install_emits_default_mode_result(home_dir, spellbook_dir, tmp_path, monkeypatch):
    """install() emits exactly one InstallResult for component='default_mode'.

    Counted-and-extracted (not "in components") so a regression that wires
    install_default_mode twice would fail this test.
    """
    from installer.platforms.claude_code import ClaudeCodeInstaller

    _redirect_state_file(monkeypatch, tmp_path)
    mocks = _register_install_mocks(home_dir)

    config_dir = home_dir / ".claude"
    installer = ClaudeCodeInstaller(spellbook_dir, config_dir, "0.10.0")

    with tripwire:
        results = installer.install()

    _assert_install_mocks(*mocks)

    dm_results = [r for r in results if r.component == "default_mode"]
    assert len(dm_results) == 1
    dm_result = dm_results[0]
    assert dm_result.success is True
    assert dm_result.platform == "claude_code"


def test_install_emits_permissions_result(home_dir, spellbook_dir, tmp_path, monkeypatch):
    """install() emits exactly one InstallResult for component='permissions'."""
    from installer.platforms.claude_code import ClaudeCodeInstaller

    _redirect_state_file(monkeypatch, tmp_path)
    mocks = _register_install_mocks(home_dir)

    config_dir = home_dir / ".claude"
    installer = ClaudeCodeInstaller(spellbook_dir, config_dir, "0.10.0")

    with tripwire:
        results = installer.install()

    _assert_install_mocks(*mocks)

    p_results = [r for r in results if r.component == "permissions"]
    assert len(p_results) == 1
    p_result = p_results[0]
    assert p_result.success is True
    assert p_result.platform == "claude_code"


def test_install_writes_acceptedits_default_mode(home_dir, spellbook_dir, tmp_path, monkeypatch):
    """The wired-in mode for Phase 1 is 'acceptEdits'; settings.json reflects it."""
    import json

    from installer.platforms.claude_code import ClaudeCodeInstaller

    _redirect_state_file(monkeypatch, tmp_path)
    mocks = _register_install_mocks(home_dir)

    config_dir = home_dir / ".claude"
    installer = ClaudeCodeInstaller(spellbook_dir, config_dir, "0.10.0")

    with tripwire:
        installer.install()

    _assert_install_mocks(*mocks)

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

    _redirect_state_file(monkeypatch, tmp_path)

    config_dir = home_dir / ".claude"
    installer = ClaudeCodeInstaller(spellbook_dir, config_dir, "0.10.0")

    # install + uninstall happen in the SAME sandbox so we can assert across
    # the combined call budget. Tripwire allows each target to be mocked
    # exactly once per sandbox, so registrations must be combined.
    mocks = _register_install_and_uninstall_mocks(home_dir)

    with tripwire:
        installer.install()
        results = installer.uninstall()

    _assert_install_and_uninstall_mocks(*mocks)

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

    _redirect_state_file(monkeypatch, tmp_path)

    config_dir = home_dir / ".claude"
    installer = ClaudeCodeInstaller(spellbook_dir, config_dir, "0.10.0")

    mocks = _register_install_and_uninstall_mocks(home_dir)

    with tripwire:
        installer.install()

        settings_path = config_dir / "settings.json"
        assert _json.loads(settings_path.read_text(encoding="utf-8")).get("defaultMode") == "acceptEdits"

        installer.uninstall()

    _assert_install_and_uninstall_mocks(*mocks)

    written = _json.loads(settings_path.read_text(encoding="utf-8"))
    assert "defaultMode" not in written

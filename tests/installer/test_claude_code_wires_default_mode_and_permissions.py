"""WI-0 wiring: ClaudeCodeInstaller.install() invokes install_default_mode
and install_permissions and surfaces the results as InstallResult entries.
"""

import sys

import pytest
import tripwire
from dirty_equals import AnyThing

# install_hooks calls shutil.which("powershell") on Windows. Tripwire's
# SubprocessPlugin always intercepts shutil.which; without a registered
# mock it returns None and the SUT short-circuits before writing settings.
# On non-Windows the SUT does not enter that branch, so the mock sits
# unused (mock_which is required=False by default).
_FAKE_POWERSHELL = "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe"


def _register_powershell_which_mock() -> None:
    tripwire.subprocess.mock_which("powershell", returns=_FAKE_POWERSHELL)


def _assert_powershell_which_if_windows(times: int = 1) -> None:
    if sys.platform == "win32":
        for _ in range(times):
            tripwire.subprocess.assert_which(
                "powershell", returns=_FAKE_POWERSHELL
            )


def _assert_spellbook_cco_which_if_posix(times: int = 1) -> None:
    """Assert the WI-7 alias-dispatcher's ``shutil.which("spellbook-cco")``.

    ``installer.platforms.claude_code._install_claude_code_aliases`` gates
    the per-dir alias install on the presence of the ``spellbook-cco``
    wrapper via ``shutil.which("spellbook-cco")`` (or ``which("cco")`` when
    ``SPELLBOOK_USE_VANILLA_CCO=1`` is set). Tripwire's SubprocessPlugin
    intercepts that call; without an explicit ``assert_which`` after the
    sandbox closes, tripwire's strict verifier raises
    ``UnassertedInteractionsError`` at teardown when the binary is absent
    from PATH (the case in CI environments).

    The dispatch only runs on POSIX (LINUX / MACOS); the Windows branch
    routes to ``install_aliases_windows`` which does not call
    ``shutil.which`` for the cco wrapper. Hence the platform gate.
    """
    if sys.platform != "win32":
        for _ in range(times):
            tripwire.subprocess.assert_which(
                name="spellbook-cco", returns=None
            )


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


def _redirect_state_file(tmp_path, *, budget: int):
    """Redirect the managed-permissions state file to tmp_path so the test
    does not mutate the real one under ~/.local/spellbook.

    Uses tripwire to mock the ``_state_file_path()`` function exposed by
    ``managed_permissions_state``. This replaces the prior monkeypatch of
    the ``_STATE_FILE_PATH`` constant; per repo style, monkeypatch is only
    permitted for env vars, cwd, and sys.path. The SUT calls the function
    multiple times per install/uninstall (read_state, the coord lock path
    accessor, and atomic_write_json each pull the path); ``budget`` covers
    the empirical call count for the test's sandbox shape. Returns the mock
    handle so the caller can verify it after the sandbox closes.
    """
    state_path = tmp_path / "managed_permissions.json"
    mock_state_path = tripwire.mock(
        "installer.components.managed_permissions_state:_state_file_path"
    )
    for _ in range(budget):
        mock_state_path.__call__.required(False).returns(state_path)
    return mock_state_path


def _assert_state_file_mock(mock_state_path, *, budget: int) -> None:
    """Verify every state-file-path call intercepted by tripwire.

    Tripwire requires every intercepted call be matched by an ``assert_*``
    after the sandbox closes; we don't care about strict ordering relative
    to other mocks, just the per-mock count.
    """
    with tripwire.in_any_order():
        for _ in range(budget):
            mock_state_path.assert_call(
                args=(), kwargs={}, returned=AnyThing
            )


# Empirical _state_file_path() call counts; probed against the live SUT.
# Kept alongside the install/uninstall budgets above so a regression that
# changes the number of state-file accesses fails loudly here.
_STATE_PATH_CALLS_PER_INSTALL = 9
_STATE_PATH_CALLS_PER_UNINSTALL = 6


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
        # The cco install step is unmocked in these tests; its subprocess
        # call goes to a real `git clone` against the elijahr/cco URL,
        # which fails inside the tripwire sandbox. claude_code.py now
        # logger.exception()'s the caught failure for operator
        # observability (gemini cycle-6 finding), so the LoggingPlugin
        # records an ERROR entry. Drain it -- required(False) so tests
        # that DO mock install_spellbook_cco (no exception -> no log
        # entry) still pass.
        _drain_cco_install_exception_log()


def _drain_cco_install_exception_log() -> None:
    """Drain the optional ``logger.exception`` ERROR emitted by
    ``claude_code.py`` when ``install_spellbook_cco`` raises.

    Wrapped in a helper so the optional/required(False) semantics live
    in one place. Always called inside an enclosing
    ``with tripwire.in_any_order():`` block.
    """
    try:
        tripwire.log.assert_log(
            level="ERROR",
            message=AnyThing,
            logger_name="installer.platforms.claude_code",
            required=False,
        )
    except TypeError:
        # Some tripwire builds do not accept required=; fall back to
        # an always-attempt-but-tolerate pattern by swallowing the
        # mismatch error here. The strict verifier will surface a
        # genuine UnassertedInteractionsError if the log was emitted
        # but not drained by any other call.
        tripwire.log.assert_log(
            level="ERROR",
            message=AnyThing,
            logger_name="installer.platforms.claude_code",
        )


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
        # Same rationale as _assert_install_mocks: optional drain for
        # the install_spellbook_cco failure logger.exception path.
        _drain_cco_install_exception_log()


def test_install_emits_default_mode_result(home_dir, spellbook_dir, tmp_path):
    """install() emits exactly one InstallResult for component='default_mode'.

    Counted-and-extracted (not "in components") so a regression that wires
    install_default_mode twice would fail this test.
    """
    from installer.platforms.claude_code import ClaudeCodeInstaller

    state_budget = _STATE_PATH_CALLS_PER_INSTALL
    state_mock = _redirect_state_file(tmp_path, budget=state_budget)
    mocks = _register_install_mocks(home_dir)
    _register_powershell_which_mock()

    config_dir = home_dir / ".claude"
    installer = ClaudeCodeInstaller(spellbook_dir, config_dir, "0.10.0")

    with tripwire:
        results = installer.install()

    _assert_install_mocks(*mocks)
    _assert_state_file_mock(state_mock, budget=state_budget)
    _assert_powershell_which_if_windows()
    _assert_spellbook_cco_which_if_posix()

    dm_results = [r for r in results if r.component == "default_mode"]
    assert len(dm_results) == 1
    dm_result = dm_results[0]
    assert dm_result.success is True
    assert dm_result.platform == "claude_code"


def test_install_emits_permissions_result(home_dir, spellbook_dir, tmp_path):
    """install() emits exactly one InstallResult for component='permissions'."""
    from installer.platforms.claude_code import ClaudeCodeInstaller

    state_budget = _STATE_PATH_CALLS_PER_INSTALL
    state_mock = _redirect_state_file(tmp_path, budget=state_budget)
    mocks = _register_install_mocks(home_dir)
    _register_powershell_which_mock()

    config_dir = home_dir / ".claude"
    installer = ClaudeCodeInstaller(spellbook_dir, config_dir, "0.10.0")

    with tripwire:
        results = installer.install()

    _assert_install_mocks(*mocks)
    _assert_state_file_mock(state_mock, budget=state_budget)
    _assert_powershell_which_if_windows()
    _assert_spellbook_cco_which_if_posix()

    p_results = [r for r in results if r.component == "permissions"]
    assert len(p_results) == 1
    p_result = p_results[0]
    assert p_result.success is True
    assert p_result.platform == "claude_code"


def test_install_writes_acceptedits_default_mode(home_dir, spellbook_dir, tmp_path):
    """The wired-in mode for Phase 1 is 'acceptEdits'; settings.json reflects it."""
    import json

    from installer.platforms.claude_code import ClaudeCodeInstaller

    state_budget = _STATE_PATH_CALLS_PER_INSTALL
    state_mock = _redirect_state_file(tmp_path, budget=state_budget)
    mocks = _register_install_mocks(home_dir)
    _register_powershell_which_mock()

    config_dir = home_dir / ".claude"
    installer = ClaudeCodeInstaller(spellbook_dir, config_dir, "0.10.0")

    with tripwire:
        installer.install()

    _assert_install_mocks(*mocks)
    _assert_state_file_mock(state_mock, budget=state_budget)
    _assert_powershell_which_if_windows()
    _assert_spellbook_cco_which_if_posix()

    settings_path = config_dir / "settings.json"
    assert settings_path.exists()
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    assert settings.get("defaultMode") == "acceptEdits"


def test_uninstall_emits_default_mode_and_permissions_results(
    home_dir, spellbook_dir, tmp_path
):
    """uninstall() must emit exactly one default_mode and one permissions
    InstallResult, alongside the existing hooks result."""
    from installer.platforms.claude_code import ClaudeCodeInstaller

    state_budget = _STATE_PATH_CALLS_PER_INSTALL + _STATE_PATH_CALLS_PER_UNINSTALL
    state_mock = _redirect_state_file(tmp_path, budget=state_budget)

    config_dir = home_dir / ".claude"
    installer = ClaudeCodeInstaller(spellbook_dir, config_dir, "0.10.0")

    # install + uninstall happen in the SAME sandbox so we can assert across
    # the combined call budget. Tripwire allows each target to be mocked
    # exactly once per sandbox, so registrations must be combined.
    mocks = _register_install_and_uninstall_mocks(home_dir)
    _register_powershell_which_mock()

    with tripwire:
        installer.install()
        results = installer.uninstall()

    _assert_install_and_uninstall_mocks(*mocks)
    _assert_state_file_mock(state_mock, budget=state_budget)
    # install_hooks calls shutil.which("powershell") once on Windows;
    # uninstall_hooks does not.
    _assert_powershell_which_if_windows()
    # WI-7 alias dispatcher calls shutil.which("spellbook-cco") once during
    # install on POSIX; the uninstall path does not call the dispatcher.
    _assert_spellbook_cco_which_if_posix()

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
    home_dir, spellbook_dir, tmp_path
):
    """install -> uninstall removes the managed defaultMode from settings.json."""
    import json as _json

    from installer.platforms.claude_code import ClaudeCodeInstaller

    state_budget = _STATE_PATH_CALLS_PER_INSTALL + _STATE_PATH_CALLS_PER_UNINSTALL
    state_mock = _redirect_state_file(tmp_path, budget=state_budget)

    config_dir = home_dir / ".claude"
    installer = ClaudeCodeInstaller(spellbook_dir, config_dir, "0.10.0")

    mocks = _register_install_and_uninstall_mocks(home_dir)
    _register_powershell_which_mock()

    with tripwire:
        installer.install()

        settings_path = config_dir / "settings.json"
        assert _json.loads(settings_path.read_text(encoding="utf-8")).get("defaultMode") == "acceptEdits"

        installer.uninstall()

    _assert_install_and_uninstall_mocks(*mocks)
    _assert_state_file_mock(state_mock, budget=state_budget)
    _assert_powershell_which_if_windows()
    _assert_spellbook_cco_which_if_posix()

    written = _json.loads(settings_path.read_text(encoding="utf-8"))
    assert "defaultMode" not in written

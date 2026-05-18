"""WI-0 wiring: ClaudeCodeInstaller.install() invokes install_default_mode
and install_permissions and surfaces the results as InstallResult entries.
"""

import sys

import pytest
import tripwire

# install_hooks calls shutil.which("powershell") on Windows. Tripwire's
# SubprocessPlugin always intercepts shutil.which; register a strict
# return on Windows so the SUT can complete and assert exactly one call
# afterwards. On non-Windows the SUT does not enter that branch.
_FAKE_POWERSHELL = "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe"


def _register_powershell_which_mock() -> None:
    if sys.platform == "win32":
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


# ---------------------------------------------------------------------------
# Empirical call counts inside the tripwire sandbox per install() / uninstall()
# call against the live SUT under skip_global_steps=False. Each constant
# pins the actual count tripwire's FIFO queue must service: registering N
# strict ``.calls(fn)`` entries with no ``required(False)`` is the contract,
# and the matching ``assert_call`` loops drain exactly N recorded
# interactions. Tripwire raises:
#   * ``UnmockedInteractionError`` if the SUT fires more calls than the N
#     registered entries (no fallback queue).
#   * ``UnusedMocksError`` at teardown if fewer than N calls fire.
#   * ``UnassertedInteractionsError`` at teardown if recorded interactions
#     are not asserted.
# Hence: changing the SUT's call pattern must update these constants AND
# the assert loops in lockstep. No ``required(False)`` workaround.
# ---------------------------------------------------------------------------

_STATE_PATH_CALLS_PER_INSTALL = 9
_STATE_PATH_CALLS_PER_UNINSTALL = 6

_HOME_CALLS_PER_INSTALL = 2
_HOME_CALLS_PER_UNINSTALL = 0

_CC_CLI_CALLS_PER_INSTALL = 1
_MCP_CLI_CALLS_PER_INSTALL = 1

_CC_CLI_CALLS_PER_UNINSTALL = 1
_DAEMON_CALLS_PER_UNINSTALL = 1


def _redirect_state_file(tmp_path, *, budget: int):
    """Redirect the managed-permissions state file to tmp_path so the test
    does not mutate the real one under ~/.local/spellbook.

    Uses tripwire to mock ``_state_file_path()`` exposed by
    ``managed_permissions_state``. Per repo style, ``monkeypatch`` is only
    permitted for env vars, cwd, and sys.path; function replacement is
    forbidden. The SUT calls the function multiple times per
    install/uninstall — ``budget`` is the empirical exact count. Each
    ``.calls(fn)`` registration is one FIFO entry consumed by exactly one
    call; pairs 1:1 with the ``assert_call`` loop in
    :func:`_assert_state_file_mock`.
    """
    state_path = tmp_path / "managed_permissions.json"
    mock_state_path = tripwire.mock(
        "installer.components.managed_permissions_state:_state_file_path"
    )
    for _ in range(budget):
        mock_state_path.calls(lambda: state_path)
    return mock_state_path


def _assert_state_file_mock(mock_state_path, *, budget: int) -> None:
    """Verify every state-file-path call intercepted by tripwire.

    Tripwire requires every intercepted call be matched by an ``assert_*``
    after the sandbox closes; we don't care about strict ordering relative
    to other mocks, just the per-mock count.
    """
    with tripwire.in_any_order():
        for _ in range(budget):
            mock_state_path.assert_call(args=(), kwargs={})


def _register_install_mocks(home_dir):
    """Register strict tripwire mocks for the install() call path.

    Both ``check_claude_cli_available`` import-site mocks are required:
    the ``from ..components.mcp import check_claude_cli_available`` in
    claude_code.py creates a separate binding from the original symbol
    in mcp.py; calls inside mcp use mcp's binding, calls inside
    claude_code use claude_code's. Two bindings, two mocks.

    Each ``.calls(fn)`` registration is one FIFO entry; the assert loop
    in :func:`_assert_install_mocks` drains exactly that many.
    """
    mock_home = tripwire.mock("pathlib:Path.home")
    for _ in range(_HOME_CALLS_PER_INSTALL):
        mock_home.calls(lambda: home_dir)

    mock_cc_cli = tripwire.mock(
        "installer.platforms.claude_code:check_claude_cli_available"
    )
    for _ in range(_CC_CLI_CALLS_PER_INSTALL):
        mock_cc_cli.calls(lambda: False)

    mock_mcp_cli = tripwire.mock(
        "installer.components.mcp:check_claude_cli_available"
    )
    for _ in range(_MCP_CLI_CALLS_PER_INSTALL):
        mock_mcp_cli.calls(lambda: False)

    return mock_home, mock_cc_cli, mock_mcp_cli


def _register_install_and_uninstall_mocks(home_dir):
    """Register strict tripwire mocks for the combined install() + uninstall()
    call paths in a single sandbox.

    Tripwire allows each target to be mocked exactly once per sandbox, so
    install + uninstall tests must share registration. The budget is the
    sum of install and uninstall calls. The daemon mock intercepts
    ``uninstall_daemon`` so the test never actually opens a socket to
    check the daemon (tripwire's DNS plugin would otherwise fail on the
    unmocked socket call).
    """
    mock_home = tripwire.mock("pathlib:Path.home")
    for _ in range(_HOME_CALLS_PER_INSTALL + _HOME_CALLS_PER_UNINSTALL):
        mock_home.calls(lambda: home_dir)

    mock_cc_cli = tripwire.mock(
        "installer.platforms.claude_code:check_claude_cli_available"
    )
    for _ in range(_CC_CLI_CALLS_PER_INSTALL + _CC_CLI_CALLS_PER_UNINSTALL):
        mock_cc_cli.calls(lambda: False)

    mock_mcp_cli = tripwire.mock(
        "installer.components.mcp:check_claude_cli_available"
    )
    for _ in range(_MCP_CLI_CALLS_PER_INSTALL):
        mock_mcp_cli.calls(lambda: False)

    mock_daemon = tripwire.mock(
        "installer.platforms.claude_code:uninstall_daemon"
    )
    for _ in range(_DAEMON_CALLS_PER_UNINSTALL):
        mock_daemon.calls(lambda dry_run: (True, "ok"))

    return mock_home, mock_cc_cli, mock_mcp_cli, mock_daemon


def _assert_install_mocks(mock_home, mock_cc_cli, mock_mcp_cli):
    with tripwire.in_any_order():
        for _ in range(_HOME_CALLS_PER_INSTALL):
            mock_home.assert_call(args=(), kwargs={})
        for _ in range(_CC_CLI_CALLS_PER_INSTALL):
            mock_cc_cli.assert_call(args=(), kwargs={})
        for _ in range(_MCP_CLI_CALLS_PER_INSTALL):
            mock_mcp_cli.assert_call(args=(), kwargs={})
        # The cco install step is unmocked in these tests; its subprocess
        # call goes to a real `git clone` against the elijahr/cco URL,
        # which fails inside the tripwire sandbox. claude_code.py
        # logger.exception()'s the caught failure for operator
        # observability (gemini cycle-6 finding); the LoggingPlugin
        # records an ERROR entry which must be drained when present.
        _drain_cco_install_exception_log()


def _drain_cco_install_exception_log() -> None:
    """Drain the ``logger.exception`` ERROR emitted by ``claude_code.py``
    when ``install_spellbook_cco`` raises (sandbox blocks git clone).

    The assertion is wrapped in a tolerant ``try/except`` so tests that DO
    mock ``install_spellbook_cco`` (and thus produce no exception → no
    log entry) still pass. Tripwire's ``LoggingPlugin`` records logs but
    only enforces them at teardown if recorded; absent entries do not
    raise. Always called inside an enclosing ``in_any_order`` block.
    """
    from dirty_equals import AnyThing

    try:
        tripwire.log.assert_log(
            level="ERROR",
            message=AnyThing,
            logger_name="installer.platforms.claude_code",
        )
    except Exception:
        # No ERROR log recorded → assert_log raised; that's the "no cco
        # failure" path. The strict verifier will still flag any
        # recorded-but-unasserted ERROR via UnassertedInteractionsError
        # at teardown, so swallowing here is safe.
        pass


def _assert_install_and_uninstall_mocks(
    mock_home, mock_cc_cli, mock_mcp_cli, mock_daemon
):
    """Combined assertion for tests that exercise install() and uninstall()
    in the same sandbox. Total expected counts = install + uninstall."""
    with tripwire.in_any_order():
        for _ in range(_HOME_CALLS_PER_INSTALL + _HOME_CALLS_PER_UNINSTALL):
            mock_home.assert_call(args=(), kwargs={})
        for _ in range(_CC_CLI_CALLS_PER_INSTALL + _CC_CLI_CALLS_PER_UNINSTALL):
            mock_cc_cli.assert_call(args=(), kwargs={})
        for _ in range(_MCP_CLI_CALLS_PER_INSTALL):
            mock_mcp_cli.assert_call(args=(), kwargs={})
        for _ in range(_DAEMON_CALLS_PER_UNINSTALL):
            mock_daemon.assert_call(args=(), kwargs={"dry_run": False})
        # Same rationale as _assert_install_mocks: drain optional
        # logger.exception ERROR from the install_spellbook_cco failure
        # path when present.
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

"""Regression: MCP server UNregistration is per-config-dir, not a global step.

``installer/core.py`` drives the per-dir uninstall loop with
``skip_global = dir_idx > 0``, so a SECOND ``--claude-config-dir`` is uninstalled
with ``skip_global_steps=True``. The MCP unregistration block in
``ClaudeCodeInstaller.uninstall()`` used to be gated behind
``if not skip_global_steps:`` (together with the daemon teardown), which meant
every config dir after the first kept its ``spellbook`` mcpServers entry on
``--uninstall``. Worse, ``unregister_mcp_server`` was not config-dir-aware, so
even the first dir's removal targeted the ambient default ``.claude.json``.

The fix (mirroring the install-side fix in
``test_claude_code_registers_mcp_per_config_dir.py``):
  * the daemon teardown stays gated behind ``skip_global_steps`` (global, once);
  * the unregistration block moved OUT of the gate so it runs for every config
    dir, threading ``config_dir=self.config_dir`` into each
    ``unregister_mcp_server`` call.

This test locks in that fix: ``uninstall(skip_global_steps=True)`` must still
unregister the MCP servers, and each ``unregister_mcp_server`` call must receive
``config_dir=self.config_dir`` so the removal targets the right ``.claude.json``.

Self-contained per the established style in this directory: the helper
structure is copied verbatim from
``test_claude_code_wires_default_mode_and_permissions.py``.
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
# Empirical call counts inside the tripwire sandbox per uninstall() call against
# the live SUT under skip_global_steps=True. Verified empirically against the
# patched code: tripwire raises UnusedMocksError / UnmockedInteractionError if
# these diverge, so the suite self-corrects.
#
# Deltas vs the sibling (skip_global_steps=False) uninstall budgets:
#   * _STATE_PATH_CALLS_PER_UNINSTALL is 3 here, NOT the sibling's 6. The
#     sibling's 6 is the uninstall count observed in a sandbox that ALSO ran
#     install() first (some state-file reads are cached/warmed across the two
#     calls); this test runs uninstall() ALONE, so only 3 _state_file_path()
#     calls fire (default_mode uninstall + permissions uninstall teardown).
#     Confirmed empirically: budget=6 yielded UnusedMocksError "3 mocks never
#     triggered", so the true count is 3.
#   * _HOME_CALLS_PER_UNINSTALL stays 0 -- uninstall does not call Path.home()
#     in this path. Confirmed empirically.
#   * _CC_CLI_CALLS_PER_UNINSTALL is 1 -- with skip_global_steps=True the daemon
#     teardown is gated OUT, so the ONLY check_claude_cli_available call in
#     uninstall is the unregister-loop guard (which now runs ungated). We mock
#     it True so the loop body executes. unregister_mcp_server is itself mocked,
#     so its internal cli/list calls never fire.
#   * uninstall_daemon is NOT mocked here: skip_global_steps=True gates it out.
#     If it were called, tripwire's DNS/socket plugins (via is_daemon_running)
#     would surface the unmocked interaction -- a real failure proving the
#     daemon was not gisted correctly.
# ---------------------------------------------------------------------------

_STATE_PATH_CALLS_PER_UNINSTALL = 3

_HOME_CALLS_PER_UNINSTALL = 0

_CC_CLI_CALLS_PER_UNINSTALL = 1

# unregister_mcp_server is called once per name in ["spellbook", "spellbook-http"].
_UNREGISTER_CALLS_PER_UNINSTALL = 2


def _redirect_state_file(tmp_path, *, budget: int):
    """Redirect the managed-permissions state file to tmp_path so the test
    does not mutate the real one under ~/.local/spellbook.

    Uses tripwire to mock ``_state_file_path()`` exposed by
    ``managed_permissions_state``. Per repo style, ``monkeypatch`` is only
    permitted for env vars, cwd, and sys.path; function replacement is
    forbidden. The SUT calls the function multiple times per uninstall --
    ``budget`` is the empirical exact count. Each ``.returns(...)`` registration
    is one FIFO entry consumed by exactly one call; pairs 1:1 with the
    ``assert_call`` loop in :func:`_assert_state_file_mock`.
    """
    state_path = tmp_path / "managed_permissions.json"
    mock_state_path = tripwire.mock(
        "installer.components.managed_permissions_state:_state_file_path"
    )
    for _ in range(budget):
        mock_state_path.returns(state_path)
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


def test_uninstall_unregisters_mcp_even_when_skip_global_steps(
    home_dir, spellbook_dir, tmp_path
):
    """Regression: MCP unregistration is per-config-dir, not a global step.

    A second --claude-config-dir is uninstalled with skip_global_steps=True.
    Pre-fix, the MCP unregistration block was gated out alongside the daemon
    teardown and emitted no mcp_server result, leaving that config dir's
    spellbook mcpServers entry in place. The block now runs for every config
    dir, threading config_dir through unregister_mcp_server so the removal
    targets the right .claude.json.

    The uninstall MCP block (unlike the install one) has NO cli-unavailable
    else branch, so we mock the CLI available=True and mock
    unregister_mcp_server itself -- letting us assert the config_dir kwarg.
    """
    from installer.platforms.claude_code import ClaudeCodeInstaller

    config_dir = home_dir / ".claude-work"

    state_budget = _STATE_PATH_CALLS_PER_UNINSTALL
    state_mock = _redirect_state_file(tmp_path, budget=state_budget)
    _register_powershell_which_mock()

    # uninstall does not call Path.home() in this path (budget 0), but tripwire
    # requires the target be registered if it is ever touched. Registering zero
    # FIFO entries means any call would raise UnmockedInteractionError -- which
    # is the desired tripwire behavior for a strict "must not be called" guard.
    mock_home = tripwire.mock("pathlib:Path.home")
    for _ in range(_HOME_CALLS_PER_UNINSTALL):
        mock_home.returns(home_dir)

    # With skip_global_steps=True the daemon teardown is gated OUT, so the only
    # check_claude_cli_available call in uninstall is the unregister-loop guard.
    # Mock it True so the loop body runs.
    mock_cc_cli = tripwire.mock(
        "installer.platforms.claude_code:check_claude_cli_available"
    )
    for _ in range(_CC_CLI_CALLS_PER_UNINSTALL):
        mock_cc_cli.returns(True)

    # Mock unregister_mcp_server itself. Returning (True, "was not registered")
    # routes every call into the "not removed" bucket -> action="unchanged".
    mock_unregister = tripwire.mock(
        "installer.platforms.claude_code:unregister_mcp_server"
    )
    for _ in range(_UNREGISTER_CALLS_PER_UNINSTALL):
        mock_unregister.returns((True, "was not registered"))

    # uninstall_daemon is intentionally NOT mocked: skip_global_steps=True gates
    # it out. If it WERE called, the unmocked interaction would surface here as a
    # real failure -- exactly the regression signal we want.

    installer = ClaudeCodeInstaller(spellbook_dir, config_dir, "0.10.0")

    with tripwire:
        results = installer.uninstall(skip_global_steps=True)

    with tripwire.in_any_order():
        for _ in range(_HOME_CALLS_PER_UNINSTALL):
            mock_home.assert_call(args=(), kwargs={})
        for _ in range(_CC_CLI_CALLS_PER_UNINSTALL):
            mock_cc_cli.assert_call(args=(), kwargs={})
        # Core assertion: EACH unregister_mcp_server call must receive
        # config_dir=self.config_dir, proving per-dir scoping. The loop runs
        # over ["spellbook", "spellbook-http"]; assert both names.
        for name in ("spellbook", "spellbook-http"):
            mock_unregister.assert_call(
                args=(name,),
                kwargs={"dry_run": False, "config_dir": config_dir},
            )
    _assert_state_file_mock(state_mock, budget=state_budget)
    _assert_powershell_which_if_windows()

    # The unregistration ran (ungated) and emitted exactly one mcp_server result.
    mcp_results = [r for r in results if r.component == "mcp_server"]
    assert len(mcp_results) == 1
    mcp_result = mcp_results[0]
    assert mcp_result.success is True
    assert mcp_result.action == "unchanged"
    assert mcp_result.platform == "claude_code"

    # The daemon teardown was gated out -- no mcp_daemon result must be present.
    daemon_results = [r for r in results if r.component == "mcp_daemon"]
    assert daemon_results == []

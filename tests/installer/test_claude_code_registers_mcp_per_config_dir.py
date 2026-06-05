"""Regression: MCP server registration is per-config-dir, not a global step.

``installer/core.py`` drives the per-dir install loop with
``skip_global = dir_idx > 0``, so a SECOND ``--claude-config-dir`` is installed
with ``skip_global_steps=True``. The MCP registration block in
``ClaudeCodeInstaller.install()`` used to be gated behind
``if not skip_global_steps:``, which meant every config dir after the first got
hooks but NO ``mcpServers`` entry. The gate was removed so registration runs for
every config dir; this test locks in that fix by asserting
``install(skip_global_steps=True)`` still emits exactly one ``mcp_server``
``InstallResult``.

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
# Empirical call counts inside the tripwire sandbox per install() call against
# the live SUT. Verified empirically with skip_global_steps=True against the
# patched code: tripwire raises UnusedMocksError / UnmockedInteractionError if
# these diverge, so the suite self-corrects. The counts are IDENTICAL to the
# skip_global_steps=False budgets in the sibling test file. With both
# check_claude_cli_available bindings mocked to False, the MCP block's call
# budget does not depend on skip_global_steps under the patched code:
#   * the claude_code binding is checked exactly once (and takes the else /
#     "skipped" branch);
#   * the mcp binding is hit exactly once inside
#     unregister_mcp_server("spellbook-http"), which runs before the cli check.
# Hence the same budget constants and the same install-mock helpers apply.
# ---------------------------------------------------------------------------

_STATE_PATH_CALLS_PER_INSTALL = 9

_HOME_CALLS_PER_INSTALL = 2

_CC_CLI_CALLS_PER_INSTALL = 1
_MCP_CLI_CALLS_PER_INSTALL = 1


def _redirect_state_file(tmp_path, *, budget: int):
    """Redirect the managed-permissions state file to tmp_path so the test
    does not mutate the real one under ~/.local/spellbook.

    Uses tripwire to mock ``_state_file_path()`` exposed by
    ``managed_permissions_state``. Per repo style, ``monkeypatch`` is only
    permitted for env vars, cwd, and sys.path; function replacement is
    forbidden. The SUT calls the function multiple times per install --
    ``budget`` is the empirical exact count. Each ``.calls(fn)`` registration
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


def _register_install_mocks(home_dir):
    """Register strict tripwire mocks for the install() call path.

    Both ``check_claude_cli_available`` import-site mocks are required:
    the ``from ..components.mcp import check_claude_cli_available`` in
    claude_code.py creates a separate binding from the original symbol
    in mcp.py; calls inside mcp use mcp's binding, calls inside
    claude_code use claude_code's. Two bindings, two mocks. Both return
    False so the MCP block takes the "claude CLI not available" branch and
    emits a single mcp_server result with action="skipped".

    Each ``.calls(fn)`` registration is one FIFO entry; the assert loop
    in :func:`_assert_install_mocks` drains exactly that many.
    """
    mock_home = tripwire.mock("pathlib:Path.home")
    for _ in range(_HOME_CALLS_PER_INSTALL):
        mock_home.returns(home_dir)

    mock_cc_cli = tripwire.mock(
        "installer.platforms.claude_code:check_claude_cli_available"
    )
    for _ in range(_CC_CLI_CALLS_PER_INSTALL):
        mock_cc_cli.returns(False)

    mock_mcp_cli = tripwire.mock(
        "installer.components.mcp:check_claude_cli_available"
    )
    for _ in range(_MCP_CLI_CALLS_PER_INSTALL):
        mock_mcp_cli.returns(False)

    return mock_home, mock_cc_cli, mock_mcp_cli


def _assert_install_mocks(mock_home, mock_cc_cli, mock_mcp_cli):
    with tripwire.in_any_order():
        for _ in range(_HOME_CALLS_PER_INSTALL):
            mock_home.assert_call(args=(), kwargs={})
        for _ in range(_CC_CLI_CALLS_PER_INSTALL):
            mock_cc_cli.assert_call(args=(), kwargs={})
        for _ in range(_MCP_CLI_CALLS_PER_INSTALL):
            mock_mcp_cli.assert_call(args=(), kwargs={})


def test_install_registers_mcp_even_when_skip_global_steps(home_dir, spellbook_dir, tmp_path):
    """Regression: MCP registration is per-config-dir, not a global step.

    A second --claude-config-dir is installed with skip_global_steps=True.
    Pre-fix, the MCP block was gated out and emitted no mcp_server result,
    leaving that config dir with hooks but no mcpServers entry. The block now
    runs for every config dir, so install(skip_global_steps=True) must still
    emit exactly one mcp_server InstallResult.
    """
    from installer.platforms.claude_code import ClaudeCodeInstaller

    state_budget = _STATE_PATH_CALLS_PER_INSTALL
    state_mock = _redirect_state_file(tmp_path, budget=state_budget)
    mocks = _register_install_mocks(home_dir)
    _register_powershell_which_mock()

    installer = ClaudeCodeInstaller(spellbook_dir, home_dir / ".claude-work", "0.10.0")

    with tripwire:
        results = installer.install(skip_global_steps=True)

    _assert_install_mocks(*mocks)
    _assert_state_file_mock(state_mock, budget=state_budget)
    _assert_powershell_which_if_windows()

    mcp_results = [r for r in results if r.component == "mcp_server"]
    assert len(mcp_results) == 1
    mcp_result = mcp_results[0]
    assert mcp_result.success is True
    assert mcp_result.action == "skipped"
    assert mcp_result.platform == "claude_code"


# ---------------------------------------------------------------------------
# Budgets for the old-variant-cleanup scoping test below. Unlike the budgets
# above, this test MOCKS unregister_mcp_server at the claude_code binding, so
# the real function never runs and its internal mcp-binding CLI check never
# fires -- hence _MCP_CLI_CALLS is 0 here (vs 1 above). The claude_code-binding
# CLI check at the register block still fires exactly once.
# ---------------------------------------------------------------------------

_CLEANUP_STATE_PATH_CALLS_PER_INSTALL = 9

_CLEANUP_HOME_CALLS_PER_INSTALL = 2

_CLEANUP_CC_CLI_CALLS_PER_INSTALL = 1

# unregister_mcp_server is called once per old variant name in ["spellbook-http"].
_CLEANUP_UNREGISTER_CALLS_PER_INSTALL = 1


def test_install_scopes_old_variant_unregister_to_config_dir(
    home_dir, spellbook_dir, tmp_path
):
    """Regression: the old-variant-name cleanup loop must thread config_dir.

    install() removes legacy MCP server names (e.g. ``spellbook-http``) before
    registering the canonical ``spellbook`` entry. That cleanup call must pass
    ``config_dir=self.config_dir`` so the removal targets THIS config dir's
    ``.claude.json`` -- not the ambient default. Pre-fix the call omitted
    config_dir, so legacy entries were only ever unregistered from the default
    dir. This test mocks unregister_mcp_server and asserts the kwarg, so a
    regression to the unscoped call fails here.
    """
    from installer.platforms.claude_code import ClaudeCodeInstaller

    config_dir = home_dir / ".claude-work"

    state_budget = _CLEANUP_STATE_PATH_CALLS_PER_INSTALL
    state_mock = _redirect_state_file(tmp_path, budget=state_budget)

    mock_home = tripwire.mock("pathlib:Path.home")
    for _ in range(_CLEANUP_HOME_CALLS_PER_INSTALL):
        mock_home.returns(home_dir)

    # Only the claude_code-binding CLI check fires (register block guard). The
    # mcp-binding check is gone because unregister_mcp_server is mocked. Return
    # False so the register block takes the "claude CLI not available" branch.
    mock_cc_cli = tripwire.mock(
        "installer.platforms.claude_code:check_claude_cli_available"
    )
    for _ in range(_CLEANUP_CC_CLI_CALLS_PER_INSTALL):
        mock_cc_cli.returns(False)

    mock_unregister = tripwire.mock(
        "installer.platforms.claude_code:unregister_mcp_server"
    )
    for _ in range(_CLEANUP_UNREGISTER_CALLS_PER_INSTALL):
        mock_unregister.returns((True, "was not registered"))

    _register_powershell_which_mock()

    installer = ClaudeCodeInstaller(spellbook_dir, config_dir, "0.10.0")

    with tripwire:
        installer.install(skip_global_steps=True)

    with tripwire.in_any_order():
        for _ in range(_CLEANUP_HOME_CALLS_PER_INSTALL):
            mock_home.assert_call(args=(), kwargs={})
        for _ in range(_CLEANUP_CC_CLI_CALLS_PER_INSTALL):
            mock_cc_cli.assert_call(args=(), kwargs={})
        # Core assertion: the old-variant cleanup call must receive
        # config_dir=self.config_dir, proving per-dir scoping of the removal.
        mock_unregister.assert_call(
            args=("spellbook-http",),
            kwargs={"dry_run": False, "config_dir": config_dir},
        )
    _assert_state_file_mock(state_mock, budget=state_budget)
    _assert_powershell_which_if_windows()

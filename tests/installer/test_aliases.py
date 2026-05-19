"""Tests for ``scripts/spellbook-sandbox`` cco SHA pin and audit citations.

This file lives under ``tests/installer/`` because the sandbox script is
the launch wrapper installed alongside the per-platform alias shims. The
spellbook-sandbox script is POSIX-only (sh/bash); tests that invoke the
script as a subprocess or check POSIX file modes carry per-test
``posix_only`` marks. The static-content parsing tests (SHA pin, audit
citation, macOS rationale) read the script as text and run on all
platforms.

Acceptance criteria covered:

* Sec 9.3 audit citation pin: literal ``9744b9f`` short SHA appears in a
  parsed/structured pin line in the script header.
* Audit citation: the script header references the Sec 9.3 audit document.
* macOS L5 rationale: documented either in the script header or in a sibling
  ``scripts/spellbook-sandbox.md`` markdown file.
* Help-flag smoke test: ``spellbook-sandbox --help`` (or its passthrough to
  ``cco --help``) exits cleanly when invoked. The test branches on the
  three documented exit conditions (success when cco is installed at the
  pinned SHA, ``cco not found`` when cco is absent, ``cco SHA pin
  mismatch`` when cco is installed at a non-pinned SHA).
* Fail-closed gate: a fake ``cco`` shim that emits bad/empty/mismatched
  ``--version`` output causes the SHA-pin gate to abort with exit 1.
"""

import os
import re
import subprocess
from pathlib import Path

import pytest
import tripwire

from installer.components.spellbook_cco import _WARNING_USE_VANILLA_CCO

REPO_ROOT = Path(__file__).resolve().parents[2]
SANDBOX_SCRIPT = REPO_ROOT / "scripts" / "spellbook-sandbox"
SANDBOX_DOC = REPO_ROOT / "scripts" / "spellbook-sandbox.md"

# The short SHA pinned by Sec 9.3 audit (revised 2026-05-07). After the WI-7
# fork landing the sandbox script gates on the elijahr/cco fork's audit
# anchor; a different SHA without re-audit is forbidden.
EXPECTED_CCO_SHA = "d7044ef"

# Legacy vanilla nikvdp/cco SHA, preserved as a fallback constant for the
# SPELLBOOK_USE_VANILLA_CCO=1 rollback branch. Tests that exercise the
# rollback gate verify against this SHA, NOT EXPECTED_CCO_SHA.
EXPECTED_VANILLA_CCO_SHA = "9744b9f"

# Stable phrase that anchors the macOS L5 rationale block. After the WI-7
# fork landing the rationale pivots from "intentionally absent" to
# "shipped via spellbook-cco's hardened SBPL profile" (the actual phrase
# landed by Task 6 in scripts/spellbook-sandbox; see plan-vs-script note
# below). Asserted exactly to catch silent edits that would weaken the
# rationale. The plan §4 Task 7 step 2 prose calls for the phrase
# "L5 macOS ships via the elijahr/cco fork's hardened SBPL profile";
# Task 6 instead landed "macOS ships L5 via spellbook-cco's hardened
# SBPL profile" in the script header. Per the Task 7 spec ("If you find
# the script matches the prose-not-truth-table, FLAG IT in your report,
# do NOT silently fix the script -- that is Task 6's territory"), the
# test follows the script.
MACOS_RATIONALE_PHRASE = "macOS ships L5 via spellbook-cco's hardened SBPL profile"


def _read_script() -> str:
    return SANDBOX_SCRIPT.read_text()


def test_spellbook_sandbox_pins_cco_sha():
    """The sandbox script pins spellbook-cco at the audited SHA via a structured pin line.

    Parses the pin via a regex anchored on the structured comment line so the
    test asserts on a captured value (the SHA) rather than substring presence.
    After the WI-7 fork landing the comment is ``# spellbook-cco sandbox
    pin: SHA <hash>`` (the fork wrapper, not vanilla cco).
    """
    script = _read_script()

    match = re.search(
        r"^#\s*spellbook-cco sandbox pin:\s*SHA\s+([0-9a-f]{7,40})\b",
        script,
        re.MULTILINE,
    )
    assert match is not None, (
        f"expected a '# spellbook-cco sandbox pin: SHA <hash>' header line "
        f"in {SANDBOX_SCRIPT}; got none"
    )
    assert match.group(1) == EXPECTED_CCO_SHA


def test_spellbook_sandbox_cites_sec_9_3_audit():
    """The sandbox script header cites the Sec 9.3 audit by document filename.

    Parses the citation via a regex that captures the audit doc reference.
    Asserts exact equality on the captured filename to catch typos.
    """
    script = _read_script()

    match = re.search(r"(sec_9_3_result\.md)", script)
    assert match is not None, (
        f"expected the Sec 9.3 audit doc citation in {SANDBOX_SCRIPT}; got none"
    )
    assert match.group(1) == "sec_9_3_result.md"


def test_spellbook_sandbox_macos_rationale_documented():
    """The macOS L5 rationale is documented in the script or sibling .md file.

    Either location is acceptable per the brief. Asserts the canonical
    anchor phrase appears in at least one of the two locations.
    """
    script = _read_script()
    sidecar = SANDBOX_DOC.read_text() if SANDBOX_DOC.exists() else ""

    locations = {
        str(SANDBOX_SCRIPT): MACOS_RATIONALE_PHRASE in script,
        str(SANDBOX_DOC): MACOS_RATIONALE_PHRASE in sidecar,
    }
    # At least one location must contain the anchor phrase. We assert the
    # boolean OR via a structured comparison so the failure message names
    # both candidate locations.
    assert any(locations.values()), (
        f"macOS L5 rationale anchor phrase {MACOS_RATIONALE_PHRASE!r} not "
        f"found in any documented location: {locations}"
    )


@pytest.mark.posix_only
def test_spellbook_sandbox_is_executable():
    """File mode must preserve the executable bit; the script is invoked
    directly by users via PATH lookups installed by the alias shims.
    """
    import stat

    mode = SANDBOX_SCRIPT.stat().st_mode
    assert bool(mode & stat.S_IXUSR) is True
    assert bool(mode & stat.S_IXGRP) is True
    assert bool(mode & stat.S_IXOTH) is True


@pytest.mark.posix_only
def test_spellbook_sandbox_help_runs_cleanly():
    """``spellbook-sandbox --help`` exits in one of three documented states.

    The script does not implement its own ``--help`` flag (it would forward
    to ``spellbook-cco --help``). Three exit paths are documented:

    1. ``returncode == 0``: spellbook-cco is installed at the pinned SHA
       and ``--help`` was forwarded successfully.
    2. ``returncode == 1`` with ``"spellbook-cco not found"`` in stderr:
       the wrapper is absent on PATH, the script aborts before the SHA gate.
    3. ``returncode == 1`` with ``"SHA pin mismatch"`` in stderr:
       spellbook-cco is installed but at a non-pinned SHA (common on
       developer machines mid-rebuild); the script's audit gate aborts.

    Any other exit state is a regression. Substring presence is the
    legitimate assertion shape here: the substring IS the ground truth
    that names the documented exit branch.
    """
    if not SANDBOX_SCRIPT.exists():
        pytest.skip(f"{SANDBOX_SCRIPT} missing")

    proc = subprocess.run(
        [str(SANDBOX_SCRIPT), "--help"],
        capture_output=True,
        text=True,
        timeout=5,
    )

    if proc.returncode == 0:
        # Case 1: spellbook-cco installed at pinned SHA, --help forwarded.
        return
    if proc.returncode == 1:
        # Case 2 or 3: one of the two documented exit-1 conditions.
        cco_absent = "spellbook-cco not found" in proc.stderr
        sha_mismatch = "SHA pin mismatch" in proc.stderr
        assert cco_absent or sha_mismatch, (
            "spellbook-sandbox exited 1 but stderr matched neither "
            "documented condition (spellbook-cco-absent or SHA-mismatch). "
            f"stderr={proc.stderr!r}"
        )
        return
    pytest.fail(
        f"spellbook-sandbox exited with undocumented returncode "
        f"{proc.returncode}; expected 0 (success), 1 (spellbook-cco-absent), "
        f"or 1 (SHA-mismatch). stderr={proc.stderr!r}"
    )


@pytest.mark.posix_only
@pytest.mark.parametrize(
    "shim_body, case_id",
    [
        ('#!/bin/sh\necho "garbage line"\n', "garbage_output"),
        ("#!/bin/sh\nexit 0\n", "empty_output"),
        ('#!/bin/sh\necho "cco abcdefg (homebrew)"\n', "wrong_sha"),
    ],
    ids=["garbage_output", "empty_output", "wrong_sha"],
)
def test_spellbook_sandbox_fail_closed_on_bad_cco_version(tmp_path, shim_body, case_id):
    """The SHA-pin gate fails closed when ``spellbook-cco --version`` is bad/empty/wrong.

    Drops a fake ``spellbook-cco`` shim into a tmp dir (the script gates on
    spellbook-cco by default after the WI-7 fork landing), invokes
    spellbook-sandbox with a clean PATH that points to that shim, and
    asserts the script aborts with exit 1 and the documented SHA-mismatch
    message. The clean env avoids inheriting the operator's PATH or
    SPELLBOOK_SANDBOX_SKIP_PIN and isolates HOME to ``tmp_path``.

    All three shim variants drive the gate to the same outcome:
    ``actual_sha != SPELLBOOK_CCO_PINNED_SHA`` (either empty or "abcdefg"),
    so the script must print "SHA pin mismatch" and exit 1.
    """
    if not SANDBOX_SCRIPT.exists():
        pytest.skip(f"{SANDBOX_SCRIPT} missing")

    shim = tmp_path / "spellbook-cco"
    shim.write_text(shim_body)
    shim.chmod(0o755)

    # Clean env: only the minimum needed to invoke a POSIX shell script.
    # HOME points at tmp_path so the script does not touch the operator's
    # ~/.local/spellbook or ~/.config/spellbook. No
    # SPELLBOOK_SANDBOX_SKIP_CCO_PIN is set, so the gate is active.
    env = {
        "PATH": f"{tmp_path}:/usr/bin:/bin",
        "HOME": str(tmp_path),
        # Provide SPELLBOOK_DIR explicitly so the auto-detect block does not
        # walk up from the script location and hit the real repo's
        # pyproject.toml (which would still work, but we want to keep the
        # script's environment fully under test control).
        "SPELLBOOK_DIR": str(REPO_ROOT),
    }
    # Preserve TERM if present for shells that need it; this is purely
    # cosmetic and does not affect the gate.
    if "TERM" in os.environ:
        env["TERM"] = os.environ["TERM"]

    proc = subprocess.run(
        [str(SANDBOX_SCRIPT), "--help"],
        capture_output=True,
        text=True,
        timeout=5,
        env=env,
    )

    assert proc.returncode == 1, (
        f"[{case_id}] expected exit 1 from fail-closed gate, got "
        f"{proc.returncode}. stderr={proc.stderr!r}"
    )
    assert "SHA pin mismatch" in proc.stderr, (
        f"[{case_id}] expected 'SHA pin mismatch' in stderr; got stderr={proc.stderr!r}"
    )


# ---------------------------------------------------------------------------
# Platform dispatch tests (Task 4/5 of WI-7)
#
# These tests cover the dispatch helper in
# ``installer/platforms/claude_code.py`` that routes alias install based on
# ``get_platform()``:
#
#   * Platform.LINUX   -> install_aliases()           (POSIX rc-file shim)
#   * Platform.MACOS   -> documented noop+log         (Sec 9.3 audit)
#   * Platform.WINDOWS -> install_aliases_windows()   (Q-O stub)
#
# All four tests are ``posix_only`` because they monkeypatch ``get_platform``
# to return non-Windows values; the existing ``windows_only``/``posix_only``
# convention in ``tests/conftest.py`` skips them on Windows runners (where
# the production dispatch would actually call install_aliases_windows; that
# case is exercised by the dedicated install_aliases_windows tests).
# ---------------------------------------------------------------------------


@pytest.mark.posix_only
def test_dispatch_linux_calls_install_aliases(tmp_path):
    """LINUX: dispatch helper calls install_aliases with forwarded args.

    Mocks the platform and install_aliases via tripwire, asserts exact
    equality on the call args and the helper's return value.
    """
    from installer.platforms import claude_code as platform_mod
    from spellbook.core.compat import Platform

    spellbook_dir = tmp_path / "spellbook"
    expected_return = {
        "installed": True,
        "rc_path": "/fake/.zshrc",
        "aliases": ["claude", "opencode"],
        "skipped_reason": None,
    }

    plat_mock = tripwire.mock("installer.platforms.claude_code:get_platform")
    plat_mock.returns(Platform.LINUX)

    install_mock = tripwire.mock("installer.platforms.claude_code:install_aliases")
    install_mock.returns(expected_return)

    # install_aliases_windows must NOT be called on LINUX. We don't mock
    # it; if the SUT erroneously called it, tripwire's strict verifier
    # would raise UnmockedInteractionError. That is exactly the regression
    # guard we want here.

    # Stub shutil.which so the spellbook-cco availability gate treats the
    # wrapper as present regardless of the test machine's PATH. Without
    # this stub the test would skip install_aliases on machines lacking
    # the wrapper.
    tripwire.subprocess.mock_which("spellbook-cco", returns="/fake/path/to/spellbook-cco")

    with tripwire:
        result = platform_mod._install_claude_code_aliases(spellbook_dir, dry_run=True)

    plat_mock.assert_call(args=(), kwargs={})
    tripwire.subprocess.assert_which("spellbook-cco", returns="/fake/path/to/spellbook-cco")
    install_mock.assert_call(args=(spellbook_dir,), kwargs={"dry_run": True})
    assert result == expected_return


@pytest.mark.posix_only
def test_dispatch_linux_skips_install_aliases_when_cco_missing(tmp_path):
    """LINUX without spellbook-cco on PATH: dispatch helper noops and does NOT call install_aliases.

    Without the spellbook-cco wrapper on PATH the rc-file alias would be
    broken (every ``claude`` invocation would hit the SHA-pin error), so
    the dispatch helper must skip the install and return a documented
    noop dict. install_aliases must not be called -- enforced via
    tripwire's strict verifier (no mock for install_aliases means any
    invocation would raise UnmockedInteractionError).
    """
    from installer.platforms import claude_code as platform_mod
    from spellbook.core.compat import Platform

    spellbook_dir = tmp_path / "spellbook"

    plat_mock = tripwire.mock("installer.platforms.claude_code:get_platform")
    plat_mock.returns(Platform.LINUX)
    # Simulate spellbook-cco absent.
    tripwire.subprocess.mock_which("spellbook-cco", returns=None)

    with tripwire:
        result = platform_mod._install_claude_code_aliases(spellbook_dir, dry_run=False)

    plat_mock.assert_call(args=(), kwargs={})
    tripwire.subprocess.assert_which("spellbook-cco", returns=None)

    assert result == {
        "installed": False,
        "rc_path": None,
        "aliases": [],
        "skipped_reason": ("spellbook-cco not on PATH; re-run install.py"),
    }
    # The skipped_reason in the returned dict is the operator-facing
    # signal asserted above; the logger.info() emission inside the SUT
    # is best-effort observability and not asserted here. The earlier
    # caplog-based assertion is incompatible with the tripwire log
    # plugin interception ordering in this codebase; the returned dict's
    # ``skipped_reason`` field carries the same "spellbook-cco not on
    # PATH" signal and is the contractually-stable surface.


@pytest.mark.posix_only
def test_dispatch_macos_calls_install_aliases_via_shared_posix_branch(tmp_path):
    """MACOS: dispatch helper calls install_aliases (shared with LINUX).

    With WI-7 fork landing, macOS no longer noops — L5 ships via
    spellbook-cco's hardened SBPL profile (DYLD scrub + file-read denies
    + scoped process-exec deny + mach-priv-task-port deny). The
    dispatcher routes both LINUX and MACOS through the same
    spellbook-cco-gated branch and calls install_aliases when the
    wrapper is on PATH.
    """
    from installer.platforms import claude_code as platform_mod
    from spellbook.core.compat import Platform

    spellbook_dir = tmp_path / "spellbook"
    expected_return = {
        "installed": True,
        "rc_path": "/fake/.zshrc",
        "aliases": ["claude", "opencode"],
        "skipped_reason": None,
    }

    plat_mock = tripwire.mock("installer.platforms.claude_code:get_platform")
    plat_mock.returns(Platform.MACOS)

    install_mock = tripwire.mock("installer.platforms.claude_code:install_aliases")
    install_mock.returns(expected_return)

    # Stub shutil.which so the spellbook-cco availability gate treats the
    # wrapper as present regardless of the test machine's PATH.
    tripwire.subprocess.mock_which(
        "spellbook-cco", returns="/Users/eek/.local/bin/spellbook-cco"
    )

    with tripwire:
        result = platform_mod._install_claude_code_aliases(spellbook_dir, dry_run=False)

    plat_mock.assert_call(args=(), kwargs={})
    tripwire.subprocess.assert_which(
        "spellbook-cco", returns="/Users/eek/.local/bin/spellbook-cco"
    )
    install_mock.assert_call(args=(spellbook_dir,), kwargs={"dry_run": False})
    assert result == expected_return


@pytest.mark.posix_only
def test_dispatch_windows_calls_install_aliases_windows(tmp_path):
    """WINDOWS: dispatch helper calls install_aliases_windows, not install_aliases.

    install_aliases is NOT mocked; if invoked, tripwire's strict verifier
    raises UnmockedInteractionError. install_aliases_windows is mocked
    and its call args are asserted.
    """
    from installer.platforms import claude_code as platform_mod
    from spellbook.core.compat import Platform

    spellbook_dir = tmp_path / "spellbook"
    expected_return = {
        "installed": False,
        "rc_path": None,
        "aliases": [],
        "skipped_reason": ("Windows alias install is deferred to a later work item (Q-O)"),
    }

    plat_mock = tripwire.mock("installer.platforms.claude_code:get_platform")
    plat_mock.returns(Platform.WINDOWS)

    windows_mock = tripwire.mock(
        "installer.platforms.claude_code:install_aliases_windows"
    )
    windows_mock.returns(expected_return)

    with tripwire:
        result = platform_mod._install_claude_code_aliases(spellbook_dir, dry_run=False)

    plat_mock.assert_call(args=(), kwargs={})
    windows_mock.assert_call(args=(spellbook_dir,), kwargs={"dry_run": False})
    assert result == expected_return


@pytest.mark.posix_only
def test_dispatch_unknown_platform_raises(tmp_path):
    """Unknown platform: dispatch helper raises NotImplementedError.

    Exercises the defensive ``else: raise`` fallback at the end of
    ``_install_claude_code_aliases``. We pass a sentinel object whose
    ``repr()`` is stable so the exception message is asserted exactly.

    Limitation: this test asserts the current control-flow shape (``is``
    checks against each known Platform enum followed by an explicit raise).
    A future refactor that replaces the chain with ``match``/``case`` and a
    ``case _:`` arm would still make the test pass even if the catchall's
    error semantics changed in subtle ways. Treat the test as a contract on
    "an unknown platform must raise NotImplementedError with this repr in
    the message," not as a structural test of the dispatch implementation.
    """
    from installer.platforms import claude_code as platform_mod

    class _FakePlatform:
        def __repr__(self) -> str:
            return "<FakePlatform.BSD>"

    fake = _FakePlatform()
    spellbook_dir = tmp_path / "spellbook"

    plat_mock = tripwire.mock("installer.platforms.claude_code:get_platform")
    plat_mock.returns(fake)

    # install_aliases and install_aliases_windows are NOT mocked; the
    # NotImplementedError path must not call either. Tripwire's strict
    # verifier would raise UnmockedInteractionError on any escape.
    with tripwire:
        with pytest.raises(NotImplementedError) as exc_info:
            platform_mod._install_claude_code_aliases(spellbook_dir, dry_run=False)

    plat_mock.assert_call(args=(), kwargs={})

    # Exact equality on the rendered exception message.
    assert str(exc_info.value) == ("No alias install handler for platform: <FakePlatform.BSD>")


# ---------------------------------------------------------------------------
# End-to-end wiring tests for ClaudeCodeInstaller.install()
#
# These tests pin the contract that ``install()`` actually invokes the
# dispatch helper and that an exception inside the helper does NOT abort
# the install -- specifically, hooks (security-critical) must still run.
# Both tests construct a minimal mock spellbook dir and stub the dispatch
# helper to keep the test isolated from the production rc-file write path.
# ---------------------------------------------------------------------------


def _make_minimal_spellbook_dir(tmp_path):
    """Build a minimal spellbook directory tree the full installer can walk.

    Mirrors ``tests/test_security/test_installer_hooks.py::_make_installer_spellbook_dir``
    but inlined here so this test file remains self-contained.
    """
    spellbook = tmp_path / "spellbook"
    spellbook.mkdir()
    (spellbook / ".version").write_text("1.0.0")
    mcp_dir = spellbook / "spellbook"
    mcp_dir.mkdir()
    (mcp_dir / "server.py").write_text("# stub")
    (spellbook / "AGENTS.spellbook.md").write_text("# Spellbook Context\n\nTest content.\n")
    (spellbook / "skills").mkdir()
    (spellbook / "commands").mkdir()
    hooks_dir = spellbook / "hooks"
    hooks_dir.mkdir()
    for name in (
        "bash-gate.sh",
        "spawn-guard.sh",
        "state-sanitize.sh",
        "audit-log.sh",
        "canary-check.sh",
    ):
        (hooks_dir / name).write_text("#!/usr/bin/env bash\nexit 0\n")
    return spellbook


# Empirical call counts for the multi-component install path inside the
# tripwire sandbox (probed against the live ClaudeCodeInstaller.install /
# .uninstall under skip_global_steps=False on POSIX). These constants and
# the matching ``.calls(fn)`` registrations + ``assert_call`` loops below
# must be updated together: tripwire raises ``UnmockedInteractionError``
# if the SUT fires more calls than registered, and
# ``UnassertedInteractionsError`` at teardown if a recorded interaction
# is not asserted. Hence: no ``required(False)`` workaround needed.
#
# Per-call-site provenance (verified against the installer/ tree under
# skip_global_steps=False on POSIX):
#
#   _INSTALL_HOME_CALLS=2     -> pathlib.Path.home() called by:
#     - installer/components/aliases.py:30 (rc-file resolution inside
#       install_aliases via _install_claude_code_aliases)
#     - installer/platforms/claude_code.py:518 (default_dir = Path.home()
#       / ".claude" during install config_dir resolution)
#
#   _INSTALL_CC_CLI_CALLS=1   -> installer.platforms.claude_code:
#                                check_claude_cli_available called by:
#     - installer/platforms/claude_code.py:600 (MCP HTTP registration
#       branch during ClaudeCodeInstaller.install)
#
#   _INSTALL_MCP_CLI_CALLS=1  -> installer.components.mcp:
#                                check_claude_cli_available called by:
#     - one of installer/components/mcp.py:53, :114, :157 (the
#       register_mcp_http_server path invoked during install — exact
#       branch depends on dry_run/config_dir state; empirically exactly
#       one of these fires per install cycle)
#
#   _UNINSTALL_CC_CLI_CALLS=1 -> installer.platforms.claude_code:
#                                check_claude_cli_available called by:
#     - installer/platforms/claude_code.py:847 (MCP unregister branch
#       during ClaudeCodeInstaller.uninstall)
#
#   _UNINSTALL_DAEMON_CALLS=1 -> installer.platforms.claude_code:
#                                uninstall_daemon called by:
#     - installer/platforms/claude_code.py:835 (daemon teardown branch
#       during ClaudeCodeInstaller.uninstall)
#
# If the production-code call graph drifts (e.g. an added Path.home() in
# config.py becomes reachable, or the MCP gating moves), bump the matching
# constant AND update this comment. A constant that no longer matches its
# enumerated sites is a bug, not a refactor.
_INSTALL_HOME_CALLS = 2
_INSTALL_CC_CLI_CALLS = 1
_INSTALL_MCP_CLI_CALLS = 1
# uninstall calls cc_cli once (uninstall side) and daemon once.
_UNINSTALL_CC_CLI_CALLS = 1
_UNINSTALL_DAEMON_CALLS = 1


def _register_aux_install_mocks(home_path):
    """Register the incidental Path.home / check_claude_cli_available mocks.

    These are called incidentally by the multi-component install path
    (config_dir resolution + per-step CLI gating). The exact call counts
    are empirical and pinned by the module-level constants above. Returns
    (home_mock, cc_cli_mock, mcp_cli_mock); each must be drained via
    ``_assert_aux_install_mocks`` after the sandbox closes.
    """
    home_mock = tripwire.mock("pathlib:Path.home")
    for _ in range(_INSTALL_HOME_CALLS):
        home_mock.returns(home_path)

    cc_cli_mock = tripwire.mock(
        "installer.platforms.claude_code:check_claude_cli_available"
    )
    for _ in range(_INSTALL_CC_CLI_CALLS):
        cc_cli_mock.returns(False)

    mcp_cli_mock = tripwire.mock(
        "installer.components.mcp:check_claude_cli_available"
    )
    for _ in range(_INSTALL_MCP_CLI_CALLS):
        mcp_cli_mock.returns(False)

    return home_mock, cc_cli_mock, mcp_cli_mock


def _assert_aux_install_mocks(home_mock, cc_cli_mock, mcp_cli_mock):
    """Drain the auxiliary install-path mocks via in_any_order.

    Each registered ``.calls(fn)`` entry corresponds to one recorded
    interaction; we assert exactly that many here.
    """
    with tripwire.in_any_order():
        for _ in range(_INSTALL_HOME_CALLS):
            home_mock.assert_call(args=(), kwargs={})
        for _ in range(_INSTALL_CC_CLI_CALLS):
            cc_cli_mock.assert_call(args=(), kwargs={})
        for _ in range(_INSTALL_MCP_CLI_CALLS):
            mcp_cli_mock.assert_call(args=(), kwargs={})


@pytest.mark.posix_only
def test_install_invokes_dispatch_and_records_aliases_result(tmp_path, monkeypatch):
    """ClaudeCodeInstaller.install() actually calls _install_claude_code_aliases.

    Behavioral wiring test: mock the dispatch helper via tripwire,
    run ``install()``, and assert (a) the helper was called exactly once
    with the installer's ``spellbook_dir`` and ``dry_run`` values, and (b)
    the returned ``results`` list contains an ``InstallResult`` with
    ``component="aliases"`` and ``action="installed"``.

    Without this test, a refactor that drops the dispatch call from
    ``install()`` would still pass every existing dispatch-helper test in
    isolation because the helper itself is unchanged.
    """
    from installer.platforms import claude_code as platform_mod
    from installer.platforms.claude_code import ClaudeCodeInstaller

    spellbook_dir = _make_minimal_spellbook_dir(tmp_path)
    config_dir = tmp_path / ".claude"
    config_dir.mkdir(parents=True)

    home_mock, cli_mock_claude, cli_mock_mcp = _register_aux_install_mocks(tmp_path)

    dispatch_mock = tripwire.mock(
        "installer.platforms.claude_code:_install_claude_code_aliases"
    )
    dispatch_mock.returns({
        "installed": True,
        "rc_path": "/fake/.zshrc",
        "aliases": ["claude"],
        "skipped_reason": None,
    })

    installer = ClaudeCodeInstaller(spellbook_dir, config_dir, "1.0.0", dry_run=True)
    with tripwire:
        results = installer.install()

    dispatch_mock.assert_call(args=(spellbook_dir,), kwargs={"dry_run": True})
    _assert_aux_install_mocks(home_mock, cli_mock_claude, cli_mock_mcp)

    # Exactly one aliases InstallResult must be present in the returned list.
    alias_results = [r for r in results if r.component == "aliases"]
    assert len(alias_results) == 1, (
        f"expected exactly one aliases InstallResult; got {alias_results!r}"
    )
    assert alias_results[0].action == "installed"
    assert alias_results[0].success is True
    assert "/fake/.zshrc" in alias_results[0].message


@pytest.mark.posix_only
def test_install_does_not_abort_when_dispatch_raises(tmp_path):
    """A dispatch-helper exception records a failed aliases result and continues.

    Pins the F1 contract: an OSError (e.g. unwritable rc file) inside the
    dispatch helper must NOT propagate to ``core.py`` and abort the install.
    install() must (a) record an ``InstallResult`` with ``component="aliases"``,
    ``success=False``, and the original error text in the message, and
    (b) continue executing subsequent components -- specifically the
    security-critical hooks install -- so they still produce results.
    """
    from dirty_equals import AnyThing

    from installer.platforms.claude_code import ClaudeCodeInstaller

    spellbook_dir = _make_minimal_spellbook_dir(tmp_path)
    config_dir = tmp_path / ".claude"
    config_dir.mkdir(parents=True)

    home_mock, cli_mock_claude, cli_mock_mcp = _register_aux_install_mocks(tmp_path)

    # Stub install_spellbook_cco so install() does NOT attempt a real fork
    # clone during this test. Returns a healthy noop dict so the chain
    # dependency contract treats the wrapper as available.
    cco_mock = tripwire.mock(
        "installer.platforms.claude_code:install_spellbook_cco"
    )
    cco_mock.returns({
        "installed": True,
        "path": "/fake/spellbook-cco",
        "skipped_reason": None,
        "action": "noop",
        "install_root": "/fake/install-root",
    })

    # Dispatch helper raises OSError to exercise the catch-and-continue path.
    dispatch_mock = tripwire.mock(
        "installer.platforms.claude_code:_install_claude_code_aliases"
    )
    dispatch_mock.raises(OSError("Permission denied"))

    installer = ClaudeCodeInstaller(spellbook_dir, config_dir, "1.0.0", dry_run=False)
    # install() must NOT raise; the exception must be caught and recorded.
    with tripwire:
        results = installer.install()

    cco_mock.assert_call(args=(), kwargs={"install_root": None, "dry_run": False})
    dispatch_mock.assert_call(
        args=(spellbook_dir,),
        kwargs={"dry_run": False},
        raised=AnyThing,
    )
    with tripwire.in_any_order():
        for _ in range(_INSTALL_HOME_CALLS):
            home_mock.assert_call(args=(), kwargs={})
        for _ in range(_INSTALL_CC_CLI_CALLS):
            cli_mock_claude.assert_call(args=(), kwargs={})
        for _ in range(_INSTALL_MCP_CLI_CALLS):
            cli_mock_mcp.assert_call(args=(), kwargs={})
        # claude_code.py now logger.exception()'s the caught alias OSError
        # for operator observability (gemini cycle-6 finding). Drain the
        # LoggingPlugin entry so the strict verifier does not flag it.
        tripwire.log.assert_log(
            level="ERROR",
            message=AnyThing,
            logger_name="installer.platforms.claude_code",
        )

    # (a) failed aliases result is recorded with the original error text.
    alias_results = [r for r in results if r.component == "aliases"]
    assert len(alias_results) == 1
    assert alias_results[0].success is False
    assert alias_results[0].action == "failed"
    assert "Permission denied" in alias_results[0].message

    # (b) install did NOT abort early: subsequent components still ran.
    components = {r.component for r in results}
    assert "CLAUDE.md" in components, (
        "CLAUDE.md update step did not run after aliases failure; install() may have aborted early"
    )
    assert "hooks" in components, (
        "hooks install step did not run after aliases failure; "
        "the security-critical install path was skipped"
    )
    assert "mcp_server" in components, (
        "MCP server registration step did not run after aliases failure; "
        "install() may have aborted early before the global MCP step"
    )
    # The hooks result itself must reflect that hooks were actually
    # installed, not failed-by-association with the aliases failure.
    hook_results = [r for r in results if r.component == "hooks"]
    assert len(hook_results) == 1
    assert hook_results[0].success is True


# ---------------------------------------------------------------------------
# Task 3 — once-globally spellbook-cco wiring tests
#
# These tests pin the contract that ``ClaudeCodeInstaller.install()`` calls
# ``install_spellbook_cco`` once per platform install (before the per-config
# alias loop), and that ``ClaudeCodeInstaller.uninstall()`` symmetrically
# calls ``uninstall_spellbook_cco``. The dispatcher
# ``_install_claude_code_aliases`` is also covered for the
# ``SPELLBOOK_USE_VANILLA_CCO=1`` rollback codepath.
#
# Stable WARNING string: emitted by both the once-globally block (when the
# rollback env var is set) and by ``_install_claude_code_aliases`` (when the
# rollback env var routes the dispatcher to gate on vanilla ``cco``).
# ---------------------------------------------------------------------------

# Canonical rollback WARNING is asserted via full-equality with
# ``_WARNING_USE_VANILLA_CCO`` (imported from the production module at the
# top of this file). The substring constant that lived here previously was
# replaced when the green-mirage audit tightened these assertions.


@pytest.mark.posix_only
def test_install_chains_install_spellbook_cco(tmp_path):
    """install() calls install_spellbook_cco exactly once before per-dir alias work.

    Pins the chain-dependency contract: the once-globally wrapper install
    runs as part of every ``ClaudeCodeInstaller.install()`` invocation
    (gated on ``not skip_global_steps``). The per-dir alias dispatcher
    runs after, and depends on the wrapper being on PATH.

    Ordering is verified via tripwire's timeline (strict order between
    out-of-block assertions): cco_mock and dispatch_mock asserted in
    sequence verifies the cco-before-aliases contract.
    """
    from dirty_equals import AnyThing

    from installer.core import InstallResult
    from installer.platforms.claude_code import ClaudeCodeInstaller

    spellbook_dir = _make_minimal_spellbook_dir(tmp_path)
    config_dir = tmp_path / ".claude"
    config_dir.mkdir(parents=True)

    home_mock, cli_mock_claude, cli_mock_mcp = _register_aux_install_mocks(tmp_path)

    cco_mock = tripwire.mock(
        "installer.platforms.claude_code:install_spellbook_cco"
    )
    cco_mock.returns({
        "installed": True,
        "action": "installed",
        "path": "/Users/eek/.local/bin/spellbook-cco",
        "skipped_reason": None,
        "install_root": "/Users/eek/.local/spellbook/cco",
    })

    # Stub the per-dir alias dispatcher so we don't double-pay on
    # tested-elsewhere wiring.
    dispatch_mock = tripwire.mock(
        "installer.platforms.claude_code:_install_claude_code_aliases"
    )
    dispatch_mock.returns({
        "installed": True,
        "rc_path": "/fake/.zshrc",
        "aliases": ["claude"],
        "skipped_reason": None,
    })

    installer = ClaudeCodeInstaller(spellbook_dir, config_dir, "1.0.0", dry_run=True)
    with tripwire:
        results = installer.install()

    # cco runs strictly before aliases (chain-dependency contract).
    # Asserted in sequence outside any in_any_order block.
    cco_mock.assert_call(args=(), kwargs={"install_root": None, "dry_run": True})
    dispatch_mock.assert_call(args=(spellbook_dir,), kwargs={"dry_run": True})
    _assert_aux_install_mocks(home_mock, cli_mock_claude, cli_mock_mcp)

    # The recorded InstallResult for spellbook_cco matches the canonical
    # shape exactly (component, platform, success, action, message). The
    # message is a deterministic f-string in ClaudeCodeInstaller.install():
    # ``f"spellbook-cco: {action} ({skipped_reason or 'ok'})"``.
    cco_results = [r for r in results if r.component == "spellbook_cco"]
    expected = InstallResult(
        component="spellbook_cco",
        platform="claude_code",
        success=True,
        action="installed",
        message="spellbook-cco: installed (ok)",
    )
    assert cco_results == [expected]


@pytest.mark.posix_only
def test_install_chains_emits_warning_under_env_override(tmp_path, monkeypatch, capsys):
    """SPELLBOOK_USE_VANILLA_CCO=1: install_spellbook_cco is skipped, WARNING fires.

    Under the rollback override, the once-globally block synthesizes a
    skipped result (without invoking install_spellbook_cco) and fires a
    stderr WARNING that names the env var. The per-dir alias dispatcher
    then routes through the vanilla ``which("cco")`` gate; we mock that
    gate to return None so the per-dir aliases short-circuit with a clear
    skipped_reason. install_spellbook_cco and install_aliases must NOT
    be called -- tripwire's strict verifier enforces this (no mock = no
    call permitted).
    """
    from dirty_equals import AnyThing

    from installer.platforms.claude_code import ClaudeCodeInstaller

    spellbook_dir = _make_minimal_spellbook_dir(tmp_path)
    config_dir = tmp_path / ".claude"
    config_dir.mkdir(parents=True)

    home_mock, cli_mock_claude, cli_mock_mcp = _register_aux_install_mocks(tmp_path)

    monkeypatch.setenv("SPELLBOOK_USE_VANILLA_CCO", "1")

    # Vanilla cco missing on PATH; dispatcher returns its skip dict.
    # install_aliases is NOT mocked -- tripwire enforces it must not be
    # called on this codepath.
    tripwire.subprocess.mock_which("cco", returns=None)

    installer = ClaudeCodeInstaller(spellbook_dir, config_dir, "1.0.0", dry_run=False)
    with tripwire:
        results = installer.install()

    tripwire.subprocess.assert_which("cco", returns=None)
    _assert_aux_install_mocks(home_mock, cli_mock_claude, cli_mock_mcp)

    captured = capsys.readouterr()
    # The canonical rollback WARNING fires twice on this codepath (once
    # from the once-globally install block, once from
    # ``_install_claude_code_aliases`` when the dispatcher routes through
    # the vanilla branch). Assert exact stderr equality so any drift in
    # the canonical wording or the emission count is caught.
    assert captured.err == _WARNING_USE_VANILLA_CCO * 2

    # The recorded InstallResult for spellbook_cco matches the canonical
    # shape exactly. The cco_result dict synthesized inline by the
    # once-globally block under env override is:
    #   action="skipped",
    #   skipped_reason="SPELLBOOK_USE_VANILLA_CCO=1 active; routing
    #                   aliases to legacy vanilla cco"
    # which the message f-string renders as below.
    from installer.core import InstallResult

    cco_results = [r for r in results if r.component == "spellbook_cco"]
    expected_cco = InstallResult(
        component="spellbook_cco",
        platform="claude_code",
        success=False,
        action="skipped",
        message=(
            "spellbook-cco: skipped "
            "(SPELLBOOK_USE_VANILLA_CCO=1 active; routing aliases to legacy vanilla cco)"
        ),
    )
    assert cco_results == [expected_cco]

    # The per-dir aliases were short-circuited (install_aliases NOT called).
    # The recorded aliases InstallResult uses the canonical skipped_reason
    # produced by ``_install_claude_code_aliases`` when ``shutil.which``
    # returns None for the sandbox binary (vanilla cco under env override).
    alias_results = [r for r in results if r.component == "aliases"]
    expected_aliases = InstallResult(
        component="aliases",
        platform="claude_code",
        success=True,
        action="skipped",
        message="aliases: cco not on PATH; re-run install.py",
    )
    assert alias_results == [expected_aliases]


@pytest.mark.posix_only
def test_uninstall_chains_uninstall_spellbook_cco(tmp_path):
    """uninstall() calls uninstall_spellbook_cco exactly once.

    Pins the F-B mitigation: every full ``ClaudeCodeInstaller.uninstall()``
    invocation tears down the wrapper and managed clone via
    uninstall_spellbook_cco (idempotent: clean machine returns
    ``action="noop"``).
    """
    from dirty_equals import AnyThing

    from installer.platforms.claude_code import ClaudeCodeInstaller

    spellbook_dir = _make_minimal_spellbook_dir(tmp_path)
    config_dir = tmp_path / ".claude"
    config_dir.mkdir(parents=True)

    # Empirical: uninstall() invokes check_claude_cli_available exactly
    # once (claude_code-side) and uninstall_daemon exactly once. It does
    # NOT call Path.home or the mcp-side check_claude_cli_available on
    # this code path. Register precisely what fires; tripwire's strict
    # guard catches any regression that adds an unmocked incidental call.
    cli_mock_claude = tripwire.mock(
        "installer.platforms.claude_code:check_claude_cli_available"
    )
    for _ in range(_UNINSTALL_CC_CLI_CALLS):
        cli_mock_claude.returns(False)

    uninstall_mock = tripwire.mock(
        "installer.platforms.claude_code:uninstall_spellbook_cco"
    )
    uninstall_mock.returns({
        "installed": False,
        "path": "/Users/eek/.local/bin/spellbook-cco",
        "action": "removed",
        "skipped_reason": None,
    })

    # uninstall path also tears down the daemon; mock that to avoid the
    # real socket/DNS interaction tripwire's DNS plugin would catch.
    daemon_mock = tripwire.mock(
        "installer.platforms.claude_code:uninstall_daemon"
    )
    for _ in range(_UNINSTALL_DAEMON_CALLS):
        # SUT calls uninstall_daemon(dry_run=False); the lambda ignored
        # its arg and returned a constant, so .returns() is equivalent
        # and idiomatic for a stateless return value.
        daemon_mock.returns((True, "ok"))

    installer = ClaudeCodeInstaller(spellbook_dir, config_dir, "1.0.0", dry_run=False)
    with tripwire:
        results = installer.uninstall()

    # Exactly one call with dry_run forwarded.
    uninstall_mock.assert_call(args=(), kwargs={"install_root": None, "dry_run": False})
    with tripwire.in_any_order():
        for _ in range(_UNINSTALL_CC_CLI_CALLS):
            cli_mock_claude.assert_call(args=(), kwargs={})
        for _ in range(_UNINSTALL_DAEMON_CALLS):
            daemon_mock.assert_call(args=(), kwargs={"dry_run": False})

    # The recorded InstallResult for spellbook_cco matches the canonical
    # shape exactly. ``ClaudeCodeInstaller.uninstall`` always sets
    # success=True for this component and renders the message as
    # ``f"spellbook-cco: {action} ({skipped_reason or 'ok'})"``.
    from installer.core import InstallResult

    cco_results = [r for r in results if r.component == "spellbook_cco"]
    expected = InstallResult(
        component="spellbook_cco",
        platform="claude_code",
        success=True,
        action="removed",
        message="spellbook-cco: removed (ok)",
    )
    assert cco_results == [expected]


@pytest.mark.posix_only
def test_install_chain_failure_when_fork_install_fails(tmp_path, capsys):
    """When install_spellbook_cco fails, per-dir aliases short-circuit cleanly.

    Chain dependency: the per-dir alias dispatcher gates on
    ``shutil.which("spellbook-cco")``. When the once-globally fork install
    returns ``installed=False`` (e.g., ``git clone`` failed), the wrapper
    is absent on PATH and the per-dir alias install short-circuits with a
    skipped_reason that names the missing sandbox binary. install_aliases
    is NOT mocked -- tripwire's strict verifier enforces it must not fire.
    """
    from dirty_equals import AnyThing

    from installer.platforms.claude_code import ClaudeCodeInstaller

    spellbook_dir = _make_minimal_spellbook_dir(tmp_path)
    config_dir = tmp_path / ".claude"
    config_dir.mkdir(parents=True)

    home_mock, cli_mock_claude, cli_mock_mcp = _register_aux_install_mocks(tmp_path)

    cco_mock = tripwire.mock(
        "installer.platforms.claude_code:install_spellbook_cco"
    )
    cco_mock.returns({
        "installed": False,
        "action": "skipped",
        "path": None,
        "skipped_reason": "git clone failed: network unreachable",
        "install_root": None,
    })

    # spellbook-cco is NOT on PATH because the once-globally install failed.
    tripwire.subprocess.mock_which("spellbook-cco", returns=None)

    installer = ClaudeCodeInstaller(spellbook_dir, config_dir, "1.0.0", dry_run=False)
    with tripwire:
        results = installer.install()

    cco_mock.assert_call(args=(), kwargs={"install_root": None, "dry_run": False})
    tripwire.subprocess.assert_which("spellbook-cco", returns=None)
    _assert_aux_install_mocks(home_mock, cli_mock_claude, cli_mock_mcp)

    # The recorded InstallResult for spellbook_cco matches the canonical
    # shape exactly. The cco_failed stub returns
    # ``skipped_reason="git clone failed: network unreachable"`` and the
    # message f-string renders it verbatim.
    from installer.core import InstallResult

    cco_results = [r for r in results if r.component == "spellbook_cco"]
    expected_cco = InstallResult(
        component="spellbook_cco",
        platform="claude_code",
        success=False,
        action="skipped",
        message="spellbook-cco: skipped (git clone failed: network unreachable)",
    )
    assert cco_results == [expected_cco]

    # Per-dir aliases short-circuited with the canonical skipped_reason
    # produced by ``_install_claude_code_aliases`` when the spellbook-cco
    # wrapper is absent from PATH (default codepath, no env override).
    alias_results = [r for r in results if r.component == "aliases"]
    expected_aliases = InstallResult(
        component="aliases",
        platform="claude_code",
        success=True,
        action="skipped",
        message="aliases: spellbook-cco not on PATH; re-run install.py",
    )
    assert alias_results == [expected_aliases]


@pytest.mark.posix_only
@pytest.mark.parametrize(
    "platform_value",
    ["LINUX", "MACOS"],
    ids=["linux", "macos"],
)
def test_install_claude_code_aliases_routes_to_vanilla_under_env_override(
    tmp_path, monkeypatch, capsys, platform_value
):
    """SPELLBOOK_USE_VANILLA_CCO=1: dispatcher gates on vanilla cco + WARNs.

    When the env override is set the dispatcher gates on
    ``shutil.which("cco")`` (the vanilla binary), not
    ``shutil.which("spellbook-cco")``. With vanilla cco present on PATH
    the dispatcher proceeds to ``install_aliases`` AND fires the rollback
    WARNING so the operator sees the rollback codepath in transcripts.
    """
    from installer.platforms import claude_code as platform_mod
    from spellbook.core.compat import Platform

    spellbook_dir = tmp_path / "spellbook"
    monkeypatch.setenv("SPELLBOOK_USE_VANILLA_CCO", "1")

    plat_mock = tripwire.mock("installer.platforms.claude_code:get_platform")
    plat_mock.returns(getattr(Platform, platform_value))

    # which("cco") -> a path. The dispatcher only consults "cco" under
    # the env override (vanilla branch); it does not call which on
    # "spellbook-cco" in this path.
    tripwire.subprocess.mock_which("cco", returns="/usr/local/bin/cco")

    aliases_mock = tripwire.mock(
        "installer.platforms.claude_code:install_aliases"
    )
    aliases_mock.returns({
        "installed": True,
        "rc_path": "/fake/.zshrc",
        "aliases": ["claude"],
        "skipped_reason": None,
    })

    # install_aliases_windows is NOT mocked; tripwire's strict verifier
    # ensures it cannot fire on the POSIX-dispatch codepath.

    with tripwire:
        result = platform_mod._install_claude_code_aliases(spellbook_dir, dry_run=False)

    plat_mock.assert_call(args=(), kwargs={})
    tripwire.subprocess.assert_which("cco", returns="/usr/local/bin/cco")
    aliases_mock.assert_call(args=(spellbook_dir,), kwargs={"dry_run": False})
    assert result == {
        "installed": True,
        "rc_path": "/fake/.zshrc",
        "aliases": ["claude"],
        "skipped_reason": None,
    }

    # Canonical WARNING fired by the dispatcher itself under env override.
    # Full-equality (not substring) so any drift in the imported constant's
    # wording is caught here.
    captured = capsys.readouterr()
    assert captured.err == _WARNING_USE_VANILLA_CCO


# ---------------------------------------------------------------------------
# Task 6 — scripts/spellbook-sandbox rewrite tests
#
# These tests pin the contract that the sandbox script:
#   * pins SPELLBOOK_CCO_PINNED_SHA="d7044ef" (fork)
#   * carries the revised macOS rationale (fork ships L5)
#   * invokes spellbook-cco by default (not vanilla cco)
#   * gates on the fork SHA
#   * implements the dual-env-var transition with deprecation warning
#   * supports the SPELLBOOK_USE_VANILLA_CCO=1 rollback to legacy 9744b9f
#
# All tests use tmp_path-isolated shims and HOME so the operator's actual
# ~/.local/bin/spellbook-cco wrapper and PATH are never touched.
# ---------------------------------------------------------------------------


# Task 7 consolidation: the Task-6-local EXPECTED_FORK_SHA / EXPECTED_VANILLA_SHA
# constants now alias the module-level EXPECTED_CCO_SHA / EXPECTED_VANILLA_CCO_SHA
# so the SHA values live in exactly one place. Tests in this class reference
# the aliases to keep the original Task-6 framing legible at the call sites.
EXPECTED_FORK_SHA = EXPECTED_CCO_SHA
EXPECTED_VANILLA_SHA = EXPECTED_VANILLA_CCO_SHA


def _sandbox_env_with_shim(tmp_path: Path, *, extra: dict | None = None) -> dict:
    """Build a clean env that points PATH at tmp_path (where the test wrote
    a fake spellbook-cco / cco shim) and isolates HOME to tmp_path.

    Never inherits the operator's PATH, ~/.local/bin, or any
    SPELLBOOK_SANDBOX_SKIP_* / SPELLBOOK_USE_VANILLA_CCO vars from the
    invoking environment.
    """
    env = {
        "PATH": f"{tmp_path}:/usr/bin:/bin",
        "HOME": str(tmp_path),
        # Pin SPELLBOOK_DIR so the script's auto-detect block does not
        # walk up from the script location and hit the real repo root.
        "SPELLBOOK_DIR": str(REPO_ROOT),
    }
    if "TERM" in os.environ:
        env["TERM"] = os.environ["TERM"]
    if extra:
        env.update(extra)
    return env


def _write_shim(tmp_path: Path, name: str, version_output: str) -> Path:
    """Write a fake CLI shim at tmp_path/<name>. The shim:

    - emits ``version_output`` on ``--version``
    - exits 0 on every invocation (so the sandbox script's exec succeeds)
    """
    shim = tmp_path / name
    body = (
        "#!/bin/sh\n"
        'if [ "$1" = "--version" ]; then\n'
        f'  echo "{version_output}"\n'
        "  exit 0\n"
        "fi\n"
        "exit 0\n"
    )
    shim.write_text(body)
    shim.chmod(0o755)
    return shim


class TestSpellbookSandboxScript:
    """Task 6: sandbox script rewrite to invoke spellbook-cco at d7044ef.

    Tests are organized around the truth-table predicate logic in the
    plan §6 step 6 Revision R3:

        SKIP_PIN | SKIP_CCO_PIN | warn? | skip pin gate?
        unset    | unset        | no    | no
        unset    | "1"          | YES   | yes
        "1"      | unset        | no    | yes
        "1"      | "1"          | YES   | yes
        "1"      | "0"          | no    | yes
        "0"      | "1"          | YES   | no   (new var wins)
        any      | "0"/other    | no    | per SKIP_PIN
    """

    def test_sandbox_pin_constant_is_d7044ef(self):
        """Source-of-truth: SPELLBOOK_CCO_PINNED_SHA="d7044ef" in the script.

        Parses the assignment line via a regex that captures the SHA.
        The constant name (SPELLBOOK_CCO_PINNED_SHA) must match the one
        used in installer/components/spellbook_cco.py so a single source
        of truth governs both install-time and sandbox-time verification.
        """
        script = _read_script()
        match = re.search(
            r'^SPELLBOOK_CCO_PINNED_SHA="([0-9a-f]{7,40})"',
            script,
            re.MULTILINE,
        )
        assert match is not None, (
            f'expected SPELLBOOK_CCO_PINNED_SHA="<hash>" assignment in {SANDBOX_SCRIPT}; got none'
        )
        assert match.group(1) == EXPECTED_FORK_SHA

    def test_sandbox_header_cites_fork_and_revised_decision(self):
        """The header pivots from "intentionally absent" to fork-ships-L5.

        Asserts (1) the fork repo (elijahr/cco) is cited, (2) the new pin
        d7044ef is cited, (3) the revised macOS rationale is present,
        (4) the Sec 9.3 (revised 2026-05-07) reference is present,
        and (5) the old "intentionally absent" phrasing is GONE.
        """
        script = _read_script()
        # Read header region (first 100 lines) for the macOS rationale block.
        header = "\n".join(script.splitlines()[:100])

        assert "elijahr/cco" in header, (
            f"header must cite the fork repo (elijahr/cco); got header={header!r}"
        )
        assert "d7044ef" in header, "header must cite the new fork pin SHA"
        assert "macOS ships L5 via spellbook-cco" in header, (
            "header must contain revised macOS rationale phrase 'macOS ships L5 via spellbook-cco'"
        )
        assert "Sec 9.3 (revised 2026-05-07)" in header, (
            "header must cite the revised audit decision 'Sec 9.3 (revised 2026-05-07)'"
        )
        # The audit-doc citation is preserved across the rewrite.
        assert "sec_9_3_result.md" in script

        # The legacy "intentionally absent" phrasing must be gone.
        assert "intentionally absent" not in script, (
            "old 'intentionally absent' macOS phrasing must be removed from the rewritten header"
        )

    @pytest.mark.posix_only
    def test_sandbox_invokes_spellbook_cco_by_default(self, tmp_path):
        """Default path: sandbox invokes spellbook-cco, gate passes at d7044ef.

        Drops a fake spellbook-cco shim into tmp_path. The shim emits
        ``cco d7044ef (installation)`` on --version and exits 0 on the
        passthrough exec. Asserts the script exits 0 and the shim was
        invoked (sentinel file written by a child process).
        """
        if not SANDBOX_SCRIPT.exists():
            pytest.skip(f"{SANDBOX_SCRIPT} missing")

        # Shim that records its invocation to a sentinel file when called
        # for the exec passthrough. We use a single combined shim so the
        # test is robust to the script's exec behavior.
        shim = tmp_path / "spellbook-cco"
        sentinel = tmp_path / "shim-invoked"
        shim.write_text(
            "#!/bin/sh\n"
            'if [ "$1" = "--version" ]; then\n'
            f'  echo "cco {EXPECTED_FORK_SHA} (installation)"\n'
            "  exit 0\n"
            "fi\n"
            f'echo "exec called" > "{sentinel}"\n'
            "exit 0\n"
        )
        shim.chmod(0o755)

        env = _sandbox_env_with_shim(tmp_path)
        proc = subprocess.run(
            [str(SANDBOX_SCRIPT), "echo", "ok"],
            capture_output=True,
            text=True,
            timeout=10,
            env=env,
        )

        assert proc.returncode == 0, (
            f"expected exit 0 from default path with valid pin; got "
            f"returncode={proc.returncode}, stderr={proc.stderr!r}"
        )
        assert sentinel.exists(), (
            f"spellbook-cco shim was not invoked for the exec passthrough; stderr={proc.stderr!r}"
        )

    @pytest.mark.posix_only
    def test_sandbox_pin_gate_fires_on_sha_mismatch(self, tmp_path):
        """Gate fires at startup when spellbook-cco --version reports wrong SHA.

        With a shim that emits ``cco wrongsha (installation)`` on
        --version, the script must abort with exit 1 and a pin-mismatch
        error message naming the expected and actual SHAs.
        """
        if not SANDBOX_SCRIPT.exists():
            pytest.skip(f"{SANDBOX_SCRIPT} missing")

        _write_shim(tmp_path, "spellbook-cco", "cco wrongsha (installation)")

        env = _sandbox_env_with_shim(tmp_path)
        proc = subprocess.run(
            [str(SANDBOX_SCRIPT), "echo", "ok"],
            capture_output=True,
            text=True,
            timeout=10,
            env=env,
        )

        assert proc.returncode == 1, (
            f"expected exit 1 from pin-mismatch gate; got "
            f"returncode={proc.returncode}, stderr={proc.stderr!r}"
        )
        assert "SHA pin mismatch" in proc.stderr, (
            f"expected pin mismatch error in stderr; got stderr={proc.stderr!r}"
        )
        assert EXPECTED_FORK_SHA in proc.stderr, (
            f"stderr must name the expected fork SHA; got stderr={proc.stderr!r}"
        )

    @pytest.mark.posix_only
    def test_sandbox_skip_pin_via_new_env_var(self, tmp_path):
        """SKIP_PIN=1 (new name): gate skipped, no deprecation warning."""
        if not SANDBOX_SCRIPT.exists():
            pytest.skip(f"{SANDBOX_SCRIPT} missing")

        _write_shim(tmp_path, "spellbook-cco", "cco wrongsha (installation)")

        env = _sandbox_env_with_shim(tmp_path, extra={"SPELLBOOK_SANDBOX_SKIP_PIN": "1"})
        proc = subprocess.run(
            [str(SANDBOX_SCRIPT), "echo", "ok"],
            capture_output=True,
            text=True,
            timeout=10,
            env=env,
        )

        assert proc.returncode == 0, (
            f"expected exit 0 with SKIP_PIN=1 (gate bypassed); got "
            f"returncode={proc.returncode}, stderr={proc.stderr!r}"
        )
        # No deprecation warning (legacy var unset).
        assert "DEPRECATION" not in proc.stderr.upper(), (
            f"new-var path must not emit deprecation warning; stderr={proc.stderr!r}"
        )

    @pytest.mark.posix_only
    def test_sandbox_skip_pin_via_legacy_env_var_with_deprecation_warning(self, tmp_path):
        """SKIP_CCO_PIN=1 (legacy name) only: gate skipped + deprecation warn.

        Truth-table row: SKIP_PIN=unset, SKIP_CCO_PIN="1" → warn=YES, skip=YES.
        """
        if not SANDBOX_SCRIPT.exists():
            pytest.skip(f"{SANDBOX_SCRIPT} missing")

        _write_shim(tmp_path, "spellbook-cco", "cco wrongsha (installation)")

        env = _sandbox_env_with_shim(tmp_path, extra={"SPELLBOOK_SANDBOX_SKIP_CCO_PIN": "1"})
        proc = subprocess.run(
            [str(SANDBOX_SCRIPT), "echo", "ok"],
            capture_output=True,
            text=True,
            timeout=10,
            env=env,
        )

        assert proc.returncode == 0, (
            f"expected exit 0 with legacy SKIP_CCO_PIN=1 (gate bypassed); got "
            f"returncode={proc.returncode}, stderr={proc.stderr!r}"
        )
        # Deprecation warning must fire because legacy var = "1".
        assert "DEPRECATION" in proc.stderr.upper() or "deprecated" in proc.stderr.lower(), (
            f"legacy var path must emit deprecation warning; stderr={proc.stderr!r}"
        )
        # The warning must name the legacy variable so operators can grep.
        assert "SPELLBOOK_SANDBOX_SKIP_CCO_PIN" in proc.stderr, (
            f"deprecation warning must name SPELLBOOK_SANDBOX_SKIP_CCO_PIN; stderr={proc.stderr!r}"
        )

    @pytest.mark.posix_only
    def test_sandbox_new_env_var_wins_when_both_set_skip_overrides_legacy(self, tmp_path):
        """SKIP_PIN="0" + SKIP_CCO_PIN="1": new var wins (gate fires), warn YES.

        Truth-table row: SKIP_PIN="0", SKIP_CCO_PIN="1" → warn=YES, skip=NO
        (gate fires because new var = "0", legacy var still triggers warn
        because operator is using a deprecated name).
        """
        if not SANDBOX_SCRIPT.exists():
            pytest.skip(f"{SANDBOX_SCRIPT} missing")

        _write_shim(tmp_path, "spellbook-cco", "cco wrongsha (installation)")

        env = _sandbox_env_with_shim(
            tmp_path,
            extra={
                "SPELLBOOK_SANDBOX_SKIP_PIN": "0",
                "SPELLBOOK_SANDBOX_SKIP_CCO_PIN": "1",
            },
        )
        proc = subprocess.run(
            [str(SANDBOX_SCRIPT), "echo", "ok"],
            capture_output=True,
            text=True,
            timeout=10,
            env=env,
        )

        # New var = "0" → gate fires → exit 1.
        assert proc.returncode == 1, (
            f"expected exit 1 (new var wins, gate fires); got "
            f"returncode={proc.returncode}, stderr={proc.stderr!r}"
        )
        assert "SHA pin mismatch" in proc.stderr, (
            f"expected pin mismatch error in stderr; got stderr={proc.stderr!r}"
        )
        # Deprecation warning still fires because legacy var = "1".
        assert "DEPRECATION" in proc.stderr.upper() or "deprecated" in proc.stderr.lower(), (
            f"legacy var = '1' must still emit deprecation warning even when "
            f"new var wins precedence; stderr={proc.stderr!r}"
        )

    @pytest.mark.posix_only
    def test_sandbox_legacy_env_var_set_to_zero_no_warning(self, tmp_path):
        """SKIP_CCO_PIN="0" (legacy, not "1"): no deprecation, gate fires.

        Truth-table row: SKIP_PIN=unset, SKIP_CCO_PIN="0" → warn=NO, skip=NO.
        Predicate: deprecation warning fires iff legacy var == "1" literally
        (not != "" — a zero or empty value must not trip the warning).
        """
        if not SANDBOX_SCRIPT.exists():
            pytest.skip(f"{SANDBOX_SCRIPT} missing")

        _write_shim(tmp_path, "spellbook-cco", "cco wrongsha (installation)")

        env = _sandbox_env_with_shim(tmp_path, extra={"SPELLBOOK_SANDBOX_SKIP_CCO_PIN": "0"})
        proc = subprocess.run(
            [str(SANDBOX_SCRIPT), "echo", "ok"],
            capture_output=True,
            text=True,
            timeout=10,
            env=env,
        )

        assert proc.returncode == 1, (
            f"expected exit 1 (gate fires); got "
            f"returncode={proc.returncode}, stderr={proc.stderr!r}"
        )
        # No deprecation warning (legacy var ≠ "1").
        assert (
            "DEPRECATION" not in proc.stderr.upper() and "deprecated" not in proc.stderr.lower()
        ), f"legacy var = '0' (not '1') must not emit deprecation warning; stderr={proc.stderr!r}"

    @pytest.mark.posix_only
    def test_sandbox_both_skip_vars_set_to_one_warn_and_skip(self, tmp_path):
        """SKIP_PIN="1" + SKIP_CCO_PIN="1": new var wins (gate skipped), warn YES.

        Truth-table row: SKIP_PIN="1", SKIP_CCO_PIN="1" → warn=YES, skip=YES.
        Per the truth table at plan §4 Task 6 step 6, the deprecation
        warning fires whenever the legacy var literally equals "1",
        independent of which var actually controls the gate. With both
        vars set to "1", the new var still wins precedence on the skip
        decision (gate skipped) and the legacy var still triggers the
        deprecation warning (operator is using a deprecated name).
        """
        if not SANDBOX_SCRIPT.exists():
            pytest.skip(f"{SANDBOX_SCRIPT} missing")

        _write_shim(tmp_path, "spellbook-cco", "cco wrongsha (installation)")

        env = _sandbox_env_with_shim(
            tmp_path,
            extra={
                "SPELLBOOK_SANDBOX_SKIP_PIN": "1",
                "SPELLBOOK_SANDBOX_SKIP_CCO_PIN": "1",
            },
        )
        proc = subprocess.run(
            [str(SANDBOX_SCRIPT), "echo", "ok"],
            capture_output=True,
            text=True,
            timeout=10,
            env=env,
        )

        # New var = "1" → gate skipped → exit 0 (passthrough exec succeeds).
        assert proc.returncode == 0, (
            f"expected exit 0 (gate skipped via new var = '1'); got "
            f"returncode={proc.returncode}, stderr={proc.stderr!r}"
        )
        # Deprecation warning fires because legacy var = "1" literally.
        assert "DEPRECATION" in proc.stderr.upper() or "deprecated" in proc.stderr.lower(), (
            f"legacy var = '1' must emit deprecation warning even when "
            f"new var also = '1'; stderr={proc.stderr!r}"
        )
        # The warning must name the legacy variable so operators can grep.
        assert "SPELLBOOK_SANDBOX_SKIP_CCO_PIN" in proc.stderr, (
            f"deprecation warning must name SPELLBOOK_SANDBOX_SKIP_CCO_PIN; stderr={proc.stderr!r}"
        )

    @pytest.mark.posix_only
    def test_sandbox_use_vanilla_cco_routes_to_legacy_pin(self, tmp_path):
        """SPELLBOOK_USE_VANILLA_CCO=1: gate against legacy 9744b9f via vanilla cco.

        Drops a fake vanilla ``cco`` shim that emits the legacy SHA. Under
        the rollback override the script:
        - gates on ``command -v cco`` (not spellbook-cco)
        - parses ``cco --version`` against legacy SHA 9744b9f
        - exec's vanilla ``cco`` (not spellbook-cco)
        - emits a stderr WARNING that names SPELLBOOK_USE_VANILLA_CCO=1
        """
        if not SANDBOX_SCRIPT.exists():
            pytest.skip(f"{SANDBOX_SCRIPT} missing")

        # Vanilla cco shim at the legacy pin.
        cco_shim = tmp_path / "cco"
        sentinel = tmp_path / "vanilla-cco-invoked"
        cco_shim.write_text(
            "#!/bin/sh\n"
            'if [ "$1" = "--version" ]; then\n'
            f'  echo "cco {EXPECTED_VANILLA_SHA} (installation)"\n'
            "  exit 0\n"
            "fi\n"
            f'echo "vanilla called" > "{sentinel}"\n'
            "exit 0\n"
        )
        cco_shim.chmod(0o755)

        # spellbook-cco shim that, if invoked, fails the test loudly.
        sb_cco_shim = tmp_path / "spellbook-cco"
        sb_cco_shim.write_text(
            "#!/bin/sh\n"
            'echo "FAIL: spellbook-cco invoked under SPELLBOOK_USE_VANILLA_CCO=1" >&2\n'
            "exit 99\n"
        )
        sb_cco_shim.chmod(0o755)

        env = _sandbox_env_with_shim(tmp_path, extra={"SPELLBOOK_USE_VANILLA_CCO": "1"})
        proc = subprocess.run(
            [str(SANDBOX_SCRIPT), "echo", "ok"],
            capture_output=True,
            text=True,
            timeout=10,
            env=env,
        )

        assert proc.returncode == 0, (
            f"expected exit 0 from rollback path with valid legacy pin; got "
            f"returncode={proc.returncode}, stderr={proc.stderr!r}"
        )
        # Vanilla cco was invoked, spellbook-cco was NOT.
        assert sentinel.exists(), (
            "vanilla cco shim was not invoked under SPELLBOOK_USE_VANILLA_CCO=1; "
            f"stderr={proc.stderr!r}"
        )
        # Rollback WARNING fires; substring is byte-equivalent to the
        # canonical emit_rollback_warning() chokepoint in
        # installer/components/spellbook_cco.py (at minimum contains the
        # canonical env-var substring).
        assert "SPELLBOOK_USE_VANILLA_CCO=1" in proc.stderr, (
            f"rollback WARNING must name SPELLBOOK_USE_VANILLA_CCO=1 on "
            f"stderr; got stderr={proc.stderr!r}"
        )
        assert "WARNING" in proc.stderr, (
            f"rollback path must emit a WARNING; got stderr={proc.stderr!r}"
        )

    @pytest.mark.posix_only
    def test_sandbox_use_vanilla_cco_pin_mismatch_against_legacy_sha(self, tmp_path):
        """Rollback path also pin-gates: vanilla cco at wrong SHA → exit 1.

        Confirms that SPELLBOOK_USE_VANILLA_CCO=1 is not a free pass: the
        rollback path STILL pin-verifies, just against the legacy SHA
        9744b9f (not d7044ef).
        """
        if not SANDBOX_SCRIPT.exists():
            pytest.skip(f"{SANDBOX_SCRIPT} missing")

        # Vanilla cco shim at the WRONG SHA.
        _write_shim(tmp_path, "cco", "cco wrongsha (installation)")

        env = _sandbox_env_with_shim(tmp_path, extra={"SPELLBOOK_USE_VANILLA_CCO": "1"})
        proc = subprocess.run(
            [str(SANDBOX_SCRIPT), "echo", "ok"],
            capture_output=True,
            text=True,
            timeout=10,
            env=env,
        )

        assert proc.returncode == 1, (
            f"expected exit 1 from rollback pin-mismatch gate; got "
            f"returncode={proc.returncode}, stderr={proc.stderr!r}"
        )
        # WARNING still fires (operator opted into the rollback codepath).
        assert "SPELLBOOK_USE_VANILLA_CCO=1" in proc.stderr, (
            f"rollback WARNING must fire even on pin mismatch; stderr={proc.stderr!r}"
        )
        # Pin-mismatch error names the legacy SHA (rollback gate).
        assert "SHA pin mismatch" in proc.stderr, (
            f"expected pin mismatch error in stderr; got stderr={proc.stderr!r}"
        )
        assert EXPECTED_VANILLA_SHA in proc.stderr, (
            f"stderr must name the expected legacy SHA on rollback gate; got stderr={proc.stderr!r}"
        )

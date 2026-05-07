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

REPO_ROOT = Path(__file__).resolve().parents[2]
SANDBOX_SCRIPT = REPO_ROOT / "scripts" / "spellbook-sandbox"
SANDBOX_DOC = REPO_ROOT / "scripts" / "spellbook-sandbox.md"

# The short SHA pinned by Sec 9.3 audit. The brief and operator durable rule
# require this exact value; a different SHA without re-audit is forbidden.
EXPECTED_CCO_SHA = "9744b9f"

# Stable phrase that anchors the macOS L5 rationale block. The wording was
# chosen by the brief and is asserted exactly to catch silent edits that
# would weaken the rationale.
MACOS_RATIONALE_PHRASE = "L5 macOS is intentionally absent"


def _read_script() -> str:
    return SANDBOX_SCRIPT.read_text()


def test_spellbook_sandbox_pins_cco_sha():
    """The sandbox script pins cco at the audited SHA via a structured pin line.

    Parses the pin via a regex anchored on the structured comment line so the
    test asserts on a captured value (the SHA) rather than substring presence.
    """
    script = _read_script()

    match = re.search(
        r"^#\s*cco sandbox pin:\s*SHA\s+([0-9a-f]{7,40})\b",
        script,
        re.MULTILINE,
    )
    assert match is not None, (
        "expected a '# cco sandbox pin: SHA <hash>' header line in "
        f"{SANDBOX_SCRIPT}; got none"
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
    to ``cco --help``). Three exit paths are documented:

    1. ``returncode == 0``: cco is installed at the pinned SHA and ``--help``
       was forwarded successfully.
    2. ``returncode == 1`` with ``"cco not found"`` in stderr: cco is absent
       on PATH, the script aborts before the SHA gate.
    3. ``returncode == 1`` with ``"cco SHA pin mismatch"`` in stderr: cco is
       installed but at a non-pinned SHA (common on developer machines
       running a different cco build); the script's audit gate aborts.

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
        # Case 1: cco installed at pinned SHA, --help forwarded.
        return
    if proc.returncode == 1:
        # Case 2 or 3: one of the two documented exit-1 conditions.
        cco_absent = "cco not found" in proc.stderr
        sha_mismatch = "cco SHA pin mismatch" in proc.stderr
        assert cco_absent or sha_mismatch, (
            "spellbook-sandbox exited 1 but stderr matched neither "
            "documented condition (cco-absent or SHA-mismatch). "
            f"stderr={proc.stderr!r}"
        )
        return
    pytest.fail(
        f"spellbook-sandbox exited with undocumented returncode "
        f"{proc.returncode}; expected 0 (success), 1 (cco-absent), or "
        f"1 (SHA-mismatch). stderr={proc.stderr!r}"
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
def test_spellbook_sandbox_fail_closed_on_bad_cco_version(
    tmp_path, shim_body, case_id
):
    """The SHA-pin gate fails closed when ``cco --version`` is bad/empty/wrong.

    Drops a fake ``cco`` shim into a tmp dir, invokes spellbook-sandbox with
    a clean PATH that points to that shim, and asserts the script aborts
    with exit 1 and the documented SHA-mismatch message. The clean env
    avoids inheriting the operator's PATH or SPELLBOOK_SANDBOX_SKIP_CCO_PIN
    and isolates HOME to ``tmp_path``.

    All three shim variants drive the gate to the same outcome:
    ``cco_actual_sha != CCO_PINNED_SHA`` (either empty or "abcdefg"), so
    the script must print "cco SHA pin mismatch" and exit 1.
    """
    if not SANDBOX_SCRIPT.exists():
        pytest.skip(f"{SANDBOX_SCRIPT} missing")

    shim = tmp_path / "cco"
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
    assert "cco SHA pin mismatch" in proc.stderr, (
        f"[{case_id}] expected 'cco SHA pin mismatch' in stderr; "
        f"got stderr={proc.stderr!r}"
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
def test_dispatch_linux_calls_install_aliases(tmp_path, monkeypatch):
    """LINUX: dispatch helper calls install_aliases with forwarded args.

    Records the call args via a recorder list and asserts exact equality on
    the full call list and the helper's return value.
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
    calls: list[tuple] = []

    def recorder(sb_dir, dry_run=False):
        calls.append((sb_dir, dry_run))
        return expected_return

    def windows_recorder(sb_dir, dry_run=False):
        pytest.fail(
            "install_aliases_windows must not be called on LINUX; "
            f"got args=({sb_dir!r}, dry_run={dry_run!r})"
        )

    monkeypatch.setattr(platform_mod, "get_platform", lambda: Platform.LINUX)
    monkeypatch.setattr(platform_mod, "install_aliases", recorder)
    monkeypatch.setattr(
        platform_mod, "install_aliases_windows", windows_recorder
    )
    # Stub shutil.which so the cco-availability gate (F2) treats cco as
    # present regardless of the test machine's PATH. Without this stub the
    # test would skip install_aliases on machines lacking cco.
    monkeypatch.setattr(
        platform_mod.shutil, "which", lambda name: "/fake/path/to/cco"
    )

    result = platform_mod._install_claude_code_aliases(
        spellbook_dir, dry_run=True
    )

    assert calls == [(spellbook_dir, True)]
    assert result == expected_return


@pytest.mark.posix_only
def test_dispatch_linux_skips_install_aliases_when_cco_missing(
    tmp_path, monkeypatch, caplog
):
    """LINUX without cco on PATH: dispatch helper noops and does NOT call install_aliases.

    Without cco the rc-file alias would be broken (every ``claude`` invocation
    would hit the SHA-pin error), so the dispatch helper must skip the install
    and return a documented noop dict. install_aliases must not be called.
    """
    import logging

    from installer.platforms import claude_code as platform_mod
    from spellbook.core.compat import Platform

    spellbook_dir = tmp_path / "spellbook"

    def must_not_call(sb_dir, dry_run=False):
        pytest.fail(
            "install_aliases must not be called when cco is missing on LINUX; "
            f"got args=({sb_dir!r}, dry_run={dry_run!r})"
        )

    def must_not_call_windows(sb_dir, dry_run=False):
        pytest.fail(
            "install_aliases_windows must not be called on LINUX; "
            f"got args=({sb_dir!r}, dry_run={dry_run!r})"
        )

    monkeypatch.setattr(platform_mod, "get_platform", lambda: Platform.LINUX)
    monkeypatch.setattr(platform_mod, "install_aliases", must_not_call)
    monkeypatch.setattr(
        platform_mod, "install_aliases_windows", must_not_call_windows
    )
    # Simulate cco absent.
    monkeypatch.setattr(platform_mod.shutil, "which", lambda name: None)

    with caplog.at_level(logging.INFO, logger=platform_mod.__name__):
        result = platform_mod._install_claude_code_aliases(
            spellbook_dir, dry_run=False
        )

    assert result == {
        "installed": False,
        "rc_path": None,
        "aliases": [],
        "skipped_reason": (
            "cco not installed; install cco then re-run install.py"
        ),
    }
    # Operator-facing log message names cco as the gating cause.
    linux_records = [
        r for r in caplog.records if r.name == platform_mod.__name__
    ]
    assert len(linux_records) == 1
    assert "cco is not on PATH" in linux_records[0].getMessage()


@pytest.mark.posix_only
def test_dispatch_macos_returns_noop_without_calling_install_aliases(
    tmp_path, monkeypatch, caplog
):
    """MACOS: dispatch helper returns the documented noop dict and logs.

    install_aliases must NOT be called on macOS per the Sec 9.3 audit
    decision; the recorder fails the test if invoked. The log message is
    asserted via caplog with exact-equality on getMessage().
    """
    import logging

    from installer.platforms import claude_code as platform_mod
    from spellbook.core.compat import Platform

    spellbook_dir = tmp_path / "spellbook"

    def must_not_call(sb_dir, dry_run=False):
        pytest.fail(
            "install_aliases must not be called on macOS; "
            f"got args=({sb_dir!r}, dry_run={dry_run!r})"
        )

    def must_not_call_windows(sb_dir, dry_run=False):
        pytest.fail(
            "install_aliases_windows must not be called on macOS; "
            f"got args=({sb_dir!r}, dry_run={dry_run!r})"
        )

    monkeypatch.setattr(platform_mod, "get_platform", lambda: Platform.MACOS)
    monkeypatch.setattr(platform_mod, "install_aliases", must_not_call)
    monkeypatch.setattr(
        platform_mod, "install_aliases_windows", must_not_call_windows
    )

    expected_log_message = (
        "Claude Code L5 sandbox alias install (dry_run=False) is "
        "intentionally absent on macOS; cco's sandbox-exec profile is "
        "insufficient per Sec 9.3 audit. macOS sessions rely on L4 "
        "(PreToolUse hooks, shipped) and L6 (devcontainer, WI-8 planned). "
        "See scripts/spellbook-sandbox."
    )

    with caplog.at_level(logging.INFO, logger=platform_mod.__name__):
        result = platform_mod._install_claude_code_aliases(
            spellbook_dir, dry_run=False
        )

    assert result == {
        "installed": False,
        "rc_path": None,
        "aliases": [],
        "skipped_reason": "L5 macOS is intentionally absent (Sec 9.3 audit)",
    }

    # Exact-equality on the rendered log message catches silent edits to
    # the macOS rationale wording.
    macos_records = [
        r for r in caplog.records if r.name == platform_mod.__name__
    ]
    assert len(macos_records) == 1
    assert macos_records[0].getMessage() == expected_log_message
    assert macos_records[0].levelno == logging.INFO


@pytest.mark.posix_only
def test_dispatch_windows_calls_install_aliases_windows(tmp_path, monkeypatch):
    """WINDOWS: dispatch helper calls install_aliases_windows, not install_aliases.

    Records the windows call args; install_aliases recorder fails the test
    if invoked. Asserts exact equality on the call list and return value.
    """
    from installer.platforms import claude_code as platform_mod
    from spellbook.core.compat import Platform

    spellbook_dir = tmp_path / "spellbook"
    expected_return = {
        "installed": False,
        "rc_path": None,
        "aliases": [],
        "skipped_reason": (
            "Windows alias install is deferred to a later work item (Q-O)"
        ),
    }
    windows_calls: list[tuple] = []

    def must_not_call(sb_dir, dry_run=False):
        pytest.fail(
            "install_aliases must not be called on WINDOWS; "
            f"got args=({sb_dir!r}, dry_run={dry_run!r})"
        )

    def windows_recorder(sb_dir, dry_run=False):
        windows_calls.append((sb_dir, dry_run))
        return expected_return

    monkeypatch.setattr(platform_mod, "get_platform", lambda: Platform.WINDOWS)
    monkeypatch.setattr(platform_mod, "install_aliases", must_not_call)
    monkeypatch.setattr(
        platform_mod, "install_aliases_windows", windows_recorder
    )

    result = platform_mod._install_claude_code_aliases(
        spellbook_dir, dry_run=False
    )

    assert windows_calls == [(spellbook_dir, False)]
    assert result == expected_return


@pytest.mark.posix_only
def test_dispatch_unknown_platform_raises(tmp_path, monkeypatch):
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

    def must_not_call(sb_dir, dry_run=False):
        pytest.fail("install_aliases must not be called for unknown platform")

    def must_not_call_windows(sb_dir, dry_run=False):
        pytest.fail(
            "install_aliases_windows must not be called for unknown platform"
        )

    monkeypatch.setattr(platform_mod, "get_platform", lambda: fake)
    monkeypatch.setattr(platform_mod, "install_aliases", must_not_call)
    monkeypatch.setattr(
        platform_mod, "install_aliases_windows", must_not_call_windows
    )

    with pytest.raises(NotImplementedError) as exc_info:
        platform_mod._install_claude_code_aliases(spellbook_dir, dry_run=False)

    # Exact equality on the rendered exception message.
    assert str(exc_info.value) == (
        "No alias install handler for platform: <FakePlatform.BSD>"
    )


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
    (spellbook / "AGENTS.spellbook.md").write_text(
        "# Spellbook Context\n\nTest content.\n"
    )
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


@pytest.mark.posix_only
def test_install_invokes_dispatch_and_records_aliases_result(
    tmp_path, monkeypatch
):
    """ClaudeCodeInstaller.install() actually calls _install_claude_code_aliases.

    Behavioral wiring test: monkeypatch the dispatch helper to a recorder,
    run ``install()``, and assert (a) the recorder was called exactly once
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

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(
        "installer.platforms.claude_code.check_claude_cli_available",
        lambda *a, **kw: False,
    )
    monkeypatch.setattr(
        "installer.components.mcp.check_claude_cli_available",
        lambda *a, **kw: False,
    )

    calls: list[tuple] = []

    def recorder(sb_dir, dry_run=False):
        calls.append((sb_dir, dry_run))
        return {
            "installed": True,
            "rc_path": "/fake/.zshrc",
            "aliases": ["claude"],
            "skipped_reason": None,
        }

    monkeypatch.setattr(
        platform_mod, "_install_claude_code_aliases", recorder
    )

    installer = ClaudeCodeInstaller(
        spellbook_dir, config_dir, "1.0.0", dry_run=True
    )
    results = installer.install()

    # The recorder must be called exactly once with forwarded args.
    assert calls == [(spellbook_dir, True)], (
        f"expected dispatch helper called once with ({spellbook_dir!r}, True); "
        f"got calls={calls!r}"
    )

    # Exactly one aliases InstallResult must be present in the returned list.
    alias_results = [r for r in results if r.component == "aliases"]
    assert len(alias_results) == 1, (
        f"expected exactly one aliases InstallResult; got {alias_results!r}"
    )
    assert alias_results[0].action == "installed"
    assert alias_results[0].success is True
    assert "/fake/.zshrc" in alias_results[0].message


@pytest.mark.posix_only
def test_install_does_not_abort_when_dispatch_raises(tmp_path, monkeypatch):
    """A dispatch-helper exception records a failed aliases result and continues.

    Pins the F1 contract: an OSError (e.g. unwritable rc file) inside the
    dispatch helper must NOT propagate to ``core.py`` and abort the install.
    install() must (a) record an ``InstallResult`` with ``component="aliases"``,
    ``success=False``, and the original error text in the message, and
    (b) continue executing subsequent components -- specifically the
    security-critical hooks install -- so they still produce results.
    """
    from installer.platforms import claude_code as platform_mod
    from installer.platforms.claude_code import ClaudeCodeInstaller

    spellbook_dir = _make_minimal_spellbook_dir(tmp_path)
    config_dir = tmp_path / ".claude"
    config_dir.mkdir(parents=True)

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(
        "installer.platforms.claude_code.check_claude_cli_available",
        lambda *a, **kw: False,
    )
    monkeypatch.setattr(
        "installer.components.mcp.check_claude_cli_available",
        lambda *a, **kw: False,
    )

    def boom(sb_dir, dry_run=False):
        raise OSError("Permission denied")

    monkeypatch.setattr(
        platform_mod, "_install_claude_code_aliases", boom
    )

    installer = ClaudeCodeInstaller(
        spellbook_dir, config_dir, "1.0.0", dry_run=False
    )
    # install() must NOT raise; the exception must be caught and recorded.
    results = installer.install()

    # (a) failed aliases result is recorded with the original error text.
    alias_results = [r for r in results if r.component == "aliases"]
    assert len(alias_results) == 1
    assert alias_results[0].success is False
    assert alias_results[0].action == "failed"
    assert "Permission denied" in alias_results[0].message

    # (b) install did NOT abort early: subsequent components still ran.
    components = {r.component for r in results}
    assert "CLAUDE.md" in components, (
        "CLAUDE.md update step did not run after aliases failure; "
        "install() may have aborted early"
    )
    assert "hooks" in components, (
        "hooks install step did not run after aliases failure; "
        "the security-critical install path was skipped"
    )
    # The hooks result itself must reflect that hooks were actually
    # installed, not failed-by-association with the aliases failure.
    hook_results = [r for r in results if r.component == "hooks"]
    assert len(hook_results) == 1
    assert hook_results[0].success is True

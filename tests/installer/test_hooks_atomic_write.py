"""Regression: hooks.py settings writes go through atomic_replace and tolerate
Windows transient-error PermissionError on os.replace.

Drive-by part of WI-0. Without this, install_hooks/uninstall_hooks would lose
data on Windows when an antivirus / Claude Code / another process holds an
open handle on settings.json at the moment of write.

This test verifies that hooks.py's settings writes route through
``command_utils.atomic_replace`` (rather than ``Path.write_text``), and that
``atomic_replace`` tolerates a transient PermissionError on the first
``os.replace`` attempt and retries successfully. The retry semantics inside
``atomic_replace`` are also exercised here end-to-end via the real
``os.replace`` (only the platform-detection branch and the backoff sleep are
stubbed).

The retry loop's pure unit semantics (max attempts, backoff) are intended to
be covered by direct unit tests of ``spellbook.core.command_utils`` rather
than via this hooks-level integration test.
"""

import json
import os
import sys
from pathlib import Path

import tripwire
from dirty_equals import AnyThing

# Capture the real os.replace at import time so flaky-replace stubs can fall
# through to the genuine rename even after tripwire patches os.replace.
_REAL_OS_REPLACE = os.replace

# On Windows, install_hooks / uninstall_hooks call shutil.which("powershell")
# before reaching atomic_write_json. Tripwire's SubprocessPlugin always
# intercepts shutil.which; without a registered mock it returns None and the
# SUT short-circuits ("PowerShell not found"). On non-Windows the SUT does
# not enter that branch, so the mock sits unused (mock_which is required=False
# by default).
_FAKE_POWERSHELL = "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe"


def _register_powershell_which_mock() -> None:
    tripwire.subprocess.mock_which("powershell", returns=_FAKE_POWERSHELL)


def _assert_powershell_which_if_windows() -> None:
    if sys.platform == "win32":
        tripwire.subprocess.assert_which("powershell", returns=_FAKE_POWERSHELL)


def _write_baseline(settings_path: Path) -> None:
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps({"existing": "value"}), encoding="utf-8")


class _FlakyReplace:
    """Records the call count so .calls() registrations stay symmetric.

    First call raises ``PermissionError`` to mimic Windows ``WinError 5``;
    second call performs the real rename so the post-write assertions pass.
    """

    def __init__(self) -> None:
        self.count = 0

    def __call__(self, src, dst):
        self.count += 1
        if self.count == 1:
            raise PermissionError("simulated WinError 5: file in use")
        _REAL_OS_REPLACE(src, dst)


def _register_windows_branch(call_budget: int):
    """Force ``atomic_replace`` to enter the Windows retry path.

    ``platform.system()`` is queried inside ``atomic_replace`` and may also
    be queried by other ``hooks`` code paths; we hand back ``"Windows"`` for
    every call within the recorded budget. ``required(False)`` keeps the
    teardown happy if some calls aren't consumed.
    """
    mock_system = tripwire.mock("spellbook.core.command_utils:platform.system")
    for _ in range(call_budget):
        mock_system.__call__.required(False).returns("Windows")
    return mock_system


def test_install_hooks_retries_os_replace_permission_error_once(tmp_path):
    """install_hooks must retry os.replace once when it raises PermissionError.

    Simulates the Windows behaviour where os.replace fails with WinError 5
    (PermissionError) the first time because settings.json has an open
    handle, then succeeds on retry. atomic_replace's retry budget covers
    this; if hooks.py wrote via Path.write_text instead, the test would
    show no retry happened and the write would have lost data.
    """
    from installer.components import hooks

    config_dir = tmp_path / ".claude"
    settings_path = config_dir / "settings.json"
    _write_baseline(settings_path)

    # Force the Windows code path inside atomic_replace. install_hooks itself
    # also calls platform.system() at hook-path-resolution time, so we need
    # a healthy budget; non-required entries don't error if unused.
    mock_system = _register_windows_branch(call_budget=8)

    # Skip the real backoff sleep inside atomic_replace's retry loop. There
    # should be exactly one between the failed attempt and the successful
    # retry; mark it required for clarity.
    mock_sleep = tripwire.mock("spellbook.core.command_utils:time.sleep")
    mock_sleep.calls(lambda _: None)

    # First os.replace raises PermissionError; second performs the real
    # rename. atomic_replace's retry loop is what makes the second attempt
    # happen.
    flaky = _FlakyReplace()
    mock_replace = tripwire.mock("spellbook.core.command_utils:os.replace")
    mock_replace.calls(flaky)
    mock_replace.calls(flaky)

    _register_powershell_which_mock()

    with tripwire:
        result = hooks.install_hooks(
            settings_path=settings_path,
            spellbook_dir=tmp_path / "spellbook_dir",
            dry_run=False,
        )

    assert result.success is True
    assert result.component == "hooks"
    # Two os.replace attempts: first fails, second succeeds. This is the
    # core regression contract.
    assert flaky.count == 2

    _assert_powershell_which_if_windows()

    # Tripwire requires every recorded interaction to be asserted
    # (UnassertedInteractionsError otherwise); platform.system() is
    # called 5x by install_hooks + atomic_replace combined.
    with tripwire.in_any_order():
        mock_replace.assert_call(args=(AnyThing, AnyThing), kwargs={})
        mock_replace.assert_call(args=(AnyThing, AnyThing), kwargs={})
        mock_sleep.assert_call(args=(AnyThing,), kwargs={})
        for _ in range(5):
            mock_system.assert_call(args=(), kwargs={})

    # The hooks section ended up registered (with at least one PreToolUse
    # entry pointing at the spellbook hook), and the prior "existing" key
    # survived. We deliberately scope this test to the retry+atomic-write
    # contract; full hook-content correctness is covered in
    # tests/installer/test_hooks.py against unmocked atomic_replace.
    written = json.loads(settings_path.read_text(encoding="utf-8"))
    assert written["existing"] == "value"
    pretool_entries = written.get("hooks", {}).get("PreToolUse", [])
    assert isinstance(pretool_entries, list)
    assert len(pretool_entries) >= 1, (
        "PreToolUse must contain at least the spellbook hook entry after install"
    )



def test_uninstall_hooks_retries_os_replace_permission_error_once(tmp_path):
    """uninstall_hooks must also use the atomic-write retry path."""
    from installer.components import hooks

    config_dir = tmp_path / ".claude"
    settings_path = config_dir / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    # Pre-populate with a spellbook-managed hook so uninstall has work to do.
    settings_path.write_text(
        json.dumps(
            {
                "existing": "value",
                "hooks": {
                    "PreToolUse": [
                        {
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": "$SPELLBOOK_DIR/hooks/spellbook_hook.py",
                                    "spellbook_managed": True,
                                }
                            ]
                        }
                    ]
                },
            }
        ),
        encoding="utf-8",
    )

    mock_system = _register_windows_branch(call_budget=8)

    mock_sleep = tripwire.mock("spellbook.core.command_utils:time.sleep")
    mock_sleep.calls(lambda _: None)

    flaky = _FlakyReplace()
    mock_replace = tripwire.mock("spellbook.core.command_utils:os.replace")
    mock_replace.calls(flaky)
    mock_replace.calls(flaky)

    with tripwire:
        result = hooks.uninstall_hooks(
            settings_path=settings_path,
            spellbook_dir=tmp_path / "spellbook_dir",
            dry_run=False,
        )

    assert result.success is True
    assert flaky.count == 2

    # uninstall path: 1 platform.system() call from atomic_replace.
    with tripwire.in_any_order():
        mock_replace.assert_call(args=(AnyThing, AnyThing), kwargs={})
        mock_replace.assert_call(args=(AnyThing, AnyThing), kwargs={})
        mock_sleep.assert_call(args=(AnyThing,), kwargs={})
        mock_system.assert_call(args=(), kwargs={})

    written = json.loads(settings_path.read_text(encoding="utf-8"))
    assert written.get("existing") == "value"

"""Tests for the ``install_aliases_windows`` stub.

WI-7 defers the production Windows alias install + sandbox path to a
later WI (Q-O in the security architecture plan). The stub satisfies
the API contract for the upcoming ``claude_code.py`` platform dispatch
(LINUX / MACOS / WINDOWS) without committing to Windows behavior that
hasn't been audited.

These tests verify that the stub:

* Returns a noop dict matching ``install_aliases()``'s return shape.
* Does not write to the filesystem (regardless of ``dry_run``).
* Does not raise.
* Logs a clear deferral message on stdlib's ``logging`` channel.

All tests are marked ``windows_only`` per the impl plan §WI-7 contract,
even though the stub is pure Python and would in fact run cleanly on
POSIX. The marker matches the plan; the per-test placement (rather
than module-level) follows the L2 fix pattern from Task 2.
"""

import logging

import pytest

from installer.components.aliases import install_aliases_windows


_EXPECTED_NOOP_RESULT = {
    "installed": False,
    "rc_path": None,
    "aliases": [],
    "skipped_reason": "windows_alias_install_pending",
}

_EXPECTED_LOG_MESSAGE = (
    "Windows alias install is deferred to a later WI (Q-O); "
    "see install README for status."
)


@pytest.mark.windows_only
def test_install_aliases_windows_returns_noop_dict(tmp_path):
    """Returns the exact noop dict matching install_aliases() shape.

    Asserts complete-equality on the returned dict so that any drift in
    keys, values, or extra/missing fields is caught.
    """
    result = install_aliases_windows(tmp_path)

    assert result == _EXPECTED_NOOP_RESULT


@pytest.mark.windows_only
def test_install_aliases_windows_does_not_write_files(tmp_path):
    """The stub must not create any files under tmp_path.

    Snapshots the directory contents before and after the call and
    asserts exact-equality on the sorted path list.
    """
    before = sorted(p.relative_to(tmp_path) for p in tmp_path.rglob("*"))

    install_aliases_windows(tmp_path)

    after = sorted(p.relative_to(tmp_path) for p in tmp_path.rglob("*"))

    assert before == []
    assert after == []


@pytest.mark.windows_only
def test_install_aliases_windows_dry_run_path(tmp_path):
    """``dry_run=True`` returns the same noop shape and writes nothing.

    The stub is a no-op regardless of ``dry_run``; this test pins that
    contract so that a future implementation that introduces dry_run
    branching cannot accidentally write under dry_run=True (or vice
    versa) without updating this test.
    """
    before = sorted(p.relative_to(tmp_path) for p in tmp_path.rglob("*"))

    result = install_aliases_windows(tmp_path, dry_run=True)

    after = sorted(p.relative_to(tmp_path) for p in tmp_path.rglob("*"))

    assert result == _EXPECTED_NOOP_RESULT
    assert before == []
    assert after == []


@pytest.mark.windows_only
def test_install_aliases_windows_logs_deferral_message(tmp_path, caplog):
    """The stub logs the canonical deferral message via stdlib logging.

    The message string is asserted exactly against the expected text so
    that silent edits to the deferral wording (which doubles as
    operator-facing documentation of the Q-O punt) are caught.
    """
    with caplog.at_level(logging.INFO, logger="installer.components.aliases"):
        install_aliases_windows(tmp_path)

    messages = [r.getMessage() for r in caplog.records]
    assert messages == [_EXPECTED_LOG_MESSAGE]

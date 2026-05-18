"""Regression tests for the spellbook-cco entry-point rewrites at the two
non-platform-installer sites that gate behaviour on whether a sandbox binary
is on PATH:

* ``installer/tui.py`` — ``render_post_install_notes`` (post-install "Next
  Steps" panel that mentions the sandbox).
* ``install.py`` — interactive sandbox-aliases offer at the tail of
  ``run_installation``.

The post-WI-7 contract is:

* Default codepath: gate on ``shutil.which("spellbook-cco")``. The
  user-facing copy must reference ``spellbook-cco`` (and re-running
  ``install.py``) — never vanilla ``cco`` or ``nikvdp/cco``.
* Rollback codepath: when the operator sets
  ``SPELLBOOK_USE_VANILLA_CCO=1``, gate on ``shutil.which("cco")``
  (the vanilla nikvdp wrapper) instead. This mirrors the documented
  rollback escape hatch already wired through
  ``installer/platforms/claude_code.py::_install_claude_code_aliases``.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from types import SimpleNamespace

import pytest
import tripwire

from installer.components.spellbook_cco import _WARNING_USE_VANILLA_CCO


# ---------------------------------------------------------------------------
# installer/tui.py :: render_post_install_notes  (Task 4)
# ---------------------------------------------------------------------------


class _CapturingConsole:
    """Minimal Rich-console stand-in: records every printed object."""

    def __init__(self) -> None:
        self.printed: list[object] = []

    def print(self, obj: object) -> None:  # noqa: A003 - mirror Rich API
        self.printed.append(obj)


def _panel_body(panel: object) -> str:
    """Extract a Rich Panel's inner text (renderable) as a plain string."""
    renderable = getattr(panel, "renderable", panel)
    return str(renderable)


def test_tui_post_install_notes_gate_on_spellbook_cco_by_default(monkeypatch):
    """Default codepath: render_post_install_notes() consults
    ``shutil.which("spellbook-cco")`` — NOT vanilla ``cco`` — and the
    rendered "Next Steps" panel references spellbook-cco / re-running
    install.py.
    """
    from installer import tui

    monkeypatch.delenv("SPELLBOOK_USE_VANILLA_CCO", raising=False)

    tripwire.subprocess.mock_which("spellbook-cco", returns="/usr/local/bin/spellbook-cco")

    console = _CapturingConsole()
    with tripwire:
        tui.render_post_install_notes(console, ["claude_code"])

    # Gate is consulted on the post-rewrite binary name, not vanilla cco.
    tripwire.subprocess.assert_which("spellbook-cco", returns="/usr/local/bin/spellbook-cco")

    # Exactly one panel was rendered (Next Steps).
    assert len(console.printed) == 1
    body = _panel_body(console.printed[0])

    # Post-rewrite copy references spellbook-cco AND re-running install.py;
    # the legacy "nikvdp/cco" mention must be gone.
    assert "spellbook-cco" in body
    assert "nikvdp/cco" not in body


def test_tui_post_install_notes_routes_to_vanilla_cco_under_env_override(monkeypatch, capsys):
    """Rollback codepath: with ``SPELLBOOK_USE_VANILLA_CCO=1`` set,
    render_post_install_notes() gates on ``shutil.which("cco")`` (the
    vanilla nikvdp binary) and still emits the Next Steps panel when
    vanilla cco is on PATH. The post-rewrite copy still references the
    spellbook wrapper as the canonical entry point — the env override
    only changes the gate, not the user-facing instructions.

    F1 (Phase 4.5 finding): under env override the rollback WARNING
    must fire to stderr so the rollback codepath is visible in
    transcripts (matching the canonical emission in claude_code.py).
    """
    from installer import tui

    monkeypatch.setenv("SPELLBOOK_USE_VANILLA_CCO", "1")

    tripwire.subprocess.mock_which("cco", returns="/usr/local/bin/cco")

    console = _CapturingConsole()
    with tripwire:
        tui.render_post_install_notes(console, ["claude_code"])

    # Under env override the gate consults the vanilla binary.
    tripwire.subprocess.assert_which("cco", returns="/usr/local/bin/cco")

    # Panel still rendered.
    assert len(console.printed) == 1

    # F1: WARNING must fire to stderr under env override. The full
    # canonical warning (and ONLY that warning) must appear on stderr;
    # tightening from substring-on-fragments to full-equality with the
    # imported constant catches drift in the canonical wording.
    captured = capsys.readouterr()
    assert captured.err == _WARNING_USE_VANILLA_CCO


def test_tui_post_install_notes_emits_no_rollback_warning_by_default(monkeypatch, capsys):
    """F1 default-codepath guard: with no env override the WARNING must
    NOT fire. Regression guard: a future change that incorrectly fires
    the WARNING on the default path would be caught here."""
    from installer import tui

    monkeypatch.delenv("SPELLBOOK_USE_VANILLA_CCO", raising=False)
    tripwire.subprocess.mock_which("spellbook-cco", returns="/usr/local/bin/spellbook-cco")

    console = _CapturingConsole()
    with tripwire:
        tui.render_post_install_notes(console, ["claude_code"])

    tripwire.subprocess.assert_which("spellbook-cco", returns="/usr/local/bin/spellbook-cco")

    # Full-equality assertion: stderr must be empty on the default codepath.
    # Stronger than the prior `not in` substring check, which would pass
    # even if some other emitter wrote to stderr.
    captured = capsys.readouterr()
    assert captured.err == ""


def test_tui_post_install_notes_skips_panel_when_neither_binary_present(monkeypatch):
    """When the relevant sandbox binary is absent the "Next Steps" panel
    is not rendered at all (no platforms => nothing to say either)."""
    from installer import tui

    monkeypatch.delenv("SPELLBOOK_USE_VANILLA_CCO", raising=False)
    # Default codepath gates on spellbook-cco; the SUT consults the gate
    # before deciding whether to render the panel.
    tripwire.subprocess.mock_which("spellbook-cco", returns=None)

    console = _CapturingConsole()
    with tripwire:
        tui.render_post_install_notes(console, [])

    tripwire.subprocess.assert_which("spellbook-cco", returns=None)
    assert console.printed == []


# ---------------------------------------------------------------------------
# install.py :: _offer_sandbox_aliases  (Task 5)
# ---------------------------------------------------------------------------


def _make_session(success: bool = True) -> SimpleNamespace:
    """Build a minimal stand-in for installer.core.Installer.run()'s session."""
    return SimpleNamespace(
        success=success,
        previous_version=None,
        version="0.0.0-test",
        platforms_installed=["claude_code"],
    )


def test_install_offer_sandbox_aliases_gates_on_spellbook_cco_by_default(monkeypatch, tmp_path):
    """Default codepath: ``_offer_sandbox_aliases`` consults
    ``shutil.which("spellbook-cco")`` and, when present, dispatches to
    ``installer.components.aliases.install_aliases``.
    """
    import install as install_mod

    monkeypatch.delenv("SPELLBOOK_USE_VANILLA_CCO", raising=False)

    tripwire.subprocess.mock_which("spellbook-cco", returns="/usr/local/bin/spellbook-cco")

    # Mock the lazily-imported aliases module attributes via tripwire.
    rc_path = Path("/fake/.zshrc")
    get_shell_rc = tripwire.mock("installer.components.aliases:get_shell_rc_path")
    get_shell_rc.returns(rc_path)

    install_alias_mock = tripwire.mock("installer.components.aliases:install_aliases")
    install_alias_mock.returns({
        "installed": True,
        "rc_path": "/fake/.zshrc",
        "aliases": ["claude", "opencode"],
        "skipped_reason": None,
    })

    args = argparse.Namespace(dry_run=False, yes=True)
    session = _make_session(success=True)

    with tripwire:
        install_mod._offer_sandbox_aliases(args, session, tmp_path / "spellbook")

    tripwire.subprocess.assert_which("spellbook-cco", returns="/usr/local/bin/spellbook-cco")
    get_shell_rc.assert_call(args=(), kwargs={})
    install_alias_mock.assert_call(
        args=(tmp_path / "spellbook",), kwargs={"dry_run": False}
    )


def test_install_offer_sandbox_aliases_routes_to_vanilla_cco_under_env_override(
    monkeypatch, tmp_path, capsys
):
    """Rollback codepath: with ``SPELLBOOK_USE_VANILLA_CCO=1`` set,
    ``_offer_sandbox_aliases`` gates on ``shutil.which("cco")`` and
    dispatches when the vanilla binary is on PATH.

    F1 (Phase 4.5 finding): under env override the rollback WARNING
    must fire to stderr so the rollback codepath is visible in
    transcripts (matching the canonical emission in claude_code.py).
    """
    import install as install_mod

    monkeypatch.setenv("SPELLBOOK_USE_VANILLA_CCO", "1")

    tripwire.subprocess.mock_which("cco", returns="/usr/local/bin/cco")

    rc_path = Path("/fake/.zshrc")
    get_shell_rc = tripwire.mock("installer.components.aliases:get_shell_rc_path")
    get_shell_rc.returns(rc_path)

    install_alias_mock = tripwire.mock("installer.components.aliases:install_aliases")
    install_alias_mock.returns({
        "installed": True,
        "rc_path": "/fake/.zshrc",
        "aliases": ["claude", "opencode"],
        "skipped_reason": None,
    })

    args = argparse.Namespace(dry_run=False, yes=True)
    session = _make_session(success=True)

    with tripwire:
        install_mod._offer_sandbox_aliases(args, session, tmp_path / "spellbook")

    tripwire.subprocess.assert_which("cco", returns="/usr/local/bin/cco")
    get_shell_rc.assert_call(args=(), kwargs={})
    install_alias_mock.assert_call(
        args=(tmp_path / "spellbook",), kwargs={"dry_run": False}
    )

    # F1: WARNING must fire to stderr under env override. The full
    # canonical warning (and ONLY that warning) must appear on stderr;
    # tightening from substring-on-fragments to full-equality with the
    # imported constant catches drift in the canonical wording.
    captured = capsys.readouterr()
    assert captured.err == _WARNING_USE_VANILLA_CCO


def test_install_offer_sandbox_aliases_emits_no_rollback_warning_by_default(
    monkeypatch, tmp_path, capsys
):
    """F1 default-codepath guard: with no env override the WARNING must
    NOT fire. Regression guard."""
    import install as install_mod

    monkeypatch.delenv("SPELLBOOK_USE_VANILLA_CCO", raising=False)

    tripwire.subprocess.mock_which("spellbook-cco", returns="/usr/local/bin/spellbook-cco")

    rc_path = Path("/fake/.zshrc")
    get_shell_rc = tripwire.mock("installer.components.aliases:get_shell_rc_path")
    get_shell_rc.returns(rc_path)

    install_alias_mock = tripwire.mock("installer.components.aliases:install_aliases")
    install_alias_mock.returns({
        "installed": True,
        "rc_path": "/fake/.zshrc",
        "aliases": ["claude", "opencode"],
        "skipped_reason": None,
    })

    args = argparse.Namespace(dry_run=False, yes=True)
    session = _make_session(success=True)

    with tripwire:
        install_mod._offer_sandbox_aliases(args, session, tmp_path / "spellbook")

    tripwire.subprocess.assert_which("spellbook-cco", returns="/usr/local/bin/spellbook-cco")
    get_shell_rc.assert_call(args=(), kwargs={})
    install_alias_mock.assert_call(
        args=(tmp_path / "spellbook",), kwargs={"dry_run": False}
    )

    # Full-equality assertion: stderr must be empty on the default codepath.
    # Stronger than the prior `not in` substring check, which would pass
    # even if some other emitter wrote to stderr.
    captured = capsys.readouterr()
    assert captured.err == ""


def test_install_offer_sandbox_aliases_skips_when_dry_run(monkeypatch, tmp_path):
    """``args.dry_run=True`` short-circuits: the gate is never consulted
    and ``install_aliases`` is never invoked."""
    import install as install_mod

    monkeypatch.delenv("SPELLBOOK_USE_VANILLA_CCO", raising=False)

    args = argparse.Namespace(dry_run=True, yes=True)
    session = _make_session(success=True)

    # No tripwire mocks: dry_run short-circuits before any external
    # interaction. If shutil.which OR the aliases module were consulted,
    # tripwire's strict verifier would raise UnmockedInteractionError —
    # which is exactly the regression guard we want here.
    with tripwire:
        install_mod._offer_sandbox_aliases(args, session, tmp_path / "spellbook")


def test_install_offer_sandbox_aliases_skips_when_session_failed(monkeypatch, tmp_path):
    """``session.success=False`` short-circuits: no gate, no dispatch."""
    import install as install_mod

    monkeypatch.delenv("SPELLBOOK_USE_VANILLA_CCO", raising=False)

    args = argparse.Namespace(dry_run=False, yes=True)
    session = _make_session(success=False)

    # No tripwire mocks: session-failed short-circuits before any
    # external interaction. Any escape would raise
    # UnmockedInteractionError.
    with tripwire:
        install_mod._offer_sandbox_aliases(args, session, tmp_path / "spellbook")

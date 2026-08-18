"""Tests for the shared defaults wizard's prompt surface.

The wizard offered a ``session_mode`` choice whose options came from an
``ImportError`` fallback tuple. The import it guarded had been deleted, so the
fallback ran on every invocation and offered modes (``fun``, ``tarot``) whose
skills no longer ship. These tests assert on the wizard's actual printed
prompts rather than on its internals, so a reintroduced dead option fails here
regardless of where the option list comes from.
"""

import re
from pathlib import Path

import pytest

from installer.wizards import defaults as defaults_wizard

REPO_ROOT = Path(__file__).resolve().parents[2]

# Matches a numbered option line emitted by ``_prompt_choice``: "  1. none".
_OPTION_LINE = re.compile(r"^\s*\d+\.\s+(\S+)\s*$")


class _Args:
    dry_run = False
    reconfigure = True


@pytest.fixture
def wizard_output(monkeypatch, capsys):
    """Run the wizard with every side effect stubbed; return its stdout.

    ``input`` returns empty (keep current) so the run terminates without
    consuming a real tty, and ``_write`` is neutered so no user config file is
    touched.
    """
    monkeypatch.setattr(defaults_wizard._sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda *a, **kw: "")
    monkeypatch.setattr(defaults_wizard, "_write", lambda key, value: None)
    monkeypatch.setattr(defaults_wizard, "_is_explicit", lambda key: False)
    monkeypatch.setattr(defaults_wizard, "_config_get", lambda key, default: default)

    defaults_wizard.run_defaults_wizard(_Args())
    return capsys.readouterr().out


def test_option_line_detector_matches_the_wizard_format():
    """Pin the detector the coverage test depends on.

    Without this, a detector that matched nothing would make that test pass
    for the wrong reason.
    """
    assert _OPTION_LINE.match("  2. fun").group(1) == "fun"
    assert _OPTION_LINE.match("Enable native OS notifications? [Y/n]: ") is None


def test_wizard_offers_no_mode_without_a_backing_skill(wizard_output):
    """Every enum option the wizard offers must have a skill directory behind it.

    ``none`` is the absence of a mode and needs no skill.
    """
    # Proves the wizard actually ran; an early return would otherwise satisfy
    # the assertion below with an empty option list.
    assert "Additional defaults" in wizard_output

    offered = [
        m.group(1)
        for m in (_OPTION_LINE.match(line) for line in wizard_output.splitlines())
        if m
    ]
    unbacked = [
        option
        for option in offered
        if option != "none" and not (REPO_ROOT / "skills" / f"{option}-mode").is_dir()
    ]
    assert unbacked == []


def test_wizard_does_not_prompt_for_session_mode(wizard_output):
    """No session-mode prompt survives: nothing reads the key."""
    assert "session mode" not in wizard_output.lower()


def test_wizard_carries_no_fallback_for_a_deleted_constant():
    """``SESSION_MODES`` was deleted; no guarded import may stand in for it.

    An ``ImportError`` fallback whose import can never succeed is
    indistinguishable from a hardcoded literal, and hides the deletion.
    """
    source = (REPO_ROOT / "installer" / "wizards" / "defaults.py").read_text()
    assert "SESSION_MODES" not in source
    assert "session_mode" not in source

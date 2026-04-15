"""Tests for spellbook.memory.utils.

Covers the canonical `derive_namespace_from_cwd` implementation that both
the MCP route and the hook rely on (hook keeps an inline copy with a sync
comment; see I7 in the code review).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from spellbook.memory.utils import derive_namespace_from_cwd


def test_empty_cwd_returns_empty_string():
    assert derive_namespace_from_cwd("") == ""
    assert derive_namespace_from_cwd(None) == ""  # type: ignore[arg-type]


def test_encodes_absolute_path(monkeypatch):
    """Non-git path: fall back to input, project-encode."""
    def fake_run(*args, **kwargs):
        class R:
            returncode = 128
            stdout = ""
            stderr = ""
        return R()

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert derive_namespace_from_cwd("/Users/alice/proj") == "Users-alice-proj"


def test_resolves_worktree_to_toplevel(monkeypatch):
    """Worktree path -> git toplevel is used for the encoding."""
    def fake_run(args, **kwargs):
        # Only handle the git rev-parse call.
        assert args[:4] == ["git", "-C", "/Users/alice/wt/feature", "rev-parse"]

        class R:
            returncode = 0
            stdout = "/Users/alice/proj\n"
            stderr = ""
        return R()

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert derive_namespace_from_cwd("/Users/alice/wt/feature") == "Users-alice-proj"


def test_git_failure_falls_back_to_input(monkeypatch):
    """OSError (e.g., git not installed) -> use the raw cwd."""
    def fake_run(*a, **kw):
        raise OSError("git not found")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert derive_namespace_from_cwd("/Users/alice/proj") == "Users-alice-proj"


def test_windows_style_separators(monkeypatch):
    """Backslashes are normalized to forward slashes before encoding."""
    def fake_run(*a, **kw):
        class R:
            returncode = 128
            stdout = ""
            stderr = ""
        return R()

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert derive_namespace_from_cwd(r"C:\Users\alice\proj") == "C:-Users-alice-proj"


def test_accepts_pathlib_path(monkeypatch):
    def fake_run(*a, **kw):
        class R:
            returncode = 128
            stdout = ""
            stderr = ""
        return R()

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert derive_namespace_from_cwd(Path("/Users/alice/proj")) == "Users-alice-proj"


def test_routes_wrapper_delegates_to_utils(monkeypatch):
    """The routes._derive_namespace_from_cwd wrapper must call through."""
    from spellbook.mcp import routes as _routes

    called_with: list[str] = []

    def spy(cwd):
        called_with.append(cwd)
        return "spy-result"

    monkeypatch.setattr(
        "spellbook.memory.utils.derive_namespace_from_cwd",
        spy,
    )
    assert _routes._derive_namespace_from_cwd("/some/path") == "spy-result"
    assert called_with == ["/some/path"]


def test_hook_namespace_encoding_matches_canonical(monkeypatch):
    """Hook's inline `_derive_namespace` encoding must match the canonical util.

    If this test fails, someone changed one copy without the other; sync them.
    """
    import sys

    hooks_dir = Path(__file__).resolve().parent.parent / "hooks"
    if str(hooks_dir) not in sys.path:
        sys.path.insert(0, str(hooks_dir))
    import spellbook_hook  # noqa: E402

    # Stub the hook's git resolver so both sides see the same resolved path.
    monkeypatch.setattr(
        spellbook_hook,
        "_resolve_git_context",
        lambda cwd: ("/Users/alice/proj", ""),
    )

    # And stub subprocess for the canonical util similarly.
    def fake_run(*a, **kw):
        class R:
            returncode = 0
            stdout = "/Users/alice/proj\n"
            stderr = ""
        return R()

    monkeypatch.setattr(subprocess, "run", fake_run)

    ns_hook, _, _ = spellbook_hook._derive_namespace("/Users/alice/wt/feature")
    ns_util = derive_namespace_from_cwd("/Users/alice/wt/feature")
    assert ns_hook == ns_util == "Users-alice-proj"

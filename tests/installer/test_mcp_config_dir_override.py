"""Unit tests for the MCP config-dir override decision.

Covers the pure predicate ``_config_dir_needs_override`` (tested directly with
constructed Path objects) and the ``_subprocess_env`` wrapper's 4-case contract
(tested by setting/unsetting the ambient CLAUDE_CONFIG_DIR via the allowed
monkeypatch.setenv/delenv and asserting full equality on the returned value).

Tripwire rule: no unittest.mock, no monkeypatch.setattr/setitem/delattr. Only
env manipulation (setenv/delenv) and tmp_path are used.
"""

import os

import pytest

from installer.config import PLATFORM_CONFIG

from installer.components.mcp import (
    _config_dir_needs_override,
    _default_claude_config_dir,
    _subprocess_env,
)


# ---------------------------------------------------------------------------
# _config_dir_needs_override — pure predicate, no mocks, no env.
# ---------------------------------------------------------------------------


def test_needs_override_false_when_config_dir_none(tmp_path):
    default = tmp_path / ".claude"
    default.mkdir()
    assert _config_dir_needs_override(None, default) is False


def test_needs_override_false_when_equal_to_default(tmp_path):
    default = tmp_path / ".claude"
    default.mkdir()
    assert _config_dir_needs_override(default, default) is False


def test_needs_override_true_when_different_from_default(tmp_path):
    default = tmp_path / ".claude"
    default.mkdir()
    other = tmp_path / ".claude-work"
    other.mkdir()
    assert _config_dir_needs_override(other, default) is True


def test_needs_override_false_for_symlink_to_default(tmp_path):
    default = tmp_path / ".claude"
    default.mkdir()
    link = tmp_path / "link-to-claude"
    try:
        link.symlink_to(default, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation not permitted on this platform")
    # resolve() equalizes the symlink and its target -> no override.
    assert _config_dir_needs_override(link, default) is False


def test_needs_override_false_for_dotdot_path_resolving_to_default(tmp_path):
    default = tmp_path / ".claude"
    default.mkdir()
    (default / "sub").mkdir()
    # Not string-equal to `default` as a plain Path (it has a "sub"/".." tail),
    # but resolves to `default`. If .resolve() were dropped from the predicate,
    # the plain-Path comparison would be False and this test would fail.
    equivalent = default / "sub" / ".."
    assert equivalent != default
    assert equivalent.resolve() == default.resolve()
    assert _config_dir_needs_override(equivalent, default) is False


# ---------------------------------------------------------------------------
# _subprocess_env — 4-case contract. default_config_dir is passed explicitly
# (a tmp_path dir) so the test never depends on the real ~/.claude.
# ---------------------------------------------------------------------------


def test_subprocess_env_default_dir_no_ambient_returns_none(tmp_path, monkeypatch):
    default = tmp_path / ".claude"
    default.mkdir()
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    assert _subprocess_env(default, default_config_dir=default) is None


def test_subprocess_env_none_config_no_ambient_returns_none(tmp_path, monkeypatch):
    default = tmp_path / ".claude"
    default.mkdir()
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    assert _subprocess_env(None, default_config_dir=default) is None


def test_subprocess_env_default_dir_redirecting_stray_strips_var(tmp_path, monkeypatch):
    default = tmp_path / ".claude"
    default.mkdir()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(elsewhere))

    env = _subprocess_env(default, default_config_dir=default)

    expected = {k: v for k, v in os.environ.items() if k != "CLAUDE_CONFIG_DIR"}
    assert env == expected
    assert "CLAUDE_CONFIG_DIR" not in env
    assert "CLAUDE_CONFIG_DIR" in os.environ  # source env untouched
    assert env.get("PATH") == os.environ.get("PATH")


def test_subprocess_env_default_dir_confirming_stray_returns_none(tmp_path, monkeypatch):
    default = tmp_path / ".claude"
    default.mkdir()
    # A confirming stray: a different spelling that resolves to the default.
    link = tmp_path / "link-to-claude"
    try:
        link.symlink_to(default, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation not permitted on this platform")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(link))
    assert _subprocess_env(default, default_config_dir=default) is None


def test_subprocess_env_non_default_dir_sets_override(tmp_path, monkeypatch):
    default = tmp_path / ".claude"
    default.mkdir()
    other = tmp_path / ".claude-work"
    other.mkdir()
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)

    env = _subprocess_env(other, default_config_dir=default)

    expected = {**os.environ, "CLAUDE_CONFIG_DIR": str(other)}
    assert env == expected
    assert env["CLAUDE_CONFIG_DIR"] == str(other)
    assert env.get("PATH") == os.environ.get("PATH")


# ---------------------------------------------------------------------------
# Production-path coverage: the internal default_config_dir resolution used by
# every real caller (all invoke _subprocess_env(config_dir) with NO second
# arg). These two tests exercise the source-of-truth lookup and the internal
# None-resolution branch directly, so a mistyped PLATFORM_CONFIG key fails
# loudly instead of shipping green. Both are mock-free and HOME-independent.
# ---------------------------------------------------------------------------


def test_default_claude_config_dir_matches_platform_config():
    # Locks the helper to the single source of truth in installer.config;
    # a mistyped dict key ("claude_code" / "default_config_dir") fails here.
    assert _default_claude_config_dir() == PLATFORM_CONFIG["claude_code"]["default_config_dir"]


def test_subprocess_env_none_returns_none_and_inherits_ambient(monkeypatch):
    # config_dir=None early-returns before any default-resolution or
    # strip/honor logic runs -- it inherits the ambient env unchanged.
    # Proves this by leaving the ambient var unset; the ambient-with-stray
    # case is covered separately below.
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    assert _subprocess_env(None) is None


def test_subprocess_env_none_with_redirecting_ambient_inherits(tmp_path, monkeypatch):
    # Regression test: config_dir=None must inherit the ambient env
    # UNCHANGED even when CLAUDE_CONFIG_DIR is set to a non-default
    # (redirecting) value. Previously, None was treated as equivalent to
    # the default config dir and the redirecting stray got stripped --
    # breaking callers like list_registered_mcp_servers() for users with a
    # custom ambient CLAUDE_CONFIG_DIR.
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "some-other-dir"))
    assert _subprocess_env(None) is None


def test_subprocess_env_non_default_dir_no_explicit_default_sets_override(
    tmp_path, monkeypatch
):
    # Calls _subprocess_env(custom_dir) with NO second arg, forcing the
    # internal `_default_claude_config_dir()` to be the operative default. If
    # that helper returned a wrong path, custom_dir might wrongly equal it and
    # collapse to None instead of setting the override.
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    custom_dir = tmp_path / "custom-config"
    custom_dir.mkdir()

    env = _subprocess_env(custom_dir)

    expected = {**os.environ, "CLAUDE_CONFIG_DIR": str(custom_dir)}
    assert env == expected


def test_subprocess_env_default_dir_empty_stray_returns_none(tmp_path, monkeypatch):
    # An empty (or whitespace-only) ambient CLAUDE_CONFIG_DIR must be treated
    # as effectively unset -- inherit the ambient env unchanged -- rather than
    # falling through to Path("").resolve(), which resolves to the CWD and
    # could spuriously match the default.
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", "")
    default = tmp_path / ".claude"
    default.mkdir()
    assert _subprocess_env(default, default_config_dir=default) is None

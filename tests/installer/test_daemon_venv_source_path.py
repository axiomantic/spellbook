"""Tests for ensure_daemon_venv's source-path tracking.

The daemon venv has spellbook installed in editable mode pointing at the
stable source symlink. But if the user had an older install where the
editable install pointed at a raw worktree path, we need to detect that
(via ``~/.local/spellbook/daemon-venv/.source-path``) and force a
reinstall. We also need to handle the edge case of a missing marker file
on fresh installs and upgrades.

These tests mock all ``subprocess.run`` calls so the real filesystem and
``uv``/``pip`` binaries are never touched.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List

import pytest


@dataclass
class _FakeCompleted:
    returncode: int = 0
    stdout: str = ""
    stderr: str = ""


@pytest.fixture
def fake_venv(tmp_path, monkeypatch):
    """Point daemon venv paths at a tmp_path location and stage a pre-existing venv."""
    venv_dir = tmp_path / "daemon-venv"
    venv_dir.mkdir()
    bin_dir = venv_dir / "bin"
    bin_dir.mkdir()
    # Touch a fake python executable so ``daemon_python.exists()`` returns True.
    daemon_python = bin_dir / "python"
    daemon_python.write_text("")
    daemon_python.chmod(0o755)

    import installer.components.mcp as mcp_mod
    monkeypatch.setattr(mcp_mod, "get_daemon_venv_dir", lambda: venv_dir)
    monkeypatch.setattr(mcp_mod, "get_daemon_python", lambda: daemon_python)
    monkeypatch.setattr(
        mcp_mod,
        "stop_daemon",
        lambda dry_run=False: (True, "stopped"),
    )
    return venv_dir


@pytest.fixture
def source_dir(tmp_path):
    src = tmp_path / "worktree"
    src.mkdir()
    (src / "pyproject.toml").write_text("[project]\nname='spellbook'\n")
    return src


@pytest.fixture
def config_dir(tmp_path, monkeypatch):
    cfg = tmp_path / "spellbook-config"
    cfg.mkdir()
    import installer.config as config_mod
    import installer.components.source_link as source_link_mod
    import installer.components.hooks as hooks_mod
    monkeypatch.setattr(config_mod, "get_spellbook_config_dir", lambda: cfg)
    monkeypatch.setattr(source_link_mod, "get_spellbook_config_dir", lambda: cfg)
    monkeypatch.setattr(hooks_mod, "get_spellbook_config_dir", lambda: cfg, raising=False)
    return cfg


def _make_subprocess_recorder(calls: List[List[str]]):
    """Create a subprocess.run replacement that records args and returns success."""
    def fake_run(cmd, *args, **kwargs):
        # Only record list-form commands (str commands shouldn't happen here).
        if isinstance(cmd, list):
            calls.append(list(cmd))
        return _FakeCompleted(returncode=0, stdout="", stderr="")
    return fake_run


def test_pip_reinstalls_when_source_path_marker_missing(
    fake_venv, source_dir, config_dir, monkeypatch
):
    """No marker file = we can't prove the editable install matches, so
    force a reinstall with uninstall-twice + install.
    """
    from installer.components.mcp import ensure_daemon_venv

    # Existing hash file matches so the "hash changed" path is NOT what
    # triggers the reinstall -- the missing marker is.
    from installer.components.mcp import _hash_file
    pyproject = source_dir / "pyproject.toml"
    hash_file = fake_venv / ".pyproject-hash"
    hash_file.write_text(_hash_file(pyproject))

    calls: List[List[str]] = []
    monkeypatch.setattr(subprocess, "run", _make_subprocess_recorder(calls))
    # Also patch in mcp module's local import
    import installer.components.mcp as mcp_mod
    monkeypatch.setattr(mcp_mod.subprocess, "run", _make_subprocess_recorder(calls))

    ok, msg = ensure_daemon_venv(source_dir)

    assert ok, msg

    # Expected: two uninstalls, one editable install of the SYMLINK path (not source_dir).
    from installer.components.source_link import get_source_link_path
    daemon_python = fake_venv / "bin" / "python"

    uninstall_calls = [c for c in calls if "uninstall" in c]
    install_calls = [
        c for c in calls
        if "install" in c and "-e" in c
    ]
    assert len(uninstall_calls) == 2
    assert uninstall_calls[0] == [
        "uv", "pip", "uninstall",
        "--python", str(daemon_python),
        "spellbook",
    ]
    assert uninstall_calls[1] == [
        "uv", "pip", "uninstall",
        "--python", str(daemon_python),
        "spellbook",
    ]
    assert len(install_calls) == 1
    assert install_calls[0] == [
        "uv", "pip", "install",
        "--python", str(daemon_python),
        "-e", str(get_source_link_path()),
        "--no-deps",
    ]

    # Marker written afterwards.
    marker = fake_venv / ".source-path"
    assert marker.read_text() == str(source_dir.resolve())


def test_pip_reinstalls_when_source_path_changed(
    fake_venv, source_dir, config_dir, monkeypatch
):
    """Marker exists but points at a different worktree: force reinstall."""
    from installer.components.mcp import ensure_daemon_venv, _hash_file
    pyproject = source_dir / "pyproject.toml"
    (fake_venv / ".pyproject-hash").write_text(_hash_file(pyproject))
    (fake_venv / ".source-path").write_text("/some/other/worktree")

    calls: List[List[str]] = []
    import installer.components.mcp as mcp_mod
    monkeypatch.setattr(mcp_mod.subprocess, "run", _make_subprocess_recorder(calls))

    ok, msg = ensure_daemon_venv(source_dir)

    assert ok, msg
    uninstall_calls = [c for c in calls if "uninstall" in c]
    assert len(uninstall_calls) == 2
    install_calls = [c for c in calls if "install" in c and "-e" in c]
    assert len(install_calls) == 1
    assert (fake_venv / ".source-path").read_text() == str(source_dir.resolve())


def test_pip_skips_when_source_path_unchanged_and_hash_unchanged(
    fake_venv, source_dir, config_dir, monkeypatch
):
    """Marker and hash both match: no subprocess calls at all."""
    from installer.components.mcp import ensure_daemon_venv, _hash_file
    pyproject = source_dir / "pyproject.toml"
    (fake_venv / ".pyproject-hash").write_text(_hash_file(pyproject))
    (fake_venv / ".source-path").write_text(str(source_dir.resolve()))

    calls: List[List[str]] = []
    import installer.components.mcp as mcp_mod
    monkeypatch.setattr(mcp_mod.subprocess, "run", _make_subprocess_recorder(calls))

    ok, msg = ensure_daemon_venv(source_dir)

    assert ok, msg
    assert calls == []


def test_uninstall_runs_twice(fake_venv, source_dir, config_dir, monkeypatch):
    """The defensive double-uninstall ordering: both uninstalls run BEFORE
    any install command. This guards against stale metadata where a
    single uninstall leaves dangling .dist-info entries.
    """
    from installer.components.mcp import ensure_daemon_venv, _hash_file
    pyproject = source_dir / "pyproject.toml"
    (fake_venv / ".pyproject-hash").write_text(_hash_file(pyproject))
    # Force a refresh via differing source-path.
    (fake_venv / ".source-path").write_text("/somewhere/else")

    calls: List[List[str]] = []
    import installer.components.mcp as mcp_mod
    monkeypatch.setattr(mcp_mod.subprocess, "run", _make_subprocess_recorder(calls))

    ok, _ = ensure_daemon_venv(source_dir)
    assert ok

    # Find indices of the uninstall/install calls.
    uninstall_idxs = [i for i, c in enumerate(calls) if "uninstall" in c]
    install_idxs = [
        i for i, c in enumerate(calls) if "install" in c and "-e" in c
    ]
    assert len(uninstall_idxs) == 2
    assert len(install_idxs) == 1
    # Both uninstalls happen before the install.
    assert uninstall_idxs[0] < uninstall_idxs[1] < install_idxs[0]

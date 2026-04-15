"""Tests for the source_link installer component.

The ``source_link`` component maintains a stable symlink at
``$SPELLBOOK_CONFIG_DIR/source`` that always points at the active spellbook
source tree. Artifacts (settings.json hooks, launchd plist, editable install)
reference this symlink path instead of the underlying worktree directory so
that switching worktrees does not leave stale references behind.
"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def config_dir(tmp_path, monkeypatch):
    """Redirect ``get_spellbook_config_dir`` to a temporary directory."""
    cfg = tmp_path / "spellbook-config"
    cfg.mkdir()
    monkeypatch.setattr(
        "installer.config.get_spellbook_config_dir",
        lambda: cfg,
    )
    return cfg


@pytest.fixture
def source_dir(tmp_path):
    src = tmp_path / "worktree-A"
    src.mkdir()
    (src / "pyproject.toml").write_text("[project]\nname='spellbook'\n")
    return src


def test_get_source_link_path_uses_config_dir(config_dir):
    from installer.components.source_link import get_source_link_path
    assert get_source_link_path() == config_dir / "source"


def test_creates_link_when_absent(config_dir, source_dir):
    from installer.components.source_link import ensure_source_link, SourceLinkResult

    result = ensure_source_link(source_dir=source_dir)

    link_path = config_dir / "source"
    assert result == SourceLinkResult(
        link_path=link_path,
        target=source_dir.resolve(),
        action="created",
        backup_path=None,
        message=f"Created symlink: {link_path} -> {source_dir.resolve()}",
    )
    assert link_path.is_symlink()
    assert link_path.resolve() == source_dir.resolve()


def test_updates_when_pointing_elsewhere(config_dir, source_dir, tmp_path):
    from installer.components.source_link import ensure_source_link, SourceLinkResult

    old_source = tmp_path / "worktree-old"
    old_source.mkdir()
    link_path = config_dir / "source"
    link_path.symlink_to(old_source.resolve())

    result = ensure_source_link(source_dir=source_dir)

    assert result == SourceLinkResult(
        link_path=link_path,
        target=source_dir.resolve(),
        action="updated",
        backup_path=None,
        message=f"Updated symlink: {link_path} -> {source_dir.resolve()}",
    )
    assert link_path.is_symlink()
    assert link_path.resolve() == source_dir.resolve()


def test_unchanged_when_already_correct(config_dir, source_dir):
    import sys as _sys
    from installer.components.source_link import ensure_source_link, SourceLinkResult

    link_path = config_dir / "source"
    # Use the cross-platform helper so the link is created the same way
    # the installer creates it (handles Windows junction fallback).
    from installer.compat import create_link
    create_link(source=source_dir.resolve(), target=link_path)

    result = ensure_source_link(source_dir=source_dir)

    # On Windows without admin the link may materialize as a junction rather
    # than a symlink. ensure_source_link still treats it as the correct
    # indirection and returns action="unchanged"; only skip if the link
    # couldn't be created at all.
    if not link_path.exists():
        pytest.skip("Link creation unsupported in this environment")

    assert result.link_path == link_path
    assert result.target == source_dir.resolve()
    assert result.action == "unchanged"
    assert result.backup_path is None
    assert result.message.startswith("Symlink already correct:")
    assert link_path.resolve() == source_dir.resolve()


def test_real_dir_with_yes_backs_up_and_links(config_dir, source_dir, monkeypatch):
    from installer.components import source_link as source_link_mod
    from installer.components.source_link import ensure_source_link, SourceLinkResult

    # Pre-create a real directory at link_path with a sentinel file inside.
    link_path = config_dir / "source"
    link_path.mkdir()
    (link_path / "sentinel.txt").write_text("hello")

    # Freeze the backup timestamp so we can assert the full result shape.
    monkeypatch.setattr(source_link_mod, "_backup_timestamp", lambda: "20260414-101112")

    result = ensure_source_link(source_dir=source_dir, yes=True)

    expected_backup = config_dir / "source.backup-20260414-101112"
    assert result == SourceLinkResult(
        link_path=link_path,
        target=source_dir.resolve(),
        action="backed_up_and_linked",
        backup_path=expected_backup,
        message=(
            f"Backed up existing directory to {expected_backup} and created "
            f"symlink: {link_path} -> {source_dir.resolve()}"
        ),
    )
    assert link_path.is_symlink()
    assert link_path.resolve() == source_dir.resolve()
    assert expected_backup.is_dir()
    assert (expected_backup / "sentinel.txt").read_text() == "hello"


def test_real_dir_without_yes_raises(config_dir, source_dir):
    from installer.components.source_link import (
        ensure_source_link,
        InstallError,
    )

    link_path = config_dir / "source"
    link_path.mkdir()
    (link_path / "sentinel.txt").write_text("hello")

    with pytest.raises(InstallError) as excinfo:
        ensure_source_link(source_dir=source_dir)

    assert str(excinfo.value) == (
        f"{link_path} exists and is not a symlink. Remove it manually or "
        f"re-run with --yes to back it up automatically."
    )
    # Nothing should have changed
    assert not link_path.is_symlink()
    assert (link_path / "sentinel.txt").read_text() == "hello"


def test_dry_run_makes_no_changes(config_dir, source_dir):
    from installer.components.source_link import ensure_source_link, SourceLinkResult

    link_path = config_dir / "source"

    result = ensure_source_link(source_dir=source_dir, dry_run=True)

    assert result == SourceLinkResult(
        link_path=link_path,
        target=source_dir.resolve(),
        action="created",
        backup_path=None,
        message=(
            f"[dry-run] Would create symlink: {link_path} -> {source_dir.resolve()}"
        ),
    )
    assert not link_path.exists()
    assert not link_path.is_symlink()

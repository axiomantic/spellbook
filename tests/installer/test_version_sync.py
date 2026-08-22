"""Tests for ``installer.version.sync_version_to_files`` failure signalling.

The function used to swallow ``json.JSONDecodeError`` and ``OSError`` and
return an empty list, which is exactly what it returns for a clean tree. A
caller could not tell "nothing needed doing" from "the manifest is broken",
so a broken manifest produced a green exit. These tests pin the three
outcomes as distinguishable.
"""

import json
import os

import pytest

from installer.version import VersionSyncError, sync_version_to_files

VERSION = "9.9.9"
MANIFEST_PARTS = ("extensions", "gemini", "gemini-extension.json")


def _tree(tmp_path, payload):
    """Build a spellbook-shaped tree whose gemini manifest holds ``payload``."""
    (tmp_path / ".version").write_text(VERSION + "\n", encoding="utf-8")
    manifest = tmp_path.joinpath(*MANIFEST_PARTS)
    manifest.parent.mkdir(parents=True)
    manifest.write_text(payload, encoding="utf-8")
    return manifest


def test_clean_tree_returns_empty_list(tmp_path):
    """A manifest already at ``version`` is not rewritten and reports no change."""
    manifest = _tree(tmp_path, json.dumps({"version": VERSION, "name": "spellbook"}))
    before = manifest.read_text(encoding="utf-8")

    assert sync_version_to_files(tmp_path, VERSION) == []
    assert manifest.read_text(encoding="utf-8") == before


def test_stale_tree_returns_the_written_path(tmp_path):
    """A stale manifest is rewritten, reported, and keeps its other keys."""
    manifest = _tree(tmp_path, json.dumps({"version": "0.1.0", "name": "spellbook"}))

    assert sync_version_to_files(tmp_path, VERSION) == [str(manifest)]
    assert json.loads(manifest.read_text(encoding="utf-8")) == {
        "version": VERSION,
        "name": "spellbook",
    }


def test_malformed_manifest_raises_and_names_the_file(tmp_path):
    """Invalid JSON raises rather than reporting the clean-tree empty list."""
    manifest = _tree(tmp_path, "{not json")

    with pytest.raises(VersionSyncError) as excinfo:
        sync_version_to_files(tmp_path, VERSION)

    error = excinfo.value
    assert error.updated == []
    assert [path for path, _ in error.failures] == [str(manifest)]
    assert "invalid JSON" in error.failures[0][1]
    assert str(manifest) in str(error)


def test_non_object_manifest_raises_with_the_found_type(tmp_path):
    """A JSON array parses cleanly but is still an unusable manifest."""
    _tree(tmp_path, "[]")

    with pytest.raises(VersionSyncError) as excinfo:
        sync_version_to_files(tmp_path, VERSION)

    assert "expected a JSON object, found list" in excinfo.value.failures[0][1]


@pytest.mark.posix_only
@pytest.mark.skipif(
    getattr(os, "getuid", lambda: 1)() == 0,
    reason="root bypasses file permission bits",
)
def test_unreadable_manifest_raises_distinctly_from_malformed(tmp_path):
    """A permission failure raises with a read-failure reason, not a parse one."""
    manifest = _tree(tmp_path, json.dumps({"version": "0.1.0"}))
    manifest.chmod(0o000)
    try:
        with pytest.raises(VersionSyncError) as excinfo:
            sync_version_to_files(tmp_path, VERSION)
    finally:
        manifest.chmod(0o644)

    reason = excinfo.value.failures[0][1]
    assert "could not be read" in reason
    assert "invalid JSON" not in reason


def test_absent_manifest_is_not_a_failure(tmp_path):
    """A tree that does not carry the manifest at all has nothing to sync."""
    (tmp_path / ".version").write_text(VERSION + "\n", encoding="utf-8")

    assert sync_version_to_files(tmp_path, VERSION) == []


def test_three_outcomes_are_mutually_distinguishable(tmp_path):
    """Clean, changed, and broken must not collapse onto one signal.

    This is the regression the module carried: all three produced ``[]``.
    """
    clean = tmp_path / "clean"
    stale = tmp_path / "stale"
    broken = tmp_path / "broken"
    for d in (clean, stale, broken):
        d.mkdir()
    _tree(clean, json.dumps({"version": VERSION}))
    stale_manifest = _tree(stale, json.dumps({"version": "0.1.0"}))
    _tree(broken, "{not json")

    clean_result = sync_version_to_files(clean, VERSION)
    stale_result = sync_version_to_files(stale, VERSION)
    with pytest.raises(VersionSyncError) as excinfo:
        sync_version_to_files(broken, VERSION)

    assert clean_result == []
    assert stale_result == [str(stale_manifest)]
    assert clean_result != stale_result
    assert isinstance(excinfo.value, VersionSyncError)

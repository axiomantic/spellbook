"""Tests for the ``posix_only`` and ``windows_only`` pytest mark handling.

The conftest hook ``pytest_collection_modifyitems`` is responsible for
applying ``pytest.mark.skip`` to items decorated with ``posix_only`` when
running on Windows, and to items decorated with ``windows_only`` when
running on POSIX. These tests verify both the hook logic and that the
marks are properly registered with pytest.

This file lives under ``tests/installer/`` because the marks are scaffolding
for WI-7 platform-dispatched installer tests, even though the marks
themselves (and the conftest hook that consumes them) are repo-global.
"""

import sys

from tests.conftest import pytest_collection_modifyitems


class _FakeKeywords:
    """Minimal stand-in for ``item.keywords`` (a Mapping[str, Any])."""

    def __init__(self, names):
        self._names = set(names)

    def __contains__(self, name):
        return name in self._names


class _FakeItem:
    """Minimal stand-in for a pytest collection item.

    Only the attributes that ``pytest_collection_modifyitems`` reads are
    implemented: ``keywords`` (membership-tested) and ``add_marker``
    (records what the hook adds).
    """

    def __init__(self, marks):
        self.keywords = _FakeKeywords(marks)
        self.added_markers = []

    def add_marker(self, marker):
        self.added_markers.append(marker)


class _FakeConfig:
    """Minimal stand-in for the pytest ``config`` object.

    The hook reads ``--run-docker`` via ``getoption`` and looks up the
    ``terminalreporter`` plugin. We pin both: docker off (default) and
    no terminal reporter (silences the memory-tools warning path).
    """

    def __init__(self):
        # pytest calls ``config.pluginmanager.get_plugin(...)``; the fake
        # collapses both onto one object so a single class implements both
        # the config and pluginmanager surface used by the hook.
        self.pluginmanager = self

    def getoption(self, name):
        assert name == "--run-docker"
        return False

    def get_plugin(self, name):
        assert name == "terminalreporter"
        return None


def _patch_platform(monkeypatch, value):
    """Stub the memory-tools probe; it's orthogonal to mark routing and
    would otherwise call ``shutil.which`` under a fake ``sys.platform``.
    """
    import tests.conftest as _conftest

    monkeypatch.setattr(sys, "platform", value)
    monkeypatch.setattr(_conftest, "_memory_tools_installed", lambda: True)


def test_posix_only_skipped_on_windows(monkeypatch):
    """An item marked ``posix_only`` gets a skip(reason='POSIX only') on Windows."""
    _patch_platform(monkeypatch, "win32")

    item = _FakeItem(marks={"posix_only"})
    config = _FakeConfig()

    pytest_collection_modifyitems(config, [item])

    assert len(item.added_markers) == 1
    marker = item.added_markers[0]
    assert marker.name == "skip"
    assert marker.kwargs == {"reason": "POSIX only"}
    assert marker.args == ()


def test_posix_only_not_skipped_on_posix(monkeypatch):
    """An item marked ``posix_only`` is left alone on POSIX platforms."""
    _patch_platform(monkeypatch, "linux")

    item = _FakeItem(marks={"posix_only"})
    config = _FakeConfig()

    pytest_collection_modifyitems(config, [item])

    assert item.added_markers == []


def test_windows_only_skipped_on_posix(monkeypatch):
    """An item marked ``windows_only`` gets a skip(reason='Windows only') on POSIX."""
    _patch_platform(monkeypatch, "linux")

    item = _FakeItem(marks={"windows_only"})
    config = _FakeConfig()

    pytest_collection_modifyitems(config, [item])

    assert len(item.added_markers) == 1
    marker = item.added_markers[0]
    assert marker.name == "skip"
    assert marker.kwargs == {"reason": "Windows only"}
    assert marker.args == ()


def test_windows_only_skipped_on_macos(monkeypatch):
    """An item marked ``windows_only`` gets a skip(reason='Windows only') on macOS."""
    _patch_platform(monkeypatch, "darwin")

    item = _FakeItem(marks={"windows_only"})
    config = _FakeConfig()

    pytest_collection_modifyitems(config, [item])

    assert len(item.added_markers) == 1
    marker = item.added_markers[0]
    assert marker.name == "skip"
    assert marker.kwargs == {"reason": "Windows only"}
    assert marker.args == ()


def test_windows_only_not_skipped_on_windows(monkeypatch):
    """An item marked ``windows_only`` is left alone on Windows."""
    _patch_platform(monkeypatch, "win32")

    item = _FakeItem(marks={"windows_only"})
    config = _FakeConfig()

    pytest_collection_modifyitems(config, [item])

    assert item.added_markers == []


def test_unmarked_item_untouched_on_windows(monkeypatch):
    """An item with no platform mark gets no markers added on Windows."""
    _patch_platform(monkeypatch, "win32")
    item = _FakeItem(marks=set())
    pytest_collection_modifyitems(_FakeConfig(), [item])
    assert item.added_markers == []


def test_unmarked_item_untouched_on_posix(monkeypatch):
    """An item with no platform mark gets no markers added on POSIX."""
    _patch_platform(monkeypatch, "linux")
    item = _FakeItem(marks=set())
    pytest_collection_modifyitems(_FakeConfig(), [item])
    assert item.added_markers == []


def test_posix_only_mark_is_registered():
    """The ``posix_only`` marker is registered in pyproject.toml's pytest config.

    Verifies exact equality on the registered marker entry — any typo in
    the description string in pyproject.toml will fail this test.
    """
    import tomllib
    from pathlib import Path

    pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
    data = tomllib.loads(pyproject.read_text())
    markers = data["tool"]["pytest"]["ini_options"]["markers"]
    matches = [m for m in markers if m.startswith("posix_only:")]

    assert matches == ["posix_only: test runs only on POSIX systems (skipped on Windows)"]


def test_windows_only_mark_is_registered():
    """The ``windows_only`` marker is registered in pyproject.toml's pytest config.

    Verifies exact equality on the registered marker entry.
    """
    import tomllib
    from pathlib import Path

    pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
    data = tomllib.loads(pyproject.read_text())
    markers = data["tool"]["pytest"]["ini_options"]["markers"]
    matches = [m for m in markers if m.startswith("windows_only:")]

    assert matches == ["windows_only: test runs only on Windows (skipped on POSIX systems)"]

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
import tripwire

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

    The hook reads ``--run-docker`` via ``getoption``. We pin docker off
    (default). ``get_plugin`` is retained for forward-compatibility with
    any plugin lookup the hook may add.
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


def _patch_platform(value):
    """Return a tripwire mock of ``tests.conftest._current_platform``.

    Exercises the mark-routing branches deterministically regardless of the
    host OS by redirecting the platform probe used by ``pytest_collection_modifyitems``.
    """
    platform_mock = tripwire.mock("tests.conftest:_current_platform")
    platform_mock.always_returns(value)
    return platform_mock


def test_posix_only_skipped_on_windows():
    """An item marked ``posix_only`` gets a skip(reason='POSIX only') on Windows."""
    platform_mock = _patch_platform("win32")
    with tripwire:

        item = _FakeItem(marks={"posix_only"})
        config = _FakeConfig()

        pytest_collection_modifyitems(config, [item])

        assert len(item.added_markers) == 1
        marker = item.added_markers[0]
        assert marker.name == "skip"
        assert marker.kwargs == {"reason": "POSIX only"}
        assert marker.args == ()
    platform_mock.assert_call(args=(), kwargs={})


def test_posix_only_not_skipped_on_posix():
    """An item marked ``posix_only`` is left alone on POSIX platforms."""
    platform_mock = _patch_platform("linux")
    with tripwire:

        item = _FakeItem(marks={"posix_only"})
        config = _FakeConfig()

        pytest_collection_modifyitems(config, [item])

        assert item.added_markers == []
    platform_mock.assert_call(args=(), kwargs={})


def test_windows_only_skipped_on_posix():
    """An item marked ``windows_only`` gets a skip(reason='Windows only') on POSIX."""
    platform_mock = _patch_platform("linux")
    with tripwire:

        item = _FakeItem(marks={"windows_only"})
        config = _FakeConfig()

        pytest_collection_modifyitems(config, [item])

        assert len(item.added_markers) == 1
        marker = item.added_markers[0]
        assert marker.name == "skip"
        assert marker.kwargs == {"reason": "Windows only"}
        assert marker.args == ()
    platform_mock.assert_call(args=(), kwargs={})


def test_windows_only_skipped_on_macos():
    """An item marked ``windows_only`` gets a skip(reason='Windows only') on macOS."""
    platform_mock = _patch_platform("darwin")
    with tripwire:

        item = _FakeItem(marks={"windows_only"})
        config = _FakeConfig()

        pytest_collection_modifyitems(config, [item])

        assert len(item.added_markers) == 1
        marker = item.added_markers[0]
        assert marker.name == "skip"
        assert marker.kwargs == {"reason": "Windows only"}
        assert marker.args == ()
    platform_mock.assert_call(args=(), kwargs={})


def test_windows_only_not_skipped_on_windows():
    """An item marked ``windows_only`` is left alone on Windows."""
    platform_mock = _patch_platform("win32")
    with tripwire:

        item = _FakeItem(marks={"windows_only"})
        config = _FakeConfig()

        pytest_collection_modifyitems(config, [item])

        assert item.added_markers == []
    platform_mock.assert_call(args=(), kwargs={})


def test_unmarked_item_untouched_on_windows():
    """An item with no platform mark gets no markers added on Windows."""
    platform_mock = _patch_platform("win32")
    with tripwire:
        item = _FakeItem(marks=set())
        pytest_collection_modifyitems(_FakeConfig(), [item])
        assert item.added_markers == []
    platform_mock.assert_call(args=(), kwargs={})


def test_unmarked_item_untouched_on_posix():
    """An item with no platform mark gets no markers added on POSIX."""
    platform_mock = _patch_platform("linux")
    with tripwire:
        item = _FakeItem(marks=set())
        pytest_collection_modifyitems(_FakeConfig(), [item])
        assert item.added_markers == []
    platform_mock.assert_call(args=(), kwargs={})


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

"""Integration tests for the auto-update flow.

Uses monkeypatch to mock subprocess calls instead of creating real git repos,
avoiding UnmockedInteractionError from bigfoot's guard mode.
"""

import subprocess
from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.integration


def _make_subprocess_mock(known_remotes="origin"):
    """Return a callable that mimics subprocess.run for git commands.

    Handles:
    - ``git remote`` -> returns known_remotes
    - ``git fetch`` -> returns success
    """
    def _mock_run(cmd, **kwargs):
        result = MagicMock(spec=subprocess.CompletedProcess)
        result.returncode = 0
        result.stderr = ""

        if "remote" in cmd and "add" not in cmd:
            result.stdout = known_remotes
        elif "fetch" in cmd:
            result.stdout = ""
        else:
            result.stdout = ""
        return result

    return _mock_run


@pytest.fixture
def mock_spellbook_dir(tmp_path):
    """Create a minimal spellbook directory with a .version file (no real git repo)."""
    repo = tmp_path / "spellbook"
    repo.mkdir()
    (repo / ".version").write_text("0.9.9\n")
    return repo


class TestFullUpdateDetection:
    """Integration tests for update detection with mocked subprocess."""

    def test_detects_new_version(self, mock_spellbook_dir, monkeypatch):
        """Detect update when GitHub releases API reports a newer version."""
        from spellbook.updates.tools import check_for_updates

        config_map = {"auto_update_remote": "origin"}
        state_map = {"auto_update_branch": "main"}

        monkeypatch.setattr(
            "spellbook.updates.tools.config_get",
            lambda key: config_map.get(key),
        )
        monkeypatch.setattr(
            "spellbook.updates.tools.get_state",
            lambda key: state_map.get(key),
        )
        monkeypatch.setattr(
            "spellbook.updates.tools._get_latest_release_version",
            lambda *a, **kw: "0.9.10",
        )
        monkeypatch.setattr(
            "spellbook.updates.tools.subprocess.run",
            _make_subprocess_mock(),
        )

        result = check_for_updates(mock_spellbook_dir)

        assert result["error"] is None, f"Unexpected error: {result}"
        assert result["update_available"] is True, f"Expected update_available=True: {result}"
        assert result["current_version"] == "0.9.9"
        assert result["remote_version"] == "0.9.10"
        assert result["is_major_bump"] is False

    def test_no_update_when_up_to_date(self, mock_spellbook_dir, monkeypatch):
        """No update detected when versions match."""
        from spellbook.updates.tools import check_for_updates

        config_map = {"auto_update_remote": "origin"}
        state_map = {"auto_update_branch": "main"}

        monkeypatch.setattr(
            "spellbook.updates.tools.config_get",
            lambda key: config_map.get(key),
        )
        monkeypatch.setattr(
            "spellbook.updates.tools.get_state",
            lambda key: state_map.get(key),
        )
        monkeypatch.setattr(
            "spellbook.updates.tools._get_latest_release_version",
            lambda *a, **kw: "0.9.9",
        )
        monkeypatch.setattr(
            "spellbook.updates.tools.subprocess.run",
            _make_subprocess_mock(),
        )

        result = check_for_updates(mock_spellbook_dir)

        assert result["update_available"] is False
        assert result["error"] is None

    def test_version_classification_integration(self, mock_spellbook_dir, monkeypatch):
        """Major version bump is correctly detected."""
        from spellbook.updates.tools import check_for_updates

        config_map = {"auto_update_remote": "origin"}
        state_map = {"auto_update_branch": "main"}

        monkeypatch.setattr(
            "spellbook.updates.tools.config_get",
            lambda key: config_map.get(key),
        )
        monkeypatch.setattr(
            "spellbook.updates.tools.get_state",
            lambda key: state_map.get(key),
        )
        monkeypatch.setattr(
            "spellbook.updates.tools._get_latest_release_version",
            lambda *a, **kw: "1.0.0",
        )
        monkeypatch.setattr(
            "spellbook.updates.tools.subprocess.run",
            _make_subprocess_mock(),
        )

        result = check_for_updates(mock_spellbook_dir)

        assert result["error"] is None, f"Unexpected error: {result}"
        assert result["update_available"] is True, f"Expected update_available=True: {result}"
        assert result["is_major_bump"] is True

"""Integration tests for the auto-update flow using real git repos."""

import os
import subprocess
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.integration


@pytest.fixture
def mock_git_repo(tmp_path):
    """Create a mock spellbook git repo with remote.

    Populates the bare remote BEFORE cloning so that the clone creates
    proper remote-tracking refs (refs/remotes/origin/main).
    """
    seed = tmp_path / "seed"
    remote = tmp_path / "remote"
    repo = tmp_path / "spellbook"
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "test",
        "GIT_AUTHOR_EMAIL": "t@t.t",
        "GIT_COMMITTER_NAME": "test",
        "GIT_COMMITTER_EMAIL": "t@t.t",
    }

    # Create "remote" bare repo (use -c init.defaultBranch=main for portability)
    subprocess.run(
        ["git", "-c", "init.defaultBranch=main", "init", "--bare", str(remote)],
        check=True,
        env=env,
        timeout=30,
    )

    # Seed the remote with an initial commit so it is non-empty
    subprocess.run(
        ["git", "-c", "init.defaultBranch=main", "init", str(seed)],
        check=True,
        env=env,
        timeout=30,
    )
    (seed / ".version").write_text("0.9.9\n")
    subprocess.run(["git", "-C", str(seed), "add", ".version"], check=True, env=env, timeout=30)
    subprocess.run(
        ["git", "-C", str(seed), "commit", "-m", "initial"],
        check=True,
        env=env,
        timeout=30,
    )
    subprocess.run(
        ["git", "-C", str(seed), "remote", "add", "origin", str(remote)],
        check=True,
        env=env,
        timeout=30,
    )
    subprocess.run(
        ["git", "-C", str(seed), "push", "-u", "origin", "main"],
        check=True,
        env=env,
        timeout=30,
    )

    # Clone the now-populated remote; this creates proper tracking refs
    subprocess.run(["git", "clone", str(remote), str(repo)], check=True, env=env, timeout=30)

    return {"repo": repo, "remote": remote, "env": env}


class TestFullUpdateDetection:
    """Integration tests for update detection with real git repos."""

    def test_detects_new_version(self, mock_git_repo):
        """Detect update when GitHub releases API reports a newer version."""
        from spellbook_mcp.update_tools import check_for_updates

        repo = mock_git_repo["repo"]

        # Mock _get_latest_release_version to simulate a new release on GitHub
        with (
            patch("spellbook_mcp.update_tools.config_get") as mock_config_get,
            patch("spellbook_mcp.update_tools._get_latest_release_version", return_value="0.9.10"),
        ):
            mock_config_get.side_effect = lambda key: {
                "auto_update_remote": "origin",
                "auto_update_branch": "main",
            }.get(key)

            result = check_for_updates(repo)

        assert result["error"] is None, f"Unexpected error: {result}"
        assert result["update_available"] is True, f"Expected update_available=True: {result}"
        assert result["current_version"] == "0.9.9"
        assert result["remote_version"] == "0.9.10"
        assert result["is_major_bump"] is False

    def test_no_update_when_up_to_date(self, mock_git_repo):
        """No update detected when versions match."""
        from spellbook_mcp.update_tools import check_for_updates

        repo = mock_git_repo["repo"]

        # Mock _get_latest_release_version to return the same version as local
        with (
            patch("spellbook_mcp.update_tools.config_get") as mock_config_get,
            patch("spellbook_mcp.update_tools._get_latest_release_version", return_value="0.9.9"),
        ):
            mock_config_get.side_effect = lambda key: {
                "auto_update_remote": "origin",
                "auto_update_branch": "main",
            }.get(key)

            result = check_for_updates(repo)

        assert result["update_available"] is False
        assert result["error"] is None

    def test_version_classification_integration(self, mock_git_repo):
        """Major version bump is correctly detected."""
        from spellbook_mcp.update_tools import check_for_updates

        repo = mock_git_repo["repo"]

        # Mock _get_latest_release_version to simulate a major version bump
        with (
            patch("spellbook_mcp.update_tools.config_get") as mock_config_get,
            patch("spellbook_mcp.update_tools._get_latest_release_version", return_value="1.0.0"),
        ):
            mock_config_get.side_effect = lambda key: {
                "auto_update_remote": "origin",
                "auto_update_branch": "main",
            }.get(key)

            result = check_for_updates(repo)

        assert result["error"] is None, f"Unexpected error: {result}"
        assert result["update_available"] is True, f"Expected update_available=True: {result}"
        assert result["is_major_bump"] is True

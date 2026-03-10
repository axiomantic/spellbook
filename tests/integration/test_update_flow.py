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
    proper remote-tracking refs (refs/remotes/origin/main).  Cloning an
    empty bare repo and then pushing leaves some git versions without a
    usable tracking ref, which breaks ``git show origin/main:.version``
    after a subsequent ``git fetch``.
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

    def test_detects_new_version(self, mock_git_repo, tmp_path):
        """Create repo, push new version, detect update."""
        from spellbook_mcp.update_tools import check_for_updates

        repo = mock_git_repo["repo"]
        remote = mock_git_repo["remote"]
        env = mock_git_repo["env"]

        # Push a new version to the remote
        clone2 = tmp_path / "clone2"
        subprocess.run(["git", "clone", str(remote), str(clone2)], check=True, env=env, timeout=30)
        (clone2 / ".version").write_text("0.9.10\n")
        subprocess.run(["git", "-C", str(clone2), "add", ".version"], check=True, env=env, timeout=30)
        subprocess.run(
            ["git", "-C", str(clone2), "commit", "-m", "bump version"],
            check=True,
            env=env,
            timeout=30,
        )
        subprocess.run(["git", "-C", str(clone2), "push"], check=True, env=env, timeout=30)

        # Now check from the original repo
        # Mock _get_latest_release_version to None so we always exercise the
        # git-show fallback path (gh may or may not be authenticated in CI).
        with (
            patch("spellbook_mcp.update_tools.config_get") as mock_config_get,
            patch("spellbook_mcp.update_tools._get_latest_release_version", return_value=None),
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

        with (
            patch("spellbook_mcp.update_tools.config_get") as mock_config_get,
            patch("spellbook_mcp.update_tools._get_latest_release_version", return_value=None),
        ):
            mock_config_get.side_effect = lambda key: {
                "auto_update_remote": "origin",
                "auto_update_branch": "main",
            }.get(key)

            result = check_for_updates(repo)

        assert result["update_available"] is False
        assert result["error"] is None

    def test_version_classification_integration(self, mock_git_repo, tmp_path):
        """Major version bump is correctly detected."""
        from spellbook_mcp.update_tools import check_for_updates

        repo = mock_git_repo["repo"]
        remote = mock_git_repo["remote"]
        env = mock_git_repo["env"]

        # Push a major version bump
        clone2 = tmp_path / "clone2"
        subprocess.run(["git", "clone", str(remote), str(clone2)], check=True, env=env, timeout=30)
        (clone2 / ".version").write_text("1.0.0\n")
        subprocess.run(["git", "-C", str(clone2), "add", ".version"], check=True, env=env, timeout=30)
        subprocess.run(
            ["git", "-C", str(clone2), "commit", "-m", "major bump"],
            check=True,
            env=env,
            timeout=30,
        )
        subprocess.run(["git", "-C", str(clone2), "push"], check=True, env=env, timeout=30)

        with (
            patch("spellbook_mcp.update_tools.config_get") as mock_config_get,
            patch("spellbook_mcp.update_tools._get_latest_release_version", return_value=None),
        ):
            mock_config_get.side_effect = lambda key: {
                "auto_update_remote": "origin",
                "auto_update_branch": "main",
            }.get(key)

            result = check_for_updates(repo)

        assert result["error"] is None, f"Unexpected error: {result}"
        assert result["update_available"] is True, f"Expected update_available=True: {result}"
        assert result["is_major_bump"] is True

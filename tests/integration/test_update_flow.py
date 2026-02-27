"""Integration tests for the auto-update flow using real git repos."""

import json
import os
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.integration


@pytest.fixture
def mock_git_repo(tmp_path):
    """Create a mock spellbook git repo with remote."""
    repo = tmp_path / "spellbook"
    remote = tmp_path / "remote"
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

    # Clone to create local repo
    subprocess.run(["git", "clone", str(remote), str(repo)], check=True, env=env, timeout=30)

    # Add .version file
    (repo / ".version").write_text("0.9.9\n")
    subprocess.run(["git", "-C", str(repo), "add", ".version"], check=True, env=env, timeout=30)
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-m", "initial"],
        check=True,
        env=env,
        timeout=30,
    )
    subprocess.run(["git", "-C", str(repo), "push"], check=True, env=env, timeout=30)

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
        with patch("spellbook_mcp.update_tools.config_get") as mock_config_get:
            mock_config_get.side_effect = lambda key: {
                "auto_update_remote": "origin",
                "auto_update_branch": "main",
            }.get(key)

            result = check_for_updates(repo)

        assert result["update_available"] is True
        assert result["current_version"] == "0.9.9"
        assert result["remote_version"] == "0.9.10"
        assert result["is_major_bump"] is False
        assert result["error"] is None

    def test_no_update_when_up_to_date(self, mock_git_repo):
        """No update detected when versions match."""
        from spellbook_mcp.update_tools import check_for_updates

        repo = mock_git_repo["repo"]

        with patch("spellbook_mcp.update_tools.config_get") as mock_config_get:
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

        with patch("spellbook_mcp.update_tools.config_get") as mock_config_get:
            mock_config_get.side_effect = lambda key: {
                "auto_update_remote": "origin",
                "auto_update_branch": "main",
            }.get(key)

            result = check_for_updates(repo)

        assert result["update_available"] is True
        assert result["is_major_bump"] is True

"""Tests for pr_distill GitHub PR fetching."""

import subprocess
from unittest.mock import patch, MagicMock

import pytest

from spellbook_mcp.pr_distill.errors import ErrorCode, PRDistillError
from spellbook_mcp.pr_distill.fetch import (
    MIN_GH_VERSION,
    GH_TIMEOUT,
    run_command,
    compare_semver,
    check_gh_version,
    parse_pr_identifier,
    map_gh_error,
    fetch_pr,
)


class TestConstants:
    """Test module constants."""

    def test_min_gh_version(self):
        """MIN_GH_VERSION is 2.30.0."""
        assert MIN_GH_VERSION == "2.30.0"

    def test_gh_timeout(self):
        """GH_TIMEOUT is 120 seconds."""
        assert GH_TIMEOUT == 120


class TestCompareSemver:
    """Test semantic version comparison."""

    def test_equal_versions(self):
        """Equal versions return 0."""
        assert compare_semver("2.30.0", "2.30.0") == 0

    def test_less_than_major(self):
        """Lower major version returns -1."""
        assert compare_semver("1.30.0", "2.30.0") == -1

    def test_greater_than_major(self):
        """Higher major version returns 1."""
        assert compare_semver("3.0.0", "2.30.0") == 1

    def test_less_than_minor(self):
        """Lower minor version returns -1."""
        assert compare_semver("2.29.0", "2.30.0") == -1

    def test_greater_than_minor(self):
        """Higher minor version returns 1."""
        assert compare_semver("2.31.0", "2.30.0") == 1

    def test_less_than_patch(self):
        """Lower patch version returns -1."""
        assert compare_semver("2.30.0", "2.30.1") == -1

    def test_greater_than_patch(self):
        """Higher patch version returns 1."""
        assert compare_semver("2.30.1", "2.30.0") == 1

    def test_handles_different_lengths(self):
        """Handles versions with different segment counts."""
        assert compare_semver("2.30", "2.30.0") == 0
        assert compare_semver("2", "2.0.0") == 0


class TestCheckGhVersion:
    """Test gh CLI version checking."""

    def test_valid_version_exact_minimum(self):
        """Exact minimum version passes."""
        with patch(
            "spellbook_mcp.pr_distill.fetch.run_command",
            return_value="gh version 2.30.0 (2023-05-10)"
        ):
            result = check_gh_version()
            assert result is True

    def test_valid_version_higher(self):
        """Version higher than minimum passes."""
        with patch(
            "spellbook_mcp.pr_distill.fetch.run_command",
            return_value="gh version 2.40.0 (2024-01-15)"
        ):
            result = check_gh_version()
            assert result is True

    def test_version_too_old(self):
        """Version below minimum raises GH_VERSION_TOO_OLD."""
        with patch(
            "spellbook_mcp.pr_distill.fetch.run_command",
            return_value="gh version 2.29.0 (2023-04-01)"
        ):
            with pytest.raises(PRDistillError) as exc_info:
                check_gh_version()
            assert exc_info.value.code == ErrorCode.GH_VERSION_TOO_OLD
            assert "2.29.0" in str(exc_info.value)
            assert MIN_GH_VERSION in str(exc_info.value)

    def test_gh_not_installed(self):
        """gh CLI not installed raises GH_NOT_AUTHENTICATED."""
        with patch(
            "spellbook_mcp.pr_distill.fetch.run_command",
            side_effect=subprocess.CalledProcessError(1, "gh --version")
        ):
            with pytest.raises(PRDistillError) as exc_info:
                check_gh_version()
            assert exc_info.value.code == ErrorCode.GH_NOT_AUTHENTICATED
            assert "not installed" in str(exc_info.value)

    def test_unparseable_version_output(self):
        """Unparseable version output raises GH_VERSION_TOO_OLD."""
        with patch(
            "spellbook_mcp.pr_distill.fetch.run_command",
            return_value="some weird output"
        ):
            with pytest.raises(PRDistillError) as exc_info:
                check_gh_version()
            assert exc_info.value.code == ErrorCode.GH_VERSION_TOO_OLD


class TestParsePRIdentifier:
    """Test PR identifier parsing."""

    def test_parse_full_url(self):
        """Parse full GitHub PR URL."""
        result = parse_pr_identifier("https://github.com/owner/repo/pull/123")
        assert result["pr_number"] == 123
        assert result["repo"] == "owner/repo"

    def test_parse_url_with_files_tab(self):
        """Parse PR URL with /files suffix."""
        result = parse_pr_identifier("https://github.com/owner/repo/pull/456/files")
        assert result["pr_number"] == 456
        assert result["repo"] == "owner/repo"

    def test_parse_number_with_git_remote(self):
        """Parse PR number using git remote for repo."""
        with patch(
            "spellbook_mcp.pr_distill.fetch.run_command",
            return_value="https://github.com/myorg/myrepo.git"
        ):
            result = parse_pr_identifier("789")
            assert result["pr_number"] == 789
            assert result["repo"] == "myorg/myrepo"

    def test_parse_number_with_ssh_remote(self):
        """Parse PR number using SSH git remote."""
        with patch(
            "spellbook_mcp.pr_distill.fetch.run_command",
            return_value="git@github.com:org/project.git"
        ):
            result = parse_pr_identifier("42")
            assert result["pr_number"] == 42
            assert result["repo"] == "org/project"

    def test_parse_invalid_raises(self):
        """Invalid identifier raises GH_PR_NOT_FOUND."""
        with pytest.raises(PRDistillError) as exc_info:
            parse_pr_identifier("not-a-pr")
        assert exc_info.value.code == ErrorCode.GH_PR_NOT_FOUND

    def test_parse_number_no_git_remote(self):
        """PR number with no git remote raises GH_PR_NOT_FOUND."""
        with patch(
            "spellbook_mcp.pr_distill.fetch.run_command",
            side_effect=subprocess.CalledProcessError(1, "git remote")
        ):
            with pytest.raises(PRDistillError) as exc_info:
                parse_pr_identifier("123")
            assert exc_info.value.code == ErrorCode.GH_PR_NOT_FOUND
            assert "Could not determine repository" in str(exc_info.value)


class TestMapGhError:
    """Test gh CLI error mapping."""

    def test_not_found_error(self):
        """'not found' error maps to GH_PR_NOT_FOUND."""
        error = Exception("PR could not resolve to a PullRequest")
        context = {"pr_number": 123, "repo": "owner/repo"}
        result = map_gh_error(error, context)
        assert result.code == ErrorCode.GH_PR_NOT_FOUND
        assert result.context == context

    def test_rate_limit_error(self):
        """'rate limit' error maps to GH_RATE_LIMITED."""
        error = Exception("API rate limit exceeded")
        context = {"pr_number": 123, "repo": "owner/repo"}
        result = map_gh_error(error, context)
        assert result.code == ErrorCode.GH_RATE_LIMITED
        assert result.recoverable is True

    def test_auth_error(self):
        """Auth error maps to GH_NOT_AUTHENTICATED."""
        error = Exception("To get started with GitHub CLI, please run: gh auth login")
        context = {"pr_number": 123, "repo": "owner/repo"}
        result = map_gh_error(error, context)
        assert result.code == ErrorCode.GH_NOT_AUTHENTICATED

    def test_generic_error(self):
        """Unknown error maps to GH_NETWORK_ERROR."""
        error = Exception("Connection timed out")
        context = {"pr_number": 123, "repo": "owner/repo"}
        result = map_gh_error(error, context)
        assert result.code == ErrorCode.GH_NETWORK_ERROR
        assert result.recoverable is True


class TestFetchPR:
    """Test PR fetching."""

    def test_fetch_success(self):
        """Successful fetch returns metadata and diff."""
        pr_identifier = {"pr_number": 123, "repo": "owner/repo"}
        mock_meta = {
            "number": 123,
            "title": "Test PR",
            "body": "Description",
            "headRefOid": "abc123",
        }

        def mock_run_command(cmd):
            if "gh --version" in cmd:
                return "gh version 2.40.0 (2024-01-15)"
            elif "gh pr view" in cmd:
                import json
                return json.dumps(mock_meta)
            elif "gh pr diff" in cmd:
                return "diff --git a/file.py b/file.py\n+new line"
            raise Exception(f"Unexpected command: {cmd}")

        with patch(
            "spellbook_mcp.pr_distill.fetch.run_command",
            side_effect=mock_run_command
        ):
            result = fetch_pr(pr_identifier)

        assert result["meta"]["number"] == 123
        assert result["meta"]["title"] == "Test PR"
        assert "diff --git" in result["diff"]
        assert result["repo"] == "owner/repo"

    def test_fetch_pr_not_found(self):
        """Fetch with non-existent PR raises GH_PR_NOT_FOUND."""
        pr_identifier = {"pr_number": 99999, "repo": "owner/repo"}

        def mock_run_command(cmd):
            if "gh --version" in cmd:
                return "gh version 2.40.0 (2024-01-15)"
            elif "gh pr view" in cmd:
                raise subprocess.CalledProcessError(
                    1, cmd, stderr=b"could not resolve to a PullRequest"
                )
            raise Exception(f"Unexpected command: {cmd}")

        with patch(
            "spellbook_mcp.pr_distill.fetch.run_command",
            side_effect=mock_run_command
        ):
            with pytest.raises(PRDistillError) as exc_info:
                fetch_pr(pr_identifier)
            assert exc_info.value.code == ErrorCode.GH_PR_NOT_FOUND


class TestRunCommand:
    """Test shell command execution."""

    def test_run_command_success(self):
        """Successful command returns output."""
        result = run_command("echo hello")
        assert result.strip() == "hello"

    def test_run_command_failure(self):
        """Failed command raises CalledProcessError."""
        with pytest.raises(subprocess.CalledProcessError):
            run_command("exit 1")

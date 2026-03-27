"""Tests for pr_distill GitHub PR fetching."""

import subprocess
import sys

import bigfoot
import pytest
from dirty_equals import IsInstance

from spellbook.pr_distill.errors import ErrorCode, PRDistillError
from spellbook.pr_distill.fetch import (
    MIN_GH_VERSION,
    GH_TIMEOUT,
    run_command,
    compare_semver,
    check_gh_version,
    parse_pr_identifier,
    map_gh_error,
    fetch_pr,
)

# gh pr view JSON fields used by fetch_pr
_GH_VIEW_FIELDS = "number,title,body,headRefOid,baseRefName,additions,deletions,files"


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
        mock_run = bigfoot.mock("spellbook.pr_distill.fetch:run_command")
        mock_run.returns("gh version 2.30.0 (2023-05-10)")

        with bigfoot:
            result = check_gh_version()

        assert result is True
        mock_run.assert_call(args=("gh --version",), kwargs={})

    def test_valid_version_higher(self):
        """Version higher than minimum passes."""
        mock_run = bigfoot.mock("spellbook.pr_distill.fetch:run_command")
        mock_run.returns("gh version 2.40.0 (2024-01-15)")

        with bigfoot:
            result = check_gh_version()

        assert result is True
        mock_run.assert_call(args=("gh --version",), kwargs={})

    def test_version_too_old(self):
        """Version below minimum raises GH_VERSION_TOO_OLD."""
        mock_run = bigfoot.mock("spellbook.pr_distill.fetch:run_command")
        mock_run.returns("gh version 2.29.0 (2023-04-01)")

        with bigfoot:
            with pytest.raises(PRDistillError) as exc_info:
                check_gh_version()

        assert exc_info.value.code == ErrorCode.GH_VERSION_TOO_OLD
        assert "2.29.0" in str(exc_info.value)
        assert MIN_GH_VERSION in str(exc_info.value)
        mock_run.assert_call(args=("gh --version",), kwargs={})

    def test_gh_not_installed(self):
        """gh CLI not installed raises GH_NOT_AUTHENTICATED."""
        mock_run = bigfoot.mock("spellbook.pr_distill.fetch:run_command")
        mock_run.raises(subprocess.CalledProcessError(1, "gh --version"))

        with bigfoot:
            with pytest.raises(PRDistillError) as exc_info:
                check_gh_version()

        assert exc_info.value.code == ErrorCode.GH_NOT_AUTHENTICATED
        assert "not installed" in str(exc_info.value)
        mock_run.assert_call(
            args=("gh --version",), kwargs={},
            raised=IsInstance(subprocess.CalledProcessError),
        )

    def test_unparseable_version_output(self):
        """Unparseable version output raises GH_VERSION_TOO_OLD."""
        mock_run = bigfoot.mock("spellbook.pr_distill.fetch:run_command")
        mock_run.returns("some weird output")

        with bigfoot:
            with pytest.raises(PRDistillError) as exc_info:
                check_gh_version()

        assert exc_info.value.code == ErrorCode.GH_VERSION_TOO_OLD
        mock_run.assert_call(args=("gh --version",), kwargs={})


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
        mock_run = bigfoot.mock("spellbook.pr_distill.fetch:run_command")
        mock_run.returns("https://github.com/myorg/myrepo.git")

        with bigfoot:
            result = parse_pr_identifier("789")

        assert result["pr_number"] == 789
        assert result["repo"] == "myorg/myrepo"
        mock_run.assert_call(args=("git remote get-url origin",), kwargs={})

    def test_parse_number_with_ssh_remote(self):
        """Parse PR number using SSH git remote."""
        mock_run = bigfoot.mock("spellbook.pr_distill.fetch:run_command")
        mock_run.returns("git@github.com:org/project.git")

        with bigfoot:
            result = parse_pr_identifier("42")

        assert result["pr_number"] == 42
        assert result["repo"] == "org/project"
        mock_run.assert_call(args=("git remote get-url origin",), kwargs={})

    def test_parse_invalid_raises(self):
        """Invalid identifier raises GH_PR_NOT_FOUND."""
        with pytest.raises(PRDistillError) as exc_info:
            parse_pr_identifier("not-a-pr")
        assert exc_info.value.code == ErrorCode.GH_PR_NOT_FOUND

    def test_parse_number_no_git_remote(self):
        """PR number with no git remote raises GH_PR_NOT_FOUND."""
        mock_run = bigfoot.mock("spellbook.pr_distill.fetch:run_command")
        mock_run.raises(subprocess.CalledProcessError(1, "git remote"))

        with bigfoot:
            with pytest.raises(PRDistillError) as exc_info:
                parse_pr_identifier("123")

        assert exc_info.value.code == ErrorCode.GH_PR_NOT_FOUND
        assert "Could not determine repository" in str(exc_info.value)
        mock_run.assert_call(
            args=("git remote get-url origin",), kwargs={},
            raised=IsInstance(subprocess.CalledProcessError),
        )


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

        import json

        def mock_run_command(cmd):
            if "gh --version" in cmd:
                return "gh version 2.40.0 (2024-01-15)"
            elif "gh pr view" in cmd:
                return json.dumps(mock_meta)
            elif "gh pr diff" in cmd:
                return "diff --git a/file.py b/file.py\n+new line"
            raise Exception(f"Unexpected command: {cmd}")

        mock_run = bigfoot.mock("spellbook.pr_distill.fetch:run_command")
        mock_run.calls(mock_run_command).calls(mock_run_command).calls(mock_run_command)

        with bigfoot:
            result = fetch_pr(pr_identifier)

        assert result["meta"]["number"] == 123
        assert result["meta"]["title"] == "Test PR"
        assert "diff --git" in result["diff"]
        assert result["repo"] == "owner/repo"
        with bigfoot.in_any_order():
            mock_run.assert_call(args=("gh --version",), kwargs={})
            mock_run.assert_call(
                args=(f"gh pr view 123 --repo owner/repo --json {_GH_VIEW_FIELDS}",),
                kwargs={},
            )
            mock_run.assert_call(
                args=("gh pr diff 123 --repo owner/repo",), kwargs={},
            )

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

        mock_run = bigfoot.mock("spellbook.pr_distill.fetch:run_command")
        mock_run.calls(mock_run_command).calls(mock_run_command)

        with bigfoot:
            with pytest.raises(PRDistillError) as exc_info:
                fetch_pr(pr_identifier)

        assert exc_info.value.code == ErrorCode.GH_PR_NOT_FOUND
        with bigfoot.in_any_order():
            mock_run.assert_call(args=("gh --version",), kwargs={})
            mock_run.assert_call(
                args=(f"gh pr view 99999 --repo owner/repo --json {_GH_VIEW_FIELDS}",),
                kwargs={},
            )


class TestRunCommand:
    """Test shell command execution."""

    @pytest.mark.skipif(sys.platform == "win32", reason="echo is a shell built-in on Windows, not an external command")
    @pytest.mark.allow("subprocess")
    def test_run_command_success(self):
        """Successful command returns output."""
        result = run_command("echo hello")
        assert result.strip() == "hello"

    @pytest.mark.skipif(sys.platform == "win32", reason="Windows shlex.split(posix=False) preserves quotes, changing -c argument semantics")
    @pytest.mark.allow("subprocess")
    def test_run_command_failure(self):
        """Failed command raises CalledProcessError."""
        with pytest.raises(subprocess.CalledProcessError):
            run_command(f"{sys.executable} -c \"import sys; sys.exit(1)\"")

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-specific run_command tests")
    @pytest.mark.allow("subprocess")
    def test_run_command_success_windows(self):
        """Successful command returns output on Windows."""
        result = run_command(f"{sys.executable} -c print(42)")
        assert result.strip() == "42"

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-specific run_command tests")
    @pytest.mark.allow("subprocess")
    def test_run_command_failure_windows(self):
        """Failed command raises CalledProcessError on Windows."""
        with pytest.raises(subprocess.CalledProcessError):
            run_command(f"{sys.executable} -c exit(1)")

    def test_run_command_timeout(self):
        """run_command propagates TimeoutExpired from subprocess."""
        mock_run = bigfoot.mock("subprocess:run")
        mock_run.raises(subprocess.TimeoutExpired(cmd="test", timeout=120))

        with bigfoot:
            with pytest.raises(subprocess.TimeoutExpired):
                run_command("test command")

        mock_run.assert_call(
            args=(["test", "command"],),
            kwargs={"capture_output": True, "text": True, "timeout": GH_TIMEOUT, "check": True},
            raised=IsInstance(subprocess.TimeoutExpired),
        )


class TestCompareSemverEdgeCases:
    """Edge case tests for compare_semver."""

    def test_compare_with_non_numeric_raises(self):
        """compare_semver raises ValueError for non-numeric versions."""
        with pytest.raises(ValueError):
            compare_semver("2.30.a", "2.30.0")

    def test_compare_with_empty_string_raises(self):
        """compare_semver raises ValueError for empty strings."""
        with pytest.raises(ValueError):
            compare_semver("", "2.30.0")


class TestParsePRIdentifierEdgeCases:
    """Edge case tests for parse_pr_identifier."""

    def test_parse_zero_pr_number(self):
        """parse_pr_identifier rejects PR number 0."""
        with pytest.raises(PRDistillError) as exc_info:
            parse_pr_identifier("0")
        assert exc_info.value.code == ErrorCode.GH_PR_NOT_FOUND

    def test_parse_negative_pr_number(self):
        """parse_pr_identifier rejects negative PR numbers."""
        with pytest.raises(PRDistillError) as exc_info:
            parse_pr_identifier("-1")
        assert exc_info.value.code == ErrorCode.GH_PR_NOT_FOUND


class TestFetchPRErrorPaths:
    """Tests for fetch_pr error handling."""

    def test_fetch_pr_invalid_json(self):
        """fetch_pr raises PRDistillError on invalid JSON response."""
        mock_check = bigfoot.mock("spellbook.pr_distill.fetch:check_gh_version")
        mock_check.returns(True)

        mock_run = bigfoot.mock("spellbook.pr_distill.fetch:run_command")
        mock_run.returns("not valid json at all")

        with bigfoot:
            with pytest.raises(PRDistillError) as exc_info:
                fetch_pr({"pr_number": 123, "repo": "owner/repo"})

        assert exc_info.value.code == ErrorCode.GH_NETWORK_ERROR
        assert "Invalid JSON" in str(exc_info.value)
        mock_check.assert_call(args=(), kwargs={})
        mock_run.assert_call(
            args=(f"gh pr view 123 --repo owner/repo --json {_GH_VIEW_FIELDS}",),
            kwargs={},
        )

    def test_fetch_pr_diff_fails(self):
        """fetch_pr handles failure when pr view succeeds but pr diff fails."""
        mock_check = bigfoot.mock("spellbook.pr_distill.fetch:check_gh_version")
        mock_check.returns(True)

        def side_effect(cmd):
            if "gh pr view" in cmd:
                return '{"number": 123, "title": "Test"}'
            elif "gh pr diff" in cmd:
                raise subprocess.CalledProcessError(
                    1, "gh pr diff", stderr=b"not found"
                )
            raise Exception(f"Unexpected command: {cmd}")

        mock_run = bigfoot.mock("spellbook.pr_distill.fetch:run_command")
        mock_run.calls(side_effect).calls(side_effect)

        with bigfoot:
            with pytest.raises(PRDistillError) as exc_info:
                fetch_pr({"pr_number": 123, "repo": "owner/repo"})

        # Should map to GH_PR_NOT_FOUND since stderr contains "not found"
        assert exc_info.value.code == ErrorCode.GH_PR_NOT_FOUND
        mock_check.assert_call(args=(), kwargs={})
        with bigfoot.in_any_order():
            mock_run.assert_call(
                args=(f"gh pr view 123 --repo owner/repo --json {_GH_VIEW_FIELDS}",),
                kwargs={},
            )
            mock_run.assert_call(
                args=("gh pr diff 123 --repo owner/repo",), kwargs={},
            )

    def test_fetch_pr_rate_limited(self):
        """fetch_pr handles rate limit errors."""
        mock_check = bigfoot.mock("spellbook.pr_distill.fetch:check_gh_version")
        mock_check.returns(True)

        mock_run = bigfoot.mock("spellbook.pr_distill.fetch:run_command")
        mock_run.raises(subprocess.CalledProcessError(1, "gh", stderr=b"API rate limit exceeded"))

        with bigfoot:
            with pytest.raises(PRDistillError) as exc_info:
                fetch_pr({"pr_number": 123, "repo": "owner/repo"})

        assert exc_info.value.code == ErrorCode.GH_RATE_LIMITED
        assert exc_info.value.recoverable is True
        mock_check.assert_call(args=(), kwargs={})
        mock_run.assert_call(
            args=(f"gh pr view 123 --repo owner/repo --json {_GH_VIEW_FIELDS}",),
            kwargs={},
            raised=IsInstance(subprocess.CalledProcessError),
        )

    def test_fetch_pr_auth_error(self):
        """fetch_pr handles authentication errors."""
        mock_check = bigfoot.mock("spellbook.pr_distill.fetch:check_gh_version")
        mock_check.returns(True)

        mock_run = bigfoot.mock("spellbook.pr_distill.fetch:run_command")
        mock_run.raises(subprocess.CalledProcessError(1, "gh", stderr=b"gh auth login"))

        with bigfoot:
            with pytest.raises(PRDistillError) as exc_info:
                fetch_pr({"pr_number": 123, "repo": "owner/repo"})

        assert exc_info.value.code == ErrorCode.GH_NOT_AUTHENTICATED
        mock_check.assert_call(args=(), kwargs={})
        mock_run.assert_call(
            args=(f"gh pr view 123 --repo owner/repo --json {_GH_VIEW_FIELDS}",),
            kwargs={},
            raised=IsInstance(subprocess.CalledProcessError),
        )

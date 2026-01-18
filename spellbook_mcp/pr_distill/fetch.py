"""GitHub PR fetching for PR distillation.

Handles fetching PR metadata and diffs from GitHub using the gh CLI.
Includes version checking, identifier parsing, and error mapping.

Ported from lib/pr-distill/fetch.js.
"""

import json
import re
import subprocess
from typing import TypedDict

from spellbook_mcp.pr_distill.errors import ErrorCode, PRDistillError


# Minimum required gh CLI version
MIN_GH_VERSION = "2.30.0"

# Timeout for gh CLI commands in seconds
GH_TIMEOUT = 120

# Regex to parse GitHub PR URLs
# Captures owner/repo and PR number from URLs like:
# - https://github.com/owner/repo/pull/123
# - https://github.com/owner/repo/pull/123/files
PR_URL_REGEX = re.compile(r"github\.com/([^/]+/[^/]+)/pull/(\d+)")


class PRIdentifier(TypedDict):
    """Parsed PR identifier."""
    pr_number: int
    repo: str


class PRFetchResult(TypedDict):
    """Result of fetching a PR."""
    meta: dict
    diff: str
    repo: str


def run_command(cmd: str) -> str:
    """Run a shell command and return output.

    Args:
        cmd: Shell command to run

    Returns:
        Command stdout as string

    Raises:
        subprocess.CalledProcessError: If command fails
    """
    result = subprocess.run(
        cmd,
        shell=True,
        capture_output=True,
        text=True,
        timeout=GH_TIMEOUT,
        check=True,
    )
    return result.stdout


def compare_semver(a: str, b: str) -> int:
    """Compare two semver version strings.

    Args:
        a: First version string
        b: Second version string

    Returns:
        -1 if a < b, 0 if a == b, 1 if a > b
    """
    a_parts = [int(x) for x in a.split(".")] + [0, 0, 0]  # Pad to 3 elements
    b_parts = [int(x) for x in b.split(".")] + [0, 0, 0]

    for i in range(3):
        a_val = a_parts[i]
        b_val = b_parts[i]
        if a_val < b_val:
            return -1
        if a_val > b_val:
            return 1
    return 0


def check_gh_version() -> bool:
    """Check that gh CLI is installed and meets minimum version.

    Returns:
        True if version is sufficient

    Raises:
        PRDistillError: GH_NOT_AUTHENTICATED if gh not installed,
                        GH_VERSION_TOO_OLD if version too old
    """
    try:
        output = run_command("gh --version")
    except subprocess.CalledProcessError as e:
        raise PRDistillError(
            ErrorCode.GH_NOT_AUTHENTICATED,
            "gh CLI is not installed or not in PATH. Please install gh: https://cli.github.com/",
            recoverable=False,
            context={"error": str(e)},
        )

    # Parse version from output like "gh version 2.30.0 (2023-05-10)"
    version_match = re.search(r"gh version (\d+\.\d+\.\d+)", output)
    if not version_match:
        raise PRDistillError(
            ErrorCode.GH_VERSION_TOO_OLD,
            f"Could not parse gh version from output: {output}",
            recoverable=False,
        )

    version = version_match.group(1)
    if compare_semver(version, MIN_GH_VERSION) < 0:
        raise PRDistillError(
            ErrorCode.GH_VERSION_TOO_OLD,
            f"gh CLI version {version} is too old. Minimum required: {MIN_GH_VERSION}. Please update: gh upgrade",
            recoverable=False,
            context={"version": version, "min_version": MIN_GH_VERSION},
        )

    return True


def parse_pr_identifier(identifier: str) -> PRIdentifier:
    """Parse a PR identifier (number or URL) into structured format.

    Args:
        identifier: PR number or GitHub PR URL

    Returns:
        Dict with pr_number and repo

    Raises:
        PRDistillError: GH_PR_NOT_FOUND if invalid or repo cannot be determined
    """
    # Try to parse as URL first
    url_match = PR_URL_REGEX.search(identifier)
    if url_match:
        return {
            "pr_number": int(url_match.group(2)),
            "repo": url_match.group(1),
        }

    # Try to parse as plain number
    try:
        pr_number = int(identifier)
        if pr_number > 0:
            # Need to get repo from git remote
            try:
                remote_url = run_command("git remote get-url origin").strip()
            except subprocess.CalledProcessError:
                raise PRDistillError(
                    ErrorCode.GH_PR_NOT_FOUND,
                    "Could not determine repository from git remote. Provide a full PR URL instead.",
                    recoverable=False,
                    context={"identifier": identifier},
                )

            # Parse repo from HTTPS or SSH URL
            # HTTPS: https://github.com/owner/repo.git
            # SSH: git@github.com:owner/repo.git
            https_match = re.search(r"github\.com/([^/]+/[^/]+?)(?:\.git)?$", remote_url)
            ssh_match = re.search(r"github\.com:([^/]+/[^/]+?)(?:\.git)?$", remote_url)

            if https_match:
                repo = https_match.group(1)
            elif ssh_match:
                repo = ssh_match.group(1)
            else:
                raise PRDistillError(
                    ErrorCode.GH_PR_NOT_FOUND,
                    f"Could not parse GitHub repo from remote URL: {remote_url}",
                    recoverable=False,
                    context={"remote_url": remote_url},
                )

            return {
                "pr_number": pr_number,
                "repo": repo,
            }
    except ValueError:
        pass

    # Invalid identifier
    raise PRDistillError(
        ErrorCode.GH_PR_NOT_FOUND,
        f"Invalid PR identifier: {identifier}. Provide a PR number or GitHub PR URL.",
        recoverable=False,
        context={"identifier": identifier},
    )


def map_gh_error(error: Exception, context: dict) -> PRDistillError:
    """Map gh CLI error to PRDistillError.

    Args:
        error: Original exception
        context: Additional context (pr_number, repo)

    Returns:
        Mapped PRDistillError
    """
    message = str(error)
    stderr = ""
    if hasattr(error, "stderr") and error.stderr:
        stderr = error.stderr.decode() if isinstance(error.stderr, bytes) else str(error.stderr)

    combined = f"{message} {stderr}".lower()

    if "could not resolve" in combined or "not found" in combined:
        return PRDistillError(
            ErrorCode.GH_PR_NOT_FOUND,
            f"PR not found: {context.get('pr_number')} in {context.get('repo')}",
            recoverable=False,
            context=context,
        )

    if "rate limit" in combined:
        return PRDistillError(
            ErrorCode.GH_RATE_LIMITED,
            "GitHub API rate limit exceeded. Please wait and try again.",
            recoverable=True,
            context=context,
        )

    if "not logged in" in combined or "gh auth login" in combined:
        return PRDistillError(
            ErrorCode.GH_NOT_AUTHENTICATED,
            "Not authenticated with GitHub. Please run: gh auth login",
            recoverable=False,
            context=context,
        )

    # Generic network error
    return PRDistillError(
        ErrorCode.GH_NETWORK_ERROR,
        f"GitHub API error: {message}",
        recoverable=True,
        context={**context, "original_error": message},
    )


def fetch_pr(pr_identifier: PRIdentifier) -> PRFetchResult:
    """Fetch PR metadata and diff from GitHub.

    Args:
        pr_identifier: Parsed PR identifier with pr_number and repo

    Returns:
        Dict with meta, diff, and repo

    Raises:
        PRDistillError: Various error codes for different failure modes
    """
    pr_number = pr_identifier["pr_number"]
    repo = pr_identifier["repo"]

    # Verify gh version first
    check_gh_version()

    context = {"pr_number": pr_number, "repo": repo}

    # Fetch PR metadata
    try:
        meta_json = run_command(
            f"gh pr view {pr_number} --repo {repo} --json number,title,body,headRefOid,baseRefName,additions,deletions,files"
        )
        meta = json.loads(meta_json)
    except subprocess.CalledProcessError as e:
        raise map_gh_error(e, context)
    except json.JSONDecodeError as e:
        raise PRDistillError(
            ErrorCode.GH_NETWORK_ERROR,
            f"Invalid JSON response from gh pr view: {e}",
            recoverable=True,
            context=context,
        )

    # Fetch PR diff
    try:
        diff = run_command(f"gh pr diff {pr_number} --repo {repo}")
    except subprocess.CalledProcessError as e:
        raise map_gh_error(e, context)

    return {
        "meta": meta,
        "diff": diff,
        "repo": repo,
    }

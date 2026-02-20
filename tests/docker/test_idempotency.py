"""Tests for installer idempotency.

Verifies that running the installer multiple times produces identical,
stable results: same files, same content, no extra artifacts, and no
errors on subsequent runs.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Callable

import pytest

from tests.docker.conftest import InstallerResult


# Paths (relative to HOME) that are expected to change between installer runs.
# These contain run-specific data (timestamps, session IDs, debug logs) and
# should be excluded from idempotency comparisons.
_VOLATILE_PATH_PREFIXES = (
    ".claude/debug/",
    ".cache/uv/",
    ".local/spellbook/spellbook-mcp.",
)


def collect_file_hashes(
    directory: Path,
    *,
    exclude_volatile: bool = False,
) -> dict[str, str]:
    """Recursively collect SHA-256 hashes for all files under a directory.

    Args:
        directory: Root directory to walk.
        exclude_volatile: If True, skip files under known volatile path
            prefixes (debug logs, etc.) that change between runs.

    Returns:
        A dict mapping relative file paths (as POSIX strings) to their
        SHA-256 hex digests. Directories and symlink targets are not
        included; only regular file content is hashed.
    """
    hashes: dict[str, str] = {}
    if not directory.exists():
        return hashes

    for path in sorted(directory.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(directory).as_posix()
        if exclude_volatile and _is_volatile(relative):
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        hashes[relative] = digest

    return hashes


def _is_volatile(relative: str) -> bool:
    """Return True if the relative path matches a known volatile prefix."""
    return any(relative.startswith(prefix) for prefix in _VOLATILE_PATH_PREFIXES)


def collect_file_set(
    directory: Path,
    *,
    exclude_volatile: bool = False,
) -> set[str]:
    """Recursively collect relative paths of all files under a directory.

    Args:
        directory: Root directory to walk.
        exclude_volatile: If True, skip files under known volatile path
            prefixes (debug logs, caches, etc.) that may appear between runs.

    Returns:
        A set of relative file paths (as POSIX strings).
    """
    if not directory.exists():
        return set()

    result: set[str] = set()
    for path in directory.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(directory).as_posix()
        if exclude_volatile and _is_volatile(relative):
            continue
        result.add(relative)
    return result


@pytest.mark.usefixtures("isolated_home")
class TestIdempotency:
    """Tests verifying that repeated installer runs produce stable results."""

    def _run_install(
        self,
        run_installer: Callable[..., InstallerResult],
        platform_env: Callable,
    ) -> InstallerResult:
        """Run a full (non-dry-run) install for claude_code.

        Helper that encapsulates the common invocation arguments used
        across all idempotency tests.
        """
        with platform_env("claude_code"):
            return run_installer(
                "--platforms", "claude_code",
                "--yes",
                "--no-interactive",
                "--force",
            )

    def test_reinstall_identical(
        self,
        run_installer: Callable[..., InstallerResult],
        isolated_home: Path,
        platform_env: Callable,
    ) -> None:
        """Running the installer twice should produce files with identical content.

        Installs once, snapshots every file's SHA-256, installs again with
        the same arguments, and asserts that all file hashes match.
        """
        # First install
        result1 = self._run_install(run_installer, platform_env)
        assert result1.returncode == 0, (
            f"First install failed (exit {result1.returncode}).\n"
            f"stdout: {result1.stdout}\nstderr: {result1.stderr}"
        )

        hashes_after_first = collect_file_hashes(isolated_home, exclude_volatile=True)
        assert hashes_after_first, (
            "First install produced no files under isolated HOME. "
            "Installer may not be writing to the expected location."
        )

        # Second install (same args)
        result2 = self._run_install(run_installer, platform_env)
        assert result2.returncode == 0, (
            f"Second install failed (exit {result2.returncode}).\n"
            f"stdout: {result2.stdout}\nstderr: {result2.stderr}"
        )

        hashes_after_second = collect_file_hashes(isolated_home, exclude_volatile=True)

        # Compare content: every file present after the first install
        # should have the same hash after the second install.
        changed_files: list[str] = []
        for rel_path, first_hash in hashes_after_first.items():
            second_hash = hashes_after_second.get(rel_path)
            if second_hash is None:
                changed_files.append(f"  MISSING after second run: {rel_path}")
            elif second_hash != first_hash:
                changed_files.append(f"  CHANGED: {rel_path}")

        assert not changed_files, (
            "Second install produced different file contents:\n"
            + "\n".join(changed_files)
        )

    def test_no_extra_files(
        self,
        run_installer: Callable[..., InstallerResult],
        isolated_home: Path,
        platform_env: Callable,
    ) -> None:
        """Running the installer twice should not create any new files.

        Records the set of files after the first install, runs again,
        and verifies no additional files appeared.
        """
        # First install
        result1 = self._run_install(run_installer, platform_env)
        assert result1.returncode == 0, (
            f"First install failed (exit {result1.returncode}).\n"
            f"stdout: {result1.stdout}\nstderr: {result1.stderr}"
        )

        files_after_first = collect_file_set(isolated_home, exclude_volatile=True)
        assert files_after_first, (
            "First install produced no files under isolated HOME."
        )

        # Second install
        result2 = self._run_install(run_installer, platform_env)
        assert result2.returncode == 0, (
            f"Second install failed (exit {result2.returncode}).\n"
            f"stdout: {result2.stdout}\nstderr: {result2.stderr}"
        )

        files_after_second = collect_file_set(isolated_home, exclude_volatile=True)

        extra_files = files_after_second - files_after_first
        assert not extra_files, (
            f"Second install created {len(extra_files)} extra file(s):\n"
            + "\n".join(f"  {f}" for f in sorted(extra_files))
        )

    def test_stable_output(
        self,
        run_installer: Callable[..., InstallerResult],
        platform_env: Callable,
    ) -> None:
        """The second installer run should succeed without errors.

        After an initial install, a second run with the same arguments
        should exit 0 and not emit error-level messages.
        """
        # First install
        result1 = self._run_install(run_installer, platform_env)
        assert result1.returncode == 0, (
            f"First install failed (exit {result1.returncode}).\n"
            f"stdout: {result1.stdout}\nstderr: {result1.stderr}"
        )

        # Second install
        result2 = self._run_install(run_installer, platform_env)
        assert result2.returncode == 0, (
            f"Second install exited non-zero (exit {result2.returncode}).\n"
            f"stdout: {result2.stdout}\nstderr: {result2.stderr}"
        )

        # The second run should not contain error-level output.
        # We check stderr for "[error]" markers that the installer emits
        # via print_error().
        combined = result2.stdout + result2.stderr
        assert "[error]" not in combined.lower(), (
            f"Second install produced error output:\n"
            f"stdout: {result2.stdout}\nstderr: {result2.stderr}"
        )

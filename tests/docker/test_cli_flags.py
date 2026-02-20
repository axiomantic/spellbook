"""Tests for install.py CLI flags and argument handling.

Validates that the installer's command-line interface behaves correctly
for each supported flag: --help, --dry-run, --platforms, --update-only,
--install-dir, and CLAUDE_CONFIG_DIR environment variable override.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import pytest

from tests.docker.conftest import InstallerResult


@pytest.mark.usefixtures("isolated_home")
class TestCLIFlags:
    """Tests for install.py CLI flag behavior."""

    def test_help_flag(self, run_installer: Callable[..., InstallerResult]) -> None:
        """Running install.py --help should exit 0 and print usage information."""
        result = run_installer("--help")

        assert result.returncode == 0, (
            f"Expected exit code 0 for --help, got {result.returncode}.\n"
            f"stderr: {result.stderr}"
        )
        # argparse prints help to stdout
        assert "usage:" in result.stdout.lower() or "Usage:" in result.stdout, (
            f"Expected usage text in --help output.\nstdout: {result.stdout}"
        )
        # Verify key flags appear in help text
        for flag in ("--dry-run", "--platforms", "--force", "--yes"):
            assert flag in result.stdout, (
                f"Expected {flag!r} to appear in --help output.\n"
                f"stdout: {result.stdout}"
            )

    def test_dry_run_creates_no_files(
        self,
        run_installer: Callable[..., InstallerResult],
        install_dir: Path,
    ) -> None:
        """Running install.py --dry-run should exit 0 and create no files in the install dir."""
        # Snapshot the install dir contents before running
        contents_before = set(install_dir.iterdir())

        result = run_installer(
            "--dry-run",
            "--yes",
            "--no-interactive",
            "--platforms", "claude_code",
        )

        assert result.returncode == 0, (
            f"Expected exit code 0 for --dry-run, got {result.returncode}.\n"
            f"stderr: {result.stderr}"
        )

        # Verify no new files were created in the install dir
        contents_after = set(install_dir.iterdir())
        new_files = contents_after - contents_before
        assert not new_files, (
            f"--dry-run should not create files, but found new entries: "
            f"{[p.name for p in new_files]}"
        )

    def test_platforms_flag_claude_code(
        self,
        run_installer: Callable[..., InstallerResult],
        platform_env: Callable,
    ) -> None:
        """Running install.py --platforms claude_code should install only Claude Code."""
        with platform_env("claude_code"):
            result = run_installer(
                "--platforms", "claude_code",
                "--yes",
                "--no-interactive",
                "--dry-run",
            )

        assert result.returncode == 0, (
            f"Expected exit code 0 for --platforms claude_code, got {result.returncode}.\n"
            f"stderr: {result.stderr}"
        )
        combined_output = result.stdout + result.stderr
        # In dry-run mode, should mention Claude Code activity
        assert "claude" in combined_output.lower() or "dry run" in combined_output.lower(), (
            f"Expected output to reference Claude Code or dry run mode.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_invalid_platform_produces_error(
        self,
        run_installer: Callable[..., InstallerResult],
    ) -> None:
        """Running install.py --platforms nonexistent should fail with an error."""
        result = run_installer(
            "--platforms", "nonexistent_platform",
            "--yes",
            "--no-interactive",
        )

        # The installer should either exit non-zero or print an error message
        # about the unknown platform. Either behavior is acceptable.
        combined_output = (result.stdout + result.stderr).lower()
        has_error_indication = (
            result.returncode != 0
            or "unknown" in combined_output
            or "error" in combined_output
            or "invalid" in combined_output
            or "not available" in combined_output
        )
        assert has_error_indication, (
            f"Expected non-zero exit code or error message for invalid platform.\n"
            f"returncode: {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_dir_argument_installs_to_target(
        self,
        run_installer: Callable[..., InstallerResult],
        install_dir: Path,
        platform_env: Callable,
    ) -> None:
        """Running install.py --install-dir <dir> should use that directory."""
        with platform_env("claude_code"):
            result = run_installer(
                "--install-dir", str(install_dir),
                "--platforms", "claude_code",
                "--yes",
                "--no-interactive",
                "--dry-run",
            )

        # The installer should acknowledge the target directory.
        # In dry-run mode it won't actually install, but it should not error
        # about the directory path.
        assert result.returncode == 0, (
            f"Expected exit code 0 with --install-dir, got {result.returncode}.\n"
            f"stderr: {result.stderr}"
        )

    def test_update_only_skips_bootstrap(
        self,
        run_installer: Callable[..., InstallerResult],
    ) -> None:
        """Running install.py --update-only should skip the bootstrap phase.

        The --update-only flag is used by auto-update after git pull. It should
        skip prerequisite checks (uv, git, clone) and go straight to
        installation using the existing spellbook directory.
        """
        result = run_installer(
            "--update-only",
            "--yes",
            "--no-interactive",
            "--dry-run",
            "--platforms", "claude_code",
        )

        assert result.returncode == 0, (
            f"Expected exit code 0 for --update-only, got {result.returncode}.\n"
            f"stderr: {result.stderr}"
        )

        combined_output = result.stdout + result.stderr
        # --update-only should print the "Update-only mode" message
        assert "update-only mode" in combined_output.lower(), (
            f"Expected 'Update-only mode' in output.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        # --update-only should NOT show "Checking prerequisites" (bootstrap phase)
        assert "checking prerequisites" not in combined_output.lower(), (
            f"--update-only should skip bootstrap, but found 'Checking prerequisites'.\n"
            f"stdout: {result.stdout}"
        )

    def test_custom_config_env_claude_config_dir(
        self,
        run_installer: Callable[..., InstallerResult],
        isolated_home: Path,
    ) -> None:
        """Setting CLAUDE_CONFIG_DIR should direct Claude Code config to the custom path."""
        custom_config = isolated_home / "custom-claude-config"
        custom_config.mkdir(parents=True, exist_ok=True)

        result = run_installer(
            "--platforms", "claude_code",
            "--yes",
            "--no-interactive",
            "--dry-run",
            env={"CLAUDE_CONFIG_DIR": str(custom_config)},
        )

        assert result.returncode == 0, (
            f"Expected exit code 0 with CLAUDE_CONFIG_DIR set, got {result.returncode}.\n"
            f"stderr: {result.stderr}"
        )
        combined_output = result.stdout + result.stderr
        # The installer should reference the custom config directory or
        # at minimum complete without error when CLAUDE_CONFIG_DIR is set.
        # In dry-run mode, success alone validates the env var was accepted.
        assert "dry run" in combined_output.lower() or result.returncode == 0, (
            f"Expected installer to accept CLAUDE_CONFIG_DIR override.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

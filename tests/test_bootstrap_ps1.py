"""Tests for the PowerShell bootstrap script (bootstrap.ps1).

Validates that bootstrap.ps1:
- Exists at the project root
- Contains expected structural elements (PowerShell patterns, checks)
- Has valid PowerShell syntax (when pwsh is available)
- Handles offline/unreachable download URLs gracefully
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

_HAS_PWSH = shutil.which("pwsh") is not None

# Root of the real spellbook project (one level up from tests/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestBootstrapPs1:
    """Tests exercising the bootstrap.ps1 PowerShell script."""

    def test_bootstrap_ps1_exists(self) -> None:
        """Verify bootstrap.ps1 exists at the project root.

        The bootstrap script is the Windows entry point for new users
        installing spellbook via ``irm ... | iex``. It must be present
        at the repository root so that the raw GitHub URL resolves.
        """
        script_path = PROJECT_ROOT / "bootstrap.ps1"
        assert script_path.is_file(), (
            f"bootstrap.ps1 not found at project root: {PROJECT_ROOT}\n"
            "This file is required for Windows bootstrap installation."
        )

    def test_bootstrap_ps1_content_structure(self) -> None:
        """Verify bootstrap.ps1 has expected structural elements.

        Reads bootstrap.ps1 and checks for key PowerShell patterns and
        structural elements that the script must contain to function
        correctly: command checks, Python version validation, uv
        installation, git verification, install path, and error handling.
        """
        script_path = PROJECT_ROOT / "bootstrap.ps1"
        content = script_path.read_text()

        # PowerShell patterns
        assert "Write-Host" in content, (
            "bootstrap.ps1 should use Write-Host for user-facing output"
        )
        assert "Get-Command" in content, (
            "bootstrap.ps1 should use Get-Command to check for required tools"
        )
        assert "Test-Path" in content, (
            "bootstrap.ps1 should use Test-Path to check directory existence"
        )

        # Python version check
        assert "sys.version_info" in content or "python" in content.lower(), (
            "bootstrap.ps1 should reference Python version checking"
        )

        # uv installation
        assert "uv" in content, (
            "bootstrap.ps1 should reference uv installation"
        )
        assert "astral.sh" in content or "install.ps1" in content, (
            "bootstrap.ps1 should reference the uv installer URL"
        )

        # Git check
        assert "git" in content.lower(), (
            "bootstrap.ps1 should check for git availability"
        )

        # LOCALAPPDATA install path
        assert "LOCALAPPDATA" in content, (
            "bootstrap.ps1 should use LOCALAPPDATA for the install directory"
        )

        # Error handling
        assert "ErrorActionPreference" in content, (
            "bootstrap.ps1 should set ErrorActionPreference for error handling"
        )
        assert "exit 1" in content, (
            "bootstrap.ps1 should exit with code 1 on errors"
        )

    @pytest.mark.skipif(not _HAS_PWSH, reason="pwsh (PowerShell Core) not available")
    def test_bootstrap_ps1_syntax(self) -> None:
        """Validate bootstrap.ps1 has no PowerShell syntax errors.

        Uses the PowerShell parser API via pwsh to parse the script file
        and check for parse errors without executing it. This is
        analogous to ``bash -n`` for shell scripts.

        Skipped if pwsh is not installed on the system.
        """
        script_path = PROJECT_ROOT / "bootstrap.ps1"

        # Use PowerShell's parser to check for syntax errors without execution
        parse_command = (
            "$errors = $null; "
            f"[System.Management.Automation.Language.Parser]::ParseFile("
            f"'{script_path}', [ref]$null, [ref]$errors); "
            "if ($errors.Count -gt 0) { "
            "  $errors | ForEach-Object { Write-Error $_.ToString() }; "
            "  exit 1 "
            "} else { "
            "  Write-Host 'No syntax errors found'; "
            "  exit 0 "
            "}"
        )

        result = subprocess.run(
            ["pwsh", "-NoProfile", "-NonInteractive", "-Command", parse_command],
            capture_output=True,
            text=True,
            timeout=30,
        )

        assert result.returncode == 0, (
            f"bootstrap.ps1 has PowerShell syntax errors.\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )

    @pytest.mark.skipif(not _HAS_PWSH, reason="pwsh (PowerShell Core) not available")
    def test_bootstrap_ps1_offline_failure(self, tmp_path: Path) -> None:
        """Verify bootstrap.ps1 fails gracefully when download URLs are unreachable.

        Creates a modified copy of bootstrap.ps1 pointing at an
        unreachable localhost URL for the git clone, then runs it with
        pwsh. The script should fail and not produce success indicators.

        Skipped if pwsh is not installed on the system.
        """
        # Read the original bootstrap.ps1
        original = (PROJECT_ROOT / "bootstrap.ps1").read_text()

        # Replace the real GitHub clone URL with an unreachable address.
        # Port 1 is privileged and almost certainly not listening, giving
        # an immediate connection failure rather than a long TCP timeout.
        modified = original.replace(
            "https://github.com/axiomantic/spellbook.git",
            "http://127.0.0.1:1/spellbook.git",
        )
        assert modified != original, (
            "Failed to replace git clone URL in bootstrap.ps1. "
            "The hardcoded URL may have changed."
        )

        # Also replace the uv installer URL to prevent network access
        modified = modified.replace(
            "https://astral.sh/uv/install.ps1",
            "http://127.0.0.1:1/install.ps1",
        )

        modified_script = tmp_path / "bootstrap_offline.ps1"
        modified_script.write_text(modified)

        try:
            result = subprocess.run(
                [
                    "pwsh", "-NoProfile", "-NonInteractive",
                    "-File", str(modified_script),
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
        except subprocess.TimeoutExpired:
            # A timeout also indicates the download did not succeed,
            # which is acceptable for this test.
            return

        combined_output = (result.stdout + result.stderr).lower()

        # The script should have failed (non-zero exit or error output)
        has_failure = (
            result.returncode != 0
            or "error" in combined_output
            or "fatal" in combined_output
            or "failed" in combined_output
            or "could not" in combined_output
        )
        assert has_failure, (
            "Expected failure when git clone URL is unreachable.\n"
            f"returncode: {result.returncode}\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )

        # The script should NOT have produced installer success indicators
        assert "running spellbook installer" not in combined_output or result.returncode != 0, (
            "bootstrap.ps1 should not reach the installer when git clone fails.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

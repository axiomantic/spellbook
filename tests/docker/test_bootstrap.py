"""Tests for the curl-pipe-bash bootstrap flow.

Validates that bootstrap.sh:
- Is served correctly by the local HTTP server
- Contains valid bash syntax and expected content
- Handles offline/unreachable download URLs gracefully
- Works alongside existing installations (upgrade path)
"""

from __future__ import annotations

import os
import subprocess
import urllib.request
from pathlib import Path
from typing import Callable

import pytest

from tests.docker.conftest import InstallerResult

# Root of the real spellbook project (two levels up from this file)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class TestBootstrap:
    """Tests exercising the curl | bash bootstrap flow."""

    def test_curl_bootstrap(self, http_server: str) -> None:
        """Verify bootstrap.sh is served by the HTTP fixture and curl can fetch it.

        Downloads bootstrap.sh via curl from the local HTTP server and
        verifies the response contains the expected script content. This
        does NOT execute the full bootstrap (which would try to download
        install.py from GitHub). Instead it confirms the serving
        infrastructure works and the script is retrievable.
        """
        result = subprocess.run(
            ["curl", "-fsSL", f"{http_server}/bootstrap.sh"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        assert result.returncode == 0, (
            f"curl failed to fetch bootstrap.sh from {http_server}.\n"
            f"returncode: {result.returncode}\n"
            f"stderr: {result.stderr}"
        )

        # The fetched content should be the bootstrap script
        content = result.stdout
        assert "#!/usr/bin/env bash" in content, (
            "Fetched content does not start with expected shebang.\n"
            f"Content preview: {content[:200]}"
        )
        assert "INSTALL_PY_URL" in content, (
            "Fetched content missing INSTALL_PY_URL variable.\n"
            f"Content preview: {content[:200]}"
        )
        assert "install.py" in content.lower(), (
            "Fetched content does not reference install.py.\n"
            f"Content preview: {content[:200]}"
        )

    def test_bootstrap_script_content(self, http_server: str) -> None:
        """Verify bootstrap.sh has valid bash syntax and expected structure.

        Fetches the script from the HTTP server, then runs ``bash -n`` to
        validate syntax. Also checks for key structural elements: shebang,
        ``set -e``, curl/wget download commands, python invocation, and
        error handling functions.
        """
        # Fetch the script via urllib (no curl dependency for content checks)
        with urllib.request.urlopen(f"{http_server}/bootstrap.sh") as resp:
            content = resp.read().decode("utf-8")

        # Structural checks
        assert content.startswith("#!/usr/bin/env bash"), (
            "bootstrap.sh must start with #!/usr/bin/env bash shebang"
        )
        assert "set -e" in content, (
            "bootstrap.sh should use 'set -e' for fail-fast behavior"
        )
        assert "curl" in content, (
            "bootstrap.sh should use curl to download install.py"
        )
        assert "python" in content.lower(), (
            "bootstrap.sh should invoke python to run install.py"
        )
        assert "print_error" in content, (
            "bootstrap.sh should define a print_error function for error reporting"
        )
        assert "find_python" in content, (
            "bootstrap.sh should define a find_python function"
        )
        assert "main" in content, (
            "bootstrap.sh should define a main function"
        )

        # Validate bash syntax via bash -n (parse without executing)
        syntax_result = subprocess.run(
            ["bash", "-n"],
            input=content,
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert syntax_result.returncode == 0, (
            f"bootstrap.sh has bash syntax errors.\n"
            f"stderr: {syntax_result.stderr}"
        )

    def test_bootstrap_offline_failure(self, tmp_path: Path) -> None:
        """Verify bootstrap.sh produces a curl error when the download URL is unreachable.

        Creates a modified copy of bootstrap.sh pointing at localhost on a
        port that refuses connections, then runs it. The curl command within
        the script should fail and report an error to stderr.

        Note: bootstrap.sh uses ``curl ... | python ...`` without
        ``set -o pipefail``, so the script's exit code may be 0 even when
        curl fails (bash pipeline exit code is that of the last command).
        This test therefore checks that curl's connection failure is visible
        in stderr rather than relying on the overall exit code.
        """
        # Read the original bootstrap.sh
        original = (PROJECT_ROOT / "bootstrap.sh").read_text()

        # Replace the real GitHub URL with localhost port 1 (privileged,
        # almost certainly not listening). This gives an immediate
        # "Connection refused" rather than a long TCP timeout.
        modified = original.replace(
            "https://raw.githubusercontent.com/axiomantic/spellbook/main/install.py",
            "http://127.0.0.1:1/install.py",
        )
        assert modified != original, (
            "Failed to replace INSTALL_PY_URL in bootstrap.sh. "
            "The hardcoded URL may have changed."
        )

        modified_script = tmp_path / "bootstrap_offline.sh"
        modified_script.write_text(modified)
        modified_script.chmod(0o755)

        try:
            result = subprocess.run(
                ["bash", str(modified_script)],
                capture_output=True,
                text=True,
                timeout=15,
            )
        except subprocess.TimeoutExpired:
            # A timeout also indicates the download did not succeed.
            return

        # curl should report a connection error in stderr
        combined_output = (result.stdout + result.stderr).lower()
        has_connection_error = (
            "failed to connect" in combined_output
            or "couldn't connect" in combined_output
            or "connection refused" in combined_output
            or result.returncode != 0
        )
        assert has_connection_error, (
            "Expected curl connection failure when download URL is unreachable.\n"
            f"returncode: {result.returncode}\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )

        # The script should NOT have produced install.py success indicators
        assert "spellbook installer" not in combined_output, (
            "bootstrap.sh should not run install.py when download fails.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    @pytest.mark.usefixtures("isolated_home")
    @pytest.mark.skipif(
        bool(os.environ.get("CLAUDECODE")),
        reason="MCP registration times out inside a nested Claude Code session",
    )
    def test_bootstrap_existing_install_upgrade(
        self,
        run_installer: Callable[..., InstallerResult],
        platform_env: Callable,
    ) -> None:
        """Verify the upgrade path: running install.py again after an initial install.

        Performs a real (non-dry-run) install for claude_code, then runs the
        installer a second time to simulate the upgrade path that bootstrap.sh
        would trigger. The second run should succeed without duplicating files
        or leaving the installation in a broken state.
        """
        with platform_env("claude_code"):
            # First install
            first_result = run_installer(
                "--platforms", "claude_code",
                "--yes",
                "--no-interactive",
            )
            assert first_result.returncode == 0, (
                f"Initial install failed.\n"
                f"stdout: {first_result.stdout}\n"
                f"stderr: {first_result.stderr}"
            )

            # Second install (simulates what bootstrap.sh does on re-run)
            second_result = run_installer(
                "--platforms", "claude_code",
                "--yes",
                "--no-interactive",
                "--force",
            )
            assert second_result.returncode == 0, (
                f"Upgrade (second) install failed.\n"
                f"stdout: {second_result.stdout}\n"
                f"stderr: {second_result.stderr}"
            )

        # Both runs should succeed. The second run with --force ensures
        # all files are re-written, exercising the upgrade/overwrite path.
        combined_output = (second_result.stdout + second_result.stderr).lower()
        # Verify it did not report duplication errors
        assert "duplicate" not in combined_output, (
            "Upgrade install reported duplication issues.\n"
            f"stdout: {second_result.stdout}\nstderr: {second_result.stderr}"
        )

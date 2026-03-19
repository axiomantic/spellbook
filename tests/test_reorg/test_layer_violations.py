"""Tests for the layer violation detection script.

Verifies that the spellbook package follows core -> domains -> interfaces
layering with no violations.
"""

import subprocess
import sys


class TestLayerViolationScript:
    """Verify the layer violation detection script works correctly."""

    def test_script_exists_and_runs(self):
        """The script should exist and be executable via python."""
        result = subprocess.run(
            [sys.executable, "scripts/check_layer_violations.py"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, (
            f"Layer violation script failed with exit code {result.returncode}.\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )

    def test_script_reports_no_violations(self):
        """Current structure should have no layer violations."""
        result = subprocess.run(
            [sys.executable, "scripts/check_layer_violations.py"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0
        # Should report clean
        assert "no layer violations found" in result.stdout.lower()

    def test_script_checks_all_layers(self):
        """Script output should mention all three layers."""
        result = subprocess.run(
            [sys.executable, "scripts/check_layer_violations.py"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        output = result.stdout.lower()
        assert "core" in output
        assert "domain" in output
        assert "interface" in output

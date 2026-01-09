"""Tests for MCP health check tool and CLI script."""

import json
import os
import pytest
import time
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestHealthCheckMCPTool:
    """Tests for the spellbook_health_check MCP tool."""

    def test_returns_healthy_status(self):
        """Test that health check returns healthy status."""
        from spellbook_mcp import server

        result = server.spellbook_health_check.fn()

        assert result["status"] == "healthy"

    def test_returns_version(self, tmp_path, monkeypatch):
        """Test that health check returns version from .version file."""
        from spellbook_mcp import server

        # Create a mock version file
        version_file = tmp_path / ".version"
        version_file.write_text("1.2.3\n")

        # Patch the __file__ lookup to use our temp path
        original_get_version = server._get_version

        def mock_get_version():
            return "1.2.3"

        monkeypatch.setattr(server, "_get_version", mock_get_version)

        result = server.spellbook_health_check.fn()

        assert result["version"] == "1.2.3"

    def test_returns_tools_list(self):
        """Test that health check returns list of available tools."""
        from spellbook_mcp import server

        result = server.spellbook_health_check.fn()

        assert "tools_available" in result
        assert isinstance(result["tools_available"], list)
        # Should include at least the health check itself
        assert "spellbook_health_check" in result["tools_available"]
        # And other known tools
        assert "find_session" in result["tools_available"]
        assert "spellbook_config_get" in result["tools_available"]

    def test_returns_uptime_seconds(self):
        """Test that health check returns uptime in seconds."""
        from spellbook_mcp import server

        result = server.spellbook_health_check.fn()

        assert "uptime_seconds" in result
        assert isinstance(result["uptime_seconds"], (int, float))
        assert result["uptime_seconds"] >= 0


class TestGetVersion:
    """Tests for the _get_version helper function."""

    def test_reads_version_from_file(self, tmp_path, monkeypatch):
        """Test reading version from .version file."""
        from spellbook_mcp import server

        # Monkeypatch __file__ to use tmp_path
        fake_server_file = tmp_path / "spellbook_mcp" / "server.py"
        fake_server_file.parent.mkdir(parents=True)
        fake_server_file.touch()

        version_file = tmp_path / ".version"
        version_file.write_text("2.0.0\n")

        # We need to temporarily replace the __file__ reference
        original_file = server.__file__

        try:
            server.__file__ = str(fake_server_file)
            result = server._get_version()
            assert result == "2.0.0"
        finally:
            server.__file__ = original_file

    def test_returns_unknown_when_file_missing(self, tmp_path, monkeypatch):
        """Test that missing .version file returns unknown."""
        from spellbook_mcp import server

        fake_server_file = tmp_path / "spellbook_mcp" / "server.py"
        fake_server_file.parent.mkdir(parents=True)
        fake_server_file.touch()
        # Don't create .version file

        original_file = server.__file__
        monkeypatch.delenv("SPELLBOOK_DIR", raising=False)

        try:
            server.__file__ = str(fake_server_file)
            result = server._get_version()
            assert result == "unknown"
        finally:
            server.__file__ = original_file

    def test_uses_spellbook_dir_env_fallback(self, tmp_path, monkeypatch):
        """Test that SPELLBOOK_DIR env var is used as fallback."""
        from spellbook_mcp import server

        # Set up a temp dir with .version
        spellbook_dir = tmp_path / "spellbook"
        spellbook_dir.mkdir()
        (spellbook_dir / ".version").write_text("3.0.0\n")

        # Point __file__ to a location without .version
        fake_server_file = tmp_path / "other" / "spellbook_mcp" / "server.py"
        fake_server_file.parent.mkdir(parents=True)
        fake_server_file.touch()

        original_file = server.__file__
        monkeypatch.setenv("SPELLBOOK_DIR", str(spellbook_dir))

        try:
            server.__file__ = str(fake_server_file)
            result = server._get_version()
            assert result == "3.0.0"
        finally:
            server.__file__ = original_file


class TestGetToolNames:
    """Tests for the _get_tool_names helper function."""

    def test_returns_list_of_strings(self):
        """Test that tool names are returned as a list of strings."""
        from spellbook_mcp import server

        result = server._get_tool_names()

        assert isinstance(result, list)
        assert all(isinstance(name, str) for name in result)

    def test_includes_registered_tools(self):
        """Test that all registered tools are included."""
        from spellbook_mcp import server

        result = server._get_tool_names()

        # These tools should be registered
        expected_tools = [
            "find_session",
            "split_session",
            "list_sessions",
            "spawn_claude_session",
            "spellbook_config_get",
            "spellbook_config_set",
            "spellbook_session_init",
            "spellbook_health_check",
        ]

        for tool in expected_tools:
            assert tool in result, f"Expected tool '{tool}' not found"


class TestHealthCheckCLI:
    """Tests for the mcp-health-check.py CLI script."""

    @pytest.fixture
    def cli_module(self):
        """Load the CLI module for testing."""
        import importlib.util
        scripts_dir = Path(__file__).parent.parent.parent / "scripts"
        spec = importlib.util.spec_from_file_location(
            "mcp_health_check",
            str(scripts_dir / "mcp-health-check.py")
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_run_command_success(self, cli_module):
        """Test run_command returns output on success."""
        returncode, stdout, stderr = cli_module.run_command(["echo", "hello"])

        assert returncode == 0
        assert "hello" in stdout
        assert stderr == ""

    def test_run_command_timeout(self, cli_module):
        """Test run_command handles timeout."""
        returncode, stdout, stderr = cli_module.run_command(
            ["sleep", "10"],
            timeout=0.1
        )

        assert returncode == -1
        assert "timed out" in stderr

    def test_run_command_not_found(self, cli_module):
        """Test run_command handles missing command."""
        returncode, stdout, stderr = cli_module.run_command(
            ["nonexistent-command-xyz"]
        )

        assert returncode == -1
        assert "not found" in stderr.lower()

    def test_diagnostic_result_dataclass(self, cli_module):
        """Test DiagnosticResult dataclass."""
        diag = cli_module.DiagnosticResult(
            check="test_check",
            passed=True,
            message="Test message",
            details={"key": "value"}
        )

        assert diag.check == "test_check"
        assert diag.passed is True
        assert diag.message == "Test message"
        assert diag.details == {"key": "value"}

    def test_health_check_result_to_dict(self, cli_module):
        """Test HealthCheckResult.to_dict serialization."""
        result = cli_module.HealthCheckResult(
            healthy=True,
            platform="claude",
            connected=True,
            configured=True,
            process_running=True,
        )
        result.diagnostics.append(cli_module.DiagnosticResult(
            check="test",
            passed=True,
            message="OK",
        ))

        d = result.to_dict()

        assert d["healthy"] is True
        assert d["platform"] == "claude"
        assert d["connected"] is True
        assert len(d["diagnostics"]) == 1
        assert d["diagnostics"][0]["check"] == "test"

    def test_detect_platform_claude(self, cli_module, monkeypatch):
        """Test platform detection prefers claude."""
        import shutil

        original_which = shutil.which

        def mock_which(cmd):
            if cmd == "claude":
                return "/usr/bin/claude"
            return None

        monkeypatch.setattr(shutil, "which", mock_which)

        result = cli_module.detect_platform()
        assert result == "claude"

    def test_detect_platform_gemini_fallback(self, cli_module, monkeypatch):
        """Test platform detection falls back to gemini."""
        import shutil

        original_which = shutil.which

        def mock_which(cmd):
            if cmd == "gemini":
                return "/usr/bin/gemini"
            return None

        monkeypatch.setattr(shutil, "which", mock_which)

        result = cli_module.detect_platform()
        assert result == "gemini"

    def test_format_result_healthy(self, cli_module):
        """Test format_result for healthy server."""
        result = cli_module.HealthCheckResult(
            healthy=True,
            platform="claude",
            connected=True,
            configured=True,
            process_running=True,
        )

        output = cli_module.format_result(result)

        assert "✓" in output
        assert "Spellbook MCP (claude)" in output
        assert "Healthy: True" in output

    def test_format_result_unhealthy(self, cli_module):
        """Test format_result for unhealthy server."""
        result = cli_module.HealthCheckResult(
            healthy=False,
            platform="claude",
            error="Connection failed",
        )

        output = cli_module.format_result(result)

        assert "✗" in output
        assert "Healthy: False" in output
        assert "Error: Connection failed" in output


class TestCheckClaudeConfigOnly:
    """Tests for the fast config-only check."""

    @pytest.fixture
    def cli_module(self):
        """Load the CLI module for testing."""
        import importlib.util
        scripts_dir = Path(__file__).parent.parent.parent / "scripts"
        spec = importlib.util.spec_from_file_location(
            "mcp_health_check",
            str(scripts_dir / "mcp-health-check.py")
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_no_claude_cli(self, cli_module, monkeypatch):
        """Test behavior when claude CLI is not available."""
        import shutil

        monkeypatch.setattr(shutil, "which", lambda cmd: None)

        result = cli_module.check_claude_config_only()

        assert result.healthy is False
        assert "not found" in result.error.lower()

    def test_mcp_not_configured(self, cli_module, monkeypatch):
        """Test behavior when spellbook MCP is not configured."""
        import shutil

        def mock_which(cmd):
            if cmd == "claude":
                return "/usr/bin/claude"
            return None

        monkeypatch.setattr(shutil, "which", mock_which)

        # Mock run_command to simulate MCP not found
        def mock_run_command(cmd, timeout=10.0):
            if "mcp" in cmd and "get" in cmd:
                return 1, "", "MCP server 'spellbook' not found"
            return 0, "", ""

        monkeypatch.setattr(cli_module, "run_command", mock_run_command)

        result = cli_module.check_claude_config_only()

        assert result.healthy is False
        assert result.configured is False

    def test_mcp_connected(self, cli_module, monkeypatch):
        """Test behavior when MCP is configured and connected."""
        import shutil

        def mock_which(cmd):
            if cmd in ["claude", "python3"]:
                return f"/usr/bin/{cmd}"
            return None

        monkeypatch.setattr(shutil, "which", mock_which)

        # Mock run_command for successful config check
        def mock_run_command(cmd, timeout=10.0):
            if "mcp" in cmd and "get" in cmd:
                return 0, """spellbook:
  Scope: Local config
  Status: ✓ Connected
  Type: stdio
  Command: python3
  Args: /path/to/server.py""", ""
            if "pgrep" in cmd:
                return 0, "12345", ""
            return 0, "", ""

        monkeypatch.setattr(cli_module, "run_command", mock_run_command)

        # Mock Path.exists to return True for server script
        original_exists = Path.exists

        def mock_exists(self):
            if "server.py" in str(self):
                return True
            return original_exists(self)

        monkeypatch.setattr(Path, "exists", mock_exists)

        result = cli_module.check_claude_config_only()

        assert result.healthy is True
        assert result.configured is True
        assert result.connected is True


class TestWaitForHealth:
    """Tests for the wait_for_health function with exponential backoff."""

    @pytest.fixture
    def cli_module(self):
        """Load the CLI module for testing."""
        import importlib.util
        scripts_dir = Path(__file__).parent.parent.parent / "scripts"
        spec = importlib.util.spec_from_file_location(
            "mcp_health_check",
            str(scripts_dir / "mcp-health-check.py")
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_returns_immediately_when_healthy(self, monkeypatch, cli_module):
        """Test that wait returns immediately when server is healthy."""
        healthy_result = cli_module.HealthCheckResult(
            healthy=True,
            platform="claude",
            connected=True,
        )

        monkeypatch.setattr(
            cli_module,
            "check_claude_mcp",
            lambda verbose=False: healthy_result
        )

        start = time.time()
        result = cli_module.wait_for_health(platform="claude", timeout=5.0)
        elapsed = time.time() - start

        assert result.healthy is True
        assert elapsed < 1.0  # Should be nearly instant

    def test_retries_on_failure(self, monkeypatch, cli_module):
        """Test that wait retries when health check fails."""
        call_count = 0
        healthy_result = cli_module.HealthCheckResult(
            healthy=True,
            platform="claude",
        )
        unhealthy_result = cli_module.HealthCheckResult(
            healthy=False,
            platform="claude",
            error="Not ready",
        )

        def mock_check(verbose=False):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return unhealthy_result
            return healthy_result

        monkeypatch.setattr(cli_module, "check_claude_mcp", mock_check)

        result = cli_module.wait_for_health(
            platform="claude",
            timeout=10.0,
            initial_delay=0.1,
            max_delay=0.2
        )

        assert result.healthy is True
        assert call_count == 3

    def test_timeout_when_never_healthy(self, monkeypatch, cli_module):
        """Test that timeout is handled when server never becomes healthy."""
        unhealthy_result = cli_module.HealthCheckResult(
            healthy=False,
            platform="claude",
            error="Not ready",
        )

        monkeypatch.setattr(
            cli_module,
            "check_claude_mcp",
            lambda verbose=False: unhealthy_result
        )

        result = cli_module.wait_for_health(
            platform="claude",
            timeout=0.5,
            initial_delay=0.1,
            max_delay=0.2
        )

        assert result.healthy is False
        assert "Timeout" in result.error

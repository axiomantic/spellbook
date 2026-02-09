"""Tests for MCP health check tool and CLI script."""

import json
import os
import pytest
import time
from pathlib import Path
from unittest.mock import patch, MagicMock


@pytest.fixture
def reset_health_check_state():
    """Reset health check global state before each test."""
    from spellbook_mcp import server

    # Save original state
    original_first_done = server._first_health_check_done
    original_last_full = server._last_full_health_check_time

    # Reset to initial state
    server._first_health_check_done = False
    server._last_full_health_check_time = 0.0

    yield

    # Restore original state
    server._first_health_check_done = original_first_done
    server._last_full_health_check_time = original_last_full


@pytest.fixture
def simulate_not_first_call():
    """Simulate that first health check has already been done."""
    from spellbook_mcp import server

    # Save original state
    original_first_done = server._first_health_check_done
    original_last_full = server._last_full_health_check_time

    # Set state as if first call already happened
    server._first_health_check_done = True
    server._last_full_health_check_time = time.time()

    yield

    # Restore original state
    server._first_health_check_done = original_first_done
    server._last_full_health_check_time = original_last_full


class TestHealthCheckMCPTool:
    """Tests for the spellbook_health_check MCP tool."""

    def test_returns_healthy_status(self):
        """Test that health check returns healthy status."""
        from spellbook_mcp import server

        result = server.spellbook_health_check.fn()

        assert result["status"] == "healthy"

    def test_returns_unhealthy_when_database_missing(self, tmp_path, monkeypatch):
        """MCP tool returns unhealthy when database is missing."""
        from spellbook_mcp import server

        # Point to nonexistent database
        monkeypatch.setattr(
            "spellbook_mcp.server.get_db_path",
            lambda: str(tmp_path / "nonexistent.db")
        )
        # Setup valid directories to isolate database failure
        config_dir = tmp_path / "config"
        data_dir = tmp_path / "data"
        skills_dir = tmp_path / "skills"
        config_dir.mkdir()
        data_dir.mkdir()
        skills_dir.mkdir()
        monkeypatch.setenv("SPELLBOOK_CONFIG_DIR", str(config_dir))
        monkeypatch.setenv("SPELLBOOK_DATA_DIR", str(data_dir))
        monkeypatch.setenv("SPELLBOOK_DIR", str(skills_dir.parent))

        result = server.spellbook_health_check.fn()

        assert result["status"] == "unhealthy"
        assert "domains" in result
        assert "database" in result["domains"]
        assert result["domains"]["database"]["status"] == "unhealthy"

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


class TestHealthCheckFullMode:
    """Tests for the full parameter in spellbook_health_check."""

    def test_quick_mode_returns_only_critical_domains(
        self, tmp_path, monkeypatch, simulate_not_first_call
    ):
        """Quick mode (full=False) only checks database and filesystem.

        Note: Uses simulate_not_first_call fixture because first call is always full.
        """
        from spellbook_mcp import server
        from spellbook_mcp.db import init_db

        # Setup directories
        config_dir = tmp_path / "config"
        data_dir = tmp_path / "data"
        skills_dir = tmp_path / "skills"
        config_dir.mkdir()
        data_dir.mkdir()
        skills_dir.mkdir()

        # Setup database
        db_path = tmp_path / "test.db"
        init_db(str(db_path))

        # Patch get_db_path and directory paths
        monkeypatch.setattr(
            "spellbook_mcp.server.get_db_path", lambda: str(db_path)
        )
        monkeypatch.setenv("SPELLBOOK_CONFIG_DIR", str(config_dir))
        monkeypatch.setenv("SPELLBOOK_DATA_DIR", str(data_dir))
        monkeypatch.setenv("SPELLBOOK_DIR", str(skills_dir.parent))

        result = server.spellbook_health_check.fn(full=False)

        # Quick mode should have domains
        assert "domains" in result
        assert result["check_mode"] == "quick"
        domains = result["domains"]
        assert "database" in domains
        assert "filesystem" in domains
        # Quick mode should NOT include optional domains
        assert "watcher" not in domains
        assert "github_cli" not in domains

    def test_full_mode_returns_all_domains(self, tmp_path, monkeypatch):
        """Full mode (full=True) checks all 6 domains."""
        from spellbook_mcp import server
        from spellbook_mcp.db import init_db
        from spellbook_mcp.preferences import CoordinationConfig, CoordinationBackend
        import subprocess

        # Setup directories
        config_dir = tmp_path / "config"
        data_dir = tmp_path / "data"
        skills_dir = tmp_path / "skills"
        config_dir.mkdir()
        data_dir.mkdir()
        skills_dir.mkdir()

        # Create a valid skill
        skill = skills_dir / "test-skill"
        skill.mkdir()
        (skill / "SKILL.md").write_text("# Test Skill")

        # Setup database
        db_path = tmp_path / "test.db"
        init_db(str(db_path))

        # Patch paths
        monkeypatch.setattr(
            "spellbook_mcp.server.get_db_path", lambda: str(db_path)
        )
        monkeypatch.setenv("SPELLBOOK_CONFIG_DIR", str(config_dir))
        monkeypatch.setenv("SPELLBOOK_DATA_DIR", str(data_dir))
        monkeypatch.setenv("SPELLBOOK_DIR", str(skills_dir.parent))

        # Mock gh CLI as unavailable
        def mock_run(cmd, *args, **kwargs):
            raise FileNotFoundError()

        monkeypatch.setattr(subprocess, "run", mock_run)

        # Mock coordination config
        def mock_load():
            return CoordinationConfig(backend=CoordinationBackend.NONE)

        monkeypatch.setattr(
            "spellbook_mcp.health.load_coordination_config", mock_load
        )

        result = server.spellbook_health_check.fn(full=True)

        # Full mode should check all domains
        assert "domains" in result
        domains = result["domains"]
        assert "database" in domains
        assert "filesystem" in domains
        assert "watcher" in domains
        assert "github_cli" in domains
        assert "coordination" in domains
        assert "skills" in domains

    def test_first_call_is_full_mode(self, tmp_path, monkeypatch, reset_health_check_state):
        """First call after server start is automatically full mode."""
        from spellbook_mcp import server
        from spellbook_mcp.db import init_db
        from spellbook_mcp.preferences import CoordinationConfig, CoordinationBackend
        import subprocess

        # Setup directories
        config_dir = tmp_path / "config"
        data_dir = tmp_path / "data"
        skills_dir = tmp_path / "skills"
        config_dir.mkdir()
        data_dir.mkdir()
        skills_dir.mkdir()

        # Create a valid skill
        skill = skills_dir / "test-skill"
        skill.mkdir()
        (skill / "SKILL.md").write_text("# Test Skill")

        # Setup database
        db_path = tmp_path / "test.db"
        init_db(str(db_path))

        # Patch paths
        monkeypatch.setattr(
            "spellbook_mcp.server.get_db_path", lambda: str(db_path)
        )
        monkeypatch.setenv("SPELLBOOK_CONFIG_DIR", str(config_dir))
        monkeypatch.setenv("SPELLBOOK_DATA_DIR", str(data_dir))
        monkeypatch.setenv("SPELLBOOK_DIR", str(skills_dir.parent))

        # Mock gh to avoid actual CLI calls
        mock_gh_result = MagicMock()
        mock_gh_result.stdout = "gh version 2.45.0 (2024-01-01)"
        mock_gh_result.returncode = 0
        monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: mock_gh_result)

        # Mock coordination config
        mock_config = CoordinationConfig(backend=CoordinationBackend.NONE)
        mock_load = MagicMock(return_value=mock_config)
        monkeypatch.setattr(
            "spellbook_mcp.health.load_coordination_config", mock_load
        )

        # Call without full parameter - first call should be full
        result = server.spellbook_health_check.fn()

        # First call should be full mode (all domains)
        assert "domains" in result
        assert result["check_mode"] == "full_first_call"
        domains = result["domains"]
        assert "database" in domains
        assert "filesystem" in domains
        assert "watcher" in domains
        assert "github_cli" in domains

    def test_subsequent_calls_are_quick_mode(
        self, tmp_path, monkeypatch, simulate_not_first_call
    ):
        """Subsequent calls (after first) default to quick mode."""
        from spellbook_mcp import server
        from spellbook_mcp.db import init_db

        # Setup directories
        config_dir = tmp_path / "config"
        data_dir = tmp_path / "data"
        skills_dir = tmp_path / "skills"
        config_dir.mkdir()
        data_dir.mkdir()
        skills_dir.mkdir()

        # Setup database
        db_path = tmp_path / "test.db"
        init_db(str(db_path))

        # Patch paths
        monkeypatch.setattr(
            "spellbook_mcp.server.get_db_path", lambda: str(db_path)
        )
        monkeypatch.setenv("SPELLBOOK_CONFIG_DIR", str(config_dir))
        monkeypatch.setenv("SPELLBOOK_DATA_DIR", str(data_dir))
        monkeypatch.setenv("SPELLBOOK_DIR", str(skills_dir.parent))

        # Call without full parameter - should be quick since not first call
        result = server.spellbook_health_check.fn()

        # Should be quick mode (only critical domains)
        assert "domains" in result
        assert result["check_mode"] == "quick"
        domains = result["domains"]
        assert "database" in domains
        assert "filesystem" in domains
        assert "watcher" not in domains

    def test_periodic_full_check_after_interval(self, tmp_path, monkeypatch):
        """Full check triggers automatically after interval expires."""
        from spellbook_mcp import server
        from spellbook_mcp.db import init_db
        from spellbook_mcp.preferences import CoordinationConfig, CoordinationBackend
        import subprocess

        # Setup directories
        config_dir = tmp_path / "config"
        data_dir = tmp_path / "data"
        skills_dir = tmp_path / "skills"
        config_dir.mkdir()
        data_dir.mkdir()
        skills_dir.mkdir()

        # Create a valid skill
        skill = skills_dir / "test-skill"
        skill.mkdir()
        (skill / "SKILL.md").write_text("# Test Skill")

        # Setup database
        db_path = tmp_path / "test.db"
        init_db(str(db_path))

        # Patch paths
        monkeypatch.setattr(
            "spellbook_mcp.server.get_db_path", lambda: str(db_path)
        )
        monkeypatch.setenv("SPELLBOOK_CONFIG_DIR", str(config_dir))
        monkeypatch.setenv("SPELLBOOK_DATA_DIR", str(data_dir))
        monkeypatch.setenv("SPELLBOOK_DIR", str(skills_dir.parent))

        # Mock gh to avoid actual CLI calls
        mock_gh_result = MagicMock()
        mock_gh_result.stdout = "gh version 2.45.0 (2024-01-01)"
        mock_gh_result.returncode = 0
        monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: mock_gh_result)

        # Mock coordination config
        mock_config = CoordinationConfig(backend=CoordinationBackend.NONE)
        mock_load = MagicMock(return_value=mock_config)
        monkeypatch.setattr(
            "spellbook_mcp.health.load_coordination_config", mock_load
        )

        # Simulate first call already done, but interval has expired
        server._first_health_check_done = True
        server._last_full_health_check_time = (
            time.time() - server.FULL_HEALTH_CHECK_INTERVAL_SECONDS - 1
        )

        try:
            # Call without full parameter - should be full due to interval
            result = server.spellbook_health_check.fn()

            # Should be periodic full mode (all domains)
            assert "domains" in result
            assert result["check_mode"] == "full_periodic"
            domains = result["domains"]
            assert "database" in domains
            assert "filesystem" in domains
            assert "watcher" in domains
            assert "github_cli" in domains
        finally:
            # Reset state
            server._first_health_check_done = False
            server._last_full_health_check_time = 0.0

    def test_returns_checked_at_timestamp(self, tmp_path, monkeypatch):
        """Health check returns ISO timestamp in checked_at field."""
        from spellbook_mcp import server
        from spellbook_mcp.db import init_db
        from datetime import datetime

        # Setup directories
        config_dir = tmp_path / "config"
        data_dir = tmp_path / "data"
        skills_dir = tmp_path / "skills"
        config_dir.mkdir()
        data_dir.mkdir()
        skills_dir.mkdir()

        # Setup database
        db_path = tmp_path / "test.db"
        init_db(str(db_path))

        # Patch paths
        monkeypatch.setattr(
            "spellbook_mcp.server.get_db_path", lambda: str(db_path)
        )
        monkeypatch.setenv("SPELLBOOK_CONFIG_DIR", str(config_dir))
        monkeypatch.setenv("SPELLBOOK_DATA_DIR", str(data_dir))
        monkeypatch.setenv("SPELLBOOK_DIR", str(skills_dir.parent))

        result = server.spellbook_health_check.fn()

        assert "checked_at" in result
        # Should be parseable as ISO datetime
        parsed = datetime.fromisoformat(result["checked_at"].replace("Z", "+00:00"))
        assert parsed is not None


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

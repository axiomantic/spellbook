"""Tests for comprehensive health check module."""

import pytest


class TestHealthStatusEnum:
    """Test HealthStatus enum definition."""

    def test_healthy_status_exists(self):
        """HealthStatus.HEALTHY should exist with value 'healthy'."""
        from spellbook_mcp.health import HealthStatus

        assert HealthStatus.HEALTHY.value == "healthy"

    def test_degraded_status_exists(self):
        """HealthStatus.DEGRADED should exist with value 'degraded'."""
        from spellbook_mcp.health import HealthStatus

        assert HealthStatus.DEGRADED.value == "degraded"

    def test_unhealthy_status_exists(self):
        """HealthStatus.UNHEALTHY should exist with value 'unhealthy'."""
        from spellbook_mcp.health import HealthStatus

        assert HealthStatus.UNHEALTHY.value == "unhealthy"

    def test_unavailable_status_exists(self):
        """HealthStatus.UNAVAILABLE should exist with value 'unavailable'."""
        from spellbook_mcp.health import HealthStatus

        assert HealthStatus.UNAVAILABLE.value == "unavailable"

    def test_not_configured_status_exists(self):
        """HealthStatus.NOT_CONFIGURED should exist with value 'not_configured'."""
        from spellbook_mcp.health import HealthStatus

        assert HealthStatus.NOT_CONFIGURED.value == "not_configured"

    def test_status_is_str_enum(self):
        """HealthStatus should be a string enum for JSON serialization."""
        from spellbook_mcp.health import HealthStatus

        # Should be usable as string directly
        assert str(HealthStatus.HEALTHY) == "HealthStatus.HEALTHY"
        assert HealthStatus.HEALTHY == "healthy"


class TestDomainCheckDataclass:
    """Test DomainCheck dataclass definition."""

    def test_domain_check_creation(self):
        """DomainCheck should be creatable with required fields."""
        from spellbook_mcp.health import DomainCheck, HealthStatus

        check = DomainCheck(
            domain="database",
            status=HealthStatus.HEALTHY,
            message="All good"
        )

        assert check.domain == "database"
        assert check.status == HealthStatus.HEALTHY
        assert check.message == "All good"
        assert check.latency_ms is None
        assert check.details is None

    def test_domain_check_with_optional_fields(self):
        """DomainCheck should accept optional latency_ms and details."""
        from spellbook_mcp.health import DomainCheck, HealthStatus

        check = DomainCheck(
            domain="database",
            status=HealthStatus.HEALTHY,
            message="All good",
            latency_ms=1.5,
            details={"path": "/tmp/test.db", "tables": 5}
        )

        assert check.latency_ms == 1.5
        assert check.details == {"path": "/tmp/test.db", "tables": 5}


class TestHealthCheckResultDataclass:
    """Test HealthCheckResult dataclass definition."""

    def test_health_check_result_creation(self):
        """HealthCheckResult should be creatable with required fields."""
        from spellbook_mcp.health import HealthCheckResult, HealthStatus

        result = HealthCheckResult(
            status=HealthStatus.HEALTHY,
            version="0.9.6",
            uptime_seconds=123.4,
            tools_available=["tool1", "tool2"]
        )

        assert result.status == HealthStatus.HEALTHY
        assert result.version == "0.9.6"
        assert result.uptime_seconds == 123.4
        assert result.tools_available == ["tool1", "tool2"]
        assert result.domains is None
        assert result.checked_at is None

    def test_health_check_result_with_domains(self):
        """HealthCheckResult should accept optional domains dict."""
        from spellbook_mcp.health import HealthCheckResult, HealthStatus, DomainCheck

        db_check = DomainCheck(
            domain="database",
            status=HealthStatus.HEALTHY,
            message="OK"
        )

        result = HealthCheckResult(
            status=HealthStatus.HEALTHY,
            version="0.9.6",
            uptime_seconds=123.4,
            tools_available=[],
            domains={"database": db_check},
            checked_at="2026-02-08T12:00:00Z"
        )

        assert result.domains is not None
        assert "database" in result.domains
        assert result.checked_at == "2026-02-08T12:00:00Z"


class TestHelperFunctions:
    """Test helper functions for health checks."""

    def test_parse_version_part_simple_number(self):
        """_parse_version_part should extract integer from simple number."""
        from spellbook_mcp.health import _parse_version_part

        assert _parse_version_part("0") == 0
        assert _parse_version_part("30") == 30
        assert _parse_version_part("123") == 123

    def test_parse_version_part_with_suffix(self):
        """_parse_version_part should strip non-numeric suffixes."""
        from spellbook_mcp.health import _parse_version_part

        assert _parse_version_part("0-beta") == 0
        assert _parse_version_part("30-rc1") == 30
        assert _parse_version_part("123abc") == 123
        assert _parse_version_part("5.alpha") == 5

    def test_parse_version_part_empty_string(self):
        """_parse_version_part should return 0 for empty string."""
        from spellbook_mcp.health import _parse_version_part

        assert _parse_version_part("") == 0

    def test_parse_version_part_non_numeric(self):
        """_parse_version_part should return 0 for non-numeric input."""
        from spellbook_mcp.health import _parse_version_part

        assert _parse_version_part("beta") == 0
        assert _parse_version_part("abc") == 0

    def test_parse_gh_version_valid(self):
        """_parse_gh_version should extract version from gh --version output."""
        from spellbook_mcp.health import _parse_gh_version

        output = "gh version 2.45.0 (2024-01-15)\nhttps://github.com/cli/cli/releases/tag/v2.45.0"
        assert _parse_gh_version(output) == "2.45.0"

    def test_parse_gh_version_minimal(self):
        """_parse_gh_version should work with minimal output."""
        from spellbook_mcp.health import _parse_gh_version

        output = "gh version 2.30.0"
        assert _parse_gh_version(output) == "2.30.0"

    def test_parse_gh_version_invalid(self):
        """_parse_gh_version should return None for invalid output."""
        from spellbook_mcp.health import _parse_gh_version

        assert _parse_gh_version("not a version") is None
        assert _parse_gh_version("") is None

    def test_compare_versions_equal(self):
        """_compare_versions should return 0 for equal versions."""
        from spellbook_mcp.health import _compare_versions

        assert _compare_versions("2.30.0", "2.30.0") == 0

    def test_compare_versions_less(self):
        """_compare_versions should return -1 when v1 < v2."""
        from spellbook_mcp.health import _compare_versions

        assert _compare_versions("2.29.0", "2.30.0") == -1
        assert _compare_versions("2.30.0", "2.30.1") == -1
        assert _compare_versions("1.0.0", "2.0.0") == -1

    def test_compare_versions_greater(self):
        """_compare_versions should return 1 when v1 > v2."""
        from spellbook_mcp.health import _compare_versions

        assert _compare_versions("2.31.0", "2.30.0") == 1
        assert _compare_versions("2.30.1", "2.30.0") == 1
        assert _compare_versions("3.0.0", "2.99.99") == 1

    def test_get_heartbeat_age_no_heartbeat(self, tmp_path):
        """_get_heartbeat_age should return None when no heartbeat exists."""
        from spellbook_mcp.health import _get_heartbeat_age
        from spellbook_mcp.db import init_db

        db_path = tmp_path / "test.db"
        init_db(str(db_path))

        age = _get_heartbeat_age(str(db_path))
        assert age is None

    def test_get_heartbeat_age_with_heartbeat(self, tmp_path):
        """_get_heartbeat_age should return seconds since heartbeat."""
        from spellbook_mcp.health import _get_heartbeat_age
        from spellbook_mcp.db import init_db, get_connection
        from datetime import datetime, timedelta, timezone

        db_path = tmp_path / "test.db"
        init_db(str(db_path))

        # Insert a heartbeat 5 seconds ago (UTC-aware)
        conn = get_connection(str(db_path))
        past_time = (datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat()
        conn.execute(
            "INSERT OR REPLACE INTO heartbeat (id, timestamp) VALUES (1, ?)",
            (past_time,)
        )
        conn.commit()

        age = _get_heartbeat_age(str(db_path))
        assert age is not None
        assert 4.0 < age < 10.0  # Allow some tolerance


class TestDatabaseCheck:
    """Test database domain health check."""

    def test_healthy_database(self, tmp_path):
        """Database with valid schema returns HEALTHY."""
        from spellbook_mcp.health import _check_database, HealthStatus
        from spellbook_mcp.db import init_db

        db_path = tmp_path / "test.db"
        init_db(str(db_path))

        result = _check_database(str(db_path))

        assert result.domain == "database"
        assert result.status == HealthStatus.HEALTHY
        assert result.latency_ms is not None
        assert result.latency_ms >= 0
        assert "path" in result.details
        assert "tables" in result.details
        # Verify table count is positive (schema was actually created)
        assert result.details["tables"] > 0

    def test_missing_database(self, tmp_path):
        """Missing database file returns UNHEALTHY."""
        from spellbook_mcp.health import _check_database, HealthStatus

        db_path = tmp_path / "nonexistent.db"

        result = _check_database(str(db_path))

        assert result.status == HealthStatus.UNHEALTHY
        assert "not found" in result.message.lower() or "error" in result.message.lower()

    def test_database_query_execution(self, tmp_path):
        """Database check executes SELECT 1 successfully."""
        from spellbook_mcp.health import _check_database, HealthStatus
        from spellbook_mcp.db import init_db

        db_path = tmp_path / "test.db"
        init_db(str(db_path))

        result = _check_database(str(db_path))

        assert result.status == HealthStatus.HEALTHY
        # Should have verified query execution
        assert "valid" in result.message.lower() or "verified" in result.message.lower()
        # CONSUMPTION FIX: Verify latency_ms is present (proves query was timed)
        assert result.latency_ms is not None
        assert result.latency_ms >= 0  # Query took measurable time

    def test_database_query_fails_on_corrupt_db(self, tmp_path):
        """Database check returns UNHEALTHY when query fails on corrupt db."""
        from spellbook_mcp.health import _check_database, HealthStatus

        db_path = tmp_path / "corrupt.db"
        # Create a file that's not a valid SQLite database
        db_path.write_bytes(b"not a database")

        result = _check_database(str(db_path))

        assert result.status == HealthStatus.UNHEALTHY
        assert "error" in result.message.lower()

    def test_database_wal_mode_detection(self, tmp_path):
        """Database check detects WAL mode."""
        from spellbook_mcp.health import _check_database
        from spellbook_mcp.db import init_db

        db_path = tmp_path / "test.db"
        init_db(str(db_path))

        result = _check_database(str(db_path))

        assert "wal_mode" in result.details
        assert result.details["wal_mode"] is True

    def test_database_size_bytes(self, tmp_path):
        """Database check reports file size."""
        from spellbook_mcp.health import _check_database
        from spellbook_mcp.db import init_db

        db_path = tmp_path / "test.db"
        init_db(str(db_path))

        result = _check_database(str(db_path))

        assert "size_bytes" in result.details
        assert result.details["size_bytes"] > 0


class TestWatcherCheck:
    """Test watcher domain health check."""

    def test_fresh_heartbeat(self, tmp_path):
        """Fresh heartbeat returns HEALTHY."""
        from spellbook_mcp.health import _check_watcher, HealthStatus
        from spellbook_mcp.db import init_db, get_connection
        from datetime import datetime, timezone

        db_path = tmp_path / "test.db"
        init_db(str(db_path))

        # Insert fresh heartbeat (UTC-aware)
        conn = get_connection(str(db_path))
        conn.execute(
            "INSERT OR REPLACE INTO heartbeat (id, timestamp) VALUES (1, ?)",
            (datetime.now(timezone.utc).isoformat(),)
        )
        conn.commit()

        result = _check_watcher(str(db_path), server_uptime=60.0)

        assert result.domain == "watcher"
        assert result.status == HealthStatus.HEALTHY
        assert "fresh" in result.message.lower()
        # Verify heartbeat age is actually fresh (below 30s threshold)
        assert result.details["heartbeat_age_seconds"] is not None
        assert result.details["heartbeat_age_seconds"] < 30.0

    def test_stale_heartbeat(self, tmp_path):
        """Stale heartbeat (>30s) returns DEGRADED."""
        from spellbook_mcp.health import _check_watcher, HealthStatus
        from spellbook_mcp.db import init_db, get_connection
        from datetime import datetime, timedelta, timezone

        db_path = tmp_path / "test.db"
        init_db(str(db_path))

        # Insert stale heartbeat (45 seconds ago, UTC-aware)
        conn = get_connection(str(db_path))
        stale_time = (datetime.now(timezone.utc) - timedelta(seconds=45)).isoformat()
        conn.execute(
            "INSERT OR REPLACE INTO heartbeat (id, timestamp) VALUES (1, ?)",
            (stale_time,)
        )
        conn.commit()

        result = _check_watcher(str(db_path), server_uptime=60.0)

        assert result.status == HealthStatus.DEGRADED
        assert "stale" in result.message.lower()
        # Verify heartbeat age matches expected staleness (>30s threshold)
        assert result.details["heartbeat_age_seconds"] is not None
        assert result.details["heartbeat_age_seconds"] > 30.0

    def test_startup_grace_period(self, tmp_path):
        """Within grace period, missing heartbeat returns HEALTHY."""
        from spellbook_mcp.health import _check_watcher, HealthStatus
        from spellbook_mcp.db import init_db

        db_path = tmp_path / "test.db"
        init_db(str(db_path))

        # No heartbeat, but server just started (5 seconds uptime)
        result = _check_watcher(
            str(db_path),
            server_uptime=5.0,
            startup_grace_seconds=10.0
        )

        assert result.status == HealthStatus.HEALTHY
        assert result.details["in_grace_period"] is True

    def test_no_heartbeat_row_after_grace(self, tmp_path):
        """Missing heartbeat row after grace period returns DEGRADED."""
        from spellbook_mcp.health import _check_watcher, HealthStatus
        from spellbook_mcp.db import init_db

        db_path = tmp_path / "test.db"
        init_db(str(db_path))

        # No heartbeat, server running for 60 seconds
        result = _check_watcher(
            str(db_path),
            server_uptime=60.0,
            startup_grace_seconds=10.0
        )

        assert result.status == HealthStatus.DEGRADED
        assert result.details["heartbeat_age_seconds"] is None

    def test_heartbeat_age_in_details(self, tmp_path):
        """Heartbeat age should be in details."""
        from spellbook_mcp.health import _check_watcher
        from spellbook_mcp.db import init_db, get_connection
        from datetime import datetime, timedelta, timezone

        db_path = tmp_path / "test.db"
        init_db(str(db_path))

        # Insert heartbeat 10 seconds ago (UTC-aware)
        conn = get_connection(str(db_path))
        past_time = (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat()
        conn.execute(
            "INSERT OR REPLACE INTO heartbeat (id, timestamp) VALUES (1, ?)",
            (past_time,)
        )
        conn.commit()

        result = _check_watcher(str(db_path), server_uptime=60.0)

        assert "heartbeat_age_seconds" in result.details
        assert 8.0 < result.details["heartbeat_age_seconds"] < 15.0


class TestFilesystemCheck:
    """Test filesystem domain health check."""

    def test_all_directories_exist(self, tmp_path):
        """All directories accessible returns HEALTHY."""
        from spellbook_mcp.health import _check_filesystem, HealthStatus

        # Create all required directories
        config_dir = tmp_path / "config"
        data_dir = tmp_path / "data"
        skills_dir = tmp_path / "skills"
        config_dir.mkdir()
        data_dir.mkdir()
        skills_dir.mkdir()

        result = _check_filesystem(
            config_dir=str(config_dir),
            data_dir=str(data_dir),
            skills_dir=str(skills_dir),
        )

        assert result.domain == "filesystem"
        assert result.status == HealthStatus.HEALTHY
        assert result.details["config_dir"]["exists"] is True
        assert result.details["data_dir"]["exists"] is True
        assert result.details["skills_dir"]["exists"] is True

    def test_missing_config_dir(self, tmp_path):
        """Missing config directory returns UNHEALTHY."""
        from spellbook_mcp.health import _check_filesystem, HealthStatus

        data_dir = tmp_path / "data"
        skills_dir = tmp_path / "skills"
        data_dir.mkdir()
        skills_dir.mkdir()

        result = _check_filesystem(
            config_dir=str(tmp_path / "nonexistent"),
            data_dir=str(data_dir),
            skills_dir=str(skills_dir),
        )

        assert result.status == HealthStatus.UNHEALTHY
        assert result.details["config_dir"]["exists"] is False

    def test_missing_skills_dir(self, tmp_path):
        """Missing skills directory returns DEGRADED (optional)."""
        from spellbook_mcp.health import _check_filesystem, HealthStatus

        config_dir = tmp_path / "config"
        data_dir = tmp_path / "data"
        config_dir.mkdir()
        data_dir.mkdir()

        result = _check_filesystem(
            config_dir=str(config_dir),
            data_dir=str(data_dir),
            skills_dir=str(tmp_path / "nonexistent"),
        )

        # Skills dir is optional, so DEGRADED not UNHEALTHY
        assert result.status == HealthStatus.DEGRADED
        assert result.details["skills_dir"]["exists"] is False

    def test_readable_check(self, tmp_path):
        """Directories should be checked for readability."""
        from spellbook_mcp.health import _check_filesystem

        config_dir = tmp_path / "config"
        data_dir = tmp_path / "data"
        skills_dir = tmp_path / "skills"
        config_dir.mkdir()
        data_dir.mkdir()
        skills_dir.mkdir()

        result = _check_filesystem(
            config_dir=str(config_dir),
            data_dir=str(data_dir),
            skills_dir=str(skills_dir),
        )

        assert result.details["config_dir"]["readable"] is True
        assert result.details["data_dir"]["readable"] is True
        assert result.details["skills_dir"]["readable"] is True


import subprocess


class TestGitHubCLICheck:
    """Test GitHub CLI domain health check."""

    def test_gh_not_installed(self, monkeypatch):
        """Missing gh binary returns UNAVAILABLE."""
        from spellbook_mcp.health import _check_github_cli, HealthStatus

        def mock_run(*args, **kwargs):
            raise FileNotFoundError("gh not found")

        monkeypatch.setattr(subprocess, "run", mock_run)

        result = _check_github_cli()

        assert result.domain == "github_cli"
        assert result.status == HealthStatus.UNAVAILABLE
        assert result.details["installed"] is False

    def test_gh_timeout(self, monkeypatch):
        """Subprocess timeout returns DEGRADED."""
        from spellbook_mcp.health import _check_github_cli, HealthStatus

        def mock_run(*args, **kwargs):
            raise subprocess.TimeoutExpired(cmd="gh", timeout=2.0)

        monkeypatch.setattr(subprocess, "run", mock_run)

        result = _check_github_cli()

        assert result.status == HealthStatus.DEGRADED
        assert "timed out" in result.message.lower()

    def test_gh_version_too_old(self, monkeypatch):
        """Old gh version returns DEGRADED."""
        from spellbook_mcp.health import _check_github_cli, HealthStatus

        def mock_run(cmd, *args, **kwargs):
            if cmd[0] == "gh" and "--version" in cmd:
                result = subprocess.CompletedProcess(
                    cmd, 0, stdout="gh version 2.20.0 (2023-01-01)\n", stderr=""
                )
                return result
            raise FileNotFoundError()

        monkeypatch.setattr(subprocess, "run", mock_run)

        result = _check_github_cli()

        assert result.status == HealthStatus.DEGRADED
        assert result.details["version"] == "2.20.0"
        assert "upgrade" in result.message.lower() or "old" in result.message.lower()

    def test_gh_not_authenticated(self, monkeypatch):
        """Unauthenticated gh returns DEGRADED."""
        from spellbook_mcp.health import _check_github_cli, HealthStatus

        call_count = [0]

        def mock_run(cmd, *args, **kwargs):
            call_count[0] += 1
            if "--version" in cmd:
                return subprocess.CompletedProcess(
                    cmd, 0, stdout="gh version 2.45.0\n", stderr=""
                )
            if "auth" in cmd and "status" in cmd:
                return subprocess.CompletedProcess(
                    cmd, 1, stdout="", stderr="You are not logged into any GitHub hosts."
                )
            raise FileNotFoundError()

        monkeypatch.setattr(subprocess, "run", mock_run)

        result = _check_github_cli()

        assert result.status == HealthStatus.DEGRADED
        assert result.details["authenticated"] is False
        assert "auth" in result.message.lower()

    def test_gh_healthy(self, monkeypatch):
        """Installed, versioned, and authenticated gh returns HEALTHY."""
        from spellbook_mcp.health import _check_github_cli, HealthStatus

        def mock_run(cmd, *args, **kwargs):
            if "--version" in cmd:
                return subprocess.CompletedProcess(
                    cmd, 0, stdout="gh version 2.45.0 (2024-01-15)\n", stderr=""
                )
            if "auth" in cmd and "status" in cmd:
                return subprocess.CompletedProcess(
                    cmd, 0, stdout="Logged in to github.com\n", stderr=""
                )
            raise FileNotFoundError()

        monkeypatch.setattr(subprocess, "run", mock_run)

        result = _check_github_cli()

        assert result.status == HealthStatus.HEALTHY
        assert result.details["installed"] is True
        assert result.details["version"] == "2.45.0"
        assert result.details["authenticated"] is True


class TestCoordinationCheck:
    """Test coordination domain health check."""

    def test_coordination_not_configured(self, monkeypatch):
        """Backend == NONE returns NOT_CONFIGURED."""
        from spellbook_mcp.health import _check_coordination, HealthStatus
        from spellbook_mcp.preferences import CoordinationConfig, CoordinationBackend

        def mock_load():
            return CoordinationConfig(backend=CoordinationBackend.NONE)

        monkeypatch.setattr(
            "spellbook_mcp.health.load_coordination_config", mock_load
        )

        result = _check_coordination()

        assert result.domain == "coordination"
        assert result.status == HealthStatus.NOT_CONFIGURED
        assert result.details["backend"] == "none"
        assert result.details["configured"] is False

    def test_coordination_configured_mcp(self, monkeypatch):
        """MCP backend configured returns HEALTHY."""
        from spellbook_mcp.health import _check_coordination, HealthStatus
        from spellbook_mcp.preferences import (
            CoordinationConfig,
            CoordinationBackend,
            MCPSSEConfig,
        )

        def mock_load():
            return CoordinationConfig(
                backend=CoordinationBackend.MCP_STREAMABLE_HTTP,
                mcp_sse=MCPSSEConfig(port=3000, host="localhost"),
            )

        monkeypatch.setattr(
            "spellbook_mcp.health.load_coordination_config", mock_load
        )

        result = _check_coordination()

        assert result.status == HealthStatus.HEALTHY
        assert result.details["backend"] == "mcp-streamable-http"
        assert result.details["configured"] is True

    def test_coordination_config_error(self, monkeypatch):
        """Config load error returns DEGRADED."""
        from spellbook_mcp.health import _check_coordination, HealthStatus

        def mock_load():
            raise ValueError("Invalid config")

        monkeypatch.setattr(
            "spellbook_mcp.health.load_coordination_config", mock_load
        )

        result = _check_coordination()

        assert result.status == HealthStatus.DEGRADED
        assert "error" in result.details
        # Verify actual error message is captured
        assert "Invalid config" in result.details["error"]


class TestSkillsCheck:
    """Test skills domain health check."""

    def test_skills_dir_missing(self, tmp_path):
        """Missing skills directory returns UNAVAILABLE."""
        from spellbook_mcp.health import _check_skills, HealthStatus

        result = _check_skills(str(tmp_path / "nonexistent"))

        assert result.domain == "skills"
        assert result.status == HealthStatus.UNAVAILABLE

    def test_no_valid_skills(self, tmp_path):
        """Empty skills directory returns DEGRADED."""
        from spellbook_mcp.health import _check_skills, HealthStatus

        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        result = _check_skills(str(skills_dir))

        assert result.status == HealthStatus.DEGRADED
        assert result.details["valid_skills"] == 0

    def test_valid_skills_found(self, tmp_path):
        """Directory with valid skills returns HEALTHY."""
        from spellbook_mcp.health import _check_skills, HealthStatus

        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        # Create valid skill
        skill1 = skills_dir / "test-skill"
        skill1.mkdir()
        (skill1 / "SKILL.md").write_text("# Test Skill")

        result = _check_skills(str(skills_dir))

        assert result.status == HealthStatus.HEALTHY
        assert result.details["valid_skills"] == 1
        assert result.details["total_directories"] == 1

    def test_invalid_skill_detected(self, tmp_path):
        """Directory without SKILL.md is detected as invalid."""
        from spellbook_mcp.health import _check_skills, HealthStatus

        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        # Create valid skill
        valid_skill = skills_dir / "valid-skill"
        valid_skill.mkdir()
        (valid_skill / "SKILL.md").write_text("# Valid")

        # Create invalid skill (no SKILL.md)
        invalid_skill = skills_dir / "invalid-skill"
        invalid_skill.mkdir()

        result = _check_skills(str(skills_dir))

        # Still HEALTHY because at least one valid skill exists
        assert result.status == HealthStatus.HEALTHY
        assert result.details["valid_skills"] == 1
        assert result.details["total_directories"] == 2
        assert "invalid-skill" in result.details["invalid_skills"]

    def test_skills_count(self, tmp_path):
        """Multiple valid skills are counted correctly."""
        from spellbook_mcp.health import _check_skills

        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        # Create 3 valid skills
        for i in range(3):
            skill = skills_dir / f"skill-{i}"
            skill.mkdir()
            (skill / "SKILL.md").write_text(f"# Skill {i}")

        result = _check_skills(str(skills_dir))

        assert result.details["valid_skills"] == 3
        assert result.details["total_directories"] == 3
        assert result.details["invalid_skills"] == []


class TestStatusAggregation:
    """Test status aggregation logic."""

    def test_all_healthy(self):
        """All HEALTHY domains -> overall HEALTHY."""
        from spellbook_mcp.health import _aggregate_status, HealthStatus, DomainCheck

        domains = {
            "database": DomainCheck("database", HealthStatus.HEALTHY, "OK"),
            "filesystem": DomainCheck("filesystem", HealthStatus.HEALTHY, "OK"),
            "watcher": DomainCheck("watcher", HealthStatus.HEALTHY, "OK"),
        }

        assert _aggregate_status(domains) == HealthStatus.HEALTHY

    def test_critical_unhealthy(self):
        """Database UNHEALTHY -> overall UNHEALTHY."""
        from spellbook_mcp.health import _aggregate_status, HealthStatus, DomainCheck

        domains = {
            "database": DomainCheck("database", HealthStatus.UNHEALTHY, "Error"),
            "filesystem": DomainCheck("filesystem", HealthStatus.HEALTHY, "OK"),
            "watcher": DomainCheck("watcher", HealthStatus.HEALTHY, "OK"),
        }

        assert _aggregate_status(domains) == HealthStatus.UNHEALTHY

    def test_filesystem_unhealthy(self):
        """Filesystem UNHEALTHY -> overall UNHEALTHY."""
        from spellbook_mcp.health import _aggregate_status, HealthStatus, DomainCheck

        domains = {
            "database": DomainCheck("database", HealthStatus.HEALTHY, "OK"),
            "filesystem": DomainCheck("filesystem", HealthStatus.UNHEALTHY, "Error"),
            "watcher": DomainCheck("watcher", HealthStatus.HEALTHY, "OK"),
        }

        assert _aggregate_status(domains) == HealthStatus.UNHEALTHY

    def test_optional_unhealthy(self):
        """Watcher UNHEALTHY -> overall DEGRADED (not UNHEALTHY)."""
        from spellbook_mcp.health import _aggregate_status, HealthStatus, DomainCheck

        domains = {
            "database": DomainCheck("database", HealthStatus.HEALTHY, "OK"),
            "filesystem": DomainCheck("filesystem", HealthStatus.HEALTHY, "OK"),
            "watcher": DomainCheck("watcher", HealthStatus.UNHEALTHY, "Error"),
        }

        assert _aggregate_status(domains) == HealthStatus.DEGRADED

    def test_any_degraded(self):
        """Any DEGRADED domain -> overall DEGRADED."""
        from spellbook_mcp.health import _aggregate_status, HealthStatus, DomainCheck

        domains = {
            "database": DomainCheck("database", HealthStatus.HEALTHY, "OK"),
            "filesystem": DomainCheck("filesystem", HealthStatus.HEALTHY, "OK"),
            "watcher": DomainCheck("watcher", HealthStatus.DEGRADED, "Stale"),
        }

        assert _aggregate_status(domains) == HealthStatus.DEGRADED

    def test_unavailable_ignored(self):
        """UNAVAILABLE domains don't affect status."""
        from spellbook_mcp.health import _aggregate_status, HealthStatus, DomainCheck

        domains = {
            "database": DomainCheck("database", HealthStatus.HEALTHY, "OK"),
            "filesystem": DomainCheck("filesystem", HealthStatus.HEALTHY, "OK"),
            "github_cli": DomainCheck("github_cli", HealthStatus.UNAVAILABLE, "Not installed"),
        }

        assert _aggregate_status(domains) == HealthStatus.HEALTHY

    def test_not_configured_ignored(self):
        """NOT_CONFIGURED domains don't affect status."""
        from spellbook_mcp.health import _aggregate_status, HealthStatus, DomainCheck

        domains = {
            "database": DomainCheck("database", HealthStatus.HEALTHY, "OK"),
            "filesystem": DomainCheck("filesystem", HealthStatus.HEALTHY, "OK"),
            "coordination": DomainCheck("coordination", HealthStatus.NOT_CONFIGURED, "Disabled"),
        }

        assert _aggregate_status(domains) == HealthStatus.HEALTHY

    def test_critical_takes_precedence(self):
        """Critical UNHEALTHY takes precedence over optional DEGRADED."""
        from spellbook_mcp.health import _aggregate_status, HealthStatus, DomainCheck

        domains = {
            "database": DomainCheck("database", HealthStatus.UNHEALTHY, "Error"),
            "filesystem": DomainCheck("filesystem", HealthStatus.HEALTHY, "OK"),
            "watcher": DomainCheck("watcher", HealthStatus.DEGRADED, "Stale"),
        }

        assert _aggregate_status(domains) == HealthStatus.UNHEALTHY


class TestRunHealthCheck:
    """Test run_health_check orchestration function."""

    def test_run_health_check_quick_mode(self, tmp_path, monkeypatch):
        """Quick mode only checks database and filesystem (critical domains)."""
        from spellbook_mcp.health import run_health_check, HealthStatus
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

        result = run_health_check(
            db_path=str(db_path),
            config_dir=str(config_dir),
            data_dir=str(data_dir),
            skills_dir=str(skills_dir),
            server_uptime=60.0,
            version="0.9.6",
            tools_available=["tool1", "tool2"],
            quick=True,
        )

        # Quick mode should only check database and filesystem
        assert result.status == HealthStatus.HEALTHY
        assert result.domains is not None
        assert "database" in result.domains
        assert "filesystem" in result.domains
        # Quick mode should NOT include optional domains
        assert "watcher" not in result.domains
        assert "github_cli" not in result.domains
        assert "coordination" not in result.domains
        assert "skills" not in result.domains

    def test_run_health_check_full_mode(self, tmp_path, monkeypatch):
        """Full mode checks all 6 domains."""
        from spellbook_mcp.health import run_health_check, HealthStatus
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

        # Mock gh CLI
        def mock_run(cmd, *args, **kwargs):
            if "--version" in cmd:
                return subprocess.CompletedProcess(
                    cmd, 0, stdout="gh version 2.45.0\n", stderr=""
                )
            if "auth" in cmd and "status" in cmd:
                return subprocess.CompletedProcess(
                    cmd, 0, stdout="Logged in\n", stderr=""
                )
            raise FileNotFoundError()

        monkeypatch.setattr(subprocess, "run", mock_run)

        # Mock coordination config
        def mock_load():
            return CoordinationConfig(backend=CoordinationBackend.NONE)

        monkeypatch.setattr(
            "spellbook_mcp.health.load_coordination_config", mock_load
        )

        result = run_health_check(
            db_path=str(db_path),
            config_dir=str(config_dir),
            data_dir=str(data_dir),
            skills_dir=str(skills_dir),
            server_uptime=60.0,
            version="0.9.6",
            tools_available=["tool1"],
            quick=False,
        )

        # Full mode should check all 6 domains
        assert result.domains is not None
        assert "database" in result.domains
        assert "filesystem" in result.domains
        assert "watcher" in result.domains
        assert "github_cli" in result.domains
        assert "coordination" in result.domains
        assert "skills" in result.domains

    def test_run_health_check_returns_health_check_result(self, tmp_path):
        """run_health_check returns HealthCheckResult dataclass."""
        from spellbook_mcp.health import run_health_check, HealthCheckResult
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

        result = run_health_check(
            db_path=str(db_path),
            config_dir=str(config_dir),
            data_dir=str(data_dir),
            skills_dir=str(skills_dir),
            server_uptime=123.4,
            version="1.0.0",
            tools_available=["a", "b", "c"],
            quick=True,
        )

        assert isinstance(result, HealthCheckResult)
        assert result.version == "1.0.0"
        assert result.uptime_seconds == 123.4
        assert result.tools_available == ["a", "b", "c"]
        assert result.checked_at is not None

    def test_run_health_check_aggregates_status(self, tmp_path):
        """run_health_check uses _aggregate_status for overall status."""
        from spellbook_mcp.health import run_health_check, HealthStatus
        from spellbook_mcp.db import init_db

        # Setup directories - missing config_dir to trigger UNHEALTHY
        data_dir = tmp_path / "data"
        skills_dir = tmp_path / "skills"
        data_dir.mkdir()
        skills_dir.mkdir()

        # Setup database
        db_path = tmp_path / "test.db"
        init_db(str(db_path))

        result = run_health_check(
            db_path=str(db_path),
            config_dir=str(tmp_path / "nonexistent"),  # Missing!
            data_dir=str(data_dir),
            skills_dir=str(skills_dir),
            server_uptime=60.0,
            version="0.9.6",
            tools_available=[],
            quick=True,
        )

        # Filesystem is critical, missing config_dir -> UNHEALTHY
        assert result.status == HealthStatus.UNHEALTHY

    def test_run_health_check_checked_at_is_iso_format(self, tmp_path):
        """checked_at should be ISO 8601 format."""
        from spellbook_mcp.health import run_health_check
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

        result = run_health_check(
            db_path=str(db_path),
            config_dir=str(config_dir),
            data_dir=str(data_dir),
            skills_dir=str(skills_dir),
            server_uptime=60.0,
            version="0.9.6",
            tools_available=[],
            quick=True,
        )

        # Should be parseable as ISO datetime
        parsed = datetime.fromisoformat(result.checked_at.replace("Z", "+00:00"))
        assert parsed is not None

    def test_run_health_check_default_is_full(self, tmp_path):
        """quick parameter defaults to False (full check)."""
        from spellbook_mcp.health import run_health_check
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

        # Mock gh CLI as unavailable
        def mock_run(cmd, *args, **kwargs):
            raise FileNotFoundError()

        # Need to patch at module level
        import spellbook_mcp.health
        original_run = subprocess.run

        def patched_run(*args, **kwargs):
            if args and args[0] and args[0][0] == "gh":
                raise FileNotFoundError()
            return original_run(*args, **kwargs)

        # Mock coordination config
        def mock_load():
            return CoordinationConfig(backend=CoordinationBackend.NONE)

        import spellbook_mcp.health as health_module
        original_load = health_module.load_coordination_config
        health_module.load_coordination_config = mock_load

        try:
            # Patch subprocess.run for gh check
            subprocess.run = patched_run

            # Call without quick parameter - should default to False (full mode)
            result = run_health_check(
                db_path=str(db_path),
                config_dir=str(config_dir),
                data_dir=str(data_dir),
                skills_dir=str(skills_dir),
                server_uptime=60.0,
                version="0.9.6",
                tools_available=[],
            )

            # Full mode includes all domains
            assert result.domains is not None
            assert "watcher" in result.domains
            assert "skills" in result.domains
        finally:
            subprocess.run = original_run
            health_module.load_coordination_config = original_load
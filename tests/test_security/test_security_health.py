"""Tests for security health check domain.

Validates:
- check_security_domain() returns correct DomainCheck for each status
- "healthy": all tables exist, no CRITICAL events, canary registered + not triggered, rules loadable
- "degraded": tables exist, no CRITICAL events, but no canary tokens registered
- "unhealthy": tables exist, CRITICAL event in last 24h
- "unavailable": DB exists but no security tables
- security_version field present in check details
- Rules import check works
"""

import sqlite3

import pytest

from spellbook_mcp.db import close_all_connections, init_db
from spellbook_mcp.health import DomainCheck, HealthStatus


@pytest.fixture(autouse=True)
def _clean_connections():
    """Close cached DB connections after each test to avoid cross-contamination."""
    yield
    close_all_connections()


@pytest.fixture
def db_path(tmp_path):
    """Create and initialize a temporary database with all tables, return path as string."""
    path = str(tmp_path / "test.db")
    init_db(path)
    return path


@pytest.fixture
def db_path_no_security_tables(tmp_path):
    """Create a DB with some tables but WITHOUT security tables."""
    path = str(tmp_path / "nosec.db")
    conn = sqlite3.connect(path)
    # Create a non-security table so the DB file exists and is valid
    conn.execute("CREATE TABLE dummy (id INTEGER PRIMARY KEY)")
    conn.commit()
    conn.close()
    return path


def _insert_canary(db_path: str, triggered: bool = False) -> None:
    """Helper: insert a canary token into the database."""
    conn = sqlite3.connect(db_path)
    if triggered:
        conn.execute(
            "INSERT INTO canary_tokens (token, token_type, context, triggered_at, triggered_by) "
            "VALUES (?, ?, ?, datetime('now'), ?)",
            ("CANARY-test123-P", "prompt", "test canary", "test"),
        )
    else:
        conn.execute(
            "INSERT INTO canary_tokens (token, token_type, context) "
            "VALUES (?, ?, ?)",
            ("CANARY-test123-P", "prompt", "test canary"),
        )
    conn.commit()
    conn.close()


def _insert_critical_event(db_path: str) -> None:
    """Helper: insert a CRITICAL security event (recent, within last 24h)."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO security_events (event_type, severity, source, detail) "
        "VALUES (?, ?, ?, ?)",
        ("injection_detected", "CRITICAL", "test", "test critical event"),
    )
    conn.commit()
    conn.close()


# =============================================================================
# TestHealthyState
# =============================================================================


class TestHealthyState:
    """All tables exist, no CRITICAL events, canary registered + not triggered, rules loadable."""

    def test_returns_domain_check(self, db_path):
        from spellbook_mcp.health import check_security_domain

        result = check_security_domain(db_path=db_path)
        assert isinstance(result, DomainCheck)

    def test_domain_is_security(self, db_path):
        from spellbook_mcp.health import check_security_domain

        _insert_canary(db_path)
        result = check_security_domain(db_path=db_path)
        assert result.domain == "security"

    def test_status_is_healthy(self, db_path):
        from spellbook_mcp.health import check_security_domain

        _insert_canary(db_path)
        result = check_security_domain(db_path=db_path)
        assert result.status == HealthStatus.HEALTHY

    def test_message_indicates_healthy(self, db_path):
        from spellbook_mcp.health import check_security_domain

        _insert_canary(db_path)
        result = check_security_domain(db_path=db_path)
        assert result.message  # non-empty message

    def test_latency_is_set(self, db_path):
        from spellbook_mcp.health import check_security_domain

        _insert_canary(db_path)
        result = check_security_domain(db_path=db_path)
        assert result.latency_ms is not None
        assert result.latency_ms >= 0

    def test_details_present(self, db_path):
        from spellbook_mcp.health import check_security_domain

        _insert_canary(db_path)
        result = check_security_domain(db_path=db_path)
        assert result.details is not None


# =============================================================================
# TestDegradedNoCanaries
# =============================================================================


class TestDegradedNoCanaries:
    """Tables exist, no CRITICAL events, but no canary tokens registered."""

    def test_status_is_degraded(self, db_path):
        from spellbook_mcp.health import check_security_domain

        # No canary tokens inserted
        result = check_security_domain(db_path=db_path)
        assert result.status == HealthStatus.DEGRADED

    def test_message_mentions_canary(self, db_path):
        from spellbook_mcp.health import check_security_domain

        result = check_security_domain(db_path=db_path)
        assert "canar" in result.message.lower()


# =============================================================================
# TestUnhealthyCriticalEvents
# =============================================================================


class TestUnhealthyCriticalEvents:
    """Tables exist, CRITICAL event in last 24h."""

    def test_status_is_unhealthy(self, db_path):
        from spellbook_mcp.health import check_security_domain

        _insert_canary(db_path)
        _insert_critical_event(db_path)
        result = check_security_domain(db_path=db_path)
        assert result.status == HealthStatus.UNHEALTHY

    def test_message_mentions_critical(self, db_path):
        from spellbook_mcp.health import check_security_domain

        _insert_canary(db_path)
        _insert_critical_event(db_path)
        result = check_security_domain(db_path=db_path)
        assert "critical" in result.message.lower()


# =============================================================================
# TestUnavailableMissingTables
# =============================================================================


class TestUnavailableMissingTables:
    """DB exists but no security tables."""

    def test_status_is_unavailable(self, db_path_no_security_tables):
        from spellbook_mcp.health import check_security_domain

        result = check_security_domain(db_path=db_path_no_security_tables)
        assert result.status == HealthStatus.UNAVAILABLE

    def test_message_mentions_tables(self, db_path_no_security_tables):
        from spellbook_mcp.health import check_security_domain

        result = check_security_domain(db_path=db_path_no_security_tables)
        assert "table" in result.message.lower()


# =============================================================================
# TestSecurityVersion
# =============================================================================


class TestSecurityVersion:
    """Verify security_version field present in check details."""

    def test_version_in_details(self, db_path):
        from spellbook_mcp.health import check_security_domain

        _insert_canary(db_path)
        result = check_security_domain(db_path=db_path)
        assert result.details is not None
        assert "security_version" in result.details
        assert result.details["security_version"] == "1.0"

    def test_version_present_when_degraded(self, db_path):
        from spellbook_mcp.health import check_security_domain

        result = check_security_domain(db_path=db_path)
        assert result.details is not None
        assert "security_version" in result.details

    def test_version_present_when_unhealthy(self, db_path):
        from spellbook_mcp.health import check_security_domain

        _insert_canary(db_path)
        _insert_critical_event(db_path)
        result = check_security_domain(db_path=db_path)
        assert result.details is not None
        assert "security_version" in result.details


# =============================================================================
# TestRulesLoadable
# =============================================================================


class TestRulesLoadable:
    """Verify rules import check works."""

    def test_rules_loadable_in_healthy(self, db_path):
        from spellbook_mcp.health import check_security_domain

        _insert_canary(db_path)
        result = check_security_domain(db_path=db_path)
        assert result.details is not None
        assert result.details.get("rules_loadable") is True

    def test_rules_count_positive(self, db_path):
        from spellbook_mcp.health import check_security_domain

        _insert_canary(db_path)
        result = check_security_domain(db_path=db_path)
        assert result.details is not None
        assert result.details.get("injection_rules_count", 0) > 0


# =============================================================================
# TestRegistration
# =============================================================================


class TestRegistration:
    """Security domain is registered in the health check infrastructure."""

    def test_security_in_full_domains(self):
        from spellbook_mcp.health import FULL_DOMAINS

        assert "security" in FULL_DOMAINS

    def test_security_included_in_full_health_check(self, db_path, tmp_path):
        from spellbook_mcp.health import run_health_check

        # Create required directories for filesystem check
        config_dir = str(tmp_path / "config")
        data_dir = str(tmp_path / "data")
        skills_dir = str(tmp_path / "skills")
        for d in [config_dir, data_dir, skills_dir]:
            import os
            os.makedirs(d, exist_ok=True)

        result = run_health_check(
            db_path=db_path,
            config_dir=config_dir,
            data_dir=data_dir,
            skills_dir=skills_dir,
            server_uptime=60.0,
            version="0.1.0",
            tools_available=["test_tool"],
            quick=False,
        )
        assert result.domains is not None
        assert "security" in result.domains

    def test_security_not_in_quick_mode(self, db_path, tmp_path):
        from spellbook_mcp.health import run_health_check

        config_dir = str(tmp_path / "config")
        data_dir = str(tmp_path / "data")
        skills_dir = str(tmp_path / "skills")
        for d in [config_dir, data_dir, skills_dir]:
            import os
            os.makedirs(d, exist_ok=True)

        result = run_health_check(
            db_path=db_path,
            config_dir=config_dir,
            data_dir=data_dir,
            skills_dir=skills_dir,
            server_uptime=60.0,
            version="0.1.0",
            tools_available=["test_tool"],
            quick=True,
        )
        assert result.domains is not None
        assert "security" not in result.domains

"""Comprehensive health check module for spellbook MCP server.

Provides domain-specific health checks with status aggregation.
Supports quick mode (liveness) and full mode (readiness).
"""

import os
import re
import sqlite3
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

from spellbook_mcp.db import get_connection
from spellbook_mcp.preferences import CoordinationBackend, load_coordination_config

# =============================================================================
# Constants
# =============================================================================

# Timeout for gh CLI commands
GH_TIMEOUT_SECONDS = 2.0

# Minimum required gh version
MIN_GH_VERSION = "2.30.0"

# Watcher health check constants
STARTUP_GRACE_SECONDS = 10.0
MAX_HEARTBEAT_AGE_SECONDS = 30.0


class HealthStatus(str, Enum):
    """Health status levels for individual domains and overall status."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNAVAILABLE = "unavailable"
    NOT_CONFIGURED = "not_configured"


@dataclass
class DomainCheck:
    """Result of a single domain health check."""

    domain: str
    status: HealthStatus
    message: str
    latency_ms: Optional[float] = None
    details: Optional[dict] = None


@dataclass
class HealthCheckResult:
    """Complete health check result."""

    status: HealthStatus
    version: str
    uptime_seconds: float
    tools_available: list[str]
    domains: Optional[dict[str, DomainCheck]] = None
    checked_at: Optional[str] = None


# =============================================================================
# Helper Functions
# =============================================================================


def _parse_version_part(part: str) -> int:
    """Parse a version part, stripping any non-numeric suffix.

    Args:
        part: Version part string (e.g., "0", "30", "0-beta")

    Returns:
        Integer value of the numeric portion
    """
    match = re.match(r"(\d+)", part)
    return int(match.group(1)) if match else 0


def _parse_gh_version(output: str) -> str | None:
    """Extract version from gh --version output.

    Args:
        output: Raw output from `gh --version` command

    Returns:
        Version string (e.g., "2.45.0") or None if not found
    """
    match = re.search(r"gh version (\d+\.\d+\.\d+)", output)
    return match.group(1) if match else None


def _compare_versions(v1: str, v2: str) -> int:
    """Compare semver versions.

    Args:
        v1: First version string (e.g., "2.30.0")
        v2: Second version string (e.g., "2.45.0")

    Returns:
        -1 if v1 < v2, 0 if equal, 1 if v1 > v2
    """
    parts1 = [_parse_version_part(x) for x in v1.split(".")]
    parts2 = [_parse_version_part(x) for x in v2.split(".")]
    for a, b in zip(parts1, parts2):
        if a < b:
            return -1
        if a > b:
            return 1
    # Handle different-length version strings
    if len(parts1) < len(parts2):
        return -1
    if len(parts1) > len(parts2):
        return 1
    return 0


def _get_heartbeat_age(db_path: str) -> float | None:
    """Return seconds since last heartbeat, or None if no heartbeat exists.

    Args:
        db_path: Path to SQLite database

    Returns:
        Age in seconds, or None if no heartbeat row
    """
    conn = get_connection(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT timestamp FROM heartbeat WHERE id = 1")
        row = cursor.fetchone()
        if not row:
            return None
        heartbeat_time = datetime.fromisoformat(row[0])
        # Handle timezone-aware datetimes properly (CRITICAL FIX from plan review)
        if heartbeat_time.tzinfo is None:
            # If heartbeat is naive, assume it's in UTC
            heartbeat_time = heartbeat_time.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        return (now - heartbeat_time).total_seconds()
    finally:
        cursor.close()


# =============================================================================
# Domain Check Functions
# =============================================================================


def _check_database(db_path: str) -> DomainCheck:
    """Check database health.

    Checks:
    1. Database file exists and is readable
    2. Connection can be established
    3. Basic query executes successfully (SELECT 1)
    4. Critical tables exist (souls, heartbeat, workflow_state)

    Args:
        db_path: Path to SQLite database file

    Returns:
        DomainCheck with status and details
    """
    start = time.perf_counter()
    db_file = Path(db_path)

    try:
        # Check file exists
        if not db_file.exists():
            return DomainCheck(
                domain="database",
                status=HealthStatus.UNHEALTHY,
                message=f"Database file not found: {db_path}",
                latency_ms=(time.perf_counter() - start) * 1000,
                details={"path": db_path, "error": "file_not_found"},
            )

        # Get file size
        size_bytes = db_file.stat().st_size

        # Establish connection and run checks
        conn = get_connection(db_path)
        cursor = conn.cursor()

        # Execute basic query
        cursor.execute("SELECT 1")
        cursor.fetchone()

        # Check WAL mode
        cursor.execute("PRAGMA journal_mode")
        journal_mode = cursor.fetchone()[0]
        wal_mode = journal_mode.upper() == "WAL"

        # Count tables
        cursor.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
        )
        table_count = cursor.fetchone()[0]

        # Verify critical tables exist
        critical_tables = ["souls", "heartbeat", "workflow_state"]
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        existing_tables = {row[0] for row in cursor.fetchall()}

        missing_tables = [t for t in critical_tables if t not in existing_tables]
        if missing_tables:
            return DomainCheck(
                domain="database",
                status=HealthStatus.UNHEALTHY,
                message=f"Missing critical tables: {missing_tables}",
                latency_ms=(time.perf_counter() - start) * 1000,
                details={
                    "path": db_path,
                    "size_bytes": size_bytes,
                    "tables": table_count,
                    "wal_mode": wal_mode,
                    "missing_tables": missing_tables,
                },
            )

        return DomainCheck(
            domain="database",
            status=HealthStatus.HEALTHY,
            message="SQLite connection valid, schema verified",
            latency_ms=(time.perf_counter() - start) * 1000,
            details={
                "path": db_path,
                "size_bytes": size_bytes,
                "tables": table_count,
                "wal_mode": wal_mode,
            },
        )

    except sqlite3.Error as e:
        return DomainCheck(
            domain="database",
            status=HealthStatus.UNHEALTHY,
            message=f"Database error: {e}",
            latency_ms=(time.perf_counter() - start) * 1000,
            details={"path": db_path, "error": str(e)},
        )
    except Exception as e:
        return DomainCheck(
            domain="database",
            status=HealthStatus.UNHEALTHY,
            message=f"Unexpected error: {e}",
            latency_ms=(time.perf_counter() - start) * 1000,
            details={"path": db_path, "error": str(e), "error_type": type(e).__name__},
        )


def _check_watcher(
    db_path: str,
    server_uptime: float,
    startup_grace_seconds: float = STARTUP_GRACE_SECONDS,
    max_heartbeat_age: float = MAX_HEARTBEAT_AGE_SECONDS,
) -> DomainCheck:
    """Check watcher heartbeat freshness.

    Args:
        db_path: Path to SQLite database
        server_uptime: Seconds since server started
        startup_grace_seconds: Grace period for first heartbeat
        max_heartbeat_age: Maximum acceptable heartbeat age in seconds

    Returns:
        DomainCheck with status and details
    """
    start = time.perf_counter()

    # Check if in grace period
    in_grace_period = server_uptime < startup_grace_seconds
    grace_remaining = max(0, startup_grace_seconds - server_uptime) if in_grace_period else None

    try:
        heartbeat_age = _get_heartbeat_age(db_path)

        # Build details dict
        details = {
            "heartbeat_age_seconds": heartbeat_age,
            "max_age_seconds": max_heartbeat_age,
            "in_grace_period": in_grace_period,
        }
        if grace_remaining is not None:
            details["grace_remaining_seconds"] = grace_remaining

        # In grace period - always healthy
        if in_grace_period:
            return DomainCheck(
                domain="watcher",
                status=HealthStatus.HEALTHY,
                message="In startup grace period",
                latency_ms=(time.perf_counter() - start) * 1000,
                details=details,
            )

        # No heartbeat after grace period
        if heartbeat_age is None:
            return DomainCheck(
                domain="watcher",
                status=HealthStatus.DEGRADED,
                message="No heartbeat found (watcher may not have started)",
                latency_ms=(time.perf_counter() - start) * 1000,
                details=details,
            )

        # Stale heartbeat
        if heartbeat_age > max_heartbeat_age:
            return DomainCheck(
                domain="watcher",
                status=HealthStatus.DEGRADED,
                message=f"Heartbeat stale ({heartbeat_age:.1f}s ago, max {max_heartbeat_age:.1f}s)",
                latency_ms=(time.perf_counter() - start) * 1000,
                details=details,
            )

        # Fresh heartbeat
        return DomainCheck(
            domain="watcher",
            status=HealthStatus.HEALTHY,
            message=f"Heartbeat fresh ({heartbeat_age:.1f}s ago)",
            latency_ms=(time.perf_counter() - start) * 1000,
            details=details,
        )

    except Exception as e:
        return DomainCheck(
            domain="watcher",
            status=HealthStatus.DEGRADED,
            message=f"Error checking heartbeat: {e}",
            latency_ms=(time.perf_counter() - start) * 1000,
            details={"error": str(e)},
        )


def _check_filesystem(
    config_dir: str,
    data_dir: str,
    skills_dir: str,
) -> DomainCheck:
    """Check filesystem paths.

    Args:
        config_dir: Path to config directory (~/.config/spellbook/)
        data_dir: Path to data directory (~/.local/spellbook/)
        skills_dir: Path to skills directory ($SPELLBOOK_DIR/skills/)

    Returns:
        DomainCheck with status and details
    """
    start = time.perf_counter()

    def check_dir(path: str) -> dict:
        """Check if directory exists and is readable."""
        p = Path(path)
        exists = p.exists() and p.is_dir()
        readable = exists and os.access(path, os.R_OK)
        return {"path": path, "exists": exists, "readable": readable}

    config_check = check_dir(config_dir)
    data_check = check_dir(data_dir)
    skills_check = check_dir(skills_dir)

    details = {
        "config_dir": config_check,
        "data_dir": data_check,
        "skills_dir": skills_check,
    }

    # Critical directories: config and data
    if not config_check["exists"] or not config_check["readable"]:
        return DomainCheck(
            domain="filesystem",
            status=HealthStatus.UNHEALTHY,
            message="Config directory missing or not readable",
            latency_ms=(time.perf_counter() - start) * 1000,
            details=details,
        )

    if not data_check["exists"] or not data_check["readable"]:
        return DomainCheck(
            domain="filesystem",
            status=HealthStatus.UNHEALTHY,
            message="Data directory missing or not readable",
            latency_ms=(time.perf_counter() - start) * 1000,
            details=details,
        )

    # Optional directory: skills
    if not skills_check["exists"] or not skills_check["readable"]:
        return DomainCheck(
            domain="filesystem",
            status=HealthStatus.DEGRADED,
            message="Skills directory missing or not readable",
            latency_ms=(time.perf_counter() - start) * 1000,
            details=details,
        )

    return DomainCheck(
        domain="filesystem",
        status=HealthStatus.HEALTHY,
        message="All directories accessible",
        latency_ms=(time.perf_counter() - start) * 1000,
        details=details,
    )


def _check_github_cli() -> DomainCheck:
    """Check GitHub CLI availability.

    Checks:
    1. gh binary exists in PATH
    2. gh version meets minimum (2.30.0)
    3. gh is authenticated (gh auth status)

    Returns:
        DomainCheck with status and details
    """
    start = time.perf_counter()
    details: dict = {
        "installed": False,
        "version": None,
        "min_version": MIN_GH_VERSION,
        "authenticated": None,
    }

    # Check if gh is installed and get version
    try:
        result = subprocess.run(
            ["gh", "--version"],
            capture_output=True,
            text=True,
            timeout=GH_TIMEOUT_SECONDS,
            shell=False,
        )
        version = _parse_gh_version(result.stdout)
        if version is None:
            return DomainCheck(
                domain="github_cli",
                status=HealthStatus.UNAVAILABLE,
                message="Could not parse gh version",
                latency_ms=(time.perf_counter() - start) * 1000,
                details=details,
            )

        details["installed"] = True
        details["version"] = version

    except FileNotFoundError:
        return DomainCheck(
            domain="github_cli",
            status=HealthStatus.UNAVAILABLE,
            message="GitHub CLI (gh) not installed",
            latency_ms=(time.perf_counter() - start) * 1000,
            details=details,
        )
    except OSError:
        # CRITICAL FIX: Catch OSError not just FileNotFoundError
        return DomainCheck(
            domain="github_cli",
            status=HealthStatus.UNAVAILABLE,
            message="GitHub CLI (gh) not installed",
            latency_ms=(time.perf_counter() - start) * 1000,
            details=details,
        )
    except subprocess.TimeoutExpired:
        return DomainCheck(
            domain="github_cli",
            status=HealthStatus.DEGRADED,
            message="GitHub CLI check timed out (>2s)",
            latency_ms=(time.perf_counter() - start) * 1000,
            details={**details, "timeout_seconds": 2.0},
        )

    # Check version meets minimum
    if _compare_versions(version, MIN_GH_VERSION) < 0:
        return DomainCheck(
            domain="github_cli",
            status=HealthStatus.DEGRADED,
            message=f"gh version {version} is too old (min {MIN_GH_VERSION}). Run: gh upgrade",
            latency_ms=(time.perf_counter() - start) * 1000,
            details=details,
        )

    # Check authentication
    try:
        auth_result = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True,
            text=True,
            timeout=GH_TIMEOUT_SECONDS,
            shell=False,
        )
        authenticated = auth_result.returncode == 0
        details["authenticated"] = authenticated

        if not authenticated:
            return DomainCheck(
                domain="github_cli",
                status=HealthStatus.DEGRADED,
                message="gh not authenticated. Run: gh auth login",
                latency_ms=(time.perf_counter() - start) * 1000,
                details=details,
            )

    except subprocess.TimeoutExpired:
        return DomainCheck(
            domain="github_cli",
            status=HealthStatus.DEGRADED,
            message="gh auth check timed out (>2s)",
            latency_ms=(time.perf_counter() - start) * 1000,
            details={**details, "timeout_seconds": 2.0},
        )

    return DomainCheck(
        domain="github_cli",
        status=HealthStatus.HEALTHY,
        message=f"gh {version} installed and authenticated",
        latency_ms=(time.perf_counter() - start) * 1000,
        details=details,
    )


def _check_coordination() -> DomainCheck:
    """Check coordination backend configuration.

    NOTE: This check does NOT attempt network connections.
    It only validates that the configuration is valid.

    Returns:
        DomainCheck with status and details
    """
    start = time.perf_counter()

    try:
        config = load_coordination_config()

        backend_value = (
            config.backend.value
            if isinstance(config.backend, CoordinationBackend)
            else str(config.backend)
        )

        details = {
            "backend": backend_value,
            "configured": config.backend != CoordinationBackend.NONE,
        }

        if config.backend == CoordinationBackend.NONE:
            return DomainCheck(
                domain="coordination",
                status=HealthStatus.NOT_CONFIGURED,
                message="Coordination backend disabled",
                latency_ms=(time.perf_counter() - start) * 1000,
                details=details,
            )

        return DomainCheck(
            domain="coordination",
            status=HealthStatus.HEALTHY,
            message=f"Coordination backend configured: {backend_value}",
            latency_ms=(time.perf_counter() - start) * 1000,
            details=details,
        )

    except Exception as e:
        return DomainCheck(
            domain="coordination",
            status=HealthStatus.DEGRADED,
            message=f"Failed to load coordination config: {e}",
            latency_ms=(time.perf_counter() - start) * 1000,
            details={"error": str(e)},
        )


def _check_skills(skills_dir: str) -> DomainCheck:
    """Check skills registry.

    Checks:
    1. Skills directory exists
    2. Contains at least one subdirectory
    3. Each subdirectory contains SKILL.md file

    Args:
        skills_dir: Path to skills directory

    Returns:
        DomainCheck with status and details
    """
    start = time.perf_counter()
    skills_path = Path(skills_dir)

    # Check directory exists
    if not skills_path.exists() or not skills_path.is_dir():
        return DomainCheck(
            domain="skills",
            status=HealthStatus.UNAVAILABLE,
            message=f"Skills directory not found: {skills_dir}",
            latency_ms=(time.perf_counter() - start) * 1000,
            details={"skills_dir": skills_dir},
        )

    # Count subdirectories and validate SKILL.md presence
    total_directories = 0
    valid_skills = 0
    invalid_skills = []

    for item in skills_path.iterdir():
        if item.is_dir():
            total_directories += 1
            skill_md = item / "SKILL.md"
            if skill_md.exists() and skill_md.is_file():
                valid_skills += 1
            else:
                invalid_skills.append(item.name)

    details = {
        "skills_dir": skills_dir,
        "total_directories": total_directories,
        "valid_skills": valid_skills,
        "invalid_skills": invalid_skills,
    }

    # No valid skills found
    if valid_skills == 0:
        return DomainCheck(
            domain="skills",
            status=HealthStatus.DEGRADED,
            message="No valid skills found (directories missing SKILL.md)",
            latency_ms=(time.perf_counter() - start) * 1000,
            details=details,
        )

    # At least one valid skill
    message = f"{valid_skills} valid skill{'s' if valid_skills != 1 else ''} found"
    if invalid_skills:
        message += f" ({len(invalid_skills)} invalid)"

    return DomainCheck(
        domain="skills",
        status=HealthStatus.HEALTHY,
        message=message,
        latency_ms=(time.perf_counter() - start) * 1000,
        details=details,
    )


# =============================================================================
# Status Aggregation
# =============================================================================

# Critical domains - UNHEALTHY causes overall UNHEALTHY
CRITICAL_DOMAINS = {"database", "filesystem"}

# Quick mode domains (liveness check)
QUICK_DOMAINS = {"database", "filesystem"}

# Full mode domains (readiness check)
FULL_DOMAINS = {"database", "filesystem", "watcher", "github_cli", "coordination", "skills"}


def _aggregate_status(domains: dict[str, DomainCheck]) -> HealthStatus:
    """Aggregate domain statuses into overall status.

    Algorithm:
    1. If any CRITICAL domain is UNHEALTHY -> UNHEALTHY
    2. If any domain is DEGRADED or optional is UNHEALTHY -> DEGRADED
    3. Otherwise -> HEALTHY

    Note: UNAVAILABLE and NOT_CONFIGURED do not affect aggregation.

    Args:
        domains: Dict mapping domain names to DomainCheck results

    Returns:
        Aggregated HealthStatus
    """
    # Check critical domains first
    for domain_name in CRITICAL_DOMAINS:
        if domain_name in domains:
            if domains[domain_name].status == HealthStatus.UNHEALTHY:
                return HealthStatus.UNHEALTHY

    # Check for any degradation
    for domain_name, check in domains.items():
        if check.status == HealthStatus.DEGRADED:
            return HealthStatus.DEGRADED
        # Optional domains being unhealthy causes degradation, not failure
        if domain_name not in CRITICAL_DOMAINS:
            if check.status == HealthStatus.UNHEALTHY:
                return HealthStatus.DEGRADED

    return HealthStatus.HEALTHY


# =============================================================================
# Orchestration Function
# =============================================================================


def run_health_check(
    db_path: str,
    config_dir: str,
    data_dir: str,
    skills_dir: str,
    server_uptime: float,
    version: str,
    tools_available: list[str],
    quick: bool = False,
) -> HealthCheckResult:
    """Run health checks across domains.

    Args:
        db_path: Path to SQLite database file
        config_dir: Path to config directory (~/.config/spellbook/)
        data_dir: Path to data directory (~/.local/spellbook/)
        skills_dir: Path to skills directory ($SPELLBOOK_DIR/skills/)
        server_uptime: Seconds since server started
        version: Server version string
        tools_available: List of available tool names
        quick: If True, only check critical domains (liveness).
               If False, check all domains (readiness).

    Returns:
        HealthCheckResult with aggregated status and domain details
    """
    domains: dict[str, DomainCheck] = {}

    # Always check critical domains
    domains["database"] = _check_database(db_path)
    domains["filesystem"] = _check_filesystem(config_dir, data_dir, skills_dir)

    # Full mode: check all optional domains
    if not quick:
        domains["watcher"] = _check_watcher(db_path, server_uptime)
        domains["github_cli"] = _check_github_cli()
        domains["coordination"] = _check_coordination()
        domains["skills"] = _check_skills(skills_dir)

    # Aggregate status
    overall_status = _aggregate_status(domains)

    # Generate ISO timestamp
    checked_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    return HealthCheckResult(
        status=overall_status,
        version=version,
        uptime_seconds=server_uptime,
        tools_available=tools_available,
        domains=domains,
        checked_at=checked_at,
    )
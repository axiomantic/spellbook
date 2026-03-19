"""CLI-oriented health checks for `spellbook doctor`.

Unlike the server-side ``checker.py`` (which runs inside the daemon),
this module performs *client-side* checks that run without a running
daemon.  Checks cover Python version, package installation, config
directories, database files, daemon reachability, token file, skill
symlinks, and platform config.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class CheckResult:
    """Result of a single diagnostic check."""

    name: str
    status: str  # "pass", "fail", "warn"
    detail: str
    fix: str | None = None


def check_python_version() -> CheckResult:
    """Check that Python >= 3.10."""
    v = sys.version_info
    version_str = f"{v.major}.{v.minor}.{v.micro}"
    if (v.major, v.minor) >= (3, 10):
        return CheckResult("python_version", "pass", f"Python {version_str}")
    return CheckResult(
        "python_version",
        "fail",
        f"Python {version_str} (need >= 3.10)",
        fix="Install Python 3.10 or later",
    )


def check_package_installed() -> CheckResult:
    """Check that the spellbook package is importable and has a version."""
    try:
        from importlib.metadata import version

        ver = version("spellbook")
        return CheckResult("package_installed", "pass", f"spellbook {ver}")
    except Exception as exc:
        return CheckResult(
            "package_installed",
            "fail",
            f"Cannot determine version: {exc}",
            fix="Run: uv pip install -e '.[dev]'",
        )


def check_config_dir() -> CheckResult:
    """Check that the config directory exists and is writable."""
    config_dir = Path(
        os.environ.get("SPELLBOOK_CONFIG_DIR", Path.home() / ".local" / "spellbook")
    )
    if not config_dir.exists():
        return CheckResult(
            "config_dir",
            "fail",
            f"Missing: {config_dir}",
            fix=f"Run: mkdir -p {config_dir}",
        )
    if not os.access(config_dir, os.W_OK):
        return CheckResult(
            "config_dir",
            "fail",
            f"Not writable: {config_dir}",
            fix=f"Run: chmod u+w {config_dir}",
        )
    return CheckResult("config_dir", "pass", str(config_dir))


def check_databases() -> CheckResult:
    """Check that the four SQLite databases exist."""
    config_dir = Path(
        os.environ.get("SPELLBOOK_CONFIG_DIR", Path.home() / ".local" / "spellbook")
    )
    db_names = ["spellbook.db", "forged.db", "fractal.db", "coordination.db"]
    missing = [name for name in db_names if not (config_dir / name).exists()]
    if missing:
        return CheckResult(
            "databases",
            "warn",
            f"Missing: {', '.join(missing)}",
            fix="Start the daemon to initialize databases",
        )
    return CheckResult("databases", "pass", f"All {len(db_names)} databases present")


def check_daemon_running() -> CheckResult:
    """Check if the daemon is reachable."""
    import socket

    from spellbook.core.config import get_env

    host = get_env("HOST", "127.0.0.1")
    port = int(get_env("PORT", "8765"))
    try:
        with socket.create_connection((host, port), timeout=2.0):
            return CheckResult("daemon", "pass", f"Reachable at {host}:{port}")
    except (OSError, TimeoutError):
        return CheckResult(
            "daemon",
            "warn",
            f"Not reachable at {host}:{port}",
            fix="Run: spellbook server start",
        )


def check_token_file() -> CheckResult:
    """Check that the bearer token file exists."""
    token_path = Path.home() / ".local" / "spellbook" / ".mcp-token"
    if token_path.exists():
        content = token_path.read_text().strip()
        if content:
            return CheckResult("token_file", "pass", str(token_path))
        return CheckResult(
            "token_file",
            "warn",
            "Token file is empty",
            fix="Start the daemon to generate a token",
        )
    return CheckResult(
        "token_file",
        "warn",
        f"Missing: {token_path}",
        fix="Start the daemon to generate a token",
    )


def check_skills_symlinks() -> CheckResult:
    """Check that the skills directory exists and has SKILL.md files."""
    spellbook_dir = os.environ.get("SPELLBOOK_DIR")
    if not spellbook_dir:
        # Try to find it from package location
        try:
            import spellbook

            pkg_dir = Path(spellbook.__file__).parent.parent
            skills_dir = pkg_dir / "skills"
        except Exception:
            return CheckResult(
                "skills",
                "warn",
                "Cannot locate skills directory (SPELLBOOK_DIR not set)",
            )
    else:
        skills_dir = Path(spellbook_dir) / "skills"

    if not skills_dir.exists():
        return CheckResult(
            "skills",
            "warn",
            f"Skills directory not found: {skills_dir}",
            fix="Run: spellbook install",
        )

    skill_files = list(skills_dir.glob("*/SKILL.md"))
    if not skill_files:
        return CheckResult(
            "skills",
            "warn",
            "No SKILL.md files found in skills/",
            fix="Run: spellbook install",
        )
    return CheckResult("skills", "pass", f"{len(skill_files)} skills found")


def check_platform_config() -> CheckResult:
    """Check if platform config (e.g. .claude.json) has MCP config."""
    claude_json = Path.home() / ".claude.json"
    if claude_json.exists():
        try:
            import json

            data = json.loads(claude_json.read_text())
            mcp_servers = data.get("mcpServers", {})
            if "spellbook" in mcp_servers:
                return CheckResult(
                    "platform_config",
                    "pass",
                    "MCP server configured in ~/.claude.json",
                )
            return CheckResult(
                "platform_config",
                "warn",
                "No 'spellbook' entry in ~/.claude.json mcpServers",
                fix="Run: spellbook install",
            )
        except Exception as exc:
            return CheckResult(
                "platform_config",
                "warn",
                f"Error reading ~/.claude.json: {exc}",
            )
    return CheckResult(
        "platform_config",
        "warn",
        "No ~/.claude.json found",
        fix="Run: spellbook install",
    )


def run_checks() -> list[CheckResult]:
    """Run all diagnostic checks and return results."""
    return [
        check_python_version(),
        check_package_installed(),
        check_config_dir(),
        check_databases(),
        check_daemon_running(),
        check_token_file(),
        check_skills_symlinks(),
        check_platform_config(),
    ]

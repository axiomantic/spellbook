"""CLI-oriented health checks for `spellbook doctor`.

Unlike the server-side ``checker.py`` (which runs inside the daemon),
this module performs *client-side* checks that run without a running
daemon.  Checks cover Python version, package installation, config
directories, database files, daemon reachability, token file, skill
symlinks, rule-module delivery, and platform config.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
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


def _dangling_rule_paths(installer) -> list[Path]:
    """Return the installer's rule artifacts that exist as links but resolve nowhere.

    ``os.path.lexists`` is required here, not ``Path.exists()``. ``exists()``
    follows the symlink and reports False for a broken one -- which is exactly
    the state being detected, so it would report the dangling link as simply
    absent and the check would never fire.
    """
    # Imported inside the function, as every other installer import in this
    # module is: doctor must still run on a partial checkout.
    from installer.components.rule_delivery import INSTALLED_GLOB

    candidates: list[Path] = []

    rules_dir = installer.rule_module_dir()
    if rules_dir is not None and rules_dir.is_dir():
        candidates.extend(rules_dir.glob(INSTALLED_GLOB))

    bundle = installer.rule_bundle_path()
    if bundle is not None:
        candidates.append(bundle)

    candidates.extend(installer.legacy_rule_paths())

    return [p for p in candidates if os.path.lexists(p) and not os.path.exists(p)]


def _core_module_missing(installer) -> bool:
    """Whether an installed platform is missing the mandatory core module.

    "Nothing is dangling" is satisfied by delivering nothing at all, so a
    prune-everything regression reads as healthy without this. The mandatory
    core module is present on every correct delivery, on both mechanisms, so
    its absence from a platform that reports itself installed is the signal.
    """
    from installer.components.rule_delivery import CORE_MODULE_GLOB

    rules_dir = installer.rule_module_dir()
    if rules_dir is not None:
        if not rules_dir.is_dir():
            return True
        return not list(rules_dir.glob(CORE_MODULE_GLOB))

    bundle = installer.rule_bundle_path()
    if bundle is None:
        return False
    if not os.path.exists(bundle):
        return True
    from installer.components.rule_bundle import MODULE_MARKER_PREFIX

    try:
        return f"{MODULE_MARKER_PREFIX} core " not in bundle.read_text(encoding="utf-8")
    except OSError:
        return True


def check_rule_modules(
    config_dirs: dict[str, Path] | None = None,
    spellbook_dir: Path | None = None,
) -> CheckResult:
    """Detect rule paths that are linked but dangling, or missing entirely.

    Between a ``git pull`` that moves or deletes rule sources and the next
    ``install.py`` run, every previously-symlinked rule path dangles. The
    harness silently loads NO spellbook rules during that window. The window
    cannot be closed -- the installer is not what runs on ``git pull`` -- so it
    is instead made loud and recoverable here.

    A platform that reports itself installed but has no core module delivered
    is also a failure. Without that, a delivery that pruned everything passes
    this check by virtue of having nothing left to dangle.

    Args:
        config_dirs: Per-platform config dir overrides. Lets a caller point the
            check at a fixture tree instead of the real machine.
        spellbook_dir: Checkout root override, for the same reason.
    """
    try:
        from installer.config import SUPPORTED_PLATFORMS
        from installer.core import get_platform_installer
        from spellbook.core.config import get_spellbook_dir

        root = Path(spellbook_dir) if spellbook_dir is not None else Path(get_spellbook_dir())
    except Exception as exc:  # pragma: no cover - a partial checkout must not crash doctor
        return CheckResult(
            "rule_modules",
            "warn",
            f"Cannot inspect rule modules: {exc}",
        )

    overrides = config_dirs or {}
    dangling: list[Path] = []
    undelivered: list[str] = []
    skipped: list[str] = []
    checked = 0
    for platform in SUPPORTED_PLATFORMS:
        try:
            installer = get_platform_installer(
                platform, root, version="0", dry_run=True,
                config_dir_override=overrides.get(platform),
            )
            found = _dangling_rule_paths(installer)
            missing_core = (
                installer.rule_delivery != "none"
                and installer.detect().installed
                and _core_module_missing(installer)
            )
        except Exception:
            # One unreadable platform must not mask the others -- but it must
            # not vanish either. A skipped platform used to leave a green line
            # that read identically to a full inspection, so "pass" could mean
            # one platform checked out of seven.
            skipped.append(platform)
            continue
        checked += 1
        dangling.extend(found)
        if missing_core:
            undelivered.append(platform)

    if dangling:
        shown = ", ".join(str(p) for p in sorted(dangling)[:5])
        more = f" (+{len(dangling) - 5} more)" if len(dangling) > 5 else ""
        return CheckResult(
            "rule_modules",
            "fail",
            f"{len(dangling)} rule path(s) point at missing sources; "
            f"no spellbook rules are loading: {shown}{more}",
            fix="Run: uv run install.py (rule sources moved; re-link them)",
        )

    if undelivered:
        return CheckResult(
            "rule_modules",
            "fail",
            "spellbook is installed but the mandatory core rule module was not "
            f"delivered to: {', '.join(sorted(undelivered))}",
            fix="Run: uv run install.py (rule modules missing; re-deliver them)",
        )

    if not checked:
        return CheckResult(
            "rule_modules",
            "warn",
            "No platform could be inspected for rule modules"
            + (f" (all failed: {', '.join(sorted(skipped))})" if skipped else ""),
        )
    if skipped:
        return CheckResult(
            "rule_modules",
            "warn",
            f"No dangling rule paths across {checked} platform(s), but "
            f"{len(skipped)} could not be inspected: {', '.join(sorted(skipped))}",
            fix="Check the config directories for the platforms named above",
        )
    return CheckResult(
        "rule_modules", "pass", f"No dangling rule paths across {checked} platform(s)"
    )


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
        check_rule_modules(),
        check_platform_config(),
    ]

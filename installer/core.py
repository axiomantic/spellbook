"""
Core orchestrator for spellbook installation.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import PLATFORM_CONFIG, SUPPORTED_PLATFORMS, get_platform_config_dir
from .platforms.base import PlatformInstaller
from .version import check_upgrade_needed, read_version


def validate_skill_security(skill_path: Path) -> tuple[bool, list[str]]:
    """Validate a skill file for security issues before installation.

    Runs the skill content through injection, exfiltration, escalation, and
    obfuscation rule sets from spellbook_mcp.security.rules. Uses the
    "standard" security mode, which flags CRITICAL and HIGH severity findings.

    Args:
        skill_path: Path to the skill file (typically SKILL.md).

    Returns:
        A tuple of (is_safe, issues) where:
        - is_safe is True if no CRITICAL or HIGH findings were detected
        - issues is a list of human-readable strings describing each finding
    """
    from spellbook_mcp.security.rules import (
        ESCALATION_RULES,
        EXFILTRATION_RULES,
        INJECTION_RULES,
        OBFUSCATION_RULES,
        check_patterns,
    )

    if not skill_path.exists():
        return (False, [f"Skill file does not exist: {skill_path}"])

    try:
        content = skill_path.read_text(encoding="utf-8")
    except OSError as e:
        return (False, [f"Failed to read skill file: {e}"])

    all_findings: list[dict] = []
    rule_sets = [
        ("injection", INJECTION_RULES),
        ("exfiltration", EXFILTRATION_RULES),
        ("escalation", ESCALATION_RULES),
        ("obfuscation", OBFUSCATION_RULES),
    ]

    for _category, rules in rule_sets:
        findings = check_patterns(content, rules, security_mode="standard")
        all_findings.extend(findings)

    if not all_findings:
        return (True, [])

    issues = [
        f"[{f['severity']}] {f['rule_id']}: {f['message']} (matched: {f['matched_text']!r})"
        for f in all_findings
    ]
    return (False, issues)


@dataclass
class InstallResult:
    """Result of a single installation component."""

    component: str
    platform: str
    success: bool
    action: str  # "installed", "upgraded", "created", "skipped", "failed", "removed", "unchanged"
    message: str
    details: Optional[Dict[str, Any]] = None


@dataclass
class InstallSession:
    """Tracks state across the installation process."""

    spellbook_dir: Path
    version: str
    previous_version: Optional[str]
    results: List[InstallResult] = field(default_factory=list)
    start_time: datetime = field(default_factory=datetime.now)
    dry_run: bool = False

    @property
    def success(self) -> bool:
        """Check if all results were successful."""
        return all(r.success for r in self.results)

    @property
    def platforms_installed(self) -> List[str]:
        """Get list of platforms that had successful installations."""
        platforms = set()
        for r in self.results:
            if r.success and r.action not in ("skipped", "unchanged"):
                platforms.add(r.platform)
        return list(platforms)


def get_platform_installer(
    platform: str,
    spellbook_dir: Path,
    version: str,
    dry_run: bool = False,
    on_step=None,
) -> PlatformInstaller:
    """Get the appropriate installer for a platform."""
    from .platforms.claude_code import ClaudeCodeInstaller
    from .platforms.codex import CodexInstaller
    from .platforms.crush import CrushInstaller
    from .platforms.gemini import GeminiInstaller
    from .platforms.opencode import OpenCodeInstaller

    config_dir = get_platform_config_dir(platform)

    installers = {
        "claude_code": ClaudeCodeInstaller,
        "opencode": OpenCodeInstaller,
        "codex": CodexInstaller,
        "gemini": GeminiInstaller,
        "crush": CrushInstaller,
    }

    installer_class = installers.get(platform)
    if not installer_class:
        raise ValueError(f"Unknown platform: {platform}")

    return installer_class(spellbook_dir, config_dir, version, dry_run, on_step=on_step)


class Installer:
    """Main orchestrator for spellbook installation."""

    def __init__(self, spellbook_dir: Path):
        self.spellbook_dir = spellbook_dir
        self.version = read_version(spellbook_dir / ".version")

    def detect_platforms(self) -> List[str]:
        """
        Auto-detect available platforms by checking config directories.

        Claude Code is always available (we create its directory).
        """
        available = []
        for platform in SUPPORTED_PLATFORMS:
            if platform == "claude_code":
                available.append(platform)
            else:
                config_dir = get_platform_config_dir(platform)
                if config_dir.exists():
                    available.append(platform)
        return available

    def run(
        self,
        platforms: Optional[List[str]] = None,
        force: bool = False,
        dry_run: bool = False,
        on_progress=None,
    ) -> InstallSession:
        """
        Execute installation workflow.

        Args:
            platforms: List of platforms to install (default: auto-detect)
            force: Force reinstall even if version matches
            dry_run: Show what would be done without making changes
            on_progress: Callback for progress updates.
                Called with (event, data) where event is one of:
                "platform_start" - data: {"name", "index", "total"}
                "platform_skip" - data: {"name", "message"}
                "step" - data: {"message"}
                "result" - data: {"result": InstallResult}

        Returns InstallSession with all results.
        """
        if platforms is None:
            platforms = self.detect_platforms()

        # Determine previous version from Claude Code context file
        claude_config = get_platform_config_dir("claude_code")
        from .demarcation import get_installed_version

        previous_version = get_installed_version(claude_config / "CLAUDE.md")

        session = InstallSession(
            spellbook_dir=self.spellbook_dir,
            version=self.version,
            previous_version=previous_version,
            dry_run=dry_run,
        )

        # Check if upgrade is needed
        needs_upgrade, upgrade_reason = check_upgrade_needed(
            previous_version, self.version, force
        )

        def _on_step(message):
            if on_progress:
                on_progress("step", {"message": message})

        # Install MCP daemon once, before any platform installations.
        # All platforms connect to this shared daemon via HTTP.
        from .components.mcp import install_daemon

        if on_progress:
            on_progress("daemon_start", {})

        _on_step("Installing MCP daemon")
        server_path = self.spellbook_dir / "spellbook_mcp" / "server.py"
        if server_path.exists():
            daemon_success, daemon_msg = install_daemon(
                self.spellbook_dir, dry_run=dry_run
            )
            daemon_result = InstallResult(
                component="mcp_daemon",
                platform="system",
                success=daemon_success,
                action="installed" if daemon_success else "failed",
                message=f"MCP daemon: {daemon_msg}",
            )
        else:
            daemon_success = False
            daemon_result = InstallResult(
                component="mcp_daemon",
                platform="system",
                success=False,
                action="failed",
                message=f"MCP daemon: server.py not found at {server_path}",
            )

        session.results.append(daemon_result)
        if on_progress:
            on_progress("result", {"result": daemon_result})

        total = len(platforms)
        for i, platform in enumerate(platforms, 1):
            installer = get_platform_installer(
                platform, self.spellbook_dir, self.version, dry_run,
                on_step=_on_step,
            )

            if on_progress:
                on_progress("platform_start", {
                    "name": installer.platform_name,
                    "index": i,
                    "total": total,
                })

            # Check platform status
            status = installer.detect()

            if not status.available and platform != "claude_code":
                skip_result = InstallResult(
                    component="platform",
                    platform=platform,
                    success=True,
                    action="skipped",
                    message=f"{installer.platform_name} not available",
                )
                session.results.append(skip_result)
                if on_progress:
                    on_progress("platform_skip", {
                        "name": installer.platform_name,
                        "message": skip_result.message,
                    })
                continue

            # Install
            results = installer.install(force=force)
            for result in results:
                if on_progress:
                    on_progress("result", {"result": result})
            session.results.extend(results)

        # Health check: verify the daemon is actually responding to MCP requests
        if not dry_run and daemon_success:
            from .components.mcp import check_daemon_health

            if on_progress:
                on_progress("health_start", {})

            _on_step("Checking daemon health")
            healthy, health_msg = check_daemon_health()
            health_result = InstallResult(
                component="mcp_health",
                platform="system",
                success=healthy,
                action="installed" if healthy else "failed",
                message=f"MCP health: {health_msg}",
            )
            session.results.append(health_result)
            if on_progress:
                on_progress("result", {"result": health_result})

        return session


class Uninstaller:
    """Orchestrator for spellbook uninstallation."""

    def __init__(self, spellbook_dir: Path):
        self.spellbook_dir = spellbook_dir
        try:
            self.version = read_version(spellbook_dir / ".version")
        except FileNotFoundError:
            self.version = "unknown"

    def detect_installed_platforms(self) -> List[str]:
        """Detect which platforms have spellbook installed."""
        installed = []
        for platform in SUPPORTED_PLATFORMS:
            try:
                installer = get_platform_installer(
                    platform, self.spellbook_dir, self.version
                )
                status = installer.detect()
                if status.installed:
                    installed.append(platform)
            except (ValueError, OSError):
                continue
        return installed

    def run(
        self,
        platforms: Optional[List[str]] = None,
        dry_run: bool = False,
    ) -> InstallSession:
        """
        Execute uninstallation workflow.

        Args:
            platforms: List of platforms to uninstall (default: all installed)
            dry_run: Show what would be done without making changes

        Returns InstallSession with all results.
        """
        if platforms is None:
            platforms = self.detect_installed_platforms()

        session = InstallSession(
            spellbook_dir=self.spellbook_dir,
            version=self.version,
            previous_version=None,
            dry_run=dry_run,
        )

        for platform in platforms:
            try:
                installer = get_platform_installer(
                    platform, self.spellbook_dir, self.version, dry_run
                )
            except ValueError:
                session.results.append(
                    InstallResult(
                        component="platform",
                        platform=platform,
                        success=False,
                        action="failed",
                        message=f"Unknown platform: {platform}",
                    )
                )
                continue

            # Uninstall
            results = installer.uninstall()
            session.results.extend(results)

        # Uninstall MCP server system service if installed
        mcp_result = self._uninstall_mcp_service(dry_run)
        if mcp_result:
            session.results.append(mcp_result)

        return session

    def _uninstall_mcp_service(self, dry_run: bool = False) -> Optional[InstallResult]:
        """Uninstall the MCP server system service if installed."""
        from installer.compat import ServiceManager

        manager = ServiceManager(self.spellbook_dir, 8765, "127.0.0.1")

        if not manager.is_installed():
            return None

        if dry_run:
            return InstallResult(
                component="mcp_service",
                platform="system",
                success=True,
                action="removed",
                message="MCP service: would uninstall system service",
            )

        manager.stop()
        success, msg = manager.uninstall()
        return InstallResult(
            component="mcp_service",
            platform="system",
            success=success,
            action="removed" if success else "failed",
            message=f"MCP service: {msg}",
        )

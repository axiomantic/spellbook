"""
Core orchestrator for spellbook installation.
"""

import logging
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from installer.compat import ServiceManager, mcp_service_config, tts_service_config
from spellbook.core.config import config_set as _config_set
from spellbook.tts.venv import get_tts_data_dir, get_tts_venv_dir

from .config import PLATFORM_CONFIG, SUPPORTED_PLATFORMS, get_platform_config_dir, resolve_config_dirs
from .platforms.base import PlatformInstaller
from .ui import shorten_home
from .version import check_upgrade_needed, read_version

logger = logging.getLogger(__name__)


def validate_skill_security(skill_path: Path) -> tuple[bool, list[str]]:
    """Validate a skill file for security issues before installation.

    Runs the skill content through injection, exfiltration, escalation, and
    obfuscation rule sets from spellbook.security.rules. Uses the
    "standard" security mode, which flags CRITICAL and HIGH severity findings.

    Args:
        skill_path: Path to the skill file (typically SKILL.md).

    Returns:
        A tuple of (is_safe, issues) where:
        - is_safe is True if no CRITICAL or HIGH findings were detected
        - issues is a list of human-readable strings describing each finding
    """
    from spellbook.security.rules import (
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

    # Only block on HIGH and CRITICAL findings (standard mode threshold).
    # LOW/MEDIUM findings (like entropy signals) are informational only.
    from spellbook.security.rules import Severity

    blocking_findings = [
        f for f in all_findings
        if Severity[f["severity"]].value >= Severity.HIGH.value
    ]

    if not blocking_findings:
        return (True, [])

    issues = [
        f"[{f['severity']}] {f['rule_id']}: {f['message']} (matched: {f.get('matched_text', 'N/A')!r})"
        for f in blocking_findings
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
    security_config: Optional[Dict[str, Any]] = None

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

    @property
    def platforms_failed(self) -> List[str]:
        """Get list of platforms that had failures."""
        failed = set()
        for r in self.results:
            if not r.success:
                failed.add(r.platform)
        # Exclude platforms that also had successes (partial success = installed)
        return list(failed - set(self.platforms_installed))


def get_platform_installer(
    platform: str,
    spellbook_dir: Path,
    version: str,
    dry_run: bool = False,
    on_step=None,
    config_dir_override: Optional[Path] = None,
    context: Optional[Dict[str, Any]] = None,
) -> PlatformInstaller:
    """Get the appropriate installer for a platform.

    Args:
        platform: Platform identifier.
        spellbook_dir: Path to spellbook repository.
        version: Spellbook version string.
        dry_run: If True, don't make changes.
        on_step: Callback for step progress.
        config_dir_override: If provided, use this dir instead of the
            platform default. Used by multi-target orchestration.
        context: Cross-platform context dict shared across installers
            (e.g., claude_config_dirs consumed by the Claude Code installer).
    """
    from .platforms.claude_code import ClaudeCodeInstaller
    from .platforms.codex import CodexInstaller
    from .platforms.gemini import GeminiInstaller
    from .platforms.opencode import OpenCodeInstaller

    config_dir = config_dir_override or get_platform_config_dir(platform)

    installers = {
        "claude_code": ClaudeCodeInstaller,
        "opencode": OpenCodeInstaller,
        "codex": CodexInstaller,
        "gemini": GeminiInstaller,
    }

    installer_class = installers.get(platform)
    if not installer_class:
        raise ValueError(f"Unknown platform: {platform}")

    return installer_class(
        spellbook_dir, config_dir, version, dry_run,
        on_step=on_step, context=context,
    )


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
        config_dir_overrides: Optional[Dict[str, List[Path]]] = None,
        security_selections: Optional[Dict[str, bool]] = None,
        renderer=None,
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
            config_dir_overrides: Per-platform list of config dirs from CLI
                flags. Keys are platform IDs, values are lists of Path.
            renderer: InstallerRenderer instance for progress rendering.
                If None, auto-detects: RichRenderer when stdout is a TTY,
                PlainTextRenderer otherwise.

        Returns InstallSession with all results.
        """
        import sys as _sys

        if renderer is None:
            from .renderer import PlainTextRenderer, RichRenderer

            renderer = RichRenderer() if _sys.stdout.isatty() else PlainTextRenderer()
        if platforms is None:
            platforms = self.detect_platforms()

        # Pre-resolve Claude dirs for cross-platform context (order-independent)
        # and for version detection
        claude_dirs = resolve_config_dirs(
            "claude_code",
            cli_dirs=(config_dir_overrides or {}).get("claude_code"),
        )

        # Determine previous version from first Claude Code config dir
        from .demarcation import get_installed_version

        version_dir = claude_dirs[0] if claude_dirs else get_platform_config_dir("claude_code")
        previous_version = get_installed_version(version_dir / "CLAUDE.md")

        session = InstallSession(
            spellbook_dir=self.spellbook_dir,
            version=self.version,
            previous_version=previous_version,
            dry_run=dry_run,
        )

        # Apply security feature configuration if selections provided
        if security_selections is not None:
            from .components.security import apply_security_config, get_default_security_config

            written_keys = apply_security_config(security_selections, dry_run=dry_run)
            # Store the resolved config on the session for downstream use
            defaults = get_default_security_config()
            resolved = dict(defaults)
            for feat_id, enabled in security_selections.items():
                enabled_key = f"security.{feat_id}.enabled"
                if enabled_key in resolved:
                    resolved[enabled_key] = enabled
            session.security_config = resolved

            security_result = InstallResult(
                component="security_config",
                platform="system",
                success=True,
                action="installed" if not dry_run else "skipped",
                message=f"Security config: {len(written_keys)} keys {'written' if not dry_run else 'would be written'}",
            )
            session.results.append(security_result)
            if on_progress:
                on_progress("result", {"result": security_result})

        # Check if upgrade is needed
        needs_upgrade, upgrade_reason = check_upgrade_needed(
            previous_version, self.version, force
        )

        def _on_step(message):
            if on_progress:
                on_progress("step", {"message": message})

        # Shared context for cross-platform data
        shared_context: Dict[str, Any] = {
            "claude_config_dirs": claude_dirs,
        }

        # Pre-resolve all dirs to compute accurate total count and
        # initialize the progress display before the daemon install so
        # the user sees status output during the (potentially slow)
        # daemon venv build and health-check loop.
        platform_dirs: list[tuple[str, list[Path]]] = []
        total = 0
        for platform in platforms:
            cli_dirs = (config_dir_overrides or {}).get(platform)
            dirs = resolve_config_dirs(platform, cli_dirs=cli_dirs)
            platform_dirs.append((platform, dirs))
            total += max(len(dirs), 1)  # Count at least 1 for skip message

        renderer.render_progress_start(total)

        # Install MCP daemon once, before any platform installations.
        # All platforms connect to this shared daemon via HTTP.
        from .components.mcp import install_daemon

        renderer.render_step("daemon_start", {})
        if on_progress:
            on_progress("daemon_start", {})

        _on_step("Installing MCP daemon")
        server_path = self.spellbook_dir / "spellbook" / "server.py"
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
        renderer.render_step("result", {"result": daemon_result})
        if on_progress:
            on_progress("result", {"result": daemon_result})

        install_index = 0
        for platform, dirs in platform_dirs:
            if not dirs:
                install_index += 1
                # All specified dirs were invalid
                skip_result = InstallResult(
                    component="platform",
                    platform=platform,
                    success=True,
                    action="skipped",
                    message=f"{platform}: no valid config directories",
                )
                session.results.append(skip_result)
                renderer.render_step("platform_skip", {
                    "name": platform,
                    "message": skip_result.message,
                })
                if on_progress:
                    on_progress("platform_skip", {
                        "name": platform,
                        "message": skip_result.message,
                    })
                continue

            for dir_idx, config_dir in enumerate(dirs):
                install_index += 1
                skip_global = dir_idx > 0

                installer = get_platform_installer(
                    platform, self.spellbook_dir, self.version, dry_run,
                    on_step=_on_step,
                    config_dir_override=config_dir,
                    context=shared_context,
                )

                _dir_display = shorten_home(config_dir)
                _start_data = {
                    "name": f"{installer.platform_name} ({_dir_display})",
                    "index": install_index,
                    "total": total,
                }
                renderer.render_step("platform_start", _start_data)
                if on_progress:
                    on_progress("platform_start", _start_data)

                # Check platform status
                status = installer.detect()

                if not status.available and platform != "claude_code":
                    skip_result = InstallResult(
                        component="platform",
                        platform=platform,
                        success=True,
                        action="skipped",
                        message=f"{installer.platform_name} not available at {config_dir}",
                    )
                    session.results.append(skip_result)
                    _skip_data = {
                        "name": installer.platform_name,
                        "message": skip_result.message,
                    }
                    renderer.render_step("platform_skip", _skip_data)
                    if on_progress:
                        on_progress("platform_skip", _skip_data)
                    continue

                # Install with error isolation per dir
                try:
                    results = installer.install(
                        force=force, skip_global_steps=skip_global,
                    )
                    for result in results:
                        _result_data = {"result": result}
                        renderer.render_step("result", _result_data)
                        if on_progress:
                            on_progress("result", _result_data)
                    session.results.extend(results)
                except Exception as e:
                    fail_result = InstallResult(
                        component="platform",
                        platform=platform,
                        success=False,
                        action="failed",
                        message=f"Installation to {config_dir} failed: {e}",
                    )
                    session.results.append(fail_result)
                    _fail_data = {"result": fail_result}
                    renderer.render_step("result", _fail_data)
                    if on_progress:
                        on_progress("result", _fail_data)

        # Health check: verify the daemon is actually responding to MCP requests
        if not dry_run and daemon_success:
            from .components.mcp import check_daemon_health

            renderer.render_step("health_start", {})
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
            renderer.render_step("result", {"result": health_result})
            if on_progress:
                on_progress("result", {"result": health_result})

        renderer.render_progress_end()
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
        config_dir_overrides: Optional[Dict[str, List[Path]]] = None,
    ) -> InstallSession:
        """
        Execute uninstallation workflow.

        Args:
            platforms: List of platforms to uninstall (default: all installed)
            dry_run: Show what would be done without making changes
            config_dir_overrides: Per-platform list of config dirs from CLI
                flags.

        Returns InstallSession with all results.
        """
        if platforms is None:
            platforms = self.detect_installed_platforms()

        # Pre-resolve Claude dirs for cross-platform context (used by ClaudeCodeInstaller to prevent redundant CLAUDE.md updates)
        claude_dirs = resolve_config_dirs(
            "claude_code",
            cli_dirs=(config_dir_overrides or {}).get("claude_code"),
        )

        shared_context: Dict[str, Any] = {
            "claude_config_dirs": claude_dirs,
        }

        session = InstallSession(
            spellbook_dir=self.spellbook_dir,
            version=self.version,
            previous_version=None,
            dry_run=dry_run,
        )

        for platform in platforms:
            cli_dirs = (config_dir_overrides or {}).get(platform)
            config_dirs = resolve_config_dirs(platform, cli_dirs=cli_dirs)

            for dir_idx, config_dir in enumerate(config_dirs):
                skip_global = dir_idx > 0

                try:
                    installer = get_platform_installer(
                        platform, self.spellbook_dir, self.version, dry_run,
                        config_dir_override=config_dir,
                        context=shared_context,
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

                # Check if anything is installed at this dir
                status = installer.detect()
                if not status.installed:
                    continue

                # Uninstall
                try:
                    results = installer.uninstall(skip_global_steps=skip_global)
                    session.results.extend(results)
                except Exception as e:
                    fail_result = InstallResult(
                        component="platform",
                        platform=platform,
                        success=False,
                        action="failed",
                        message=f"Uninstallation from {config_dir} failed: {e}",
                    )
                    session.results.append(fail_result)

        # Uninstall MCP server system service if installed
        mcp_result = self._uninstall_mcp_service(dry_run)
        if mcp_result:
            session.results.append(mcp_result)

        # Uninstall TTS service if installed
        tts_result = self._uninstall_tts_service(dry_run)
        if tts_result:
            session.results.append(tts_result)

        return session

    def _uninstall_mcp_service(self, dry_run: bool = False) -> Optional[InstallResult]:
        """Uninstall the MCP server system service if installed."""
        manager = ServiceManager(mcp_service_config(self.spellbook_dir, 8765, "127.0.0.1"))

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

    def _uninstall_tts_service(self, dry_run: bool = False) -> Optional[InstallResult]:
        """Uninstall the TTS service, remove venv, and reset config."""
        tts_venv_dir = get_tts_venv_dir()
        tts_data_dir = get_tts_data_dir()

        config = tts_service_config(tts_venv_dir=tts_venv_dir)
        manager = ServiceManager(config)

        if not manager.is_installed() and not tts_venv_dir.exists():
            return None

        if dry_run:
            return InstallResult(
                component="tts_service",
                platform="system",
                success=True,
                action="removed",
                message="TTS service: would uninstall service, remove venv, and reset config",
            )

        # Stop and uninstall the service
        manager.stop()
        success, msg = manager.uninstall()

        # Remove TTS venv if it exists
        if tts_venv_dir.exists():
            shutil.rmtree(str(tts_venv_dir))

        # Log about preserved model data
        if tts_data_dir.exists():
            logger.info(
                "TTS model data preserved at %s (remove manually if not needed)",
                tts_data_dir,
            )

        # Reset config keys
        _config_set("tts_enabled", False)
        _config_set("tts_deps_installed", False)
        _config_set("tts_service_installed", False)

        return InstallResult(
            component="tts_service",
            platform="system",
            success=success,
            action="removed" if success else "failed",
            message=f"TTS service: {msg}",
        )

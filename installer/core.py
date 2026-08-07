"""
Core orchestrator for spellbook installation.
"""

import json
import logging
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from installer.compat import ServiceManager, mcp_service_config

from .config import SUPPORTED_PLATFORMS, get_platform_config_dir, resolve_config_dirs
from .migrations import run_all_migrations
from .platforms.base import PlatformInstaller
from .ui import shorten_home
from .version import check_upgrade_needed, read_version

logger = logging.getLogger(__name__)


def validate_skill_security(skill_path: Path) -> tuple[bool, list[str]]:
    """Validate a skill file for security issues before installation.

    Runs the skill content through injection, exfiltration, escalation, and
    obfuscation rule sets from spellbook.gates.rules. Uses the
    "standard" security mode, which flags CRITICAL and HIGH severity findings.

    Args:
        skill_path: Path to the skill file (typically SKILL.md).

    Returns:
        A tuple of (is_safe, issues) where:
        - is_safe is True if no CRITICAL or HIGH findings were detected
        - issues is a list of human-readable strings describing each finding
    """
    from spellbook.gates.rules import (
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
    from spellbook.gates.rules import Severity

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
    from .platforms.antigravity import AntigravityInstaller
    from .platforms.claude_code import ClaudeCodeInstaller
    from .platforms.codex import CodexInstaller
    from .platforms.forgecode import ForgeCodeInstaller
    from .platforms.gemini import GeminiInstaller
    from .platforms.opencode import OpenCodeInstaller
    from .platforms.pi import PiInstaller

    config_dir = config_dir_override or get_platform_config_dir(platform)

    installers = {
        "claude_code": ClaudeCodeInstaller,
        "antigravity": AntigravityInstaller,
        "opencode": OpenCodeInstaller,
        "codex": CodexInstaller,
        "gemini": GeminiInstaller,
        "forgecode": ForgeCodeInstaller,
        "pi": PiInstaller,
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
        renderer=None,
        rule_selection: Optional[List[str]] = None,
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
            rule_selection: Explicit rule module ids the user chose. None means
                "not asked", in which case the selection is resolved from
                config plus each module's default and nothing is recorded.

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

        # Determine the previously installed version from the install stamp.
        #
        # This used to read the demarcated marker in CLAUDE.md, which the
        # installer strips on every run -- so it was permanently None, every
        # install reported itself a fresh install, and show_whats_new() always
        # returned early. The stamp is written at the end of a successful
        # install; the CLAUDE.md marker is kept only as a fallback for users
        # upgrading from an interpolated install that predates the stamp.
        from .version import read_installed_version, write_installed_version

        version_dir = claude_dirs[0] if claude_dirs else get_platform_config_dir("claude_code")
        previous_version = read_installed_version(version_dir / "CLAUDE.md")

        from .components.context_files import ensure_machine_config_file
        ensure_machine_config_file(self.spellbook_dir, dry_run=dry_run)

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

        # Shared context for cross-platform data
        shared_context: Dict[str, Any] = {
            "claude_config_dirs": claude_dirs,
        }

        # Resolve which rule modules this install delivers, before any platform
        # installer runs, so every platform delivers the same set.
        (
            rule_modules,
            resolved_selection,
            detection,
            rule_error,
        ) = self._resolve_rule_delivery(
            platforms, config_dir_overrides, rule_selection, dry_run
        )
        shared_context["rule_modules"] = rule_modules
        shared_context["rule_selection"] = resolved_selection
        shared_context["rule_install_state"] = detection
        shared_context["rule_delivery_error"] = rule_error

        if rule_error:
            # Not a delivery of nothing. Every platform installer refuses to
            # touch its delivered rules while this is set, and the session is
            # unsuccessful so no install stamp is written.
            session.results.append(
                InstallResult(
                    component="rule_modules",
                    platform="system",
                    success=False,
                    action="failed",
                    message=f"rule modules: {rule_error}",
                )
            )

        if detection is not None and detection.needs_migration:
            _on_step(
                f"Detected a {detection.state.value} install on "
                f"{detection.platform}; migrating to rule modules"
            )

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

        # Run one-shot legacy-state migrations before any component
        # installation. These are idempotent and cheap on clean machines.
        if not dry_run:
            _on_step("Cleaning up legacy alias block")
            try:
                # run_all_migrations() logs each modified file at INFO.
                run_all_migrations()
            except Exception as e:  # pragma: no cover - defensive
                logger.warning("Legacy migration failed: %s", e)

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

        # Build the admin SPA once, before platform installs. The daemon
        # serves the compiled bundle from spellbook/admin/static, which is no
        # longer committed to the repo: it is generated here via npm. node/npm
        # are a hard requirement, so a build failure is a failed result that
        # makes session.success False.
        from .components.admin_build import build_admin_frontend

        _on_step("Building admin SPA")
        admin_success, admin_msg = build_admin_frontend(
            self.spellbook_dir, dry_run=dry_run
        )
        admin_result = InstallResult(
            component="admin_frontend",
            platform="system",
            success=admin_success,
            action="installed" if admin_success else "failed",
            message=f"Admin SPA: {admin_msg}",
        )
        session.results.append(admin_result)
        renderer.render_step("result", {"result": admin_result})
        if on_progress:
            on_progress("result", {"result": admin_result})

        # operator decision: admin build failure halts install. node/npm are a
        # hard requirement, so on a real install a failed build aborts before
        # any platform install (intentional deviation from the daemon-failure
        # fall-through precedent, which lets platform installs proceed). Under
        # dry_run we keep going so the operator sees the full plan.
        if not admin_success and not dry_run:
            renderer.render_progress_end()
            return session

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

        # Post-install delivery verification. A symlink existing is not
        # evidence of delivery, so this looks for the marker in the harness's
        # assembled prompt where that is obtainable and reports an honest
        # degradation where it is not.
        if not dry_run:
            _on_step("Verifying rule delivery")
            for tripwire_result in self._verify_rule_delivery(
                platform_dirs, resolved_selection, session.results
            ):
                session.results.append(tripwire_result)
                renderer.render_step("result", {"result": tripwire_result})
                if on_progress:
                    on_progress("result", {"result": tripwire_result})

        # The stamp records that this version's rules were delivered, so it is
        # gated on rule delivery rather than on every component. Gating on the
        # whole session meant one unrelated failure (a daemon health blip) left
        # the stamp unwritten and the next install reporting itself fresh.
        rule_delivery_ok = not rule_error and all(
            r.success
            for r in session.results
            if r.component in ("rule_modules", "rule_modules_config", "rule_delivery")
        )
        if not dry_run and rule_delivery_ok:
            write_installed_version(self.version, dry_run=dry_run)

        renderer.render_progress_end()
        return session

    def _resolve_rule_delivery(
        self,
        platforms: List[str],
        config_dir_overrides: Optional[Dict[str, List[Path]]],
        rule_selection: Optional[List[str]],
        dry_run: bool,
    ):
        """Load the rule modules and decide which ones this install delivers.

        Returns ``(modules, selection, detection, error)``. ``error`` is a
        non-empty string when the module set could not be resolved, which is a
        hard failure rather than a delivery of nothing: delivering an empty set
        to a directory-capable harness prunes every rule already installed.
        """
        from .components.rule_migration import detect_existing_install
        from .components.rule_modules import (
            get_rules_dir,
            load_rule_modules,
            resolve_selection,
        )

        rules_dir = get_rules_dir(self.spellbook_dir)
        try:
            modules = load_rule_modules(rules_dir)
        except Exception as e:
            logger.error("Could not load rule modules from %s: %s", rules_dir, e)
            return [], None, None, f"could not load rule modules from {rules_dir}: {e}"

        if not modules:
            logger.error("No rule modules found in %s", rules_dir)
            return [], None, None, f"no rule modules found in {rules_dir}"

        detection = None
        try:
            overrides = config_dir_overrides or {}
            probes = []
            for platform in SUPPORTED_PLATFORMS:
                if platform not in platforms:
                    continue
                dirs = overrides.get(platform) or []
                probes.append(
                    get_platform_installer(
                        platform, self.spellbook_dir, self.version, dry_run=True,
                        config_dir_override=dirs[0] if dirs else None,
                    )
                )
            detection = detect_existing_install(probes)
        except Exception as e:  # pragma: no cover - defensive
            logger.warning("Could not detect existing install state: %s", e)

        if rule_selection is not None:
            # The user answered. Honor exactly what they chose.
            selection = resolve_selection(modules)
            chosen = set(rule_selection)
            selection.selected_ids = [
                m.id for m in modules if m.is_preference and m.id in chosen
            ]
            selection.declined_ids = [
                m.id for m in modules if m.is_preference and m.id not in chosen
            ]
            return modules, selection, detection, None

        # Not asked. Resolve from config plus defaults, and record nothing.
        # A migrating user has never been asked either, so their recorded
        # answers (there are none) are bypassed and every default-on module is
        # installed -- honoring the upgrade path without adding a rule they
        # never had.
        config_values = _read_rule_config()
        force_defaults = detection is not None and detection.install_all_defaults
        selection = resolve_selection(
            modules, config_values, force_all_defaults=force_defaults
        )
        return modules, selection, detection, None

    def _verify_rule_delivery(
        self, platform_dirs, selection, install_results
    ) -> List[InstallResult]:
        """Run the delivery tripwire for each platform that delivered rules.

        Scoped to platforms whose rule delivery reported success. A platform
        that was skipped -- an absent config dir, a missing harness CLI --
        delivered nothing on purpose, and reporting that as a delivery failure
        would be a false alarm in exactly the report whose value is that its
        alarms are real.
        """
        from .components.rule_tripwire import (
            TripwireStatus,
            verify_platform,
        )

        if selection is None:
            return []

        delivered = {
            r.platform
            for r in install_results
            if r.component == "rule_modules" and r.success
        }

        results: List[InstallResult] = []
        for platform, dirs in platform_dirs:
            if not dirs or platform not in delivered:
                continue
            try:
                probe = get_platform_installer(
                    platform, self.spellbook_dir, self.version, dry_run=True,
                    config_dir_override=dirs[0],
                )
                if probe.rule_delivery == "none":
                    continue
                module_dir = probe.rule_module_dir()
                outcome = verify_platform(
                    platform,
                    self.version,
                    module_dir=module_dir,
                    bundle_path=probe.rule_bundle_path(),
                    config_dir=dirs[0],
                    registered=_modules_registered(platform, probe, module_dir),
                )
            except Exception as e:
                # A probe that raises produced no verdict, and silence here read
                # exactly like a pass: the platform delivered rules and then
                # neither passed nor failed verification. Report the failure.
                logger.warning("Tripwire probe failed for %s: %s", platform, e)
                results.append(
                    InstallResult(
                        component="rule_delivery",
                        platform=platform,
                        success=False,
                        action="failed",
                        message=f"rule delivery: verification probe failed - {e}",
                    )
                )
                continue

            results.append(
                InstallResult(
                    component="rule_delivery",
                    platform=platform,
                    success=outcome.status is not TripwireStatus.FAILED,
                    action=outcome.status.value,
                    message=f"rule delivery: {outcome.method} - {outcome.message}",
                )
            )
        return results


def _modules_registered(
    platform: str, probe: PlatformInstaller, module_dir: Optional[Path]
) -> Optional[bool]:
    """Whether every installed module is registered where the harness reads it.

    OpenCode is the only harness with a registration step: its resolver loads
    exactly the paths listed in ``opencode.json``'s ``instructions`` array, so a
    module file on disk that is not listed there does not load at all. Returns
    None for every other platform, which the tripwire reads as "registration is
    not a load mechanism here".
    """
    if platform != "opencode" or module_dir is None:
        return None

    from .components.rule_delivery import INSTALLED_GLOB

    config_path = getattr(probe, "opencode_config_file", None)
    if config_path is None or not config_path.exists():
        return False
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False
    if not isinstance(data, dict):
        return False

    entries = data.get("instructions", [])
    if not isinstance(entries, list):
        entries = [entries]
    listed = {str(entry) for entry in entries}

    installed = sorted(module_dir.glob(INSTALLED_GLOB)) if module_dir.is_dir() else []
    if not installed:
        return False
    return all(probe._instructions_config_path(path) in listed for path in installed)


def _read_rule_config() -> Dict[str, Any]:
    """Read only the explicitly-set ``rules.module.*`` keys.

    Reads the config file directly rather than through ``config_get``, because
    absence is a value here: a key that has a built-in default but was never
    written means "never offered", and applying the default at read time would
    erase that distinction.
    """
    try:
        from spellbook.core.compat import get_config_dir
    except ImportError:
        return {}

    config_path = get_config_dir() / "spellbook.json"
    if not config_path.exists():
        return {}
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {k: v for k, v in data.items() if k.startswith("rules.module.")}


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

        # Run legacy-state migrations on uninstall too, so users who
        # remove spellbook also get their rc files cleaned of the
        # now-orphaned SPELLBOOK_ALIASES block.
        if not dry_run:
            try:
                # run_all_migrations() logs each modified file at INFO.
                run_all_migrations()
            except Exception as e:  # pragma: no cover - defensive
                logger.warning("Legacy migration failed: %s", e)

        # Uninstall MCP server system service if installed
        mcp_result = self._uninstall_mcp_service(dry_run)
        if mcp_result:
            session.results.append(mcp_result)

        # Remove the install-time-generated admin SPA bundle (no longer
        # committed to the repo; generated by build_admin_frontend).
        session.results.append(self._uninstall_admin_static(dry_run))

        return session

    def _uninstall_admin_static(self, dry_run: bool = False) -> InstallResult:
        """Remove the generated admin SPA bundle at spellbook/admin/static/.

        The bundle is generated at install time, not committed, so uninstall
        cleans it up. Absence is tolerated (ignore-errors).
        """
        static_dir = self.spellbook_dir / "spellbook" / "admin" / "static"

        if not static_dir.exists():
            # Nothing to remove regardless of dry_run: report the benign state.
            return InstallResult(
                component="admin_frontend",
                platform="system",
                success=True,
                action="removed",
                message="Admin SPA: no generated bundle to remove",
            )

        if dry_run:
            return InstallResult(
                component="admin_frontend",
                platform="system",
                success=True,
                action="removed",
                message=f"Admin SPA: would remove generated bundle at {static_dir}",
            )

        shutil.rmtree(static_dir, ignore_errors=True)
        return InstallResult(
            component="admin_frontend",
            platform="system",
            success=True,
            action="removed",
            message=f"Admin SPA: removed generated bundle at {static_dir}",
        )

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


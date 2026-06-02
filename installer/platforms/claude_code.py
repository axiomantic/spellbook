"""
Claude Code platform installer.
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, List

from ..components.agents import (
    cleanup_stale_agent_symlinks,
    install_agents,
    uninstall_agents,
)
from ..components.context_files import generate_claude_context
from ..components.default_mode import install_default_mode, uninstall_default_mode
from ..components.hooks import install_hooks, uninstall_hooks
from ..components.permissions import (
    derive_managed_deny,
    install_permissions,
    uninstall_permissions,
)
from ..components.mcp import (
    check_claude_cli_available,
    get_spellbook_server_url,
    register_mcp_http_server,
    uninstall_daemon,
    unregister_mcp_server,
)
from ..components.symlinks import (
    cleanup_spellbook_symlinks,
    create_command_symlinks,
    create_skill_symlinks,
    create_symlink,
)
from ..demarcation import (
    get_installed_version,
    remove_demarcated_section,
    update_demarcated_section,
)
from .base import PlatformInstaller, PlatformStatus

if TYPE_CHECKING:
    from ..core import InstallResult

logger = logging.getLogger(__name__)


class ClaudeCodeInstaller(PlatformInstaller):
    """Installer for Claude Code platform."""

    @property
    def platform_name(self) -> str:
        return "Claude Code"

    @property
    def platform_id(self) -> str:
        return "claude_code"

    def detect(self) -> PlatformStatus:
        """Detect Claude Code installation status."""
        claude_md = self.config_dir / "CLAUDE.md"
        installed_version = get_installed_version(claude_md)

        return PlatformStatus(
            platform=self.platform_id,
            available=True,  # We always create .claude directory
            installed=installed_version is not None,
            version=installed_version,
            details={
                "config_dir": str(self.config_dir),
                "cli_available": check_claude_cli_available(),
            },
        )

    def install(
        self, force: bool = False, skip_global_steps: bool = False
    ) -> List["InstallResult"]:
        """Install Claude Code components."""
        from ..core import InstallResult

        results = []

        # Ensure config directory exists
        if not self.ensure_config_dir():
            results.append(
                InstallResult(
                    component="config_dir",
                    platform=self.platform_id,
                    success=False,
                    action="failed",
                    message=f"Failed to create {self.config_dir}",
                )
            )
            return results

        # Create subdirectories
        # Note: patterns and docs are symlinked, not created as directories
        for subdir in ["skills", "commands", "scripts", "agents", "plans"]:
            subdir_path = self.config_dir / subdir
            if not self.dry_run:
                subdir_path.mkdir(parents=True, exist_ok=True)

        # Clean up existing installation before installing new one
        self._step("Cleaning up old symlinks")
        # NOTE: agents/ is intentionally absent from this broad cleanup. The
        # cleanup_spellbook_symlinks pass clobbers any symlink resolving into a
        # path containing "spellbook" -- that is fine for skills/commands/
        # scripts (which are recreated unconditionally on every install) but
        # would defeat install_agents's "unchanged" idempotency path. Stale
        # agent symlinks (renamed/removed source files) are purged below by a
        # narrowed inline pass that preserves currently-valid entries.
        cleanup_dirs = ["skills", "commands", "scripts"]
        total_cleaned = 0
        for subdir in cleanup_dirs:
            cleanup_results = cleanup_spellbook_symlinks(
                self.config_dir / subdir, dry_run=self.dry_run
            )
            total_cleaned += sum(1 for r in cleanup_results if r.success)

        if total_cleaned > 0:
            results.append(
                InstallResult(
                    component="cleanup",
                    platform=self.platform_id,
                    success=True,
                    action="removed",
                    message=f"cleanup: {total_cleaned} old symlinks removed",
                )
            )

        # Install skills
        self._step("Installing skills")
        skills_results = create_skill_symlinks(
            self.spellbook_dir / "skills",
            self.config_dir / "skills",
            as_directories=True,
            dry_run=self.dry_run,
        )
        skill_count = sum(1 for r in skills_results if r.success)
        results.append(
            InstallResult(
                component="skills",
                platform=self.platform_id,
                success=skill_count > 0 or not skills_results,
                action="installed" if skills_results else "skipped",
                message=f"skills: {skill_count} installed",
            )
        )

        # Install commands
        self._step("Installing commands")
        cmd_results = create_command_symlinks(
            self.spellbook_dir / "commands",
            self.config_dir / "commands",
            dry_run=self.dry_run,
        )
        cmd_count = sum(1 for r in cmd_results if r.success)
        results.append(
            InstallResult(
                component="commands",
                platform=self.platform_id,
                success=cmd_count > 0 or not cmd_results,
                action="installed" if cmd_results else "skipped",
                message=f"commands: {cmd_count} installed",
            )
        )

        # Install patterns directory
        self._step("Installing patterns")
        patterns_source = self.spellbook_dir / "patterns"
        patterns_target = self.config_dir / "patterns"
        if patterns_source.exists():
            pattern_result = create_symlink(patterns_source, patterns_target, self.dry_run)
            results.append(
                InstallResult(
                    component="patterns",
                    platform=self.platform_id,
                    success=pattern_result.success,
                    action=pattern_result.action,
                    message=f"patterns: {pattern_result.action}",
                )
            )

        # Install docs directory
        self._step("Installing docs")
        docs_source = self.spellbook_dir / "docs"
        docs_target = self.config_dir / "docs"
        if docs_source.exists():
            docs_result = create_symlink(docs_source, docs_target, self.dry_run)
            results.append(
                InstallResult(
                    component="docs",
                    platform=self.platform_id,
                    success=docs_result.success,
                    action=docs_result.action,
                    message=f"docs: {docs_result.action}",
                )
            )

        # Install profiles directory
        self._step("Installing profiles")
        profiles_source = self.spellbook_dir / "profiles"
        profiles_target = self.config_dir / "profiles"
        if profiles_source.exists():
            profiles_result = create_symlink(profiles_source, profiles_target, self.dry_run)
            results.append(
                InstallResult(
                    component="profiles",
                    platform=self.platform_id,
                    success=profiles_result.success,
                    action=profiles_result.action,
                    message=f"profiles: {profiles_result.action}",
                )
            )

        # Install scripts
        self._step("Installing scripts")
        scripts_source = self.spellbook_dir / "scripts"
        scripts_target = self.config_dir / "scripts"
        if scripts_source.exists():
            script_count = 0
            for script_file in scripts_source.glob("*.py"):
                script_result = create_symlink(
                    script_file, scripts_target / script_file.name, self.dry_run
                )
                if script_result.success:
                    script_count += 1
            for script_file in scripts_source.glob("*.sh"):
                script_result = create_symlink(
                    script_file, scripts_target / script_file.name, self.dry_run
                )
                if script_result.success:
                    script_count += 1
            if script_count > 0:
                results.append(
                    InstallResult(
                        component="scripts",
                        platform=self.platform_id,
                        success=True,
                        action="installed",
                        message=f"scripts: {script_count} installed",
                    )
                )

        # Install agents (claude_code only - other platforms don't yet support
        # this discovery pattern). Sub-agents must live in $CLAUDE_CONFIG_DIR/
        # agents/ to be discovered by Claude Code 2.1.x; we symlink each
        # $SPELLBOOK_DIR/agents/*.md target into place.
        #
        # Pre-cleanup: purge stale agent symlinks (point into the spellbook
        # agents dir but have no matching current source file). This handles
        # renamed/removed source agents without clobbering currently-valid
        # symlinks (which install_agents will report as "unchanged").
        # Delegated to ``cleanup_stale_agent_symlinks`` so the staleness
        # heuristic (resolved-target set + broken-link parent-dir match,
        # honouring both absolute and relative symlink targets) is the
        # single source of truth shared with future callers.
        self._step("Cleaning up stale agent symlinks")
        cleanup_stale_agent_symlinks(
            agents_target_dir=self.config_dir / "agents",
            agents_source_dir=self.spellbook_dir / "agents",
            dry_run=self.dry_run,
        )

        self._step("Installing agents")
        agent_results = install_agents(
            spellbook_dir=self.spellbook_dir,
            config_dir=self.config_dir,
            dry_run=self.dry_run,
        )
        installed = sum(1 for r in agent_results if r.action == "installed")
        upgraded = sum(1 for r in agent_results if r.action == "upgraded")
        unchanged = sum(1 for r in agent_results if r.action == "unchanged")
        skipped = sum(1 for r in agent_results if r.action == "skipped")
        failed = sum(1 for r in agent_results if not r.success)
        agent_failed = failed > 0
        if installed or upgraded:
            agents_action = "installed"
        elif unchanged:
            agents_action = "unchanged"
        else:
            agents_action = "skipped"
        message_parts = [
            f"{installed} installed",
            f"{upgraded} upgraded",
            f"{unchanged} unchanged",
            f"{skipped} skipped",
        ]
        if failed:
            # Surface the failed count when nonzero so a partial-failure
            # InstallResult (success=False) carries an actionable breakdown
            # instead of "0 installed, 0 upgraded, 0 unchanged, 0 skipped".
            message_parts.append(f"{failed} failed")
        results.append(
            InstallResult(
                component="agents",
                platform=self.platform_id,
                success=not agent_failed,
                action=agents_action,
                message="agents: " + ", ".join(message_parts),
            )
        )

        # Install CLAUDE.md with demarcated section (per-dir).
        self._step("Updating CLAUDE.md")
        claude_md = self.config_dir / "CLAUDE.md"

        # Special case: ~/.claude/CLAUDE.md is ALWAYS read by Claude Code as
        # global instructions. If the user has multiple config dirs (e.g.
        # ~/.claude and ~/.claude-work) and ~/.claude is one of them, we only
        # want the spellbook chunk in ~/.claude to avoid duplicate loading
        # and context window bloat.
        default_dir = Path.home() / ".claude"
        all_claude_dirs = self._context.get("claude_config_dirs", []) if self._context else []

        should_skip_context = self.config_dir.resolve() != default_dir.resolve() and any(
            d.resolve() == default_dir.resolve() for d in all_claude_dirs
        )

        if should_skip_context:
            self._step("Skipping CLAUDE.md (using ~/.claude instead)")
            if not self.dry_run:
                action, _backup = remove_demarcated_section(claude_md)
                if action == "removed":
                    results.append(
                        InstallResult(
                            component="CLAUDE.md",
                            platform=self.platform_id,
                            success=True,
                            action="removed",
                            message="CLAUDE.md: removed redundant spellbook section (prioritizing ~/.claude)",
                        )
                    )
                else:
                    results.append(
                        InstallResult(
                            component="CLAUDE.md",
                            platform=self.platform_id,
                            success=True,
                            action="skipped",
                            message="CLAUDE.md: skipped update (prioritizing ~/.claude)",
                        )
                    )
            else:
                results.append(
                    InstallResult(
                        component="CLAUDE.md",
                        platform=self.platform_id,
                        success=True,
                        action="skipped",
                        message="CLAUDE.md: would skip update (prioritizing ~/.claude)",
                    )
                )
        else:
            spellbook_content = generate_claude_context(self.spellbook_dir)

            if spellbook_content:
                if self.dry_run:
                    action = "would be updated"
                    results.append(
                        InstallResult(
                            component="CLAUDE.md",
                            platform=self.platform_id,
                            success=True,
                            action="installed",
                            message=f"CLAUDE.md: {action}",
                        )
                    )
                else:
                    action, backup_path = update_demarcated_section(
                        claude_md, spellbook_content, self.version
                    )
                    msg = f"CLAUDE.md: {action}"
                    if backup_path:
                        msg += f" (backup: {backup_path.name})"
                    results.append(
                        InstallResult(
                            component="CLAUDE.md",
                            platform=self.platform_id,
                            success=True,
                            action=action,
                            message=msg,
                        )
                    )

        # Register the MCP server connection in THIS config dir's .claude.json.
        # The daemon itself is global (installed once by core.py), but each Claude
        # config dir needs its own mcpServers entry pointing at that daemon -- so
        # registration is per-config-dir, NOT a global step. register_mcp_http_server
        # sets CLAUDE_CONFIG_DIR from config_dir so the entry lands in the right file.
        # (Gating this behind skip_global_steps previously left every config dir
        # after the first -- e.g. a second --claude-config-dir -- with hooks but no
        # MCP registration.)
        self._step("Registering MCP server")

        # Remove any old variant names
        for old_name in ["spellbook-http"]:
            unregister_mcp_server(old_name, dry_run=self.dry_run)

        if check_claude_cli_available():
            server_url = get_spellbook_server_url()
            reg_success, reg_msg = register_mcp_http_server(
                "spellbook",
                server_url,
                dry_run=self.dry_run,
                config_dir=self.config_dir,
            )
            results.append(
                InstallResult(
                    component="mcp_server",
                    platform=self.platform_id,
                    success=reg_success,
                    action="installed" if reg_success else "failed",
                    message=f"MCP server: {reg_msg}",
                )
            )
        else:
            results.append(
                InstallResult(
                    component="mcp_server",
                    platform=self.platform_id,
                    success=True,
                    action="skipped",
                    message="MCP server: claude CLI not available (configure manually)",
                )
            )

        # Install security hooks in settings.json
        # NOTE: Claude Code only reads hooks from ~/.claude/settings.json (user-level),
        # .claude/settings.json (project), and .claude/settings.local.json (project local).
        # User-level settings.local.json is NOT a supported hooks location.
        self._step("Installing hooks")
        settings_path = self.config_dir / "settings.json"
        hook_result = install_hooks(
            settings_path,
            spellbook_dir=self.spellbook_dir,
            dry_run=self.dry_run,
        )
        results.append(
            InstallResult(
                component=hook_result.component,
                platform=self.platform_id,
                success=hook_result.success,
                action=hook_result.action,
                message=hook_result.message,
            )
        )

        # WI-0: install spellbook-managed defaultMode and permissions entries.
        # Phase 1 hard-codes mode="acceptEdits". Permissions arrays start empty;
        # Phase 2 (allow) and Phase 6b (deny via tier projection) populate them.
        self._step("Installing default mode")
        default_mode_result = install_default_mode(
            settings_path=settings_path,
            mode="acceptEdits",
            spellbook_dir=self.spellbook_dir,
            dry_run=self.dry_run,
        )
        results.append(
            InstallResult(
                component=default_mode_result.component,
                platform=self.platform_id,
                success=default_mode_result.success,
                action=default_mode_result.action,
                message=default_mode_result.message,
            )
        )

        self._step("Installing permissions")
        # WI-6b: derive L2 permissions.deny entries from tiers.toml T3 records.
        # Each T3 record is projected through tier_record_to_deny_pattern;
        # unprojectable records (regex classes, unknown tools) are warned and
        # skipped without failing the install.
        derived_deny = derive_managed_deny(self.spellbook_dir)
        permissions_result = install_permissions(
            settings_path=settings_path,
            allow=None,
            deny=derived_deny,
            ask=None,
            spellbook_dir=self.spellbook_dir,
            dry_run=self.dry_run,
        )
        results.append(
            InstallResult(
                component=permissions_result.component,
                platform=self.platform_id,
                success=permissions_result.success,
                action=permissions_result.action,
                message=permissions_result.message,
            )
        )

        return results

    def uninstall(self, skip_global_steps: bool = False) -> List["InstallResult"]:
        """Uninstall Claude Code components."""
        from ..core import InstallResult

        results = []

        # Remove demarcated section from CLAUDE.md (per-dir).
        claude_md = self.config_dir / "CLAUDE.md"
        if claude_md.exists():
            if self.dry_run:
                results.append(
                    InstallResult(
                        component="CLAUDE.md",
                        platform=self.platform_id,
                        success=True,
                        action="removed",
                        message="CLAUDE.md: would remove spellbook section",
                    )
                )
            else:
                action, _backup = remove_demarcated_section(claude_md)
                msg = f"CLAUDE.md: {action}"
                results.append(
                    InstallResult(
                        component="CLAUDE.md",
                        platform=self.platform_id,
                        success=True,
                        action=action,
                        message=msg,
                    )
                )

        # Remove ALL symlinks in managed directories (handles orphaned symlinks too)
        cleanup_dirs = [
            ("skills", self.config_dir / "skills"),
            ("commands", self.config_dir / "commands"),
            ("scripts", self.config_dir / "scripts"),
            ("agents", self.config_dir / "agents"),
        ]
        for component_name, dir_path in cleanup_dirs:
            symlink_results = cleanup_spellbook_symlinks(dir_path, dry_run=self.dry_run)
            if symlink_results:
                removed_count = sum(1 for r in symlink_results if r.action == "removed")
                results.append(
                    InstallResult(
                        component=component_name,
                        platform=self.platform_id,
                        success=True,
                        action="removed",
                        message=f"{component_name}: {removed_count} removed",
                    )
                )

        # Source-narrowed agent symlink removal: only unlink targets whose
        # resolved path lies within $SPELLBOOK_DIR/agents/. The broader
        # cleanup_spellbook_symlinks pass above already removed any broken
        # symlink in this dir (regardless of where it pointed) and any
        # symlink whose resolved-target STRING contains "spellbook". This
        # narrowed pass exists for the case where $CLAUDE_CONFIG_DIR sits
        # under a directory whose path does NOT contain "spellbook" -- the
        # substring heuristic in cleanup_spellbook_symlinks would miss
        # valid symlinks pointing at *our* spellbook source via a path
        # without that substring. uninstall_agents checks resolved-target
        # identity (parent dir == this spellbook's agents/), not substring,
        # so it catches those.
        agent_uninstall_results = uninstall_agents(
            config_dir=self.config_dir,
            spellbook_dir=self.spellbook_dir,
            dry_run=self.dry_run,
        )
        agent_removed = sum(1 for r in agent_uninstall_results if r.action == "removed")
        if agent_removed > 0:
            results.append(
                InstallResult(
                    component="agents",
                    platform=self.platform_id,
                    success=True,
                    action="removed",
                    message=f"agents: {agent_removed} removed",
                )
            )

        # Remove patterns and docs symlinks
        for component_name in ["patterns", "docs", "profiles"]:
            symlink_path = self.config_dir / component_name
            if symlink_path.is_symlink():
                if self.dry_run:
                    results.append(
                        InstallResult(
                            component=component_name,
                            platform=self.platform_id,
                            success=True,
                            action="removed",
                            message=f"{component_name}: would be removed",
                        )
                    )
                else:
                    try:
                        symlink_path.unlink()
                        results.append(
                            InstallResult(
                                component=component_name,
                                platform=self.platform_id,
                                success=True,
                                action="removed",
                                message=f"{component_name}: removed",
                            )
                        )
                    except OSError as e:
                        results.append(
                            InstallResult(
                                component=component_name,
                                platform=self.platform_id,
                                success=False,
                                action="failed",
                                message=f"{component_name}: failed to remove - {e}",
                            )
                        )

        # Uninstall MCP daemon (global). The daemon is genuinely global -- it is
        # installed once by core.py and killed once here -- so its teardown stays
        # gated behind skip_global_steps. Unregistration, by contrast, is
        # per-config-dir: the mcpServers entry lives in each config dir's
        # .claude.json, so it must run for EVERY config dir (mirroring the
        # per-dir registration in install()). Gating unregistration behind
        # skip_global_steps previously left every config dir after the first --
        # e.g. a second --claude-config-dir -- with its spellbook mcpServers
        # entry never removed on --uninstall.
        if not skip_global_steps:
            daemon_success, daemon_msg = uninstall_daemon(dry_run=self.dry_run)
            results.append(
                InstallResult(
                    component="mcp_daemon",
                    platform=self.platform_id,
                    success=daemon_success,
                    action="removed" if daemon_success else "failed",
                    message=f"MCP daemon: {daemon_msg}",
                )
            )

        # Unregister MCP servers (both stdio and HTTP variants) for THIS config
        # dir. unregister_mcp_server sets CLAUDE_CONFIG_DIR from config_dir so the
        # removal targets the right .claude.json. Runs per config dir, not gated.
        if check_claude_cli_available():
            # Remove all known spellbook MCP server names
            mcp_names = ["spellbook", "spellbook-http"]
            removed = []
            for name in mcp_names:
                success, msg = unregister_mcp_server(
                    name, dry_run=self.dry_run, config_dir=self.config_dir
                )
                if success and "not registered" not in msg.lower():
                    removed.append(name)

            if removed:
                results.append(
                    InstallResult(
                        component="mcp_server",
                        platform=self.platform_id,
                        success=True,
                        action="removed",
                        message=f"MCP servers: removed {', '.join(removed)}",
                    )
                )
            else:
                results.append(
                    InstallResult(
                        component="mcp_server",
                        platform=self.platform_id,
                        success=True,
                        action="unchanged",
                        message="MCP servers: none were registered",
                    )
                )

        # Uninstall security hooks from settings.json
        settings_path = self.config_dir / "settings.json"
        hook_result = uninstall_hooks(
            settings_path, spellbook_dir=self.spellbook_dir, dry_run=self.dry_run
        )
        results.append(
            InstallResult(
                component=hook_result.component,
                platform=self.platform_id,
                success=hook_result.success,
                action=hook_result.action,
                message=hook_result.message,
            )
        )

        # Uninstall managed permissions entries from settings.json. Both
        # uninstall_permissions and uninstall_default_mode run unconditionally
        # below (we don't bail on perms_result.success == False), so the
        # ordering here is purely a convention -- not a partial-failure
        # safety guarantee. If a strict "leave deny rules intact on perms
        # failure" guarantee is ever needed, gate the default_mode call on
        # perms_result.success.
        perms_result = uninstall_permissions(
            settings_path,
            spellbook_dir=self.spellbook_dir,
            dry_run=self.dry_run,
        )
        results.append(
            InstallResult(
                component=perms_result.component,
                platform=self.platform_id,
                success=perms_result.success,
                action=perms_result.action,
                message=perms_result.message,
            )
        )

        # Uninstall managed defaultMode from settings.json.
        dm_result = uninstall_default_mode(
            settings_path,
            spellbook_dir=self.spellbook_dir,
            dry_run=self.dry_run,
        )
        results.append(
            InstallResult(
                component=dm_result.component,
                platform=self.platform_id,
                success=dm_result.success,
                action=dm_result.action,
                message=dm_result.message,
            )
        )

        return results

    def get_context_files(self) -> List[Path]:
        """Get context files for this platform."""
        return [self.config_dir / "CLAUDE.md"]

    def get_symlinks(self) -> List[Path]:
        """Get all symlinks created by this platform."""
        symlinks = []

        # Skills
        skills_dir = self.config_dir / "skills"
        if skills_dir.exists():
            for item in skills_dir.iterdir():
                if item.is_symlink():
                    symlinks.append(item)

        # Commands
        commands_dir = self.config_dir / "commands"
        if commands_dir.exists():
            for item in commands_dir.iterdir():
                if item.is_symlink():
                    symlinks.append(item)

        # Patterns
        patterns = self.config_dir / "patterns"
        if patterns.is_symlink():
            symlinks.append(patterns)

        # Docs
        docs = self.config_dir / "docs"
        if docs.is_symlink():
            symlinks.append(docs)

        return symlinks

"""
Claude Code platform installer.
"""

from pathlib import Path
from typing import TYPE_CHECKING, List

from ..components.context_files import generate_claude_context
from ..components.hooks import install_hooks, uninstall_hooks
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
from ..demarcation import get_installed_version, remove_demarcated_section, update_demarcated_section
from .base import PlatformInstaller, PlatformStatus

if TYPE_CHECKING:
    from ..core import InstallResult


class ClaudeCodeInstaller(PlatformInstaller):
    """Installer for Claude Code platform."""

    @property
    def platform_name(self) -> str:
        return "Claude Code"

    @property
    def platform_id(self) -> str:
        return "claude_code"

    @property
    def _default_config_dir(self) -> Path:
        """The default/global Claude Code config directory (~/.claude)."""
        return Path.home() / ".claude"

    @property
    def _is_custom_config_dir(self) -> bool:
        """Whether config_dir differs from the default ~/.claude location."""
        try:
            return self.config_dir.resolve() != self._default_config_dir.resolve()
        except OSError:
            return str(self.config_dir) != str(self._default_config_dir)

    @property
    def _global_claude_md(self) -> Path:
        """The global CLAUDE.md where spellbook content always lives."""
        return self._default_config_dir / "CLAUDE.md"

    def detect(self) -> PlatformStatus:
        """Detect Claude Code installation status.

        Always checks ~/.claude/CLAUDE.md for installed version, since
        spellbook content is always written to the global location.
        """
        global_claude_md = self._global_claude_md
        installed_version = get_installed_version(global_claude_md)

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

    def install(self, force: bool = False) -> List["InstallResult"]:
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

        # Install CLAUDE.md with demarcated section.
        self._step("Updating CLAUDE.md")
        global_claude_md = self._global_claude_md
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
                # Ensure global config dir exists
                global_claude_md.parent.mkdir(parents=True, exist_ok=True)

                action, backup_path = update_demarcated_section(
                    global_claude_md, spellbook_content, self.version
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

                # If using a custom config_dir, clean up any stale spellbook
                # section from the custom location's CLAUDE.md
                if self._is_custom_config_dir:
                    custom_claude_md = self.config_dir / "CLAUDE.md"
                    cleanup_action, _backup = remove_demarcated_section(custom_claude_md)
                    if cleanup_action == "removed":
                        results.append(
                            InstallResult(
                                component="CLAUDE.md",
                                platform=self.platform_id,
                                success=True,
                                action="removed",
                                message=f"CLAUDE.md: removed stale spellbook section from custom config dir ({self.config_dir})",
                            )
                        )

        # Register MCP server connection (daemon is installed centrally by core.py)
        self._step("Registering MCP server")

        # Remove any old variant names
        for old_name in ["spellbook-http"]:
            unregister_mcp_server(old_name, dry_run=self.dry_run)

        if check_claude_cli_available():
            server_url = get_spellbook_server_url()
            reg_success, reg_msg = register_mcp_http_server(
                "spellbook", server_url, dry_run=self.dry_run
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
        hook_result = install_hooks(settings_path, spellbook_dir=self.spellbook_dir, dry_run=self.dry_run)
        results.append(
            InstallResult(
                component=hook_result.component,
                platform=self.platform_id,
                success=hook_result.success,
                action=hook_result.action,
                message=hook_result.message,
            )
        )

        return results

    def uninstall(self) -> List["InstallResult"]:
        """Uninstall Claude Code components."""
        from ..core import InstallResult

        results = []

        # Remove demarcated section from CLAUDE.md.
        # Always target ~/.claude/CLAUDE.md (the global location).
        # If config_dir is custom, also check and clean the custom location.
        global_claude_md = self._global_claude_md
        if global_claude_md.exists():
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
                action, _backup = remove_demarcated_section(global_claude_md)
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

        # If using custom config_dir, also clean up any stale section there
        if self._is_custom_config_dir:
            custom_claude_md = self.config_dir / "CLAUDE.md"
            if custom_claude_md.exists():
                if self.dry_run:
                    results.append(
                        InstallResult(
                            component="CLAUDE.md",
                            platform=self.platform_id,
                            success=True,
                            action="removed",
                            message="CLAUDE.md: would remove spellbook section from custom config dir",
                        )
                    )
                else:
                    custom_action, _backup = remove_demarcated_section(custom_claude_md)
                    if custom_action == "removed":
                        results.append(
                            InstallResult(
                                component="CLAUDE.md",
                                platform=self.platform_id,
                                success=True,
                                action="removed",
                                message=f"CLAUDE.md: removed stale spellbook section from custom config dir ({self.config_dir})",
                            )
                        )

        # Remove ALL symlinks in managed directories (handles orphaned symlinks too)
        cleanup_dirs = [
            ("skills", self.config_dir / "skills"),
            ("commands", self.config_dir / "commands"),
            ("scripts", self.config_dir / "scripts"),
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

        # Remove patterns and docs symlinks
        for component_name in ["patterns", "docs"]:
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

        # Uninstall MCP daemon
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

        # Unregister MCP servers (both stdio and HTTP variants)
        if check_claude_cli_available():
            # Remove all known spellbook MCP server names
            mcp_names = ["spellbook", "spellbook-http"]
            removed = []
            for name in mcp_names:
                success, msg = unregister_mcp_server(name, dry_run=self.dry_run)
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
        hook_result = uninstall_hooks(settings_path, spellbook_dir=self.spellbook_dir, dry_run=self.dry_run)
        results.append(
            InstallResult(
                component=hook_result.component,
                platform=self.platform_id,
                success=hook_result.success,
                action=hook_result.action,
                message=hook_result.message,
            )
        )

        return results

    def get_context_files(self) -> List[Path]:
        """Get context files for this platform.

        Always returns the global ~/.claude/CLAUDE.md since spellbook
        content is always written there.
        """
        return [self._global_claude_md]

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

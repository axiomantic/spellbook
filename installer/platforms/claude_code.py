"""
Claude Code platform installer.
"""

from pathlib import Path
from typing import TYPE_CHECKING, List

from ..components.context_files import generate_claude_context
from ..components.mcp import check_claude_cli_available, register_mcp_server, unregister_mcp_server
from ..components.symlinks import (
    create_command_symlinks,
    create_skill_symlinks,
    create_symlink,
    remove_spellbook_symlinks,
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

    def detect(self) -> PlatformStatus:
        """Detect Claude Code installation status."""
        context_file = self.config_dir / "CLAUDE.md"
        installed_version = get_installed_version(context_file)

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
        for subdir in ["skills", "commands", "scripts", "agents", "patterns", "docs", "plans"]:
            subdir_path = self.config_dir / subdir
            if not self.dry_run:
                subdir_path.mkdir(parents=True, exist_ok=True)

        # Install skills
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

        # Install CLAUDE.md with demarcated section
        context_file = self.config_dir / "CLAUDE.md"
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
                    context_file, spellbook_content, self.version
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

        # Register MCP server (clean up old variants first)
        if check_claude_cli_available():
            server_path = self.spellbook_dir / "spellbook_mcp" / "server.py"
            if server_path.exists():
                # Remove any old variant names before installing
                # This ensures clean upgrade from older versions
                for old_name in ["spellbook-http"]:
                    unregister_mcp_server(old_name, dry_run=self.dry_run)

                success, msg = register_mcp_server(
                    "spellbook", ["python3", str(server_path)], dry_run=self.dry_run
                )
                results.append(
                    InstallResult(
                        component="mcp_server",
                        platform=self.platform_id,
                        success=success,
                        action="installed" if success else "failed",
                        message=f"MCP server: {msg}",
                    )
                )
        else:
            results.append(
                InstallResult(
                    component="mcp_server",
                    platform=self.platform_id,
                    success=True,
                    action="skipped",
                    message="MCP server: claude CLI not available",
                )
            )

        return results

    def uninstall(self) -> List["InstallResult"]:
        """Uninstall Claude Code components."""
        from ..core import InstallResult

        results = []

        # Remove demarcated section from CLAUDE.md
        context_file = self.config_dir / "CLAUDE.md"
        if context_file.exists():
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
                action, backup_path = remove_demarcated_section(context_file)
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

        # Remove skill symlinks
        skills_dir = self.config_dir / "skills"
        symlink_results = remove_spellbook_symlinks(
            skills_dir, self.spellbook_dir, dry_run=self.dry_run
        )
        if symlink_results:
            removed_count = sum(1 for r in symlink_results if r.action == "removed")
            results.append(
                InstallResult(
                    component="skills",
                    platform=self.platform_id,
                    success=True,
                    action="removed",
                    message=f"skills: {removed_count} removed",
                )
            )

        # Remove command symlinks
        commands_dir = self.config_dir / "commands"
        symlink_results = remove_spellbook_symlinks(
            commands_dir, self.spellbook_dir, dry_run=self.dry_run
        )
        if symlink_results:
            removed_count = sum(1 for r in symlink_results if r.action == "removed")
            results.append(
                InstallResult(
                    component="commands",
                    platform=self.platform_id,
                    success=True,
                    action="removed",
                    message=f"commands: {removed_count} removed",
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

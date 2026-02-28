"""
Codex platform installer.
"""

import re
from pathlib import Path
from typing import TYPE_CHECKING, List, Tuple

from ..components.context_files import generate_codex_context
from ..components.mcp import get_spellbook_server_url
from ..components.symlinks import (
    create_symlink,
    create_skill_symlinks,
    remove_symlink,
    remove_spellbook_symlinks,
)
from ..demarcation import get_installed_version, remove_demarcated_section, update_demarcated_section
from .base import PlatformInstaller, PlatformStatus

if TYPE_CHECKING:
    from ..core import InstallResult


# TOML section markers for spellbook MCP config
TOML_START_MARKER = "# SPELLBOOK:START"
TOML_END_MARKER = "# SPELLBOOK:END"


def _generate_mcp_toml_section() -> str:
    """Generate the TOML section for spellbook MCP server (HTTP transport)."""
    url = get_spellbook_server_url()
    return f"""{TOML_START_MARKER}
[mcp_servers.spellbook]
url = "{url}"
{TOML_END_MARKER}
"""


def _add_mcp_to_config_toml(
    config_path: Path, dry_run: bool = False
) -> Tuple[bool, str]:
    """Add spellbook MCP server to Codex config.toml (HTTP transport)."""
    section = _generate_mcp_toml_section()

    if dry_run:
        return (True, "would register MCP server")

    if config_path.exists():
        content = config_path.read_text(encoding="utf-8")
        # Check if already present
        if TOML_START_MARKER in content:
            # Update existing section
            pattern = re.compile(
                rf"{re.escape(TOML_START_MARKER)}.*?{re.escape(TOML_END_MARKER)}\n?",
                re.DOTALL,
            )
            new_content = pattern.sub(section, content)
            config_path.write_text(new_content, encoding="utf-8")
            return (True, "updated MCP server config")
        else:
            # Append new section
            if not content.endswith("\n"):
                content += "\n"
            content += "\n" + section
            config_path.write_text(content, encoding="utf-8")
            return (True, "registered MCP server")
    else:
        # Create new config.toml
        config_path.write_text(section, encoding="utf-8")
        return (True, "created config.toml with MCP server")


def _remove_mcp_from_config_toml(
    config_path: Path, dry_run: bool = False
) -> Tuple[bool, str]:
    """Remove spellbook MCP server from Codex config.toml."""
    if not config_path.exists():
        return (True, "config.toml not found")

    content = config_path.read_text(encoding="utf-8")
    if TOML_START_MARKER not in content:
        return (True, "MCP server was not configured")

    if dry_run:
        return (True, "would remove MCP server config")

    # Remove the section
    pattern = re.compile(
        rf"\n?{re.escape(TOML_START_MARKER)}.*?{re.escape(TOML_END_MARKER)}\n?",
        re.DOTALL,
    )
    new_content = pattern.sub("", content)
    config_path.write_text(new_content, encoding="utf-8")
    return (True, "removed MCP server config")


class CodexInstaller(PlatformInstaller):
    """Installer for Codex platform."""

    @property
    def platform_name(self) -> str:
        return "Codex"

    @property
    def platform_id(self) -> str:
        return "codex"

    def detect(self) -> PlatformStatus:
        """Detect Codex installation status."""
        context_file = self.config_dir / "AGENTS.md"
        installed_version = get_installed_version(context_file)

        spellbook_link = self.config_dir / "spellbook"
        has_link = spellbook_link.is_symlink()

        # Check if MCP server is registered
        config_toml = self.config_dir / "config.toml"
        has_mcp = False
        if config_toml.exists():
            content = config_toml.read_text(encoding="utf-8")
            has_mcp = TOML_START_MARKER in content

        return PlatformStatus(
            platform=self.platform_id,
            available=self.config_dir.exists(),
            installed=installed_version is not None or has_link or has_mcp,
            version=installed_version,
            details={
                "config_dir": str(self.config_dir),
                "spellbook_link": has_link,
                "mcp_registered": has_mcp,
            },
        )

    def install(self, force: bool = False) -> List["InstallResult"]:
        """Install Codex components."""
        from ..core import InstallResult

        results = []

        if not self.config_dir.exists():
            results.append(
                InstallResult(
                    component="platform",
                    platform=self.platform_id,
                    success=True,
                    action="skipped",
                    message="~/.codex not found",
                )
            )
            return results

        # Create symlink to spellbook root
        self._step("Creating spellbook link")
        spellbook_link = self.config_dir / "spellbook"
        link_result = create_symlink(self.spellbook_dir, spellbook_link, self.dry_run)
        results.append(
            InstallResult(
                component="spellbook_link",
                platform=self.platform_id,
                success=link_result.success,
                action=link_result.action,
                message=f"spellbook link: {link_result.action}",
            )
        )

        # Create per-skill symlinks for native discovery
        self._step("Installing skills")
        skills_dir = self.config_dir / "skills"
        if not self.dry_run:
            skills_dir.mkdir(parents=True, exist_ok=True)

        skills_results = create_skill_symlinks(
            self.spellbook_dir / "skills",
            skills_dir,
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

        # Install AGENTS.md with demarcated section
        self._step("Updating AGENTS.md")
        context_file = self.config_dir / "AGENTS.md"
        spellbook_content = generate_codex_context(self.spellbook_dir)

        if spellbook_content:
            if self.dry_run:
                results.append(
                    InstallResult(
                        component="AGENTS.md",
                        platform=self.platform_id,
                        success=True,
                        action="installed",
                        message="AGENTS.md: would be updated",
                    )
                )
            else:
                action, backup_path = update_demarcated_section(
                    context_file, spellbook_content, self.version
                )
                msg = f"AGENTS.md: {action}"
                if backup_path:
                    msg += f" (backup: {backup_path.name})"
                results.append(
                    InstallResult(
                        component="AGENTS.md",
                        platform=self.platform_id,
                        success=True,
                        action=action,
                        message=msg,
                    )
                )

        # Register MCP server connection (daemon is installed centrally by core.py)
        self._step("Registering MCP server")
        config_toml = self.config_dir / "config.toml"
        success, msg = _add_mcp_to_config_toml(config_toml, self.dry_run)
        results.append(
            InstallResult(
                component="mcp_server",
                platform=self.platform_id,
                success=success,
                action="installed" if success else "failed",
                message=f"MCP server: {msg}",
            )
        )

        return results

    def uninstall(self) -> List["InstallResult"]:
        """Uninstall Codex components."""
        from ..core import InstallResult

        results = []

        if not self.config_dir.exists():
            return results

        # Remove demarcated section from AGENTS.md
        context_file = self.config_dir / "AGENTS.md"
        if context_file.exists():
            if self.dry_run:
                results.append(
                    InstallResult(
                        component="AGENTS.md",
                        platform=self.platform_id,
                        success=True,
                        action="removed",
                        message="AGENTS.md: would remove spellbook section",
                    )
                )
            else:
                action, backup_path = remove_demarcated_section(context_file)
                msg = f"AGENTS.md: {action}"
                if backup_path:
                    msg += f" (backup: {backup_path.name})"
                results.append(
                    InstallResult(
                        component="AGENTS.md",
                        platform=self.platform_id,
                        success=True,
                        action=action,
                        message=msg,
                    )
                )

        # Remove spellbook symlink
        spellbook_link = self.config_dir / "spellbook"
        if spellbook_link.is_symlink():
            link_result = remove_symlink(
                spellbook_link, verify_source=self.spellbook_dir, dry_run=self.dry_run
            )
            results.append(
                InstallResult(
                    component="spellbook_link",
                    platform=self.platform_id,
                    success=link_result.success,
                    action=link_result.action,
                    message=f"spellbook link: {link_result.action}",
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

        # Remove MCP server from config.toml
        config_toml = self.config_dir / "config.toml"
        success, msg = _remove_mcp_from_config_toml(config_toml, self.dry_run)
        results.append(
            InstallResult(
                component="mcp_server",
                platform=self.platform_id,
                success=success,
                action="removed" if "removed" in msg else "skipped",
                message=f"MCP server: {msg}",
            )
        )

        return results

    def get_context_files(self) -> List[Path]:
        """Get context files for this platform."""
        return [self.config_dir / "AGENTS.md"]

    def get_symlinks(self) -> List[Path]:
        """Get all symlinks created by this platform."""
        symlinks = []

        # Spellbook root link
        spellbook_link = self.config_dir / "spellbook"
        if spellbook_link.is_symlink():
            symlinks.append(spellbook_link)

        # Skills
        skills_dir = self.config_dir / "skills"
        if skills_dir.exists():
            for item in skills_dir.iterdir():
                if item.is_symlink():
                    symlinks.append(item)

        return symlinks

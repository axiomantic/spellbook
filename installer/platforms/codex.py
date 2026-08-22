"""
Codex platform installer.
"""

import os
import re
from pathlib import Path
from typing import TYPE_CHECKING, List, Tuple

from ..components.mcp import get_spellbook_server_url
from ..components.symlinks import (
    create_symlink,
    create_skill_symlinks,
    remove_symlink,
    remove_spellbook_symlinks,
)
from ..components.rule_bundle import DELIVERY_MARKER_PREFIX
from ..demarcation import get_installed_version, remove_demarcated_section
from .base import RULE_DELIVERY_FLAT, PlatformInstaller, PlatformStatus

if TYPE_CHECKING:
    from ..core import InstallResult


# TOML section markers for spellbook MCP config
TOML_START_MARKER = "# SPELLBOOK:START"
TOML_END_MARKER = "# SPELLBOOK:END"


def _generate_mcp_toml_section() -> str:
    """Generate the TOML section for spellbook MCP server (HTTP transport)."""
    url = get_spellbook_server_url()
    lines = [
        TOML_START_MARKER,
        "[mcp_servers.spellbook]",
        f'url = "{url}"',
    ]
    lines.append(TOML_END_MARKER)
    lines.append("")
    return "\n".join(lines)


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

    rule_delivery = RULE_DELIVERY_FLAT

    @property
    def platform_name(self) -> str:
        return "Codex"

    @property
    def platform_id(self) -> str:
        return "codex"

    def rule_bundle_path(self) -> Path:
        """Codex reads AGENTS.override.md then AGENTS.md, and nothing else.

        The generated bundle is written here as a real file. The former
        AGENTS.spellbook.md sidecar was inert -- Codex has no import directive
        and never scanned for siblings -- so it is dropped rather than
        repointed. The 32,768-byte project_doc_max_bytes governs project docs,
        not this global file, so no cap applies.
        """
        return self.config_dir / "AGENTS.md"

    def rule_bundle_preserve_existing(self) -> bool:
        """Never clobber a user's own ``~/.codex/AGENTS.md``.

        This path is the user's global Codex instruction file, not spellbook's.
        Codex reads exactly one of AGENTS.override.md / AGENTS.md, so replacing
        it outright does not merely add spellbook's rules -- it stops the user's
        own instructions loading at all. Their bytes are kept first, verbatim,
        and the bundle follows in a demarcated region later installs replace in
        place. Same class of file, and same treatment, as ForgeCode's.
        """
        return True

    def legacy_rule_paths(self) -> List[Path]:
        return [self.config_dir / "AGENTS.spellbook.md"]

    def legacy_context_files(self) -> List[Path]:
        return [self.config_dir / "AGENTS.md"]

    def detect(self) -> PlatformStatus:
        """Detect Codex installation status."""
        context_file = self.config_dir / "AGENTS.md"
        installed_version = get_installed_version(context_file)

        spellbook_link = self.config_dir / "spellbook"
        has_link = spellbook_link.is_symlink()
        has_sidecar = any(os.path.lexists(path) for path in self.legacy_rule_paths())
        has_bundle = False
        if context_file.exists():
            try:
                has_bundle = DELIVERY_MARKER_PREFIX in context_file.read_text(
                    encoding="utf-8"
                )
            except OSError:
                has_bundle = False

        # Check if MCP server is registered
        config_toml = self.config_dir / "config.toml"
        has_mcp = False
        if config_toml.exists():
            content = config_toml.read_text(encoding="utf-8")
            has_mcp = TOML_START_MARKER in content

        installed = (
            installed_version is not None
            or has_link
            or has_sidecar
            or has_bundle
            or has_mcp
        )

        return PlatformStatus(
            platform=self.platform_id,
            available=self.config_dir.exists(),
            installed=installed,
            version=self.version if installed else None,
            details={
                "config_dir": str(self.config_dir),
                "spellbook_link": has_link,
                "mcp_registered": has_mcp,
            },
        )

    def install(self, force: bool = False, skip_global_steps: bool = False) -> List["InstallResult"]:
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

        # Strip legacy demarcated section from AGENTS.md if present
        context_file = self.config_dir / "AGENTS.md"

        # Generate the rule bundle at ~/.codex/AGENTS.md, the only global
        # instruction path Codex reads, and drop the inert sidecar.
        self._step("Installing rule modules")
        rule_results = self.install_rule_modules()
        results.extend(rule_results)

        # Strip the legacy demarcated block only AFTER delivery succeeds.
        # Stripping first would leave a user whose delivery failed with
        # neither the old interpolated rules nor the new modules.
        if (
            all(r.success for r in rule_results)
            and context_file.exists()
            and not self.dry_run
        ):
            remove_demarcated_section(context_file)

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

    def uninstall(self, skip_global_steps: bool = False) -> List["InstallResult"]:
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

        # Remove the generated rule bundle and any retired sidecar.
        results.extend(self.uninstall_rule_modules())

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
        """Get the generated rule artifact managed by this platform."""
        return [self.rule_bundle_path()]

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

"""
Codex platform installer.
"""

from pathlib import Path
from typing import TYPE_CHECKING, List

from ..components.context_files import generate_codex_context
from ..components.symlinks import create_symlink, remove_symlink
from ..demarcation import get_installed_version, remove_demarcated_section, update_demarcated_section
from .base import PlatformInstaller, PlatformStatus

if TYPE_CHECKING:
    from ..core import InstallResult


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

        return PlatformStatus(
            platform=self.platform_id,
            available=self.config_dir.exists(),
            installed=installed_version is not None or has_link,
            version=installed_version,
            details={
                "config_dir": str(self.config_dir),
                "spellbook_link": has_link,
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

        # Install AGENTS.md with demarcated section
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

        # Verify CLI script exists and is executable
        cli_script = self.spellbook_dir / ".codex" / "spellbook-codex"
        if cli_script.exists():
            results.append(
                InstallResult(
                    component="cli_script",
                    platform=self.platform_id,
                    success=True,
                    action="installed",
                    message="CLI script: ready at .codex/spellbook-codex",
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

        return results

    def get_context_files(self) -> List[Path]:
        """Get context files for this platform."""
        return [self.config_dir / "AGENTS.md"]

    def get_symlinks(self) -> List[Path]:
        """Get all symlinks created by this platform."""
        symlinks = []

        spellbook_link = self.config_dir / "spellbook"
        if spellbook_link.is_symlink():
            symlinks.append(spellbook_link)

        return symlinks

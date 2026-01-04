"""
OpenCode platform installer.
"""

from pathlib import Path
from typing import TYPE_CHECKING, List

from ..components.symlinks import create_skill_symlinks, remove_spellbook_symlinks
from ..demarcation import get_installed_version
from .base import PlatformInstaller, PlatformStatus

if TYPE_CHECKING:
    from ..core import InstallResult


class OpenCodeInstaller(PlatformInstaller):
    """Installer for OpenCode platform."""

    @property
    def platform_name(self) -> str:
        return "OpenCode"

    @property
    def platform_id(self) -> str:
        return "opencode"

    def detect(self) -> PlatformStatus:
        """Detect OpenCode installation status."""
        # OpenCode uses flat .md files in skills directory
        skills_dir = self.config_dir / "skills"
        has_skills = False

        if skills_dir.exists():
            # Check if any spellbook skills are symlinked
            for item in skills_dir.iterdir():
                if item.is_symlink():
                    target = item.resolve()
                    if "spellbook" in str(target):
                        has_skills = True
                        break

        return PlatformStatus(
            platform=self.platform_id,
            available=self.config_dir.exists(),
            installed=has_skills,
            version=None,  # No version tracking for symlink-only platform
            details={"config_dir": str(self.config_dir)},
        )

    def install(self, force: bool = False) -> List["InstallResult"]:
        """Install OpenCode components."""
        from ..core import InstallResult

        results = []

        if not self.config_dir.exists():
            results.append(
                InstallResult(
                    component="platform",
                    platform=self.platform_id,
                    success=True,
                    action="skipped",
                    message="~/.opencode not found",
                )
            )
            return results

        # Create skills directory
        skills_dir = self.config_dir / "skills"
        if not self.dry_run:
            skills_dir.mkdir(parents=True, exist_ok=True)

        # Install skills as flat .md files (OpenCode format)
        skills_results = create_skill_symlinks(
            self.spellbook_dir / "skills",
            skills_dir,
            as_directories=False,  # Flat .md files
            dry_run=self.dry_run,
        )
        skill_count = sum(1 for r in skills_results if r.success)

        results.append(
            InstallResult(
                component="skills",
                platform=self.platform_id,
                success=skill_count > 0 or not skills_results,
                action="installed" if skills_results else "skipped",
                message=f"skills: {skill_count} installed (as .md files)",
            )
        )

        return results

    def uninstall(self) -> List["InstallResult"]:
        """Uninstall OpenCode components."""
        from ..core import InstallResult

        results = []

        if not self.config_dir.exists():
            return results

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

        return results

    def get_context_files(self) -> List[Path]:
        """Get context files for this platform."""
        return []  # OpenCode doesn't have a separate context file

    def get_symlinks(self) -> List[Path]:
        """Get all symlinks created by this platform."""
        symlinks = []

        skills_dir = self.config_dir / "skills"
        if skills_dir.exists():
            for item in skills_dir.iterdir():
                if item.is_symlink():
                    symlinks.append(item)

        return symlinks

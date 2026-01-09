"""
Gemini CLI platform installer.

Uses Gemini's native extension system via `gemini extensions link`.
The extension provides:
- MCP server for skill discovery and loading
- Context via GEMINI.md in the extension directory
"""

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, List, Tuple

from ..components.symlinks import (
    create_fun_mode_symlinks,
    get_fun_mode_config_dir,
    remove_fun_mode_symlinks,
)
from .base import PlatformInstaller, PlatformStatus

if TYPE_CHECKING:
    from ..core import InstallResult


def check_gemini_cli_available() -> bool:
    """Check if gemini CLI is available."""
    try:
        result = subprocess.run(
            ["gemini", "--version"], capture_output=True, text=True, timeout=5
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


def get_linked_extensions() -> List[str]:
    """Get list of linked extension names."""
    try:
        result = subprocess.run(
            ["gemini", "extensions", "list"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            # Parse output to find linked extensions
            # Format varies, but we're looking for "spellbook"
            return [line.strip() for line in result.stdout.splitlines() if line.strip()]
        return []
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return []


def link_extension(extension_path: Path, dry_run: bool = False) -> Tuple[bool, str]:
    """
    Link a Gemini extension using `gemini extensions link`.

    Args:
        extension_path: Path to extension directory containing gemini-extension.json
        dry_run: If True, don't actually link

    Returns: (success, message)
    """
    if not check_gemini_cli_available():
        return (False, "gemini CLI not available")

    if dry_run:
        return (True, f"would link extension from {extension_path}")

    try:
        result = subprocess.run(
            ["gemini", "extensions", "link", str(extension_path)],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            return (True, "extension linked")
        else:
            error = result.stderr.strip() or result.stdout.strip()
            # Check if already linked
            if "already" in error.lower() or "exists" in error.lower():
                return (True, "extension already linked")
            return (False, f"link failed: {error}")

    except subprocess.TimeoutExpired:
        return (False, "command timed out")
    except OSError as e:
        return (False, str(e))


def unlink_extension(name: str, dry_run: bool = False) -> Tuple[bool, str]:
    """Unlink a Gemini extension using `gemini extensions unlink`."""
    if not check_gemini_cli_available():
        return (False, "gemini CLI not available")

    if dry_run:
        return (True, f"would unlink extension {name}")

    try:
        result = subprocess.run(
            ["gemini", "extensions", "unlink", name],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            return (True, "extension unlinked")
        else:
            error = result.stderr.strip() or result.stdout.strip()
            if "not found" in error.lower() or "not linked" in error.lower():
                return (True, "extension was not linked")
            return (False, f"unlink failed: {error}")

    except subprocess.TimeoutExpired:
        return (False, "command timed out")
    except OSError as e:
        return (False, str(e))


class GeminiInstaller(PlatformInstaller):
    """Installer for Gemini CLI platform using native extensions."""

    def _ensure_extension_skills_symlinks(self) -> Tuple[int, int]:
        """
        Ensure skills symlinks exist in Gemini extension.

        Creates relative symlinks: extensions/gemini/skills/<skill-name> -> ../../skills/<skill-name>/

        Returns: (created_count, error_count)
        """
        import os

        extension_skills = self.extension_dir / "skills"
        source_skills = self.spellbook_dir / "skills"

        if not self.dry_run:
            extension_skills.mkdir(parents=True, exist_ok=True)

        created = 0
        errors = 0

        for skill_dir in source_skills.iterdir():
            if not skill_dir.is_dir():
                continue

            skill_name = skill_dir.name
            target = extension_skills / skill_name

            # Create relative path: ../../../skills/<skill-name>
            # From extensions/gemini/skills/<skill-name> to skills/<skill-name>
            relative_source = Path("..") / ".." / ".." / "skills" / skill_name

            if self.dry_run:
                created += 1
                continue

            try:
                # Remove existing symlink if present
                if target.is_symlink() or target.exists():
                    if target.is_dir() and not target.is_symlink():
                        errors += 1
                        continue
                    target.unlink()

                # Create relative symlink
                target.symlink_to(relative_source)
                created += 1

            except OSError:
                errors += 1

        return (created, errors)

    @property
    def platform_name(self) -> str:
        return "Gemini CLI"

    @property
    def platform_id(self) -> str:
        return "gemini"

    @property
    def extension_dir(self) -> Path:
        """Get the spellbook extension directory in the repo."""
        return self.spellbook_dir / "extensions" / "gemini"

    @property
    def linked_extension_path(self) -> Path:
        """Get the path where the extension would be linked."""
        return self.config_dir / "extensions" / "spellbook"

    def detect(self) -> PlatformStatus:
        """Detect Gemini CLI installation status."""
        # Check if extension is linked (symlink exists)
        is_linked = (
            self.linked_extension_path.is_symlink()
            or self.linked_extension_path.exists()
        )

        # Try to resolve if it points to our extension
        points_to_spellbook = False
        if is_linked and self.linked_extension_path.is_symlink():
            try:
                target = self.linked_extension_path.resolve()
                points_to_spellbook = "spellbook" in str(target)
            except OSError:
                pass

        return PlatformStatus(
            platform=self.platform_id,
            available=self.config_dir.exists() or check_gemini_cli_available(),
            installed=is_linked and points_to_spellbook,
            version=self.version if points_to_spellbook else None,
            details={
                "config_dir": str(self.config_dir),
                "extension_linked": is_linked,
                "gemini_cli_available": check_gemini_cli_available(),
            },
        )

    def install(self, force: bool = False) -> List["InstallResult"]:
        """Install Gemini CLI extension via `gemini extensions link`."""
        from ..core import InstallResult

        results = []

        # Check if gemini CLI is available
        if not check_gemini_cli_available():
            results.append(
                InstallResult(
                    component="platform",
                    platform=self.platform_id,
                    success=True,
                    action="skipped",
                    message="gemini CLI not available",
                )
            )
            return results

        # Check if extension source exists
        if not self.extension_dir.exists():
            results.append(
                InstallResult(
                    component="extension",
                    platform=self.platform_id,
                    success=False,
                    action="failed",
                    message=f"extension not found at {self.extension_dir}",
                )
            )
            return results

        # Ensure skills symlinks exist in extension
        created, errors = self._ensure_extension_skills_symlinks()
        if created > 0 or errors > 0:
            results.append(
                InstallResult(
                    component="extension_skills",
                    platform=self.platform_id,
                    success=errors == 0,
                    action="installed",
                    message=f"extension skills: {created} linked, {errors} errors",
                )
            )

        # Link the extension
        success, msg = link_extension(self.extension_dir, dry_run=self.dry_run)
        results.append(
            InstallResult(
                component="extension",
                platform=self.platform_id,
                success=success,
                action="installed" if success else "failed",
                message=f"extension: {msg}",
            )
        )

        # Install fun-mode symlinks to ~/.config/spellbook/fun/
        fun_results = create_fun_mode_symlinks(self.spellbook_dir, dry_run=self.dry_run)
        if fun_results:
            fun_count = sum(1 for r in fun_results if r.success)
            results.append(
                InstallResult(
                    component="fun-mode",
                    platform=self.platform_id,
                    success=fun_count > 0,
                    action="installed" if fun_count > 0 else "skipped",
                    message=f"fun-mode: {fun_count} files linked",
                )
            )

        return results

    def uninstall(self) -> List["InstallResult"]:
        """Uninstall Gemini CLI extension via `gemini extensions unlink`."""
        from ..core import InstallResult

        results = []

        if not check_gemini_cli_available():
            # Try to remove symlink manually if CLI not available
            if self.linked_extension_path.is_symlink():
                if self.dry_run:
                    results.append(
                        InstallResult(
                            component="extension",
                            platform=self.platform_id,
                            success=True,
                            action="removed",
                            message="extension: would remove symlink (CLI not available)",
                        )
                    )
                else:
                    try:
                        self.linked_extension_path.unlink()
                        results.append(
                            InstallResult(
                                component="extension",
                                platform=self.platform_id,
                                success=True,
                                action="removed",
                                message="extension: removed symlink (CLI not available)",
                            )
                        )
                    except OSError as e:
                        results.append(
                            InstallResult(
                                component="extension",
                                platform=self.platform_id,
                                success=False,
                                action="failed",
                                message=f"extension: failed to remove symlink: {e}",
                            )
                        )
            return results

        # Unlink using CLI
        success, msg = unlink_extension("spellbook", dry_run=self.dry_run)
        results.append(
            InstallResult(
                component="extension",
                platform=self.platform_id,
                success=success,
                action="removed" if success else "failed",
                message=f"extension: {msg}",
            )
        )

        # Remove fun-mode symlinks
        fun_results = remove_fun_mode_symlinks(self.spellbook_dir, dry_run=self.dry_run)
        if fun_results:
            removed_count = sum(1 for r in fun_results if r.action == "removed")
            results.append(
                InstallResult(
                    component="fun-mode",
                    platform=self.platform_id,
                    success=True,
                    action="removed",
                    message=f"fun-mode: {removed_count} removed",
                )
            )

        return results

    def get_context_files(self) -> List[Path]:
        """Get context files for this platform."""
        # Context is provided via extension's GEMINI.md, not a separate file
        return []

    def get_symlinks(self) -> List[Path]:
        """Get all symlinks created by this platform."""
        symlinks = []

        if self.linked_extension_path.is_symlink():
            symlinks.append(self.linked_extension_path)

        # Fun-mode symlinks in ~/.config/spellbook/fun/
        fun_dir = get_fun_mode_config_dir()
        if fun_dir.exists():
            for item in fun_dir.iterdir():
                if item.is_symlink():
                    symlinks.append(item)

        return symlinks

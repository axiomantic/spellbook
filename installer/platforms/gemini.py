"""
Gemini CLI platform installer.
"""

import json
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, List, Tuple

from ..components.context_files import generate_gemini_context
from ..demarcation import get_installed_version, remove_demarcated_section, update_demarcated_section
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


def install_gemini_extension(extension_path: Path, dry_run: bool = False) -> Tuple[bool, str]:
    """
    Install a Gemini extension using the CLI.

    Args:
        extension_path: Path to extension directory containing gemini-extension.json
        dry_run: If True, don't actually install

    Returns: (success, message)
    """
    if not check_gemini_cli_available():
        return (False, "gemini CLI not available")

    if dry_run:
        return (True, "Would install extension")

    try:
        # Gemini extensions install takes a path
        result = subprocess.run(
            ["gemini", "extensions", "install", str(extension_path)],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            return (True, "extension installed")
        else:
            error = result.stderr.strip() or result.stdout.strip()
            # Check if already installed
            if "already" in error.lower():
                return (True, "extension already installed")
            return (False, f"install failed: {error}")

    except subprocess.TimeoutExpired:
        return (False, "command timed out")
    except OSError as e:
        return (False, str(e))


def uninstall_gemini_extension(name: str, dry_run: bool = False) -> Tuple[bool, str]:
    """Uninstall a Gemini extension."""
    if not check_gemini_cli_available():
        return (False, "gemini CLI not available")

    if dry_run:
        return (True, "Would uninstall extension")

    try:
        result = subprocess.run(
            ["gemini", "extensions", "uninstall", name],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            return (True, "extension uninstalled")
        else:
            error = result.stderr.strip() or result.stdout.strip()
            if "not found" in error.lower() or "not installed" in error.lower():
                return (True, "extension was not installed")
            return (False, f"uninstall failed: {error}")

    except subprocess.TimeoutExpired:
        return (False, "command timed out")
    except OSError as e:
        return (False, str(e))


class GeminiInstaller(PlatformInstaller):
    """Installer for Gemini CLI platform."""

    @property
    def platform_name(self) -> str:
        return "Gemini CLI"

    @property
    def platform_id(self) -> str:
        return "gemini"

    @property
    def extensions_dir(self) -> Path:
        """Get the extensions directory for spellbook."""
        return self.config_dir / "extensions" / "spellbook"

    def detect(self) -> PlatformStatus:
        """Detect Gemini CLI installation status."""
        context_file = self.extensions_dir / "GEMINI.md"
        installed_version = get_installed_version(context_file)

        manifest_file = self.extensions_dir / "gemini-extension.json"
        has_manifest = manifest_file.exists()

        return PlatformStatus(
            platform=self.platform_id,
            available=self.config_dir.exists(),
            installed=installed_version is not None or has_manifest,
            version=installed_version,
            details={
                "config_dir": str(self.config_dir),
                "extensions_dir": str(self.extensions_dir),
                "has_manifest": has_manifest,
            },
        )

    def install(self, force: bool = False) -> List["InstallResult"]:
        """Install Gemini CLI components."""
        from ..core import InstallResult

        results = []

        if not self.config_dir.exists():
            results.append(
                InstallResult(
                    component="platform",
                    platform=self.platform_id,
                    success=True,
                    action="skipped",
                    message="~/.gemini not found",
                )
            )
            return results

        # Create extensions directory
        if not self.dry_run:
            self.extensions_dir.mkdir(parents=True, exist_ok=True)

        # Generate and install extension manifest
        template_file = self.spellbook_dir / "extensions" / "gemini" / "gemini-extension.json"
        manifest_file = self.extensions_dir / "gemini-extension.json"

        if template_file.exists():
            if self.dry_run:
                results.append(
                    InstallResult(
                        component="manifest",
                        platform=self.platform_id,
                        success=True,
                        action="installed",
                        message="extension manifest: would be created",
                    )
                )
            else:
                try:
                    # Read template and replace placeholder
                    template_content = template_file.read_text(encoding="utf-8")
                    server_path = self.spellbook_dir / "spellbook_mcp" / "server.py"
                    content = template_content.replace("__SERVER_PATH__", str(server_path))

                    # Update version
                    try:
                        data = json.loads(content)
                        data["version"] = self.version
                        content = json.dumps(data, indent=2) + "\n"
                    except json.JSONDecodeError:
                        pass

                    manifest_file.write_text(content, encoding="utf-8")
                    results.append(
                        InstallResult(
                            component="manifest",
                            platform=self.platform_id,
                            success=True,
                            action="installed",
                            message="extension manifest: created",
                        )
                    )
                except OSError as e:
                    results.append(
                        InstallResult(
                            component="manifest",
                            platform=self.platform_id,
                            success=False,
                            action="failed",
                            message=f"extension manifest: {e}",
                        )
                    )
        else:
            results.append(
                InstallResult(
                    component="manifest",
                    platform=self.platform_id,
                    success=True,
                    action="skipped",
                    message="extension manifest: template not found",
                )
            )

        # Install GEMINI.md with demarcated section
        context_file = self.extensions_dir / "GEMINI.md"
        spellbook_content = generate_gemini_context(self.spellbook_dir)

        if spellbook_content:
            if self.dry_run:
                results.append(
                    InstallResult(
                        component="GEMINI.md",
                        platform=self.platform_id,
                        success=True,
                        action="installed",
                        message="GEMINI.md: would be updated",
                    )
                )
            else:
                action, backup_path = update_demarcated_section(
                    context_file, spellbook_content, self.version
                )
                msg = f"GEMINI.md: {action}"
                if backup_path:
                    msg += f" (backup: {backup_path.name})"
                results.append(
                    InstallResult(
                        component="GEMINI.md",
                        platform=self.platform_id,
                        success=True,
                        action=action,
                        message=msg,
                    )
                )

        # Register extension with Gemini CLI if available
        if check_gemini_cli_available():
            success, msg = install_gemini_extension(self.extensions_dir, dry_run=self.dry_run)
            results.append(
                InstallResult(
                    component="extension_registration",
                    platform=self.platform_id,
                    success=success,
                    action="installed" if success else "failed",
                    message=f"extension: {msg}",
                )
            )
        else:
            results.append(
                InstallResult(
                    component="extension_registration",
                    platform=self.platform_id,
                    success=True,
                    action="skipped",
                    message="extension: gemini CLI not available (manual registration needed)",
                )
            )

        return results

    def uninstall(self) -> List["InstallResult"]:
        """Uninstall Gemini CLI components."""
        from ..core import InstallResult

        results = []

        if not self.config_dir.exists():
            return results

        # Unregister extension with Gemini CLI if available
        if check_gemini_cli_available():
            success, msg = uninstall_gemini_extension("spellbook", dry_run=self.dry_run)
            results.append(
                InstallResult(
                    component="extension_registration",
                    platform=self.platform_id,
                    success=success,
                    action="removed" if success else "failed",
                    message=f"extension: {msg}",
                )
            )

        # Remove demarcated section from GEMINI.md
        context_file = self.extensions_dir / "GEMINI.md"
        if context_file.exists():
            if self.dry_run:
                results.append(
                    InstallResult(
                        component="GEMINI.md",
                        platform=self.platform_id,
                        success=True,
                        action="removed",
                        message="GEMINI.md: would remove spellbook section",
                    )
                )
            else:
                action, backup_path = remove_demarcated_section(context_file)
                msg = f"GEMINI.md: {action}"
                if backup_path:
                    msg += f" (backup: {backup_path.name})"
                results.append(
                    InstallResult(
                        component="GEMINI.md",
                        platform=self.platform_id,
                        success=True,
                        action=action,
                        message=msg,
                    )
                )

        # Remove extension manifest
        manifest_file = self.extensions_dir / "gemini-extension.json"
        if manifest_file.exists():
            if self.dry_run:
                results.append(
                    InstallResult(
                        component="manifest",
                        platform=self.platform_id,
                        success=True,
                        action="removed",
                        message="extension manifest: would be removed",
                    )
                )
            else:
                try:
                    manifest_file.unlink()
                    results.append(
                        InstallResult(
                            component="manifest",
                            platform=self.platform_id,
                            success=True,
                            action="removed",
                            message="extension manifest: removed",
                        )
                    )
                except OSError as e:
                    results.append(
                        InstallResult(
                            component="manifest",
                            platform=self.platform_id,
                            success=False,
                            action="failed",
                            message=f"extension manifest: {e}",
                        )
                    )

        return results

    def get_context_files(self) -> List[Path]:
        """Get context files for this platform."""
        return [self.extensions_dir / "GEMINI.md"]

    def get_symlinks(self) -> List[Path]:
        """Get all symlinks created by this platform."""
        return []  # Gemini doesn't use symlinks, just files

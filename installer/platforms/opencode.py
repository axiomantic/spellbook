"""
OpenCode platform installer.

OpenCode (https://github.com/anomalyco/opencode) supports:
- AGENTS.md for context (installed to ~/.config/opencode/AGENTS.md)
- MCP for session/swarm management tools (connects to HTTP daemon)
- Native skill discovery via Agent Skills (https://agentskills.io)
- Custom agents via opencode.json

Note: OpenCode uses its own skill system (Agent Skills), not ~/.claude/skills/.
Skills for OpenCode should be placed in ~/.config/opencode/skills/ or configured
via the options.skills_paths setting in opencode.json.

MCP Server: OpenCode connects to the spellbook MCP daemon via HTTP transport
at http://127.0.0.1:8765/mcp (same daemon used by Claude Code). The daemon must
be running - use `python3 scripts/spellbook-server.py start` to start it.

OpenCode MCP config uses:
- "type": "local" for stdio servers (command-based)
- "type": "remote" for HTTP servers (URL-based)

Reference: https://opencode.ai/docs/mcp-servers
"""

import json
from pathlib import Path
from typing import TYPE_CHECKING, List, Tuple

from ..components.context_files import generate_codex_context
from ..components.mcp import DEFAULT_HOST, DEFAULT_PORT
from ..components.symlinks import create_symlink, remove_symlink
from ..demarcation import get_installed_version, remove_demarcated_section, update_demarcated_section
from .base import PlatformInstaller, PlatformStatus

if TYPE_CHECKING:
    from ..core import InstallResult


def _update_opencode_config(
    config_path: Path, dry_run: bool = False
) -> Tuple[bool, str]:
    """Add spellbook MCP server to OpenCode config using HTTP transport.
    
    Connects to the spellbook daemon at http://127.0.0.1:8765/mcp.
    This is the same daemon used by Claude Code.
    
    OpenCode (anomalyco/opencode) MCP config format:
    - "mcp" key contains server definitions
    - "type": "remote" for HTTP servers
    - "url": the server URL
    
    Reference: https://opencode.ai/docs/mcp-servers
    """
    if dry_run:
        return (True, "would register MCP server (HTTP)")

    # Ensure parent directory exists
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Read existing config or create new
    config = {}
    if config_path.exists():
        try:
            content = config_path.read_text(encoding="utf-8")
            config = json.loads(content)
        except json.JSONDecodeError:
            # If config is invalid, we'll overwrite it
            pass

    # Ensure mcp section exists (OpenCode uses "mcp" key)
    if "mcp" not in config:
        config["mcp"] = {}

    # Build the daemon URL
    daemon_url = f"http://{DEFAULT_HOST}:{DEFAULT_PORT}/mcp"

    # Determine action message based on whether spellbook is already configured
    if "spellbook" in config["mcp"]:
        action = f"updated MCP server config (HTTP: {daemon_url})"
    else:
        action = f"registered MCP server (HTTP: {daemon_url})"

    # Add or update the spellbook MCP server config to use remote HTTP
    config["mcp"]["spellbook"] = {
        "type": "remote",
        "url": daemon_url,
        "enabled": True,
    }

    # Ensure schema is set to OpenCode schema
    if "$schema" not in config:
        config["$schema"] = "https://opencode.ai/config.json"

    # Write config
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    return (True, action)


def _remove_opencode_mcp_config(
    config_path: Path, dry_run: bool = False
) -> Tuple[bool, str]:
    """Remove spellbook MCP server from OpenCode config."""
    if not config_path.exists():
        return (True, "config not found")

    if dry_run:
        return (True, "would remove MCP server config")

    try:
        content = config_path.read_text(encoding="utf-8")
        config = json.loads(content)
    except json.JSONDecodeError:
        return (True, "config is not valid JSON")

    if "mcp" not in config or "spellbook" not in config.get("mcp", {}):
        return (True, "MCP server was not configured")

    # Remove spellbook from mcp
    del config["mcp"]["spellbook"]

    # Write config back
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    return (True, "removed MCP server config")


class OpenCodeInstaller(PlatformInstaller):
    """Installer for OpenCode platform."""

    @property
    def platform_name(self) -> str:
        return "OpenCode"

    @property
    def platform_id(self) -> str:
        return "opencode"

    @property
    def opencode_config_file(self) -> Path:
        """Get the OpenCode config file path.
        
        OpenCode looks for config in:
        1. .opencode.json or opencode.json (project-local)
        2. ~/.config/opencode/opencode.json (global)
        
        We install to the global config.
        """
        return self.config_dir / "opencode.json"

    @property
    def plugins_dir(self) -> Path:
        """Get the OpenCode plugins directory.
        
        OpenCode loads plugins from:
        1. .opencode/plugins/ (project-local)
        2. ~/.config/opencode/plugins/ (global)
        
        We install to the global plugins directory.
        """
        return self.config_dir / "plugins"

    @property
    def spellbook_forged_plugin_source(self) -> Path:
        """Get the source path for the spellbook-forged plugin."""
        return self.spellbook_dir / "extensions" / "opencode" / "spellbook-forged"

    def detect(self) -> PlatformStatus:
        """Detect OpenCode installation status."""
        # Check for AGENTS.md
        context_file = self.config_dir / "AGENTS.md"
        installed_version = get_installed_version(context_file)

        # Check for MCP config
        has_mcp = False
        if self.opencode_config_file.exists():
            try:
                config = json.loads(self.opencode_config_file.read_text(encoding="utf-8"))
                has_mcp = "spellbook" in config.get("mcp", {})
            except json.JSONDecodeError:
                pass

        # Check for plugin
        plugin_target = self.plugins_dir / "spellbook-forged"
        has_plugin = plugin_target.is_symlink() or plugin_target.is_dir()

        return PlatformStatus(
            platform=self.platform_id,
            available=self.config_dir.exists(),
            installed=installed_version is not None or has_mcp,
            version=installed_version,
            details={
                "config_dir": str(self.config_dir),
                "mcp_registered": has_mcp,
                "plugin_installed": has_plugin,
            },
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
                    message="~/.config/opencode not found",
                )
            )
            return results

        # Note: OpenCode (anomalyco/opencode) uses its own Agent Skills system.
        # Skills should be placed in ~/.config/opencode/skills/ or configured
        # via options.skills_paths in opencode.json.

        # Install AGENTS.md with demarcated section
        context_file = self.config_dir / "AGENTS.md"
        # Reuse generate_codex_context since format is identical
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

        # Register MCP server in opencode.json (connects to HTTP daemon)
        success, msg = _update_opencode_config(
            self.opencode_config_file, self.dry_run
        )
        if success:
            results.append(
                InstallResult(
                    component="mcp_server",
                    platform=self.platform_id,
                    success=success,
                    action="installed" if success else "failed",
                    message=f"MCP server: {msg}",
                )
            )

        # Install spellbook-forged plugin
        plugin_source = self.spellbook_forged_plugin_source
        if plugin_source.exists():
            # Ensure plugins directory exists
            if not self.dry_run:
                self.plugins_dir.mkdir(parents=True, exist_ok=True)

            plugin_target = self.plugins_dir / "spellbook-forged"
            plugin_result = create_symlink(plugin_source, plugin_target, self.dry_run)
            results.append(
                InstallResult(
                    component="plugin",
                    platform=self.platform_id,
                    success=plugin_result.success,
                    action=plugin_result.action,
                    message=f"plugin (spellbook-forged): {plugin_result.action}",
                )
            )

        return results

    def uninstall(self) -> List["InstallResult"]:
        """Uninstall OpenCode components."""
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

        # Remove MCP server from opencode.json
        success, msg = _remove_opencode_mcp_config(
            self.opencode_config_file, self.dry_run
        )
        results.append(
            InstallResult(
                component="mcp_server",
                platform=self.platform_id,
                success=success,
                action="removed" if "removed" in msg else "skipped",
                message=f"MCP server: {msg}",
            )
        )

        # Remove spellbook-forged plugin symlink
        plugin_target = self.plugins_dir / "spellbook-forged"
        if plugin_target.exists() or plugin_target.is_symlink():
            plugin_result = remove_symlink(
                plugin_target,
                verify_source=self.spellbook_forged_plugin_source,
                dry_run=self.dry_run,
            )
            results.append(
                InstallResult(
                    component="plugin",
                    platform=self.platform_id,
                    success=plugin_result.success,
                    action=plugin_result.action,
                    message=f"plugin (spellbook-forged): {plugin_result.action}",
                )
            )

        return results

    def get_context_files(self) -> List[Path]:
        """Get context files for this platform."""
        return [self.config_dir / "AGENTS.md"]

    def get_symlinks(self) -> List[Path]:
        """Get all symlinks created by this platform."""
        symlinks = []

        # Plugin symlink
        plugin_target = self.plugins_dir / "spellbook-forged"
        if plugin_target.is_symlink():
            symlinks.append(plugin_target)

        return symlinks

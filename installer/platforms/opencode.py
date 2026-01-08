"""
OpenCode platform installer.

OpenCode supports:
- AGENTS.md for context (installed to ~/.config/opencode/AGENTS.md)
- MCP for session/swarm management tools
- Native skill discovery from ~/.claude/skills/* (no symlinks needed)
- Agent definitions for YOLO mode (installed to ~/.config/opencode/agent/)

Note: OpenCode automatically reads skills from ~/.claude/skills/, so we don't
need to create skill symlinks for OpenCode. The Claude Code installer handles
skill installation to that location.

Agent files (yolo.md, yolo-focused.md) are symlinked to enable autonomous
execution via `opencode --agent yolo` or `opencode --agent yolo-focused`.
"""

import json
from pathlib import Path
from typing import TYPE_CHECKING, List, Tuple

from ..components.context_files import generate_codex_context
from ..components.symlinks import create_symlink, remove_symlink
from ..demarcation import get_installed_version, remove_demarcated_section, update_demarcated_section
from .base import PlatformInstaller, PlatformStatus

if TYPE_CHECKING:
    from ..core import InstallResult


# JSON markers for spellbook MCP config (used in comments)
JSON_MARKER_START = "spellbook-mcp-start"
JSON_MARKER_END = "spellbook-mcp-end"


def _update_opencode_config(
    config_path: Path, server_path: Path, dry_run: bool = False
) -> Tuple[bool, str]:
    """Add spellbook MCP server to OpenCode config."""
    if dry_run:
        return (True, "would register MCP server")

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

    # Ensure mcp section exists
    if "mcp" not in config:
        config["mcp"] = {}

    # Check if spellbook is already configured
    if "spellbook" in config["mcp"]:
        # Update existing config
        config["mcp"]["spellbook"]["command"] = ["python3", str(server_path)]
        config["mcp"]["spellbook"]["enabled"] = True
        action = "updated MCP server config"
    else:
        # Add new spellbook MCP server
        config["mcp"]["spellbook"] = {
            "type": "local",
            "command": ["python3", str(server_path)],
            "enabled": True,
        }
        action = "registered MCP server"

    # Ensure schema is set
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
        """Get the OpenCode config file path."""
        return self.config_dir / "opencode.json"

    @property
    def agent_source_dir(self) -> Path:
        """Get the source directory for agent definitions."""
        return self.spellbook_dir / "opencode" / "agent"

    @property
    def agent_target_dir(self) -> Path:
        """Get the target directory for agent symlinks."""
        return self.config_dir / "agent"

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

        return PlatformStatus(
            platform=self.platform_id,
            available=self.config_dir.exists(),
            installed=installed_version is not None or has_mcp,
            version=installed_version,
            details={
                "config_dir": str(self.config_dir),
                "mcp_registered": has_mcp,
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

        # Note: OpenCode reads skills from ~/.claude/skills/* natively,
        # so no skill symlinks are needed. Claude Code installer handles that.

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

        # Register MCP server in opencode.json
        server_path = self.spellbook_dir / "spellbook_mcp" / "server.py"
        if server_path.exists():
            success, msg = _update_opencode_config(
                self.opencode_config_file, server_path, self.dry_run
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

        # Install agent symlinks for YOLO mode
        if self.agent_source_dir.exists():
            for agent_file in self.agent_source_dir.glob("*.md"):
                target = self.agent_target_dir / agent_file.name
                result = create_symlink(agent_file, target, self.dry_run)
                results.append(
                    InstallResult(
                        component=f"agent:{agent_file.stem}",
                        platform=self.platform_id,
                        success=result.success,
                        action=result.action,
                        message=f"Agent {agent_file.stem}: {result.message}",
                    )
                )

        return results

    def uninstall(self) -> List["InstallResult"]:
        """Uninstall OpenCode components."""
        from ..core import InstallResult

        results = []

        if not self.config_dir.exists():
            return results

        # Note: Skills are in ~/.claude/skills/* and managed by Claude Code installer,
        # not by OpenCode installer.

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

        # Remove agent symlinks
        if self.agent_target_dir.exists():
            for agent_symlink in self.agent_target_dir.iterdir():
                if agent_symlink.is_symlink():
                    result = remove_symlink(
                        agent_symlink, verify_source=self.spellbook_dir, dry_run=self.dry_run
                    )
                    if result.action != "skipped":
                        results.append(
                            InstallResult(
                                component=f"agent:{agent_symlink.stem}",
                                platform=self.platform_id,
                                success=result.success,
                                action=result.action,
                                message=f"Agent {agent_symlink.stem}: {result.message}",
                            )
                        )

        return results

    def get_context_files(self) -> List[Path]:
        """Get context files for this platform."""
        return [self.config_dir / "AGENTS.md"]

    def get_symlinks(self) -> List[Path]:
        """Get all symlinks created by this platform."""
        symlinks = []
        # Agent symlinks for YOLO mode
        if self.agent_target_dir.exists():
            for item in self.agent_target_dir.iterdir():
                if item.is_symlink():
                    symlinks.append(item)
        return symlinks

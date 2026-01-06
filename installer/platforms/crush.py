"""
Crush platform installer.

Crush (by Charmbracelet) supports:
- AGENTS.md for context (installed to ~/.config/crush/AGENTS.md)
- MCP for spellbook tools (find_spellbook_skills, use_spellbook_skill, etc.)
- Native Agent Skills via options.skills_paths in crush.json
- Context files via options.context_paths in crush.json

Crush configuration is stored in ~/.config/crush/crush.json (JSON format).
See: https://github.com/charmbracelet/crush
"""

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Tuple

from ..components.context_files import generate_codex_context
from ..demarcation import get_installed_version, remove_demarcated_section, update_demarcated_section
from .base import PlatformInstaller, PlatformStatus

if TYPE_CHECKING:
    from ..core import InstallResult


def _update_crush_config(
    config_path: Path,
    server_path: Path,
    context_file_path: Path,
    claude_skills_path: Path,
    dry_run: bool = False,
) -> Tuple[bool, str]:
    """
    Add spellbook configuration to Crush config.

    This configures:
    - MCP server (spellbook) under the 'mcp' key
    - Skills path (~/.claude/skills) under 'options.skills_paths'
    - Context file path under 'options.context_paths'
    """
    if dry_run:
        return (True, "would register spellbook config")

    # Ensure parent directory exists
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Read existing config or create new
    config: Dict[str, Any] = {}
    if config_path.exists():
        try:
            content = config_path.read_text(encoding="utf-8")
            config = json.loads(content)
        except json.JSONDecodeError:
            # If config is invalid, we'll overwrite it
            pass

    actions = []

    # Ensure schema is set
    if "$schema" not in config:
        config["$schema"] = "https://charm.land/crush.json"

    # Ensure options section exists
    if "options" not in config:
        config["options"] = {}

    # Configure skills_paths to include ~/.claude/skills
    skills_paths = config["options"].get("skills_paths", [])
    claude_skills_str = str(claude_skills_path)
    if claude_skills_str not in skills_paths:
        skills_paths.append(claude_skills_str)
        config["options"]["skills_paths"] = skills_paths
        actions.append("added skills path")

    # Configure context_paths to include our AGENTS.md
    context_paths = config["options"].get("context_paths", [])
    context_file_str = str(context_file_path)
    if context_file_str not in context_paths:
        context_paths.append(context_file_str)
        config["options"]["context_paths"] = context_paths
        actions.append("added context path")

    # Ensure mcp section exists
    if "mcp" not in config:
        config["mcp"] = {}

    # Configure spellbook MCP server
    if "spellbook" in config["mcp"]:
        # Update existing config
        config["mcp"]["spellbook"]["type"] = "stdio"
        config["mcp"]["spellbook"]["command"] = "python3"
        config["mcp"]["spellbook"]["args"] = [str(server_path)]
        actions.append("updated MCP server")
    else:
        # Add new spellbook MCP server
        config["mcp"]["spellbook"] = {
            "type": "stdio",
            "command": "python3",
            "args": [str(server_path)],
        }
        actions.append("registered MCP server")

    # Write config
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

    if actions:
        return (True, ", ".join(actions))
    return (True, "config unchanged")


def _remove_crush_config(
    config_path: Path,
    context_file_path: Path,
    claude_skills_path: Path,
    dry_run: bool = False,
) -> Tuple[bool, str]:
    """Remove spellbook configuration from Crush config."""
    if not config_path.exists():
        return (True, "config not found")

    if dry_run:
        return (True, "would remove spellbook config")

    try:
        content = config_path.read_text(encoding="utf-8")
        config = json.loads(content)
    except json.JSONDecodeError:
        return (True, "config is not valid JSON")

    actions = []

    # Remove spellbook from mcp
    if "mcp" in config and "spellbook" in config["mcp"]:
        del config["mcp"]["spellbook"]
        actions.append("removed MCP server")

    # Remove our context path from options.context_paths
    if "options" in config:
        context_paths = config["options"].get("context_paths", [])
        context_file_str = str(context_file_path)
        if context_file_str in context_paths:
            context_paths.remove(context_file_str)
            config["options"]["context_paths"] = context_paths
            actions.append("removed context path")

        # Remove claude skills path from options.skills_paths
        skills_paths = config["options"].get("skills_paths", [])
        claude_skills_str = str(claude_skills_path)
        if claude_skills_str in skills_paths:
            skills_paths.remove(claude_skills_str)
            config["options"]["skills_paths"] = skills_paths
            actions.append("removed skills path")

    # Write config back
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

    if actions:
        return (True, ", ".join(actions))
    return (True, "nothing to remove")


class CrushInstaller(PlatformInstaller):
    """Installer for Crush platform (by Charmbracelet)."""

    @property
    def platform_name(self) -> str:
        return "Crush"

    @property
    def platform_id(self) -> str:
        return "crush"

    @property
    def crush_config_file(self) -> Path:
        """Get the Crush config file path."""
        return self.config_dir / "crush.json"

    @property
    def claude_skills_path(self) -> Path:
        """Get the Claude skills path (shared with Claude Code)."""
        return Path.home() / ".claude" / "skills"

    def detect(self) -> PlatformStatus:
        """Detect Crush installation status."""
        # Check for AGENTS.md
        context_file = self.config_dir / "AGENTS.md"
        installed_version = get_installed_version(context_file)

        # Check for MCP config
        has_mcp = False
        has_skills_path = False
        has_context_path = False

        if self.crush_config_file.exists():
            try:
                config = json.loads(self.crush_config_file.read_text(encoding="utf-8"))
                has_mcp = "spellbook" in config.get("mcp", {})

                options = config.get("options", {})
                skills_paths = options.get("skills_paths", [])
                context_paths = options.get("context_paths", [])

                has_skills_path = str(self.claude_skills_path) in skills_paths
                has_context_path = str(self.config_dir / "AGENTS.md") in context_paths
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
                "skills_path_configured": has_skills_path,
                "context_path_configured": has_context_path,
            },
        )

    def install(self, force: bool = False) -> List["InstallResult"]:
        """Install Crush components."""
        from ..core import InstallResult

        results = []

        if not self.config_dir.exists():
            results.append(
                InstallResult(
                    component="platform",
                    platform=self.platform_id,
                    success=True,
                    action="skipped",
                    message="~/.config/crush not found",
                )
            )
            return results

        # Install AGENTS.md with demarcated section
        context_file = self.config_dir / "AGENTS.md"
        # Reuse generate_codex_context since format is identical to OpenCode/Codex
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

        # Register spellbook in crush.json (MCP server + skills path + context path)
        server_path = self.spellbook_dir / "spellbook_mcp" / "server.py"
        if server_path.exists():
            success, msg = _update_crush_config(
                self.crush_config_file,
                server_path,
                context_file,
                self.claude_skills_path,
                self.dry_run,
            )
            results.append(
                InstallResult(
                    component="crush_config",
                    platform=self.platform_id,
                    success=success,
                    action="installed" if success else "failed",
                    message=f"crush.json: {msg}",
                )
            )

        return results

    def uninstall(self) -> List["InstallResult"]:
        """Uninstall Crush components."""
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

        # Remove spellbook config from crush.json
        success, msg = _remove_crush_config(
            self.crush_config_file,
            context_file,
            self.claude_skills_path,
            self.dry_run,
        )
        results.append(
            InstallResult(
                component="crush_config",
                platform=self.platform_id,
                success=success,
                action="removed" if "removed" in msg else "skipped",
                message=f"crush.json: {msg}",
            )
        )

        return results

    def get_context_files(self) -> List[Path]:
        """Get context files for this platform."""
        return [self.config_dir / "AGENTS.md"]

    def get_symlinks(self) -> List[Path]:
        """Get all symlinks created by this platform."""
        # Crush doesn't create symlinks - skills are configured via crush.json
        return []

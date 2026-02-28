"""
OpenCode platform installer.

OpenCode (https://github.com/anomalyco/opencode) supports:
- AGENTS.md for context (installed to ~/.config/opencode/AGENTS.md)
- MCP for session/swarm management tools (connects to HTTP daemon)
- Native skill discovery via Agent Skills (https://agentskills.io)
- Custom agents via opencode.json
- Instructions config for injecting system-level behavioral standards

Note: OpenCode uses its own skill system (Agent Skills), not ~/.claude/skills/.
Skills for OpenCode should be placed in ~/.config/opencode/skills/ or configured
via the options.skills_paths setting in opencode.json.

MCP Server: OpenCode connects to the spellbook MCP daemon via HTTP transport
at http://127.0.0.1:8765/mcp (same daemon used by Claude Code). The daemon must
be running - use `python3 scripts/spellbook-server.py start` to start it.

OpenCode MCP config uses:
- "type": "local" for stdio servers (command-based)
- "type": "remote" for HTTP servers (URL-based)

System Prompt Injection: Spellbook installs Claude Code behavioral standards via
the `instructions` config array. This applies to ALL agents in OpenCode, ensuring
consistent high-quality software engineering assistance. The system prompt file
is symlinked to ~/.config/opencode/instructions/claude-code-system-prompt.md.

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


def _update_opencode_instructions(
    config_path: Path, instructions_path: str, dry_run: bool = False
) -> Tuple[bool, str]:
    """Add or update the instructions array in OpenCode config.

    The instructions config tells OpenCode to load additional system-level
    instructions for all agents. We add our Claude Code behavioral standards
    while preserving any existing user-configured instructions.

    Args:
        config_path: Path to opencode.json
        instructions_path: Path to add to the instructions array
        dry_run: If True, don't actually modify the config

    Returns:
        Tuple of (success, message)
    """
    if dry_run:
        return (True, "would add instructions path")

    # Ensure parent directory exists
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Read existing config or create new
    config = {}
    if config_path.exists():
        try:
            content = config_path.read_text(encoding="utf-8")
            config = json.loads(content)
        except json.JSONDecodeError:
            pass

    # Ensure instructions is a list
    if "instructions" not in config:
        config["instructions"] = []
    elif not isinstance(config["instructions"], list):
        # Convert to list if it's a single string
        config["instructions"] = [config["instructions"]]

    # Add our instructions path if not already present
    if instructions_path not in config["instructions"]:
        config["instructions"].append(instructions_path)
        action = "added instructions path"
    else:
        action = "instructions path already configured"

    # Ensure schema is set
    if "$schema" not in config:
        config["$schema"] = "https://opencode.ai/config.json"

    # Write config
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    return (True, action)


def _remove_opencode_instructions(
    config_path: Path, instructions_path: str, dry_run: bool = False
) -> Tuple[bool, str]:
    """Remove an instructions path from OpenCode config.

    Args:
        config_path: Path to opencode.json
        instructions_path: Path to remove from the instructions array
        dry_run: If True, don't actually modify the config

    Returns:
        Tuple of (success, message)
    """
    if not config_path.exists():
        return (True, "config not found")

    if dry_run:
        return (True, "would remove instructions path")

    try:
        content = config_path.read_text(encoding="utf-8")
        config = json.loads(content)
    except json.JSONDecodeError:
        return (True, "config is not valid JSON")

    if "instructions" not in config:
        return (True, "no instructions configured")

    instructions = config["instructions"]
    if not isinstance(instructions, list):
        instructions = [instructions]

    if instructions_path not in instructions:
        return (True, "instructions path was not configured")

    # Remove our instructions path
    instructions.remove(instructions_path)
    config["instructions"] = instructions

    # Write config back
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    return (True, "removed instructions path")


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

    @property
    def security_plugin_source(self) -> Path:
        """Get the source path for the spellbook-security plugin."""
        return self.spellbook_dir / "hooks" / "opencode-plugin.ts"

    @property
    def security_plugin_target(self) -> Path:
        """Get the target path for the installed spellbook-security plugin."""
        return self.plugins_dir / "spellbook-security.ts"

    @property
    def instructions_dir(self) -> Path:
        """Get the OpenCode instructions directory.

        OpenCode loads instruction files from paths listed in the
        `instructions` config array. We install to a dedicated directory.
        """
        return self.config_dir / "instructions"

    @property
    def system_prompt_source(self) -> Path:
        """Get the source path for the Claude Code system prompt."""
        return self.spellbook_dir / "extensions" / "opencode" / "claude-code-system-prompt.md"

    @property
    def system_prompt_target(self) -> Path:
        """Get the target path for the Claude Code system prompt symlink."""
        return self.instructions_dir / "claude-code-system-prompt.md"

    @property
    def system_prompt_config_path(self) -> str:
        """Get the path to use in the instructions config array.

        Uses ~ for home directory to be portable across systems.
        """
        return "~/.config/opencode/instructions/claude-code-system-prompt.md"

    def detect(self) -> PlatformStatus:
        """Detect OpenCode installation status."""
        # Check for AGENTS.md
        context_file = self.config_dir / "AGENTS.md"
        installed_version = get_installed_version(context_file)

        # Check for MCP config
        has_mcp = False
        has_instructions = False
        if self.opencode_config_file.exists():
            try:
                config = json.loads(self.opencode_config_file.read_text(encoding="utf-8"))
                has_mcp = "spellbook" in config.get("mcp", {})
                # Check if our instructions path is in the config
                instructions = config.get("instructions", [])
                if isinstance(instructions, str):
                    instructions = [instructions]
                has_instructions = self.system_prompt_config_path in instructions
            except json.JSONDecodeError:
                pass

        # Check for plugin
        plugin_target = self.plugins_dir / "spellbook-forged"
        has_plugin = plugin_target.is_symlink() or plugin_target.is_dir()

        # Check for security plugin
        has_security_plugin = self.security_plugin_target.is_file()

        # Check for system prompt symlink
        has_system_prompt = self.system_prompt_target.is_symlink() or self.system_prompt_target.is_file()

        return PlatformStatus(
            platform=self.platform_id,
            available=self.config_dir.exists(),
            installed=installed_version is not None or has_mcp,
            version=installed_version,
            details={
                "config_dir": str(self.config_dir),
                "mcp_registered": has_mcp,
                "plugin_installed": has_plugin,
                "security_plugin_installed": has_security_plugin,
                "system_prompt_installed": has_system_prompt,
                "instructions_configured": has_instructions,
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

        # Install AGENTS.md with demarcated section
        self._step("Updating AGENTS.md")
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
        self._step("Registering MCP server")
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
        self._step("Installing plugins")
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

        # Install spellbook-security plugin (copy TypeScript file)
        if self.security_plugin_source.exists():
            if self.dry_run:
                results.append(
                    InstallResult(
                        component="security_plugin",
                        platform=self.platform_id,
                        success=True,
                        action="installed",
                        message="security plugin: would be installed",
                    )
                )
            else:
                self.plugins_dir.mkdir(parents=True, exist_ok=True)
                source_content = self.security_plugin_source.read_text(encoding="utf-8")
                self.security_plugin_target.write_text(source_content, encoding="utf-8")
                results.append(
                    InstallResult(
                        component="security_plugin",
                        platform=self.platform_id,
                        success=True,
                        action="installed",
                        message="security plugin: installed",
                    )
                )

        # Install Claude Code system prompt (behavioral standards)
        self._step("Installing system prompt")
        if self.system_prompt_source.exists():
            # Ensure instructions directory exists
            if not self.dry_run:
                self.instructions_dir.mkdir(parents=True, exist_ok=True)

            # Create symlink for the system prompt file
            prompt_result = create_symlink(
                self.system_prompt_source, self.system_prompt_target, self.dry_run
            )
            results.append(
                InstallResult(
                    component="system_prompt",
                    platform=self.platform_id,
                    success=prompt_result.success,
                    action=prompt_result.action,
                    message=f"system prompt: {prompt_result.action}",
                )
            )

            # Register the instructions path in opencode.json
            if prompt_result.success:
                instr_success, instr_msg = _update_opencode_instructions(
                    self.opencode_config_file, self.system_prompt_config_path, self.dry_run
                )
                results.append(
                    InstallResult(
                        component="instructions_config",
                        platform=self.platform_id,
                        success=instr_success,
                        action="installed" if "added" in instr_msg else "skipped",
                        message=f"instructions config: {instr_msg}",
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
                action, _backup = remove_demarcated_section(context_file)
                msg = f"AGENTS.md: {action}"
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

        # Remove spellbook-security plugin file
        if self.security_plugin_target.exists():
            if not self.dry_run:
                self.security_plugin_target.unlink()
            results.append(
                InstallResult(
                    component="security_plugin",
                    platform=self.platform_id,
                    success=True,
                    action="removed",
                    message="security plugin: removed",
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

        # Remove system prompt symlink
        if self.system_prompt_target.exists() or self.system_prompt_target.is_symlink():
            prompt_result = remove_symlink(
                self.system_prompt_target,
                verify_source=self.system_prompt_source,
                dry_run=self.dry_run,
            )
            results.append(
                InstallResult(
                    component="system_prompt",
                    platform=self.platform_id,
                    success=prompt_result.success,
                    action=prompt_result.action,
                    message=f"system prompt: {prompt_result.action}",
                )
            )

        # Remove instructions path from config
        instr_success, instr_msg = _remove_opencode_instructions(
            self.opencode_config_file, self.system_prompt_config_path, self.dry_run
        )
        if "removed" in instr_msg:
            results.append(
                InstallResult(
                    component="instructions_config",
                    platform=self.platform_id,
                    success=instr_success,
                    action="removed",
                    message=f"instructions config: {instr_msg}",
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

        # System prompt symlink
        if self.system_prompt_target.is_symlink():
            symlinks.append(self.system_prompt_target)

        return symlinks

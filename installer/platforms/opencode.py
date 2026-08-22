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
be running - use `spellbook server start` to start it.

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
import os
from pathlib import Path
from typing import TYPE_CHECKING, List, Tuple

from ..components.mcp import DEFAULT_HOST, DEFAULT_PORT
from ..components.rule_delivery import INSTALLED_GLOB
from ..components.symlinks import create_symlink, remove_symlink
from ..demarcation import get_installed_version, remove_demarcated_section
from .base import RULE_DELIVERY_DIRECTORY, PlatformInstaller, PlatformStatus

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
    server_config = {
        "type": "remote",
        "url": daemon_url,
        "enabled": True,
    }

    # Whole-entry replacement: any stale auth header from a previous
    # install disappears here rather than being merged forward.
    config["mcp"]["spellbook"] = server_config

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

    rule_delivery = RULE_DELIVERY_DIRECTORY

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
    def gate_plugin_source(self) -> Path:
        """Get the source path for the OpenCode gate plugin."""
        return self.spellbook_dir / "hooks" / "opencode-plugin.ts"

    @property
    def gate_plugin_target(self) -> Path:
        """Get the target path for the installed gate plugin.

        The filename is deliberately the one used before commit 7a8e9ab1
        removed the install step. Installs from those versions still carry a
        copy at this path, and reusing the name makes an upgrade overwrite it
        rather than leave the stale file loaded alongside a new one.
        """
        return self.plugins_dir / "spellbook-security.ts"


    @property
    def instructions_dir(self) -> Path:
        """Get the OpenCode instructions directory.

        OpenCode loads instruction files from paths listed in the
        `instructions` config array. We install to a dedicated directory.
        """
        return self.config_dir / "instructions"

    def rule_module_dir(self) -> Path:
        return self.instructions_dir

    def legacy_rule_paths(self) -> List[Path]:
        return [self.instructions_dir / "spellbook.md"]

    def legacy_context_files(self) -> List[Path]:
        return [self.config_dir / "AGENTS.md"]

    def _instructions_config_path(self, path: Path) -> str:
        """Render a path the way the instructions array expects it.

        Uses ``~`` for the home directory so the entry is portable across
        machines, matching the convention the system prompt entry already uses.
        """
        try:
            return f"~/{path.relative_to(Path.home()).as_posix()}"
        except ValueError:
            return str(path)

    def on_rule_modules_installed(
        self, installed: List[Path], removed: List[Path]
    ) -> List["InstallResult"]:
        """Register every delivered module in ``opencode.json``.

        Deregistration of removed modules happens in the same pass, because
        registration and deregistration are one mechanism: a deselected module
        whose entry survives keeps loading despite its file being gone.
        """
        from ..core import InstallResult

        config_path = self.opencode_config_file
        if config_path.exists() and not self.dry_run:
            try:
                json.loads(config_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                # Never rewrite a config we cannot parse. An unregistered
                # module does not load, so this is a delivery failure, not a
                # warning to skip past.
                return [
                    InstallResult(
                        component="rule_modules_config",
                        platform=self.platform_id,
                        success=False,
                        action="failed",
                        message=(
                            f"instructions config: {config_path} is not valid JSON; "
                            "rule modules were written but cannot be registered"
                        ),
                    )
                ]

        failures: List[str] = []
        for path in removed:
            ok, _msg = _remove_opencode_instructions(
                config_path, self._instructions_config_path(path), self.dry_run
            )
            if not ok:
                failures.append(path.name)

        registered = 0
        for path in installed:
            ok, _msg = _update_opencode_instructions(
                config_path, self._instructions_config_path(path), self.dry_run
            )
            if ok:
                registered += 1
            else:
                failures.append(path.name)

        if failures:
            return [
                InstallResult(
                    component="rule_modules_config",
                    platform=self.platform_id,
                    success=False,
                    action="failed",
                    message=f"instructions config: {len(failures)} path(s) failed",
                )
            ]

        return [
            InstallResult(
                component="rule_modules_config",
                platform=self.platform_id,
                success=True,
                action="installed",
                message=f"instructions config: {registered} rule module(s) registered",
            )
        ]

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
        Falls back to absolute path if config_dir is not under $HOME.
        """
        target = self.instructions_dir / "claude-code-system-prompt.md"
        try:
            return f"~/{target.relative_to(Path.home()).as_posix()}"
        except ValueError:
            # config_dir is not under $HOME; use absolute path
            return str(target)

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

        has_gate_plugin = self.gate_plugin_target.is_file()

        # Check for system prompt symlink
        has_system_prompt = self.system_prompt_target.is_symlink() or self.system_prompt_target.is_file()

        rules_dir = self.rule_module_dir()
        has_modules = rules_dir.is_dir() and any(rules_dir.glob(INSTALLED_GLOB))
        has_sidecar = any(os.path.lexists(path) for path in self.legacy_rule_paths())
        installed = (
            installed_version is not None
            or has_mcp
            or has_modules
            or has_sidecar
            or has_instructions
        )

        return PlatformStatus(
            platform=self.platform_id,
            available=self.config_dir.exists(),
            installed=installed,
            version=self.version if installed else None,
            details={
                "config_dir": str(self.config_dir),
                "mcp_registered": has_mcp,
                "gate_plugin_installed": has_gate_plugin,
                "system_prompt_installed": has_system_prompt,
                "instructions_configured": has_instructions,
            },
        )

    def install(self, force: bool = False, skip_global_steps: bool = False) -> List["InstallResult"]:
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

        # Always strip legacy demarcated block from AGENTS.md if present
        context_file = self.config_dir / "AGENTS.md"

        # One instruction file per selected module, each registered in
        # opencode.json. Registration is not an optimization: OpenCode's
        # resolver reads only the paths in that array and never scans the
        # instructions directory, so an unregistered file does not load.
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

        # Install the gate plugin (copied, not symlinked: OpenCode loads
        # plugins by path and a symlink into the checkout would break when the
        # checkout moves).
        self._step("Installing gate plugin")
        if self.gate_plugin_source.exists():
            if self.dry_run:
                action, message = "installed", "gate plugin: would be installed"
            else:
                self.plugins_dir.mkdir(parents=True, exist_ok=True)
                self.gate_plugin_target.write_text(
                    self.gate_plugin_source.read_text(encoding="utf-8"),
                    encoding="utf-8",
                )
                action, message = "installed", "gate plugin: installed"
            results.append(
                InstallResult(
                    component="gate_plugin",
                    platform=self.platform_id,
                    success=True,
                    action=action,
                    message=message,
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

    def uninstall(self, skip_global_steps: bool = False) -> List["InstallResult"]:
        """Uninstall OpenCode components."""
        from ..core import InstallResult

        results = []

        if not self.config_dir.exists():
            return results

        # Remove rule module files and deregister each one. A surviving
        # registration keeps a removed file's absence from being noticed.
        module_paths = (
            sorted(self.instructions_dir.glob(INSTALLED_GLOB))
            if self.instructions_dir.is_dir()
            else []
        )
        for module_path in module_paths:
            _remove_opencode_instructions(
                self.opencode_config_file,
                self._instructions_config_path(module_path),
                self.dry_run,
            )
        results.extend(self.uninstall_rule_modules())

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

        # Remove the gate plugin file
        if self.gate_plugin_target.exists():
            if not self.dry_run:
                self.gate_plugin_target.unlink()
            results.append(
                InstallResult(
                    component="gate_plugin",
                    platform=self.platform_id,
                    success=True,
                    action="removed",
                    message="gate plugin: removed",
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
        """Get rule module files managed by this platform."""
        if not self.instructions_dir.is_dir():
            return []
        return sorted(self.instructions_dir.glob(INSTALLED_GLOB))

    def get_symlinks(self) -> List[Path]:
        """Get all symlinks created by this platform."""
        symlinks = []

        # System prompt symlink
        if self.system_prompt_target.is_symlink():
            symlinks.append(self.system_prompt_target)

        return symlinks

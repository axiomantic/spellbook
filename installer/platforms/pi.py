"""Pi platform installer.

Pi (https://github.com/badlogic/pi) supports:
- AGENTS.md or CLAUDE.md for context (loaded from ~/.pi/agent/AGENTS.md globally)
- Skills via Agent Skills standard in ~/.pi/agent/skills/ (directories or flat .md files)
- Prompt templates as .md files in ~/.pi/agent/prompts/
- MCP servers via JSON config in ~/.pi/agent/mcp.json (Claude Code shape)
- HTTP MCP transport with headers map for Bearer auth

Reference:
- https://github.com/badlogic/pi-coding-agent/docs/skills.md
- https://github.com/badlogic/pi-coding-agent/docs/prompt-templates.md
"""

import json
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, List, Tuple

from ..components.context_files import generate_claude_context
from ..components.mcp import get_mcp_auth_token, get_spellbook_server_url
from ..components.symlinks import (
    cleanup_spellbook_symlinks,
    create_skill_symlinks,
    create_symlink,
    remove_symlink,
    remove_spellbook_symlinks,
)
from ..demarcation import (
    get_installed_version,
    remove_demarcated_section,
    update_demarcated_section,
)
from .base import PlatformInstaller, PlatformStatus

if TYPE_CHECKING:
    from ..core import InstallResult

logger = logging.getLogger(__name__)

SPELLBOOK_SERVER_KEY: str = "spellbook"


def _load_mcp_config_dict(config_path: Path) -> dict:
    """Read and parse ``config_path`` as JSON, returning ``{}`` on failure."""
    if not config_path.exists():
        return {}
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        logger.debug("Failed to parse %s: %s", config_path, e)
        return {}
    if not isinstance(data, dict):
        logger.debug(
            "Existing %s is not a JSON object (got %s); starting fresh",
            config_path,
            type(data).__name__,
        )
        return {}
    return data


def _write_mcp_config(config_path: Path, config: dict) -> None:
    """Write JSON config atomically."""
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")


def _generate_mcp_json_section() -> dict:
    """Generate the MCP server entry for spellbook (HTTP transport)."""
    url = get_spellbook_server_url()
    server_entry: dict = {
        "url": url,
    }
    token = get_mcp_auth_token()
    if token:
        server_entry["headers"] = {"Authorization": f"Bearer {token}"}
    return server_entry


def _update_pi_mcp_config(
    config_path: Path, dry_run: bool = False
) -> Tuple[bool, str]:
    """Add or update spellbook MCP server in pi's mcp.json (Claude Code shape)."""
    if dry_run:
        return (True, "would register MCP server (HTTP)")

    config = _load_mcp_config_dict(config_path)

    if "mcpServers" not in config or not isinstance(config["mcpServers"], dict):
        config["mcpServers"] = {}

    server_entry = _generate_mcp_json_section()
    action = (
        f"updated MCP server config (HTTP: {server_entry['url']})"
        if SPELLBOOK_SERVER_KEY in config["mcpServers"]
        else f"registered MCP server (HTTP: {server_entry['url']})"
    )

    config["mcpServers"][SPELLBOOK_SERVER_KEY] = server_entry
    _write_mcp_config(config_path, config)
    return (True, action)


def _remove_pi_mcp_config(
    config_path: Path, dry_run: bool = False
) -> Tuple[bool, str]:
    """Remove spellbook MCP server from pi's mcp.json."""
    if not config_path.exists():
        return (True, "config not found")

    if dry_run:
        return (True, "would remove MCP server config")

    config = _load_mcp_config_dict(config_path)
    if not config:
        return (True, "config is not valid JSON")

    servers = config.get("mcpServers")
    if not isinstance(servers, dict) or SPELLBOOK_SERVER_KEY not in servers:
        return (True, "MCP server was not configured")

    del servers[SPELLBOOK_SERVER_KEY]
    _write_mcp_config(config_path, config)
    return (True, "removed MCP server config")


class PiInstaller(PlatformInstaller):
    """Installer for Pi platform."""

    @property
    def platform_name(self) -> str:
        return "Pi"

    @property
    def platform_id(self) -> str:
        return "pi"

    @property
    def mcp_config_file(self) -> Path:
        """Path to ~/.pi/agent/mcp.json (Claude Code mcpServers shape)."""
        return self.config_dir / "mcp.json"

    @property
    def context_file(self) -> Path:
        """Path to ~/.pi/agent/AGENTS.md."""
        return self.config_dir / "AGENTS.md"

    @property
    def skills_dir(self) -> Path:
        """Path to ~/.pi/agent/skills/."""
        return self.config_dir / "skills"

    @property
    def prompts_dir(self) -> Path:
        """Path to ~/.pi/agent/prompts/."""
        return self.config_dir / "prompts"

    @property
    def extensions_dir(self) -> Path:
        """Path to ~/.pi/agent/extensions/."""
        return self.config_dir / "extensions"

    @property
    def task_extension_source(self) -> Path:
        """Source path for the Task extension in the spellbook repo."""
        return self.spellbook_dir / "extensions" / "pi" / "Task"

    def detect(self) -> PlatformStatus:
        """Detect Pi installation status."""
        installed_version = get_installed_version(self.context_file)

        has_mcp = False
        if self.mcp_config_file.exists():
            cfg = _load_mcp_config_dict(self.mcp_config_file)
            servers = cfg.get("mcpServers", {})
            if isinstance(servers, dict):
                has_mcp = SPELLBOOK_SERVER_KEY in servers

        # Check for any spellbook-related skills or prompts
        has_skills = False
        if self.skills_dir.exists():
            for item in self.skills_dir.iterdir():
                if item.is_symlink() or item.is_file():
                    # Check if it points to spellbook or has spellbook name
                    if "spellbook" in item.name.lower():
                        has_skills = True
                        break
                    if item.is_symlink():
                        try:
                            target = item.resolve()
                            if "spellbook" in str(target).lower():
                                has_skills = True
                                break
                        except OSError:
                            pass

        has_prompts = False
        if self.prompts_dir.exists():
            for item in self.prompts_dir.iterdir():
                if item.is_symlink() or item.is_file():
                    if "spellbook" in item.name.lower():
                        has_prompts = True
                        break
                    if item.is_symlink():
                        try:
                            target = item.resolve()
                            if "spellbook" in str(target).lower():
                                has_prompts = True
                                break
                        except OSError:
                            pass

        # Check for the Task extension
        has_task_ext = False
        task_ext_target = self.extensions_dir / "Task"
        if task_ext_target.is_symlink() or task_ext_target.is_dir():
            has_task_ext = True

        return PlatformStatus(
            platform=self.platform_id,
            available=self.config_dir.exists(),
            installed=installed_version is not None or has_mcp or has_skills or has_prompts or has_task_ext,
            version=installed_version,
            details={
                "config_dir": str(self.config_dir),
                "mcp_registered": has_mcp,
                "skills_installed": has_skills,
                "prompts_installed": has_prompts,
                "task_extension_installed": has_task_ext,
            },
        )

    def install(self, force: bool = False, skip_global_steps: bool = False) -> List["InstallResult"]:
        """Install Pi components.

        Installs:
        - Skills to ~/.pi/agent/skills/ (flat .md files or directory symlinks)
        - Commands (prompt templates) to ~/.pi/agent/prompts/ (flat .md files)
        - AGENTS.md context (demarcated section)
        - MCP server config in mcp.json
        """
        from ..core import InstallResult

        results: List[InstallResult] = []

        if not self.config_dir.exists():
            results.append(
                InstallResult(
                    component="platform",
                    platform=self.platform_id,
                    success=True,
                    action="skipped",
                    message=f"{self.config_dir} not found",
                )
            )
            return results

        # Step 1: Install skills to ~/.pi/agent/skills/
        # Pi skill discovery: ~/.pi/agent/skills/*.md are individual skills,
        # directories containing SKILL.md are also discovered.
        # We install as directory symlinks (matching the skill dir structure).
        self._step("Installing skills")
        if not self.dry_run:
            self.skills_dir.mkdir(parents=True, exist_ok=True)

        # Clean up old symlinks first
        total_cleaned = 0
        if self.skills_dir.exists():
            cleanup_results = cleanup_spellbook_symlinks(self.skills_dir, dry_run=self.dry_run)
            total_cleaned = sum(1 for r in cleanup_results if r.success)

        if total_cleaned > 0:
            results.append(
                InstallResult(
                    component="cleanup",
                    platform=self.platform_id,
                    success=True,
                    action="removed",
                    message=f"cleanup: {total_cleaned} old symlinks removed",
                )
            )

        # Create skill symlinks (as directories, matching pi's discovery rules)
        skills_results = create_skill_symlinks(
            self.spellbook_dir / "skills",
            self.skills_dir,
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

        # Step 2: Install commands as prompt templates to ~/.pi/agent/prompts/
        # Pi prompt template discovery: ~/.pi/agent/prompts/*.md are templates.
        # We install as flat .md files (command name as filename).
        self._step("Installing prompt templates (commands)")
        if not self.dry_run:
            self.prompts_dir.mkdir(parents=True, exist_ok=True)

        # Clean up old command symlinks/prompts first
        total_cleaned = 0
        if self.prompts_dir.exists():
            cleanup_results = cleanup_spellbook_symlinks(self.prompts_dir, dry_run=self.dry_run)
            total_cleaned = sum(1 for r in cleanup_results if r.success)

        if total_cleaned > 0:
            results.append(
                InstallResult(
                    component="cleanup_prompts",
                    platform=self.platform_id,
                    success=True,
                    action="removed",
                    message=f"cleanup: {total_cleaned} old prompts removed",
                )
            )

        # Install command files: simple .md files at root, and flatten
        # .md files from subdirectories (pi prompts are non-recursive).
        cmd_count = 0
        commands_source = self.spellbook_dir / "commands"
        if commands_source.exists():
            # Simple commands: .md files in commands root
            for cmd_file in commands_source.glob("*.md"):
                target = self.prompts_dir / cmd_file.name
                link_result = create_symlink(cmd_file, target, self.dry_run)
                if link_result.success:
                    cmd_count += 1

            # Complex commands: subdirectory .md files need to be flattened
            # because pi's prompt discovery is non-recursive.
            for cmd_dir in commands_source.iterdir():
                if not cmd_dir.is_dir():
                    continue

                # If the subdirectory has a .md matching the dir name,
                # symlink it as <dir_name>.md for a clean /command-name
                main_md = cmd_dir / f"{cmd_dir.name}.md"
                if main_md.exists():
                    target = self.prompts_dir / f"{cmd_dir.name}.md"
                    link_result = create_symlink(main_md, target, self.dry_run)
                    if link_result.success:
                        cmd_count += 1

                # Any other .md files in the subdirectory get prefixed with
                # the subdirectory name to avoid collisions.
                for sub_md in cmd_dir.glob("*.md"):
                    if sub_md.name == f"{cmd_dir.name}.md":
                        continue  # Already handled above
                    target_name = f"{cmd_dir.name}--{sub_md.name}"
                    target = self.prompts_dir / target_name
                    link_result = create_symlink(sub_md, target, self.dry_run)
                    if link_result.success:
                        cmd_count += 1

        if cmd_count > 0:
            results.append(
                InstallResult(
                    component="prompts",
                    platform=self.platform_id,
                    success=True,
                    action="installed",
                    message=f"prompts: {cmd_count} installed",
                )
            )

        # Step 2.5: Install the Task extension for pi
        self._step("Installing Task extension")
        if not self.dry_run:
            self.extensions_dir.mkdir(parents=True, exist_ok=True)

        task_ext_target = self.extensions_dir / "Task"
        task_ext_result = create_symlink(
            self.task_extension_source, task_ext_target, self.dry_run
        )
        results.append(
            InstallResult(
                component="task_extension",
                platform=self.platform_id,
                success=task_ext_result.success,
                action=task_ext_result.action,
                message=f"Task extension: {task_ext_result.action}",
            )
        )

        # Step 3: Install AGENTS.md with demarcated section
        self._step("Updating AGENTS.md")
        spellbook_content = generate_claude_context(self.spellbook_dir)

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
                    self.context_file, spellbook_content, self.version
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

        # Step 4: Register MCP server in mcp.json
        # This is a global step: MCP registration is system-wide, not per-dir.
        if not skip_global_steps:
            self._step("Registering MCP server")
            success, msg = _update_pi_mcp_config(self.mcp_config_file, self.dry_run)
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
        """Uninstall Pi components."""
        from ..core import InstallResult

        results: List[InstallResult] = []

        if not self.config_dir.exists():
            return results

        # Remove demarcated section from AGENTS.md
        if self.context_file.exists():
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
                action, _backup = remove_demarcated_section(self.context_file)
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

        # Remove skill symlinks
        if self.skills_dir.exists():
            symlink_results = remove_spellbook_symlinks(
                self.skills_dir, self.spellbook_dir, dry_run=self.dry_run
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

        # Remove prompt template symlinks
        if self.prompts_dir.exists():
            prompt_results = remove_spellbook_symlinks(
                self.prompts_dir, self.spellbook_dir, dry_run=self.dry_run
            )
            if prompt_results:
                removed_count = sum(1 for r in prompt_results if r.action == "removed")
                results.append(
                    InstallResult(
                        component="prompts",
                        platform=self.platform_id,
                        success=True,
                        action="removed",
                        message=f"prompts: {removed_count} removed",
                    )
                )

        # Remove Task extension symlink
        task_ext_target = self.extensions_dir / "Task"
        if task_ext_target.is_symlink():
            task_ext_result = remove_symlink(
                task_ext_target,
                verify_source=self.task_extension_source,
                dry_run=self.dry_run,
            )
            results.append(
                InstallResult(
                    component="task_extension",
                    platform=self.platform_id,
                    success=task_ext_result.success,
                    action=task_ext_result.action,
                    message=f"Task extension: {task_ext_result.action}",
                )
            )

        # Remove MCP server from mcp.json (global step)
        if not skip_global_steps:
            success, msg = _remove_pi_mcp_config(self.mcp_config_file, self.dry_run)
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
        """Get context files managed by this platform."""
        return [self.context_file]

    def get_symlinks(self) -> List[Path]:
        """Get all symlinks created by this platform."""
        symlinks: List[Path] = []

        # Skills
        if self.skills_dir.exists():
            for item in self.skills_dir.iterdir():
                if item.is_symlink():
                    symlinks.append(item)

        # Prompts
        if self.prompts_dir.exists():
            for item in self.prompts_dir.iterdir():
                if item.is_symlink():
                    symlinks.append(item)

        # Task extension
        task_ext_target = self.extensions_dir / "Task"
        if task_ext_target.is_symlink():
            symlinks.append(task_ext_target)

        return symlinks

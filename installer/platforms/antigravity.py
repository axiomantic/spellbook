"""
Antigravity platform installer.

Supports Google Antigravity agentic platform:
- Global/workspace customizations (skills in ~/.gemini/antigravity/skills or ~/.gemini/config/skills)
- Context via AGENTS.md / GEMINI.md in config dir
- MCP server registration via mcp_config.json
- Security policies in ~/.gemini/antigravity/policies/spellbook-security.toml
"""

import json
import logging
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, List, Tuple

from ..components.mcp import DEFAULT_HOST, DEFAULT_PORT, get_mcp_auth_token
from ..components.symlinks import create_symlink, remove_symlink
from ..demarcation import get_installed_version, remove_demarcated_section
from .base import PlatformInstaller, PlatformStatus

if TYPE_CHECKING:
    from ..core import InstallResult

logger = logging.getLogger(__name__)

POLICY_FILENAME = "spellbook-security.toml"
POLICY_SOURCE = "hooks/bash-policy.toml"


class AntigravityInstaller(PlatformInstaller):
    """Installer for the Antigravity coding harness."""

    @property
    def platform_name(self) -> str:
        return "Antigravity"

    @property
    def platform_id(self) -> str:
        return "antigravity"

    @property
    def mcp_config_path(self) -> Path:
        """Path to Antigravity's mcp_config.json."""
        return self.config_dir / "mcp_config.json"

    def detect(self) -> PlatformStatus:
        """Detect Antigravity status."""
        available = self.config_dir.exists() or self.ensure_config_dir()
        installed = False
        installed_version = None

        if available:
            # Check context file
            context_path = self.config_dir / "AGENTS.md"
            if context_path.exists():
                ver = get_installed_version(context_path)
                if ver:
                    installed = True
                    installed_version = ver

            # Check MCP config
            if not installed and self.mcp_config_path.exists():
                try:
                    content = self.mcp_config_path.read_text(encoding="utf-8")
                    config = json.loads(content)
                    if "mcpServers" in config and "spellbook" in config["mcpServers"]:
                        installed = True
                except (json.JSONDecodeError, OSError):
                    pass

        return PlatformStatus(
            platform=self.platform_id,
            available=available,
            installed=installed,
            version=installed_version,
            details={"config_dir": str(self.config_dir)},
        )

    def _update_mcp_config(self) -> Tuple[bool, str]:
        """Register spellbook MCP server in Antigravity's mcp_config.json."""
        if self.dry_run:
            return (True, "would register MCP server in mcp_config.json")

        self.config_dir.mkdir(parents=True, exist_ok=True)

        config = {}
        if self.mcp_config_path.exists():
            try:
                content = self.mcp_config_path.read_text(encoding="utf-8")
                config = json.loads(content)
            except json.JSONDecodeError:
                pass

        if "mcpServers" not in config:
            config["mcpServers"] = {}

        daemon_url = f"http://{DEFAULT_HOST}:{DEFAULT_PORT}/mcp"
        action = (
            f"updated MCP server config (HTTP: {daemon_url})"
            if "spellbook" in config["mcpServers"]
            else f"registered MCP server (HTTP: {daemon_url})"
        )

        server_config = {
            "url": daemon_url,
            "transport": "http",
        }
        token = get_mcp_auth_token()
        if token:
            server_config["headers"] = {"Authorization": f"Bearer {token}"}

        config["mcpServers"]["spellbook"] = server_config

        content = json.dumps(config, indent=2) + "\n"
        self.mcp_config_path.write_text(content, encoding="utf-8")

        return (True, action)

    def _ensure_skill_symlinks(self) -> Tuple[int, int]:
        """Create symlinks for spellbook skills in Antigravity's skills directory."""
        source_skills = self.spellbook_dir / "skills"
        if not source_skills.exists():
            return (0, 0)

        target_skills = self.config_dir / "skills"
        if not self.dry_run:
            target_skills.mkdir(parents=True, exist_ok=True)

        created = 0
        errors = 0

        for skill_dir in source_skills.iterdir():
            if not skill_dir.is_dir():
                continue
            if not (skill_dir / "SKILL.md").exists():
                continue

            target_link = target_skills / skill_dir.name
            if create_symlink(skill_dir, target_link, dry_run=self.dry_run):
                created += 1
            else:
                errors += 1

        return (created, errors)

    def _install_context(self) -> "InstallResult":
        """Symlink sidecar rule file rules/spellbook.md -> AGENTS.spellbook.md and strip legacy demarcated context."""
        from ..core import InstallResult

        source_agents = self.spellbook_dir / "AGENTS.spellbook.md"
        rules_dir = self.config_dir / "rules"
        rule_file = rules_dir / "spellbook.md"

        # Legacy cleanup on AGENTS.md / GEMINI.md
        for legacy_file in (self.config_dir / "AGENTS.md", self.config_dir / "GEMINI.md"):
            if legacy_file.exists() and not self.dry_run:
                remove_demarcated_section(legacy_file)

        if not rules_dir.exists() and not self.dry_run:
            rules_dir.mkdir(parents=True, exist_ok=True)

        res = create_symlink(source_agents, rule_file, dry_run=self.dry_run)

        return InstallResult(
            component="rules_sidecar",
            platform=self.platform_id,
            success=res.success,
            action=res.action,
            message=f"rule symlink: {res.message}",
        )

    def _install_security_policy(self) -> "InstallResult":
        """Install security policy for Antigravity."""
        from ..core import InstallResult

        source = self.spellbook_dir / POLICY_SOURCE
        if not source.exists():
            return InstallResult(
                component="security_policy",
                platform=self.platform_id,
                success=False,
                action="failed",
                message=f"policy source not found at {source}",
            )

        dest_dir = self.config_dir / "policies"
        dest = dest_dir / POLICY_FILENAME

        if self.dry_run:
            return InstallResult(
                component="security_policy",
                platform=self.platform_id,
                success=True,
                action="skipped",
                message=f"would install policy to {dest}",
            )

        try:
            dest_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, dest)
            return InstallResult(
                component="security_policy",
                platform=self.platform_id,
                success=True,
                action="installed",
                message=f"installed policy to {dest}",
            )
        except OSError as e:
            return InstallResult(
                component="security_policy",
                platform=self.platform_id,
                success=False,
                action="failed",
                message=f"failed to install policy: {e}",
            )

    def install(self, force: bool = False, skip_global_steps: bool = False) -> List["InstallResult"]:
        """Install spellbook components for Antigravity."""
        from ..core import InstallResult

        results = []

        if not self.ensure_config_dir():
            return [
                InstallResult(
                    component="config_dir",
                    platform=self.platform_id,
                    success=False,
                    action="failed",
                    message=f"failed to create config directory {self.config_dir}",
                )
            ]

        # Context file
        results.append(self._install_context())

        # MCP Registration
        mcp_ok, mcp_msg = self._update_mcp_config()
        results.append(
            InstallResult(
                component="mcp",
                platform=self.platform_id,
                success=mcp_ok,
                action="installed" if mcp_ok else "failed",
                message=mcp_msg,
            )
        )

        # Skill Symlinks
        created, errors = self._ensure_skill_symlinks()
        results.append(
            InstallResult(
                component="skills",
                platform=self.platform_id,
                success=errors == 0,
                action="installed" if errors == 0 else "failed",
                message=f"created {created} skill symlinks ({errors} errors)",
            )
        )

        # Security Policy
        results.append(self._install_security_policy())

        return results

    def uninstall(self, skip_global_steps: bool = False) -> List["InstallResult"]:
        """Uninstall spellbook components from Antigravity."""
        from ..core import InstallResult

        results = []

        # Remove demarcated context section
        context_file = self.config_dir / "AGENTS.md"
        if context_file.exists():
            if self.dry_run:
                results.append(
                    InstallResult(
                        component="context_file",
                        platform=self.platform_id,
                        success=True,
                        action="skipped",
                        message=f"would remove demarcated section from {context_file}",
                    )
                )
            else:
                removed = remove_demarcated_section(context_file)
                results.append(
                    InstallResult(
                        component="context_file",
                        platform=self.platform_id,
                        success=removed,
                        action="removed" if removed else "skipped",
                        message=f"removed demarcated section from {context_file}" if removed else f"no demarcated section in {context_file}",
                    )
                )

        # Remove spellbook from mcp_config.json
        if self.mcp_config_path.exists():
            if self.dry_run:
                results.append(
                    InstallResult(
                        component="mcp",
                        platform=self.platform_id,
                        success=True,
                        action="skipped",
                        message="would remove spellbook from mcp_config.json",
                    )
                )
            else:
                try:
                    content = self.mcp_config_path.read_text(encoding="utf-8")
                    config = json.loads(content)
                    if "mcpServers" in config and "spellbook" in config["mcpServers"]:
                        del config["mcpServers"]["spellbook"]
                        self.mcp_config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
                        results.append(
                            InstallResult(
                                component="mcp",
                                platform=self.platform_id,
                                success=True,
                                action="removed",
                                message="removed spellbook from mcp_config.json",
                            )
                        )
                except (json.JSONDecodeError, OSError) as e:
                    results.append(
                        InstallResult(
                            component="mcp",
                            platform=self.platform_id,
                            success=False,
                            action="failed",
                            message=f"failed to update mcp_config.json: {e}",
                        )
                    )

        # Clean up skill symlinks
        target_skills = self.config_dir / "skills"
        if target_skills.exists():
            removed_links = 0
            for item in target_skills.iterdir():
                if item.is_symlink():
                    try:
                        resolved = item.resolve()
                        if str(resolved).startswith(str(self.spellbook_dir)):
                            remove_symlink(item, dry_run=self.dry_run)
                            removed_links += 1
                    except OSError:
                        pass
            results.append(
                InstallResult(
                    component="skills",
                    platform=self.platform_id,
                    success=True,
                    action="removed",
                    message=f"removed {removed_links} skill symlinks",
                )
            )

        return results

    def get_context_files(self) -> List[Path]:
        """Get paths to context files managed by Antigravity."""
        return [self.config_dir / "rules" / "spellbook.md"]

    def get_symlinks(self) -> List[Path]:
        """Get paths to symlinks created by Antigravity."""
        links = []
        target_skills = self.config_dir / "skills"
        if target_skills.exists():
            for item in target_skills.iterdir():
                if item.is_symlink():
                    links.append(item)
        return links

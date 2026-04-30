"""ForgeCode platform installer.

ForgeCode (tailcallhq/forgecode) supports:
- AGENTS.md custom rules at <config_dir>/AGENTS.md
- MCP via .mcp.json with top-level mcpServers (Claude Code shape)
- HTTP MCP transport with headers map for Bearer auth

Config dir resolution priority (per design Section 3):
1. $FORGE_CONFIG (when set)
2. ~/forge (legacy, only when pre-existing AND default config dir)
3. ~/.forge (default)

The .mcp.json file is created with mode 0600 atomically (via ``os.open`` with
the mode argument) because it contains a plaintext bearer token. The spellbook
server entry sets ``oauth: false`` to disable OAuth auto-detection on the
forge client side.

Reference: design doc 2026-04-30-forgecode-support-design.md, Section 3.
"""

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING, List, Tuple

from ..components.context_files import generate_codex_context
from ..components.mcp import DEFAULT_HOST, DEFAULT_PORT, get_mcp_auth_token
from ..demarcation import (
    get_installed_version,
    remove_demarcated_section,
    update_demarcated_section,
)
from .base import PlatformInstaller, PlatformStatus

if TYPE_CHECKING:
    from ..core import InstallResult


SPELLBOOK_SERVER_KEY: str = "spellbook"


def _write_mcp_config_secure(config_path: Path, config: dict) -> None:
    """Write JSON config with mode 0600 atomically (no TOCTOU window).

    Using ``os.open`` with the mode argument creates the file with 0600 from
    the start, avoiding the brief 0644 window between ``write_text`` and
    ``os.chmod`` that would let other local users read the bearer token.
    Mode bits are ignored on Windows (chmod was already a no-op there).
    """
    payload = json.dumps(config, indent=2) + "\n"
    fd = os.open(
        os.fspath(config_path),
        os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
        0o600,
    )
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(payload)


def _update_forgecode_mcp_config(
    config_path: Path, dry_run: bool = False
) -> Tuple[bool, str]:
    """Merge spellbook server into mcpServers; write 0600 atomically; oauth=false."""
    if dry_run:
        return (True, "would register MCP server (HTTP)")

    config_path.parent.mkdir(parents=True, exist_ok=True)

    config: dict = {}
    if config_path.exists():
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            config = {}

    if "mcpServers" not in config or not isinstance(config["mcpServers"], dict):
        config["mcpServers"] = {}

    daemon_url = f"http://{DEFAULT_HOST}:{DEFAULT_PORT}/mcp"
    action = (
        f"updated MCP server config (HTTP: {daemon_url})"
        if SPELLBOOK_SERVER_KEY in config["mcpServers"]
        else f"registered MCP server (HTTP: {daemon_url})"
    )

    server_entry: dict = {
        "url": daemon_url,
        "oauth": False,
    }
    token = get_mcp_auth_token()
    if token:
        server_entry["headers"] = {"Authorization": f"Bearer {token}"}

    config["mcpServers"][SPELLBOOK_SERVER_KEY] = server_entry

    _write_mcp_config_secure(config_path, config)
    return (True, action)


def _remove_forgecode_mcp_config(
    config_path: Path, dry_run: bool = False
) -> Tuple[bool, str]:
    """Remove only the spellbook entry from mcpServers; preserve other servers."""
    if not config_path.exists():
        return (True, "config not found")
    if dry_run:
        return (True, "would remove MCP server config")

    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return (True, "config is not valid JSON")

    servers = config.get("mcpServers")
    if not isinstance(servers, dict) or SPELLBOOK_SERVER_KEY not in servers:
        return (True, "MCP server was not configured")

    del servers[SPELLBOOK_SERVER_KEY]
    # Re-write with 0600: file might shrink to "{}" but mode stays restrictive.
    _write_mcp_config_secure(config_path, config)
    return (True, "removed MCP server config")


class ForgeCodeInstaller(PlatformInstaller):
    """Installer for ForgeCode platform (basic tier)."""

    @property
    def platform_name(self) -> str:
        return "ForgeCode"

    @property
    def platform_id(self) -> str:
        return "forgecode"

    @property
    def mcp_config_file(self) -> Path:
        """Path to <config_dir>/.mcp.json (forge mcpServers shape)."""
        return self.config_dir / ".mcp.json"

    @property
    def context_file(self) -> Path:
        """Path to <config_dir>/AGENTS.md."""
        return self.config_dir / "AGENTS.md"

    def _resolve_effective_config_dir(self) -> Path:
        """Return the config dir to use for all install/detect operations.

        Resolution priority (per design Section 3):
        1. self.config_dir if $FORGE_CONFIG was set (resolve_config_dirs already
           honored the env var; do not second-guess it).
        2. ~/forge if it pre-exists AND $FORGE_CONFIG is unset AND self.config_dir
           is the default (~/.forge).
        3. self.config_dir unchanged (the default ~/.forge).
        """
        if os.environ.get("FORGE_CONFIG"):
            return self.config_dir
        legacy = Path.home() / "forge"
        default = Path.home() / ".forge"
        if self.config_dir == default and legacy.exists() and legacy.is_dir():
            return legacy
        return self.config_dir

    def detect(self) -> PlatformStatus:
        """Detect ForgeCode install state via config dir and .mcp.json contents."""
        effective_dir = self._resolve_effective_config_dir()
        effective_context_file = effective_dir / "AGENTS.md"
        effective_mcp_config = effective_dir / ".mcp.json"

        installed_version = get_installed_version(effective_context_file)

        has_mcp = False
        if effective_mcp_config.exists():
            try:
                cfg = json.loads(effective_mcp_config.read_text(encoding="utf-8"))
                has_mcp = SPELLBOOK_SERVER_KEY in cfg.get("mcpServers", {})
            except json.JSONDecodeError:
                pass

        return PlatformStatus(
            platform=self.platform_id,
            available=effective_dir.exists(),
            installed=(installed_version is not None) or has_mcp,
            version=installed_version,
            details={
                "config_dir": str(effective_dir),
                "mcp_registered": has_mcp,
                "mcp_config": str(effective_mcp_config),
            },
        )

    def install(self, force: bool = False, skip_global_steps: bool = False) -> List["InstallResult"]:
        """Install AGENTS.md (demarcated) and .mcp.json (created atomically with mode 0600)."""
        from ..core import InstallResult

        effective_dir = self._resolve_effective_config_dir()
        effective_context_file = effective_dir / "AGENTS.md"
        effective_mcp_config = effective_dir / ".mcp.json"

        results: List[InstallResult] = []

        if not effective_dir.exists():
            results.append(
                InstallResult(
                    component="platform",
                    platform=self.platform_id,
                    success=True,
                    action="skipped",
                    message=f"{effective_dir} not found",
                )
            )
            return results

        # AGENTS.md (demarcated section, format identical to Codex/OpenCode)
        self._step("Updating AGENTS.md")
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
                    effective_context_file, spellbook_content, self.version
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

        # MCP server entry in .mcp.json
        self._step("Registering MCP server")
        success, msg = _update_forgecode_mcp_config(effective_mcp_config, self.dry_run)
        results.append(
            InstallResult(
                component="mcp_server",
                platform=self.platform_id,
                success=success,
                action="installed" if success else "failed",
                message=f"MCP server: {msg}",
            )
        )

        # Install-time warning: $FORGE_CONFIG unset means runtime override may diverge.
        if not self.dry_run and not os.environ.get("FORGE_CONFIG"):
            results.append(
                InstallResult(
                    component="env_warning",
                    platform=self.platform_id,
                    success=True,
                    action="warned",
                    message=(
                        "FORGE_CONFIG not set at install time; future forge sessions "
                        "that set FORGE_CONFIG to a different path will not see this install"
                    ),
                )
            )

        return results

    def uninstall(self, skip_global_steps: bool = False) -> List["InstallResult"]:
        """Remove demarcated AGENTS.md section and spellbook entry from .mcp.json."""
        from ..core import InstallResult

        effective_dir = self._resolve_effective_config_dir()
        effective_context_file = effective_dir / "AGENTS.md"
        effective_mcp_config = effective_dir / ".mcp.json"

        results: List[InstallResult] = []

        if not effective_dir.exists():
            return results

        if effective_context_file.exists():
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
                action, _backup = remove_demarcated_section(effective_context_file)
                results.append(
                    InstallResult(
                        component="AGENTS.md",
                        platform=self.platform_id,
                        success=True,
                        action=action,
                        message=f"AGENTS.md: {action}",
                    )
                )

        success, msg = _remove_forgecode_mcp_config(effective_mcp_config, self.dry_run)
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
        """Return AGENTS.md path managed by this installer (effective dir)."""
        return [self._resolve_effective_config_dir() / "AGENTS.md"]

    def get_symlinks(self) -> List[Path]:
        """ForgeCode installer creates no symlinks."""
        return []

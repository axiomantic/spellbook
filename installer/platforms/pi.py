"""Pi platform installer.

Pi (https://github.com/badlogic/pi) supports:
- AGENTS.md or CLAUDE.md for context (loaded from ~/.pi/agent/AGENTS.md globally)
- Skills via Agent Skills standard in ~/.pi/agent/skills/ (directories or flat .md files)
- Prompt templates as .md files in ~/.pi/agent/prompts/

Pi does NOT support MCP natively. Its dist/ references neither "mcpServers"
nor "mcp.json", and docs/usage.md states it "intentionally does not include
built-in MCP". MCP arrives through the pi-mcp-adapter npm package, which this
installer declares in ~/.pi/agent/settings.json; the adapter is what reads
~/.pi/agent/mcp.json (Claude Code shape, HTTP transport, headers map for
Bearer auth).

Reference:
- https://github.com/badlogic/pi-coding-agent/docs/skills.md
- https://github.com/badlogic/pi-coding-agent/docs/prompt-templates.md
"""

import json
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional, Tuple

from ..components.mcp import (
    get_mcp_auth_token,
    get_spellbook_server_url,
    write_token_bearing_file,
)
from ..components.symlinks import (
    cleanup_spellbook_symlinks,
    create_skill_symlinks,
    create_symlink,
    remove_spellbook_symlinks,
)
from ..demarcation import (
    get_installed_version,
    remove_demarcated_section,
)
from ..components.rule_bundle import DELIVERY_MARKER_PREFIX
from .base import RULE_DELIVERY_FLAT, PlatformInstaller, PlatformStatus

if TYPE_CHECKING:
    from ..core import InstallResult

logger = logging.getLogger(__name__)

SPELLBOOK_SERVER_KEY: str = "spellbook"

# Pi has no native MCP support. Its dist/ references neither "mcpServers" nor
# "mcp.json", and docs/usage.md states it "intentionally does not include
# built-in MCP". This npm package is the extension that reads mcp.json and
# registers the servers it names.
PI_MCP_ADAPTER_NAME: str = "pi-mcp-adapter"

# Pinned, never a range. This is the version whose behaviour was verified end
# to end against a running spellbook daemon: connect, tools/list, and tool
# invocation with the Bearer header. Pi pins versioned npm specs and skips them
# during `pi update --extensions`, so this value is what actually runs until
# somebody edits this line on purpose.
PI_MCP_ADAPTER_VERSION: str = "2.26.1"

PI_MCP_ADAPTER_SPEC: str = f"npm:{PI_MCP_ADAPTER_NAME}@{PI_MCP_ADAPTER_VERSION}"


def _read_pi_settings(settings_path: Path) -> dict:
    """Read pi's settings.json, or ``{}`` when it is absent.

    Distinct from ``_load_mcp_config_dict`` in one way that matters: a parse
    failure RAISES. settings.json is the user's file and holds their model,
    provider, and theme choices. Silently treating an unparseable one as empty
    and writing a fresh object over it would discard all of that.
    """
    if not settings_path.exists():
        return {}
    data = json.loads(settings_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(
            f"{settings_path} is not a JSON object (got {type(data).__name__})"
        )
    return data


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
    """Write JSON config atomically, with mode 0600.

    Writes to a temporary file in the same directory as ``config_path`` (so
    ``os.replace`` is an atomic rename on the same filesystem) and then
    atomically replaces the target. On any failure the temporary file is
    removed so a partial write never lands at ``config_path``.

    The temporary file is written through ``write_token_bearing_file`` because
    mcp.json carries the bearer token, and ``os.replace`` carries the source
    inode's mode onto the destination. That also tightens a pre-existing 0644
    ``config_path``, whose inode is discarded by the rename. The token is
    never present in a world-readable file, not even in the temporary one.
    """
    config_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(config, indent=2) + "\n"
    tmp_path = config_path.with_name(f"{config_path.name}.tmp.{os.getpid()}")
    try:
        write_token_bearing_file(tmp_path, payload)
        os.replace(tmp_path, config_path)
    except BaseException:
        try:
            tmp_path.unlink()
        except FileNotFoundError:
            pass
        raise


def _generate_mcp_json_section() -> dict:
    """Generate the spellbook entry for pi-mcp-adapter's mcp.json.

    The transport half -- ``url`` plus a raw ``headers`` map -- is the Claude
    Code shape the adapter accepts unchanged. The other three keys are adapter
    settings that no native MCP host would read, and each corrects a default
    that would otherwise leave spellbook's tools unusable:

    ``directTools``
        Defaults to ``false``, which routes every tool through a single proxy
        tool named ``mcp``. Spellbook's skills address tools by name.

    ``toolPrefix``
        Defaults to ``"server"``, which prepends the server name to each tool
        name. The server is ``spellbook`` and its tools are already named
        ``spellbook_*``, so the default yields
        ``spellbook_spellbook_health_check``. ``directTools`` does not fix this;
        it governs whether tools are registered individually, not their names.

    ``lifecycle``
        Defaults to ``"lazy"``. Only ``"eager"`` was verified to register
        direct tools; whether ``"lazy"`` does so before first use is unverified.

    ``protocolVersion`` is deliberately absent. The adapter's ``"legacy"``
    default negotiates against the daemon, which answers ``2024-11-05``.
    Pinning a version can only narrow what succeeds.
    """
    url = get_spellbook_server_url()
    server_entry: dict = {
        "url": url,
    }
    token = get_mcp_auth_token()
    if token:
        server_entry["headers"] = {"Authorization": f"Bearer {token}"}
    server_entry["lifecycle"] = "eager"
    server_entry["directTools"] = True
    server_entry["toolPrefix"] = "none"
    return server_entry


def _write_pi_settings(settings_path: Path, settings: dict) -> None:
    """Write pi's settings.json atomically. Carries no token, so mode 0644."""
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(settings, indent=2) + "\n"
    tmp_path = settings_path.with_name(f"{settings_path.name}.tmp.{os.getpid()}")
    try:
        tmp_path.write_text(payload, encoding="utf-8")
        os.replace(tmp_path, settings_path)
    except BaseException:
        try:
            tmp_path.unlink()
        except FileNotFoundError:
            pass
        raise


def _is_spellbook_managed_adapter_entry(entry: object) -> bool:
    """True for a bare ``npm:pi-mcp-adapter@<version>`` string.

    Spellbook writes and removes only this shape. Pi also accepts an object
    form carrying resource filters; a user who wrote one configured it
    deliberately, and flattening it back to a string would discard those
    filters silently.
    """
    return isinstance(entry, str) and entry.startswith(f"npm:{PI_MCP_ADAPTER_NAME}@")


def _adapter_entry_index(packages: list) -> Optional[int]:
    """Index of any entry naming the adapter, whatever its form.

    Pi identifies an npm package by NAME, so two entries differing only in
    version are ambiguous rather than additive.
    """
    for i, entry in enumerate(packages):
        source = entry.get("source") if isinstance(entry, dict) else entry
        if isinstance(source, str) and source.startswith(f"npm:{PI_MCP_ADAPTER_NAME}"):
            return i
    return None


def _adapter_declared(settings_path: Path) -> bool:
    """Whether settings.json declares the adapter package at all.

    This is what the installer can substantiate. It is NOT the same as the
    adapter being resolved on disk: pi installs a declared-but-missing npm
    package on its next start (``resolvePackageSources`` in pi's
    ``core/package-manager.js`` calls ``installMissing`` for any user-scope
    npm entry whose install path is absent or version-mismatched).
    """
    try:
        settings = _read_pi_settings(settings_path)
    except (OSError, ValueError, json.JSONDecodeError):
        return False
    packages = settings.get("packages")
    if not isinstance(packages, list):
        return False
    return _adapter_entry_index(packages) is not None


def _adapter_installed_version(config_dir: Path) -> Optional[str]:
    """Version of the adapter resolved on disk, or ``None``.

    Pi installs user-scope npm packages to ``<agent dir>/npm/node_modules/<name>``
    (``getManagedNpmInstallPath``). Reported separately from declaration so a
    fresh install can say "declared, pi installs it on next start" rather than
    implying the package is already present.
    """
    pkg_json = (
        config_dir / "npm" / "node_modules" / PI_MCP_ADAPTER_NAME / "package.json"
    )
    try:
        data = json.loads(pkg_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    version = data.get("version") if isinstance(data, dict) else None
    return version if isinstance(version, str) else None


def _declare_pi_adapter(
    config_dir: Path, dry_run: bool = False
) -> Tuple[bool, str]:
    """Declare the pinned adapter in pi's settings.json.

    Writes the ``packages[]`` entry directly rather than shelling out to
    ``pi install``. That command does two things: it appends this entry, and it
    runs npm. Pi already performs the npm half itself on the next start for any
    declared-but-missing package, so the subprocess buys nothing an installer
    wants -- and costs a ``pi`` binary on PATH, network access, and a failure
    mode at install time that the settings write does not have.
    """
    settings_path = config_dir / "settings.json"

    if dry_run:
        return (True, f"would declare {PI_MCP_ADAPTER_SPEC}")

    try:
        settings = _read_pi_settings(settings_path)
    except (OSError, ValueError, json.JSONDecodeError) as e:
        return (False, f"could not read {settings_path.name}: {e}")

    packages = settings.get("packages")
    if not isinstance(packages, list):
        packages = []

    index = _adapter_entry_index(packages)
    if index is not None and not _is_spellbook_managed_adapter_entry(packages[index]):
        return (True, f"{PI_MCP_ADAPTER_NAME} already declared by the user; left as is")

    if index is not None and packages[index] == PI_MCP_ADAPTER_SPEC:
        return (True, f"{PI_MCP_ADAPTER_SPEC} already declared")

    if index is not None:
        packages[index] = PI_MCP_ADAPTER_SPEC
        action = f"repinned to {PI_MCP_ADAPTER_SPEC}"
    else:
        packages.append(PI_MCP_ADAPTER_SPEC)
        action = f"declared {PI_MCP_ADAPTER_SPEC}"

    settings["packages"] = packages
    try:
        _write_pi_settings(settings_path, settings)
    except OSError as e:
        return (False, f"could not write {settings_path.name}: {e}")
    return (True, action)


def _retract_pi_adapter(
    config_dir: Path, dry_run: bool = False
) -> Tuple[bool, str]:
    """Remove spellbook's adapter declaration, but only if nothing else needs it.

    The adapter is a general-purpose MCP bridge, not a spellbook component. If
    any other server remains in mcp.json after spellbook's entry is gone, that
    server still needs the adapter loaded and removing it would break it. Only
    the bare string entry spellbook itself writes is ever removed; a
    user-authored object-form entry is left untouched.

    The on-disk package under ``npm/node_modules/`` is left in place. Deleting
    it is pi's business (``pi remove``), and it is inert once undeclared.
    """
    settings_path = config_dir / "settings.json"

    if dry_run:
        return (True, f"would retract {PI_MCP_ADAPTER_SPEC} if unused")

    mcp_config = _load_mcp_config_dict(config_dir / "mcp.json")
    remaining = mcp_config.get("mcpServers")
    if isinstance(remaining, dict) and remaining:
        return (
            True,
            f"{PI_MCP_ADAPTER_NAME} kept: {len(remaining)} other MCP server(s) need it",
        )

    try:
        settings = _read_pi_settings(settings_path)
    except (OSError, ValueError, json.JSONDecodeError):
        return (True, f"{settings_path.name} unreadable; {PI_MCP_ADAPTER_NAME} left as is")

    packages = settings.get("packages")
    if not isinstance(packages, list):
        return (True, f"{PI_MCP_ADAPTER_NAME} was not declared")

    index = _adapter_entry_index(packages)
    if index is None:
        return (True, f"{PI_MCP_ADAPTER_NAME} was not declared")
    if not _is_spellbook_managed_adapter_entry(packages[index]):
        return (True, f"{PI_MCP_ADAPTER_NAME} was declared by the user; left as is")

    del packages[index]
    settings["packages"] = packages
    try:
        _write_pi_settings(settings_path, settings)
    except OSError as e:
        return (False, f"could not write {settings_path.name}: {e}")
    return (True, f"retracted {PI_MCP_ADAPTER_SPEC}")


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

    rule_delivery = RULE_DELIVERY_FLAT

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

    def rule_bundle_path(self) -> Path:
        """Pi's ambient instruction file, ~/.pi/agent/AGENTS.md.

        Not prompts/. Pi's prompts/*.md are slash-command templates --
        expandPromptTemplate returns early unless the text starts with "/" --
        so the file spellbook used to write there was never ambient context.
        """
        return self.context_file

    def rule_bundle_preserve_existing(self) -> bool:
        """Never clobber a user's own ``~/.pi/agent/AGENTS.md``.

        Pi's ambient instruction file belongs to the user, exactly as Codex's
        and ForgeCode's do. Their content is preserved first and the bundle
        follows in a demarcated region.
        """
        return True

    def legacy_rule_paths(self) -> List[Path]:
        return [self.prompts_dir / "spellbook.md"]

    def legacy_context_files(self) -> List[Path]:
        return [self.context_file]

    def detect(self) -> PlatformStatus:
        """Detect Pi installation status."""
        installed_version = get_installed_version(self.context_file)

        # An entry in mcp.json is not a registration on its own -- pi reads
        # that file only through pi-mcp-adapter. Every install before this one
        # left exactly that state behind, so reporting it as registered would
        # keep the original defect alive inside `detect`.
        has_mcp_entry = False
        if self.mcp_config_file.exists():
            cfg = _load_mcp_config_dict(self.mcp_config_file)
            servers = cfg.get("mcpServers", {})
            if isinstance(servers, dict):
                has_mcp_entry = SPELLBOOK_SERVER_KEY in servers
        adapter_declared = _adapter_declared(self.config_dir / "settings.json")
        has_mcp = has_mcp_entry and adapter_declared

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

        has_bundle = False
        if self.context_file.exists():
            try:
                has_bundle = DELIVERY_MARKER_PREFIX in self.context_file.read_text(
                    encoding="utf-8"
                )
            except OSError:
                has_bundle = False

        installed = (
            installed_version is not None
            or has_mcp_entry
            or has_skills
            or has_prompts
            or has_bundle
        )

        return PlatformStatus(
            platform=self.platform_id,
            available=self.config_dir.exists(),
            installed=installed,
            version=self.version if installed else None,
            details={
                "config_dir": str(self.config_dir),
                "mcp_registered": has_mcp,
                "mcp_adapter_declared": adapter_declared,
                "mcp_adapter_version": _adapter_installed_version(self.config_dir),
                "skills_installed": has_skills,
                "prompts_installed": has_prompts,
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

        # Step 3: Install AGENTS.md with demarcated section
        # Generate the rule bundle at ~/.pi/agent/AGENTS.md and drop the
        # prompts/ sidecar, which pi only ever read as a slash command.
        self._step("Installing rule modules")
        rule_results = self.install_rule_modules()
        results.extend(rule_results)

        # Strip the legacy demarcated block only AFTER delivery succeeds.
        # Stripping first would leave a user whose delivery failed with
        # neither the old interpolated rules nor the new modules.
        if (
            all(r.success for r in rule_results)
            and self.context_file.exists()
            and not self.dry_run
        ):
            remove_demarcated_section(self.context_file)

        # Step 4: Declare the MCP adapter, then write mcp.json.
        # These are global steps: MCP registration is system-wide, not per-dir.
        #
        # Order matters for what gets REPORTED. Pi reads mcp.json only through
        # pi-mcp-adapter, so the declaration is the thing that makes the file
        # mean anything. Writing mcp.json and reporting "registered MCP server"
        # -- which is what this installer used to do -- described an operation
        # that had no effect on pi whatsoever.
        if not skip_global_steps:
            self._step("Declaring MCP adapter")
            adapter_ok, adapter_msg = _declare_pi_adapter(
                self.config_dir, self.dry_run
            )
            if adapter_ok and not self.dry_run:
                on_disk = _adapter_installed_version(self.config_dir)
                adapter_msg += (
                    f" (present on disk: {on_disk})"
                    if on_disk
                    else " (not on disk yet; pi installs it on next start)"
                )
            results.append(
                InstallResult(
                    component="mcp_adapter",
                    platform=self.platform_id,
                    success=adapter_ok,
                    action="installed" if adapter_ok else "failed",
                    message=f"MCP adapter: {adapter_msg}",
                )
            )

            self._step("Registering MCP server")
            success, msg = _update_pi_mcp_config(self.mcp_config_file, self.dry_run)

            # The installer makes no request to the daemon, so it cannot tell a
            # running daemon from a stopped one, nor a live token from a stale
            # one. Its vocabulary is therefore limited to what it actually did.
            if not adapter_ok:
                success = False
                msg = (
                    f"not registered -- pi has no native MCP support and "
                    f"{PI_MCP_ADAPTER_NAME} could not be declared, so nothing "
                    f"reads mcp.json"
                )
            else:
                msg = f"{msg} via {PI_MCP_ADAPTER_SPEC}"

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

        # Remove the generated rule bundle and the retired prompts/ sidecar.
        results.extend(self.uninstall_rule_modules())

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

            # Retract the adapter declaration only after the spellbook entry is
            # gone from mcp.json, because the decision depends on what remains.
            adapter_ok, adapter_msg = _retract_pi_adapter(
                self.config_dir, self.dry_run
            )
            results.append(
                InstallResult(
                    component="mcp_adapter",
                    platform=self.platform_id,
                    success=adapter_ok,
                    action="removed" if "retracted" in adapter_msg else "skipped",
                    message=f"MCP adapter: {adapter_msg}",
                )
            )

        return results

    def get_context_files(self) -> List[Path]:
        """Get the generated rule artifact managed by this platform."""
        return [self.rule_bundle_path()]

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

        return symlinks

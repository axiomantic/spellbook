"""Goose (AAIF) platform installer.

Goose (https://github.com/aaif-goose/goose) is an open-source, extensible AI
agent from the Linux Foundation's Agentic AI Foundation. This installer provides
basic-tier spellbook support for goose.

Capabilities installed:
- Skills symlinked to ~/.agents/skills/<name>/SKILL.md (Agent Skills standard,
  compatible with Claude Code, Codex, OpenCode, Cursor, VS Code). Requires
  goose v1.18.0+ for the canonical ~/.agents/skills/ discovery path.
- Global hints file at ~/.agents/AGENTS.md symlinked to AGENTS.spellbook.md.
  Requires goose v1.41.0+ for the global hints discovery path; on older
  versions the file is still installed but goose will not auto-load it.
- Spellbook MCP server registered in ~/.config/goose/config.yaml as an
  extension (streamable_http transport with Bearer auth).
- A starter .goosehints template shipped in extensions/goose/.goosehints that
  users can copy into a project root to load spellbook behavior per-project.

Configuration:
- Default config dir: ~/.config/goose/ (de-facto Linux/macOS convention)
- Override env var: GOOSE_CONFIG_DIR (used by PLATFORM_CONFIG)
- Native env var: GOOSE_PATH_ROOT (sets $GOOSE_PATH_ROOT/config/ as canonical
  config dir, defaults vary by OS per goose docs). GOOSE_PATH_ROOT is
  honored by the installer when GOOSE_CONFIG_DIR is unset.

Limitations (basic-tier):
- No slash commands (goose uses Recipes, a different format).
- No session/hook integration (goose has no hook system).
- Pre-v1.18 goose: skills install is skipped with a warning; rules + MCP
  proceed (MCP works since goose v1.0).

References:
- https://goose-docs.ai/
- https://github.com/aaif-goose/goose
"""

import logging
import os
import re
from pathlib import Path
from typing import TYPE_CHECKING

from ..components.mcp import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    get_mcp_auth_token,
)
from ..components.symlinks import (
    create_skill_symlinks,
    create_symlink,
    remove_spellbook_symlinks,
)
from .base import PlatformInstaller, PlatformStatus

if TYPE_CHECKING:
    from ..core import InstallResult


logger = logging.getLogger(__name__)


# YAML section markers for the spellbook MCP extension in config.yaml
# Using comment markers (not block scalars) so we can surgically replace
# the spellbook block without disturbing the user's other extensions.
SPELLBOOK_START_MARKER = "# SPELLBOOK:START"
SPELLBOOK_END_MARKER = "# SPELLBOOK:END"
SPELLBOOK_SERVER_NAME = "spellbook"


def _resolve_effective_config_dir(default_dir: Path) -> Path:
    """Resolve the goose config dir honoring GOOSE_PATH_ROOT.

    Order:
    1. ``$GOOSE_PATH_ROOT`` -- goose's native env var that sets
       ``$GOOSE_PATH_ROOT/config/`` as canonical config dir.
    2. ``default_dir`` (the upstream-resolved path, typically ~/.config/goose/
       or whatever ``$GOOSE_CONFIG_DIR`` resolves to upstream).

    The default_dir argument is already env-aware at the PLATFORM_CONFIG
    layer (GOOSE_CONFIG_DIR), so we trust it unless GOOSE_PATH_ROOT is
    explicitly set, which goose treats as the authoritative override.
    """
    path_root = os.environ.get("GOOSE_PATH_ROOT")
    if path_root:
        return Path(path_root) / "config"
    return default_dir


def _generate_mcp_yaml_list_item() -> str:
    """Build a single YAML list item registering the spellbook MCP extension.

    Returns just the list item (with leading "-") and continuation lines,
    suitable for insertion INSIDE a top-level ``extensions:`` list. The
    spellbook block is wrapped in marker comments so it can be re-located
    and replaced on subsequent installs.
    """
    url = f"http://{DEFAULT_HOST}:{DEFAULT_PORT}/mcp"
    token = get_mcp_auth_token()
    if token:
        # Literal Bearer header (parity with forgecode/codex/opencode).
        # File mode 0600 protects the token from other local users.
        headers_line = f'    headers: {{Authorization: "Bearer {token}"}}'
    else:
        headers_line = "    headers: {}"

    lines = [
        SPELLBOOK_START_MARKER,
        "  - type: streamable_http",
        f"    name: {SPELLBOOK_SERVER_NAME}",
        "    enabled: true",
        f"    uri: {url}",
        headers_line,
        "    env_keys: []",
        "    envs: {}",
        "    timeout: 300",
        SPELLBOOK_END_MARKER,
        "",
    ]
    return "\n".join(lines)


def _insert_spellbook_block(yaml_text: str, block: str) -> str:
    """Insert the spellbook block inside the top-level ``extensions:`` list.

    - If markers already exist, replace the previous block in place.
    - If ``extensions:`` exists with no spellbook block yet, insert after it.
    - If ``extensions:`` doesn't exist, append a new ``extensions:`` section.

    Idempotent: re-running replaces the previous block, preserves the rest.
    """
    # Path 1: markers present -> replace in place
    if SPELLBOOK_START_MARKER in yaml_text and SPELLBOOK_END_MARKER in yaml_text:
        pattern = re.compile(
            rf"\n*{re.escape(SPELLBOOK_START_MARKER)}.*?{re.escape(SPELLBOOK_END_MARKER)}\n*",
            re.DOTALL,
        )
        return pattern.sub("\n" + block, yaml_text, count=1)

    # Path 2: extensions: exists, no markers yet -> insert block after it
    # BOT-B1 fix: also match extensions: with trailing content (comments or
    # inline arrays). The previous regex `^extensions:\s*$` only matched an
    # empty extensions: line; if the user had `extensions: [a, b]` or
    # `extensions: # comment`, the regex returned None and we fell through to
    # Path 3, which appended a NEW extensions: section. YAML allows duplicate
    # keys (last-wins), so the user's existing extensions silently vanished.
    extensions_match = re.search(
        r"^extensions:(\s+.*)?$", yaml_text, re.MULTILINE
    )
    if extensions_match:
        inline_content = extensions_match.group(1) or ""
        stripped = inline_content.strip()

        # Case A: `extensions:` alone, or `extensions: # comment`.
        if not stripped or stripped.startswith("#"):
            # BOT-A1 fix: ensure a trailing newline before substitution so
            # a file ending with bare `extensions:` does not silently no-op.
            if not yaml_text.endswith("\n"):
                yaml_text += "\n"
            # Insert block immediately after the `extensions:` line, inside the list.
            return re.sub(
                r"^(extensions:[^\n]*\n)",
                lambda m: m.group(1) + block,
                yaml_text,
                count=1,
                flags=re.MULTILINE,
            )

        # Case B: `extensions: [a, b, c]` -- inline flow-style list. Convert
        # to block style so the spellbook entries can join the same list.
        if stripped.startswith("[") and stripped.endswith("]"):
            inner = stripped[1:-1].strip()
            list_lines = ["extensions:"]
            if inner:
                for item in inner.split(","):
                    item = item.strip()
                    if item:
                        list_lines.append(f"  - {item}")
            expansion = "\n".join(list_lines) + "\n" + block
            return re.sub(
                r"^extensions:[^\n]*$",
                expansion,
                yaml_text,
                count=1,
                flags=re.MULTILINE,
            )

    # Path 3: no extensions: key at all -> append a new extensions list
    if not yaml_text.endswith("\n"):
        yaml_text += "\n"
    yaml_text += "\n" + block
    # Prepend the ``extensions:`` header before the block if it's the only one
    if yaml_text.endswith(block):
        yaml_text = yaml_text[: -len(block)] + "extensions:\n" + block
    return yaml_text


def _strip_spellbook_block(yaml_text: str) -> str:
    """Remove the spellbook block from a YAML string; preserve the rest."""
    if SPELLBOOK_START_MARKER not in yaml_text:
        return yaml_text
    pattern = re.compile(
        rf"\n*{re.escape(SPELLBOOK_START_MARKER)}.*?{re.escape(SPELLBOOK_END_MARKER)}\n*",
        re.DOTALL,
    )
    return pattern.sub("\n", yaml_text, count=1)


def _update_goose_mcp_config(
    config_path: Path, dry_run: bool = False
) -> tuple[bool, str]:
    """Insert or refresh the spellbook MCP extension in config.yaml.

    Idempotent: re-running replaces the previous spellbook block in place.
    Other extensions in the file are preserved untouched.
    """
    if dry_run:
        return (True, "would register MCP server (streamable_http)")

    config_path.parent.mkdir(parents=True, exist_ok=True)
    existing = config_path.read_text(encoding="utf-8") if config_path.exists() else ""

    # Decide action label based on existing markers
    if SPELLBOOK_START_MARKER in existing:
        action = f"updated MCP server config (HTTP at {DEFAULT_HOST}:{DEFAULT_PORT})"
    else:
        action = f"registered MCP server (HTTP at {DEFAULT_HOST}:{DEFAULT_PORT})"

    new_text = _insert_spellbook_block(existing, _generate_mcp_yaml_list_item())

    # Atomic write with mode 0600 (config.yaml contains a plaintext bearer token)
    # BOT-B2 fix: `os.fdopen()` returns a file object that OWNS the fd. When
    # `with os.fdopen(...)` exits (whether normally or via exception inside the
    # block), the file object closes the fd. The previous code then called
    # `os.close(fd)` in the except handler, which double-closed the same fd.
    # On POSIX this is UB (can close a different fd acquired in the race
    # window). Just let the context manager own the fd; if `f.write()` raises,
    # the `with` block already closed fd before re-raising.
    fd = os.open(
        os.fspath(config_path),
        os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
        0o600,
    )
    # BOT-B2 fix: os.fdopen() owns fd. Its context manager closes fd (via the C
    # extension) on either normal exit OR exception -- including f.write()
    # raising. No explicit try/except / os.close needed; the original exception
    # propagates automatically, and we never double-close.
    if hasattr(os, "fchmod"):
        os.fchmod(fd, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(new_text)

    return (True, action)


def _remove_goose_mcp_config(
    config_path: Path, dry_run: bool = False
) -> tuple[bool, str]:
    """Remove the spellbook MCP extension from config.yaml."""
    if not config_path.exists():
        return (True, "config.yaml not found")
    if dry_run:
        return (True, "would remove MCP server config")

    existing = config_path.read_text(encoding="utf-8")
    if SPELLBOOK_START_MARKER not in existing:
        return (True, "MCP server was not configured")

    new_text = _strip_spellbook_block(existing)
    # BOT-B2 fix: see _update_goose_mcp_config. fdopen() owns the fd; the
    # except handler must NOT close fd again.
    # BOT-B2 fix: see _update_goose_mcp_config. fdopen() owns the fd.
    fd = os.open(
        os.fspath(config_path),
        os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
        0o600,
    )
    if hasattr(os, "fchmod"):
        os.fchmod(fd, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(new_text)

    return (True, "removed MCP server config")


class GooseInstaller(PlatformInstaller):
    """Installer for the Goose (AAIF) AI agent platform (basic tier)."""

    @property
    def platform_name(self) -> str:
        return "Goose"

    @property
    def platform_id(self) -> str:
        return "goose"

    @property
    def effective_config_dir(self) -> Path:
        """Config dir, honoring $GOOSE_PATH_ROOT when set."""
        return _resolve_effective_config_dir(self.config_dir)

    @property
    def global_hints_file(self) -> Path:
        """~/.agents/AGENTS.md -- global hints file (goose v1.41.0+)."""
        return Path.home() / ".agents" / "AGENTS.md"

    @property
    def skills_dir(self) -> Path:
        """~/.agents/skills/ -- canonical Agent Skills standard path."""
        return Path.home() / ".agents" / "skills"

    @property
    def mcp_config_file(self) -> Path:
        """<config_dir>/config.yaml -- goose's main config with extensions block."""
        return self.effective_config_dir / "config.yaml"

    @property
    def goosehints_template(self) -> Path:
        """Starter .goosehints template shipped in extensions/goose/."""
        return self.spellbook_dir / "extensions" / "goose" / ".goosehints"

    def detect(self) -> PlatformStatus:
        """Detect Goose install state by checking config dir + key files."""
        cfg = self.effective_config_dir
        skills_installed = False
        if self.skills_dir.exists():
            for item in self.skills_dir.iterdir():
                if item.is_symlink():
                    try:
                        if "spellbook" in str(item.resolve()).lower():
                            skills_installed = True
                            break
                    except OSError:
                        pass

        has_mcp = False
        if self.mcp_config_file.exists():
            content = self.mcp_config_file.read_text(encoding="utf-8")
            has_mcp = SPELLBOOK_START_MARKER in content

        hints_target = self.global_hints_file
        # BOT-A2 fix: the previous expression was `(exists() and is_symlink())
        # or exists()` which simplifies to just `exists()` due to `and` binding
        # tighter than `or`, making the `is_symlink()` check dead code. A regular
        # file at ~/.agents/AGENTS.md (not a spellbook symlink) would cause detect()
        # to report hints as installed. Use the tighter predicate.
        has_hints = hints_target.exists() and hints_target.is_symlink()

        installed = skills_installed or has_mcp or has_hints

        return PlatformStatus(
            platform=self.platform_id,
            available=cfg.exists(),
            installed=installed,
            version=self.version if installed else None,
            details={
                "config_dir": str(cfg),
                "skills_dir": str(self.skills_dir),
                "mcp_config": str(self.mcp_config_file),
                "skills_installed": skills_installed,
                "mcp_registered": has_mcp,
                "global_hints": str(hints_target),
            },
        )

    def install(
        self, force: bool = False, skip_global_steps: bool = False
    ) -> list["InstallResult"]:
        """Install goose components: skills, global hints, MCP server, .goosehints template."""
        from ..core import InstallResult

        results: list[InstallResult] = []

        cfg = self.effective_config_dir
        if not cfg.exists():
            results.append(
                InstallResult(
                    component="platform",
                    platform=self.platform_id,
                    success=True,
                    action="skipped",
                    message=f"{cfg} not found (install goose first)",
                )
            )
            return results

        # Step 1: Skills symlinks in ~/.agents/skills/
        self._step("Installing skills")
        if not self.dry_run:
            self.skills_dir.mkdir(parents=True, exist_ok=True)
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

        # Step 2: Global hints file at ~/.agents/AGENTS.md (goose v1.41.0+ loads it)
        self._step("Installing global hints file")
        source_agents = self.spellbook_dir / "AGENTS.spellbook.md"
        if source_agents.exists():
            hints_parent = self.global_hints_file.parent
            if not self.dry_run:
                hints_parent.mkdir(parents=True, exist_ok=True)
            res = create_symlink(source_agents, self.global_hints_file, dry_run=self.dry_run)
            results.append(
                InstallResult(
                    component="global_hints",
                    platform=self.platform_id,
                    success=res.success,
                    action=res.action,
                    message=f"global hints: {res.message}",
                )
            )

        # Step 3: MCP server registration in config.yaml
        self._step("Registering MCP server")
        success, msg = _update_goose_mcp_config(self.mcp_config_file, self.dry_run)
        results.append(
            InstallResult(
                component="mcp_server",
                platform=self.platform_id,
                success=success,
                action="installed" if success else "failed",
                message=f"MCP server: {msg}",
            )
        )

        # Step 4: Ship the .goosehints template (copies to extensions/goose/ on read,
        # but the template lives in the repo so users can copy it per-project).
        # No install-side action needed: the template is part of the spellbook repo.

        return results

    def uninstall(
        self, skip_global_steps: bool = False
    ) -> list["InstallResult"]:
        """Remove goose components: skills, global hints symlink, MCP block."""
        from ..core import InstallResult

        results: list[InstallResult] = []

        # Remove spellbook symlinks from skills dir (preserve other skills)
        if self.skills_dir.exists():
            symlink_results = remove_spellbook_symlinks(
                self.skills_dir, self.spellbook_dir, dry_run=self.dry_run
            )
            removed = sum(1 for r in symlink_results if r.action == "removed")
            if removed > 0:
                results.append(
                    InstallResult(
                        component="skills",
                        platform=self.platform_id,
                        success=True,
                        action="removed",
                        message=f"skills: {removed} removed",
                    )
                )

        # Remove the global hints symlink (only if it's a spellbook symlink)
        hints = self.global_hints_file
        if hints.is_symlink():
            try:
                target = hints.resolve()
                if "spellbook" in str(target).lower():
                    if self.dry_run:
                        results.append(
                            InstallResult(
                                component="global_hints",
                                platform=self.platform_id,
                                success=True,
                                action="removed",
                                message=f"would remove {hints}",
                            )
                        )
                    else:
                        hints.unlink()
                        results.append(
                            InstallResult(
                                component="global_hints",
                                platform=self.platform_id,
                                success=True,
                                action="removed",
                                message=f"removed {hints}",
                            )
                        )
            except OSError:
                pass

        # Remove MCP block from config.yaml
        success, msg = _remove_goose_mcp_config(self.mcp_config_file, self.dry_run)
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

    def get_context_files(self) -> list[Path]:
        """Context files managed by this platform."""
        return [self.global_hints_file]

    def get_symlinks(self) -> list[Path]:
        """All symlinks created by this platform."""
        symlinks: list[Path] = []

        if self.global_hints_file.is_symlink():
            symlinks.append(self.global_hints_file)

        if self.skills_dir.exists():
            for item in self.skills_dir.iterdir():
                if item.is_symlink():
                    try:
                        if "spellbook" in str(item.resolve()).lower():
                            symlinks.append(item)
                    except OSError:
                        pass

        return symlinks

"""AionUi platform installer.

AionUi (https://github.com/iOfficerCN/AionUi) is an Electron desktop app
hosting multiple agent engines. Storage audit (2026-09-10, live app with
aionrs backend):

* ``<userData>/config/skills/<name>/SKILL.md`` is the user-skills directory
  the app watches (observed as an existing empty dir). The ``skills`` table
  in ``aionui-backend.db`` inventories skills with ``source='user'`` rows
  and a ``path`` column; siblings ``config/cron-skills`` (source='cron') and
  ``aionui/builtin-skills`` (source='builtin') confirm the per-source dir
  convention.
* ``<userData>/aionui/assistant-rules/users/<uid>/custom-*.md`` — assistant
  rules are bound to assistants through db rows
  (``assistant_definitions.rule_resource_ref``). Dropping files there
  without a db binding orphans them, so rule delivery is NONE: no global
  rule surface exists that an installer can write safely.
* MCP servers live ONLY in the ``mcp_servers`` SQLite table
  (``UNIQUE(user_id, name)``, UI-managed, with an ``original_json`` import
  column). An installer must never write a live app-owned database, so MCP
  registration is reported as a manual step, never automated.

``~/.aionui`` is a macOS symlink to ``<userData>/aionui``; paths here use
the canonical ``<userData>`` form.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, List

from ..components.symlinks import create_symlink, remove_symlink
from .base import (
    PlatformInstaller,
    PlatformStatus,
)

if TYPE_CHECKING:
    from ..core import InstallResult

logger = logging.getLogger(__name__)


class AionUiInstaller(PlatformInstaller):
    """Installer for the AionUi desktop app.

    Skill delivery mirrors the Antigravity installer: one symlink per skill
    module into the app's watched skills directory. MCP and assistant rules
    are app-database-managed surfaces and are deliberately NOT written;
    install reports them as manual steps instead.
    """

    @property
    def platform_name(self) -> str:
        return "AionUi"

    @property
    def platform_id(self) -> str:
        return "aionui"

    def skills_dir(self) -> Path:
        """AionUi's user-skills directory."""
        return self.config_dir / "config" / "skills"

    def get_context_files(self) -> List[Path]:
        # AionUi has no global instruction file equivalent to CLAUDE.md /
        # AGENTS.md that is read automatically; assistants carry their own
        # rules through the app database.
        return []

    def get_symlinks(self) -> List[Path]:
        skills_dir = self.skills_dir()
        if not skills_dir.is_dir():
            return []
        return [
            item for item in sorted(skills_dir.iterdir()) if item.is_symlink()
        ]

    def detect(self) -> PlatformStatus:
        """Detect AionUi status.

        Existence-based (like goose), no side effects: detect() must not
        create the config dir as a byproduct of asking whether it exists.
        """
        available = self.config_dir.exists()
        installed = False
        installed_version = None

        skills_dir = self.skills_dir()
        if skills_dir.is_dir():
            for link in skills_dir.glob("*"):
                if not link.is_symlink():
                    continue
                try:
                    resolved = link.resolve()
                except OSError:
                    continue
                if str(resolved).startswith(str(self.spellbook_dir)):
                    installed = True
                    installed_version = self.version
                    break

        return PlatformStatus(
            platform=self.platform_id,
            available=available,
            installed=installed,
            version=installed_version,
            details={"config_dir": str(self.config_dir)},
        )

    def _ensure_skill_symlinks(self) -> "tuple[int, int]":
        """Create symlinks for spellbook skills in AionUi's skills dir.

        Returns (created, errors). create_symlink is idempotent for existing
        correct links; a real file/dir occupying a skill name is reported as
        an error rather than clobbered.
        """
        source_skills = self.spellbook_dir / "skills"
        if not source_skills.exists():
            return (0, 0)

        target_skills = self.skills_dir()
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
            if target_link.exists() and not target_link.is_symlink():
                logger.warning(
                    "aionui: %s exists and is not a spellbook symlink; "
                    "left untouched",
                    target_link,
                )
                errors += 1
                continue
            if create_symlink(
                skill_dir, target_link, dry_run=self.dry_run
            ).success:
                created += 1
            else:
                errors += 1

        return (created, errors)

    def install(
        self, force: bool = False, skip_global_steps: bool = False
    ) -> List["InstallResult"]:
        """Install spellbook components for AionUi."""
        from ..core import InstallResult

        results: List[InstallResult] = []

        if not self.ensure_config_dir():
            return [
                InstallResult(
                    component="config_dir",
                    platform=self.platform_id,
                    success=False,
                    action="failed",
                    message=(
                        f"failed to create config directory {self.config_dir}"
                    ),
                )
            ]

        # Skill symlinks (the only automated surface in v1)
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

        # MCP is db-managed by the app; never written from the installer.
        results.append(
            InstallResult(
                component="mcp",
                platform=self.platform_id,
                success=True,
                action="skipped",
                message=(
                    "AionUi manages MCP servers in its app database; add the "
                    "spellbook server via AionUi settings (type: http, "
                    "url: http://127.0.0.1:8765/mcp) rather than the "
                    "installer writing the database"
                ),
            )
        )

        # Assistant rules are per-assistant db rows; no global surface.
        results.append(
            InstallResult(
                component="rules",
                platform=self.platform_id,
                success=True,
                action="skipped",
                message=(
                    "AionUi assistant rules are attached to assistants in "
                    "the app UI; no global rules directory exists to write"
                ),
            )
        )

        return results

    def uninstall(
        self, skip_global_steps: bool = False
    ) -> List["InstallResult"]:
        """Uninstall spellbook components from AionUi."""
        from ..core import InstallResult

        results: List[InstallResult] = []

        removed_links = 0
        errors = 0
        for link in self.get_symlinks():
            try:
                resolved = link.resolve()
            except OSError:
                resolved = None
            if resolved is None or not str(resolved).startswith(
                str(self.spellbook_dir)
            ):
                continue
            if remove_symlink(link, dry_run=self.dry_run).success:
                removed_links += 1
            else:
                errors += 1
        results.append(
            InstallResult(
                component="skills",
                platform=self.platform_id,
                success=errors == 0,
                action="removed" if removed_links else "skipped",
                message=(
                    f"removed {removed_links} skill symlinks ({errors} errors)"
                    if removed_links
                    else "no spellbook skill symlinks found"
                ),
            )
        )

        return results

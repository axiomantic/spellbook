"""
Prime Agent platform installer.

Prime Agent (https://github.com/prime-intellect-ai/prime-agent) is an RLM
(Recursive Language Model) with:
- A persistent IPython kernel (stateful across turns)
- Agent Skills standard for skill discovery
- Sub-agent spawning via `await rlm('task')`
- Continual harness (CRUD for memories, skills, subagents, prompt notes)
- No MCP client (uses Python-backed skills and kernel instead)
- No hooks system
- Skill discovery in ~/.prime/agent/skills/ (global) and .prime/agent/skills/ (project)

Key differences from other platforms:
- Skills are the primary content mechanism (no separate commands/prompts concept)
- No MCP registration needed (prime-agent connects differently)
- No hooks installation (no hook system in prime-agent)
- AGENTS.spellbook.md is installed as a skill, not injected into system prompt
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, List

from ..components.symlinks import (
    cleanup_spellbook_symlinks,
    create_skill_symlinks,
    create_symlink,
)
from .base import PlatformInstaller, PlatformStatus

if TYPE_CHECKING:
    from ..core import InstallResult

logger = logging.getLogger(__name__)


class PrimeAgentInstaller(PlatformInstaller):
    """Installer for Prime Agent platform."""

    @property
    def platform_name(self) -> str:
        return "Prime Agent"

    @property
    def platform_id(self) -> str:
        return "prime_agent"

    @property
    def skills_dir(self) -> Path:
        """Path to ~/.prime/agent/skills/."""
        return self.config_dir / "skills"

    def detect(self) -> PlatformStatus:
        """Detect Prime Agent installation status."""
        has_skills = False
        if self.skills_dir.exists():
            for item in self.skills_dir.iterdir():
                if item.is_symlink():
                    try:
                        target = item.resolve()
                        if "spellbook" in str(target).lower():
                            has_skills = True
                            break
                    except OSError:
                        pass
                elif item.is_dir() and (item / "SKILL.md").exists():
                    # Check if SKILL.md points to spellbook
                    skill_file = item / "SKILL.md"
                    if skill_file.is_symlink():
                        try:
                            target = skill_file.resolve()
                            if "spellbook" in str(target).lower():
                                has_skills = True
                                break
                        except OSError:
                            pass

        return PlatformStatus(
            platform=self.platform_id,
            available=True,  # We always create the directory
            installed=has_skills,
            version=self.version if has_skills else None,
            details={
                "config_dir": str(self.config_dir),
                "skills_dir": str(self.skills_dir),
            },
        )

    def install(
        self, force: bool = False, skip_global_steps: bool = False
    ) -> List["InstallResult"]:
        """Install Prime Agent components.

        Installs:
        - Skills from spellbook/skills/ -> ~/.prime/agent/skills/
        - Commands from spellbook/commands/ -> ~/.prime/agent/skills/commands/
        - AGENTS.spellbook.md as a skill at ~/.prime/agent/skills/spellbook/SKILL.md
        """
        from ..core import InstallResult

        results: List[InstallResult] = []

        # Ensure config directory exists
        if not self.ensure_config_dir():
            results.append(
                InstallResult(
                    component="config_dir",
                    platform=self.platform_id,
                    success=False,
                    action="failed",
                    message=f"Failed to create {self.config_dir}",
                )
            )
            return results

        # Create skills directory
        if not self.dry_run:
            self.skills_dir.mkdir(parents=True, exist_ok=True)

        # Step 1: Clean up old spellbook symlinks
        self._step("Cleaning up old symlinks")
        total_cleaned = 0
        if self.skills_dir.exists():
            cleanup_results = cleanup_spellbook_symlinks(
                self.skills_dir, dry_run=self.dry_run
            )
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

        # Step 2: Install skills as directory symlinks
        self._step("Installing skills")
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

        # Step 3: Install commands as skills in a commands/ subdirectory.
        # Prime Agent doesn't have a separate "commands" concept - everything is a skill.
        # Command names are used directly as skill directory names. The only collision
        # with existing skills is "canvas" which gets a "cmd-" prefix.
        self._step("Installing commands as skills")
        commands_skills_dir = self.skills_dir / "commands"
        if not self.dry_run:
            commands_skills_dir.mkdir(parents=True, exist_ok=True)

        # Clean up old command symlinks
        if commands_skills_dir.exists():
            cleanup_spellbook_symlinks(commands_skills_dir, dry_run=self.dry_run)

        cmd_count = 0
        commands_source = self.spellbook_dir / "commands"
        if commands_source.exists():
            for cmd_file in commands_source.glob("*.md"):
                cmd_name = cmd_file.stem
                cmd_skill_dir = commands_skills_dir / cmd_name

                if not self.dry_run:
                    cmd_skill_dir.mkdir(parents=True, exist_ok=True)

                # Symlink the command file as SKILL.md in the skill directory
                target = cmd_skill_dir / "SKILL.md"
                link_result = create_symlink(cmd_file, target, self.dry_run)
                if link_result.success:
                    cmd_count += 1

        if cmd_count > 0:
            results.append(
                InstallResult(
                    component="commands",
                    platform=self.platform_id,
                    success=True,
                    action="installed",
                    message=f"commands: {cmd_count} installed as skills",
                )
            )

        # Step 4: AGENTS.spellbook.md is intentionally NOT installed.
        # PR #442 (feat/modular-rule-modules) splits the monolithic
        # AGENTS.spellbook.md into installable rule modules under rules/.
        # When that PR merges, the modular rules will install via the
        # existing rules/ directory mechanism. For now, prime-agent users
        # who want spellbook behavioral rules loaded should either:
        #   (a) wait for PR #442 to merge, or
        #   (b) run `rlm.harness.create_prompt_note(...)` manually after
        #       install to inject AGENTS.spellbook.md content as a prompt
        #       note (cannot be done from the installer — runs outside
        #       prime-agent's IPython kernel).
        self._step("Skipping AGENTS.spellbook.md (modularized in PR #442)")

        return results

    def uninstall(self, skip_global_steps: bool = False) -> List["InstallResult"]:
        """Uninstall Prime Agent components."""
        from ..core import InstallResult

        results: List[InstallResult] = []

        if not self.config_dir.exists():
            return results

        # Remove all spellbook symlinks in skills directory
        if self.skills_dir.exists():
            # Remove individual skill symlinks
            for item in list(self.skills_dir.iterdir()):
                if item.is_symlink():
                    if self.dry_run:
                        results.append(
                            InstallResult(
                                component="skill",
                                platform=self.platform_id,
                                success=True,
                                action="removed",
                                message=f"would remove {item.name}",
                            )
                        )
                    else:
                        try:
                            item.unlink()
                            results.append(
                                InstallResult(
                                    component="skill",
                                    platform=self.platform_id,
                                    success=True,
                                    action="removed",
                                    message=f"removed {item.name}",
                                )
                            )
                        except OSError as e:
                            results.append(
                                InstallResult(
                                    component="skill",
                                    platform=self.platform_id,
                                    success=False,
                                    action="failed",
                                    message=f"failed to remove {item.name}: {e}",
                                )
                            )
                elif item.is_dir():
                    # Check if it's a spellbook skill (has symlinked SKILL.md pointing to spellbook)
                    skill_file = item / "SKILL.md"
                    if skill_file.is_symlink():
                        try:
                            target = skill_file.resolve()
                            if "spellbook" in str(target).lower():
                                if self.dry_run:
                                    results.append(
                                        InstallResult(
                                            component="skill_dir",
                                            platform=self.platform_id,
                                            success=True,
                                            action="removed",
                                            message=f"would remove {item.name}/",
                                        )
                                    )
                                else:
                                    import shutil
                                    shutil.rmtree(item)
                                    results.append(
                                        InstallResult(
                                            component="skill_dir",
                                            platform=self.platform_id,
                                            success=True,
                                            action="removed",
                                            message=f"removed {item.name}/",
                                        )
                                    )
                        except OSError:
                            pass

            # Clean up commands subdirectory
            commands_dir = self.skills_dir / "commands"
            if commands_dir.exists():
                if self.dry_run:
                    results.append(
                        InstallResult(
                            component="commands",
                            platform=self.platform_id,
                            success=True,
                            action="removed",
                            message="would remove commands/",
                        )
                    )
                else:
                    import shutil
                    shutil.rmtree(commands_dir)
                    results.append(
                        InstallResult(
                            component="commands",
                            platform=self.platform_id,
                            success=True,
                            action="removed",
                            message="removed commands/",
                        )
                    )

        return results

    def get_context_files(self) -> List[Path]:
        """Get context files managed by this platform.

        Prime Agent doesn't use context files the same way as other platforms.
        Instead, behavioral guidance is loaded via the spellbook skill.
        """
        return [self.skills_dir / "spellbook" / "SKILL.md"]

    def get_symlinks(self) -> List[Path]:
        """Get all symlinks created by this platform."""
        symlinks: List[Path] = []

        if self.skills_dir.exists():
            for item in self.skills_dir.iterdir():
                if item.is_symlink():
                    symlinks.append(item)
                elif item.is_dir():
                    skill_file = item / "SKILL.md"
                    if skill_file.is_symlink():
                        symlinks.append(skill_file)

        return symlinks

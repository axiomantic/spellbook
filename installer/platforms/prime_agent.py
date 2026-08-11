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
- Rule modules are delivered as files at ~/.prime/agent/rules/ and injected
  into the system prompt at session start via a TypeScript extension at
  ~/.prime/agent/extensions/spellbook-rules.ts. The extension auto-loads
  them as content; the user's own ~/.prime/agent/AGENTS.md is never touched.
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, List

from ..components.symlinks import (
    cleanup_spellbook_symlinks,
    create_skill_symlinks,
    create_symlink,
)
from .base import RULE_DELIVERY_DIRECTORY, PlatformInstaller, PlatformStatus

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

    @property
    def extensions_dir(self) -> Path:
        """Path to ~/.prime/agent/extensions/ (Prime Agent's auto-discovery root)."""
        return self.config_dir / "extensions"

    @property
    def extension_source(self) -> Path:
        """Source file shipped from the spellbook checkout."""
        return self.spellbook_dir / "extensions" / "prime-agent" / "spellbook-rules.ts"

    @property
    def extension_target(self) -> Path:
        """Installed location the extension will be auto-discovered from."""
        return self.extensions_dir / "spellbook-rules.ts"

    # Rule module delivery via a TypeScript extension. Prime Agent has no
    # native rules-directory walker, so the rule files are placed in a
    # rules/ subdir and the extension reads them at session_start.
    rule_delivery = RULE_DELIVERY_DIRECTORY

    def rule_module_dir(self) -> Path:
        """Prime Agent's rules directory: ~/.prime/agent/rules/.

        The spellbook installer symlinks one XX-spellbook-<id>.md per
        selected module into this directory. The TypeScript extension at
        extensions/spellbook-rules.ts reads every file matching the
        XX-spellbook-*.md pattern at session_start and inlines the bodies
        into the system prompt -- so the rules are part of the prompt,
        not skills the agent has to remember to load dynamically.
        """
        return self.config_dir / "rules"

    def legacy_rule_paths(self) -> List[Path]:
        """No legacy rule artifacts exist for prime-agent yet."""
        return []

    def detect(self) -> PlatformStatus:
        """Detect Prime Agent installation status.

        "Installed" requires at least one spellbook skill symlink, since
        that is the oldest stable signal. Rules and the rules extension
        are reported in ``details`` so users can see whether the newer
        behavioral-guidance path is in place, but a missing rules layer
        does not flip installed to False -- otherwise upgrading across
        the rules rollout would look like a downgrade.
        """
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

        rules_dir = self.rule_module_dir()
        rules_count = sum(1 for _ in rules_dir.glob("??-spellbook-*.md")) if rules_dir.is_dir() else 0
        extension_installed = self.extension_target.is_symlink()

        return PlatformStatus(
            platform=self.platform_id,
            available=True,  # We always create the directory
            installed=has_skills,
            version=self.version if has_skills else None,
            details={
                "config_dir": str(self.config_dir),
                "skills_dir": str(self.skills_dir),
                "rules_dir": str(rules_dir),
                "rules_installed": rules_count,
                "extension_installed": extension_installed,
            },
        )

    def install(
        self, force: bool = False, skip_global_steps: bool = False
    ) -> List["InstallResult"]:
        """Install Prime Agent components.

        Installs:
        - Skills from spellbook/skills/ -> ~/.prime/agent/skills/
        - Commands from spellbook/commands/ -> ~/.prime/agent/skills/commands/
        - Rule modules from spellbook/rules/ -> ~/.prime/agent/rules/
          (selection honors rules.module.<id> config; deselection prunes)
        - The spellbook-rules TypeScript extension at
          ~/.prime/agent/extensions/spellbook-rules.ts, which auto-loads
          the rule bodies into the system prompt at session start.
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

        # Step 4: Install rule modules. Honors the same rules.module.<id>
        # selection config every other platform uses (mandatory always,
        # preference gated on the user's recorded true/false). The base
        # class install_rule_modules() handles resolution, symlink
        # creation, and pruning of deselected modules.
        self._step("Installing rule modules")
        rule_results = self.install_rule_modules()
        results.extend(rule_results)

        # Step 5: Install the spellbook-rules TypeScript extension that
        # reads the rule files at session_start and inlines their bodies
        # into the system prompt. Symlinked (not copied) so spellbook
        # upgrades flow through without reinstalling prime-agent.
        self._step("Installing rules extension")
        extension_results = self._install_rules_extension()
        results.extend(extension_results)

        return results

    def _install_rules_extension(self) -> List["InstallResult"]:
        """Symlink the spellbook-rules extension into Prime Agent's auto-discovery root.

        Returns a single InstallResult. Success requires the source file to
        exist in the spellbook checkout; if it is missing the install
        fails rather than silently leaving the user without rule injection.
        """
        from ..core import InstallResult

        source = self.extension_source
        target = self.extension_target

        if not source.exists():
            return [
                InstallResult(
                    component="rules_extension",
                    platform=self.platform_id,
                    success=False,
                    action="failed",
                    message=(
                        f"rules extension: source not found at {source}; "
                        "spellbook checkout may be incomplete"
                    ),
                )
            ]

        # If the target already points at the right source, do nothing.
        # This makes reinstall idempotent without churning mtime on the
        # user's symlink every run.
        if target.is_symlink():
            try:
                existing = target.resolve()
                if existing == source.resolve():
                    return [
                        InstallResult(
                            component="rules_extension",
                            platform=self.platform_id,
                            success=True,
                            action="skipped",
                            message="rules extension: already installed",
                        )
                    ]
                # Wrong target: replace.
                if not self.dry_run:
                    target.unlink()
            except OSError:
                # Broken symlink -- unlink so create_symlink can replace it.
                if target.is_symlink():
                    target.unlink()

        if not self.dry_run:
            self.extensions_dir.mkdir(parents=True, exist_ok=True)

        result = create_symlink(source, target, dry_run=self.dry_run)
        return [
            InstallResult(
                component="rules_extension",
                platform=self.platform_id,
                success=result.success,
                action=result.action,
                message=f"rules extension: {result.message}",
            )
        ]

    def uninstall(self, skip_global_steps: bool = False) -> List["InstallResult"]:
        """Uninstall Prime Agent components.

        Removes in this order: rules (base class), rules extension,
        then skills / commands. Rules go first so the extension is
        removed before any rule file it reads -- leaving the rules
        files behind after the extension is gone means they are
        unread by Prime Agent until reinstall, which is silently
        broken state.
        """
        from ..core import InstallResult

        results: List[InstallResult] = []

        if not self.config_dir.exists():
            return results

        results.extend(self.uninstall_rule_modules())

        # Remove the rules extension symlink. Never remove anything
        # that is not a symlink pointing at our source -- a user
        # may have a different extension at this path.
        if self.extension_target.is_symlink():
            try:
                if self.extension_target.resolve() == self.extension_source.resolve():
                    if self.dry_run:
                        results.append(
                            InstallResult(
                                component="rules_extension",
                                platform=self.platform_id,
                                success=True,
                                action="removed",
                                message="would remove rules extension symlink",
                            )
                        )
                    else:
                        self.extension_target.unlink()
                        results.append(
                            InstallResult(
                                component="rules_extension",
                                platform=self.platform_id,
                                success=True,
                                action="removed",
                                message="removed rules extension symlink",
                            )
                        )
            except OSError:
                # Broken symlink or unreadable source -- nothing to do
                # safely, leave it for the user to inspect.
                pass

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

        Prime Agent uses two parallel paths for behavioral guidance:

        - ``~/.prime/agent/rules/<id>.md`` symlinks read by the
          spellbook-rules extension at session_start (the rules
          themselves, inlined into the system prompt).
        - ``~/.prime/agent/extensions/spellbook-rules.ts`` the
          extension file Prime Agent auto-discovers.

        We deliberately do NOT list ``~/.prime/agent/AGENTS.md`` here:
        that file belongs to the user, and spellbook does not own it.
        """
        rules_dir = self.rule_module_dir()
        return list(rules_dir.glob("??-spellbook-*.md")) + [self.extension_target]

    def get_symlinks(self) -> List[Path]:
        """Get all symlinks created by this platform.

        Reports skill symlinks under skills/, command symlinks under
        skills/commands/, rule symlinks under rules/, and the rules
        extension symlink under extensions/. A broken symlink is
        skipped so the inspection helper does not crash on a partial
        install state.
        """
        symlinks: List[Path] = []

        rules_dir = self.rule_module_dir()
        for parent in (self.skills_dir, rules_dir, self.extensions_dir):
            if not parent.exists():
                continue
            for item in parent.iterdir():
                if item.is_symlink():
                    try:
                        item.resolve()
                        symlinks.append(item)
                    except OSError:
                        # Broken symlink -- not safe to report.
                        continue
                elif item.is_dir():
                    skill_file = item / "SKILL.md"
                    if skill_file.is_symlink():
                        try:
                            skill_file.resolve()
                            symlinks.append(skill_file)
                        except OSError:
                            continue

        return symlinks

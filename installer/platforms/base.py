"""
Abstract base class for platform installers.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from ..components.rule_bundle import BundleTooLargeError, generate_bundle
from ..components.rule_delivery import (
    install_module_symlinks,
    remove_bundle,
    remove_legacy_artifacts,
    remove_module_symlinks,
    write_bundle,
)
from ..components.rule_modules import (
    RuleModule,
    get_rules_dir,
    load_rule_modules,
    resolve_selection,
)

if TYPE_CHECKING:
    from ..core import InstallResult

# How a platform receives rule modules.
#
# "directory" -- one real symlink per selected module, so module identity
#     survives at the destination.
# "flat" -- a generated concatenation at the harness's real instruction path,
#     because the harness cannot follow a reference.
# "none" -- the platform delivers rules by some other mechanism entirely.
RULE_DELIVERY_DIRECTORY = "directory"
RULE_DELIVERY_FLAT = "flat"
RULE_DELIVERY_NONE = "none"


@dataclass
class PlatformStatus:
    """Status of a platform installation."""

    platform: str
    available: bool  # Config directory exists or can be created
    installed: bool  # Spellbook components are installed
    version: Optional[str]  # Installed version if any
    details: Dict[str, Any] = field(default_factory=dict)


class PlatformInstaller(ABC):
    """Abstract base class for platform-specific installers."""

    def __init__(
        self,
        spellbook_dir: Path,
        config_dir: Path,
        version: str,
        dry_run: bool = False,
        on_step: Optional[Callable[[str], None]] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        self.spellbook_dir = spellbook_dir
        self.config_dir = config_dir
        self.version = version
        self.dry_run = dry_run
        self._on_step = on_step
        self._context = context or {}

    def _step(self, message: str) -> None:
        """Emit a progress step message."""
        if self._on_step:
            self._on_step(message)

    @property
    @abstractmethod
    def platform_name(self) -> str:
        """Human-readable platform name."""
        pass

    @property
    @abstractmethod
    def platform_id(self) -> str:
        """Platform identifier (e.g., 'claude_code')."""
        pass

    @abstractmethod
    def detect(self) -> PlatformStatus:
        """
        Detect platform status.

        Returns PlatformStatus with:
        - available: True if platform can be installed to
        - installed: True if spellbook is already installed
        - version: Installed version if any
        """
        pass

    @abstractmethod
    def install(self, force: bool = False, skip_global_steps: bool = False) -> List["InstallResult"]:
        """
        Install spellbook components for this platform.

        Args:
            force: Reinstall even if already installed
            skip_global_steps: If True, skip steps that are global (not
                per-config-dir). Used when installing to multiple config dirs
                for the same platform: global steps run on the first dir,
                then are skipped on subsequent dirs.

        Returns list of InstallResult for each component.
        """
        pass

    @abstractmethod
    def uninstall(self, skip_global_steps: bool = False) -> List["InstallResult"]:
        """
        Uninstall spellbook components from this platform.

        Args:
            skip_global_steps: If True, skip global cleanup steps.

        Returns list of InstallResult for each component.
        """
        pass

    @abstractmethod
    def get_context_files(self) -> List[Path]:
        """Get paths to context files managed by this platform."""
        pass

    @abstractmethod
    def get_symlinks(self) -> List[Path]:
        """Get paths to symlinks created by this platform."""
        pass

    def ensure_config_dir(self) -> bool:
        """Ensure the config directory exists."""
        if self.dry_run:
            return True
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            return True
        except OSError:
            return False

    # ------------------------------------------------------------------
    # Rule module delivery
    # ------------------------------------------------------------------

    rule_delivery: str = RULE_DELIVERY_NONE

    def rule_module_dir(self) -> Optional[Path]:
        """Directory that receives one file per selected module.

        None on a flat harness, which receives a generated bundle instead.
        """
        return None

    def rule_bundle_path(self) -> Optional[Path]:
        """Real instruction path that receives the generated bundle.

        None on a directory-capable harness.
        """
        return None

    def rule_bundle_preserve_existing(self) -> bool:
        """Whether an existing user file at the bundle path must be preserved.

        True only where spellbook must own a path the user may already own, in
        which case their content is kept and the bundle is appended inside a
        demarcated region.
        """
        return False

    def rule_bundle_cap(self) -> Optional[int]:
        """Byte cap for this harness's bundle, or None when it imposes none."""
        return None

    def legacy_rule_paths(self) -> List[Path]:
        """Retired sidecar paths this platform must clean up.

        These are probed with ``lexists`` because after the monolith's deletion
        they are dangling symlinks, which ``exists()`` reports as absent.
        """
        return []

    def legacy_context_files(self) -> List[Path]:
        """Context files that may carry a legacy demarcated spellbook block."""
        return []

    def all_rule_modules(self) -> List[RuleModule]:
        """Every module in the checkout, in delivery order."""
        modules = self._context.get("rule_modules")
        if modules is None:
            modules = load_rule_modules(get_rules_dir(self.spellbook_dir))
        return list(modules)

    def selected_rule_modules(self) -> List[RuleModule]:
        """The modules this install delivers.

        Falls back to resolving defaults when no selection is in the shared
        context, so an installer constructed directly still delivers a coherent
        ruleset rather than nothing.
        """
        selection = self._context.get("rule_selection")
        modules = self.all_rule_modules()
        if selection is None:
            return resolve_selection(modules).selected
        chosen = set(selection.selected_ids)
        return [m for m in modules if m.is_mandatory or m.id in chosen]

    def on_rule_modules_installed(
        self, installed: List[Path], removed: List[Path]
    ) -> List["InstallResult"]:
        """Hook for platforms that must register delivered files somewhere.

        OpenCode is the case this exists for: its resolver loads only the paths
        listed in ``opencode.json``, so a file on disk that is not registered
        does not load at all.
        """
        return []

    def install_rule_modules(self) -> List["InstallResult"]:
        """Deliver the selected rule modules and clean up retired artifacts.

        Legacy artifacts are removed only after delivery succeeds. The reverse
        order would leave a user with neither the retired sidecar nor the
        modules that replace it.
        """
        from ..core import InstallResult

        results: List["InstallResult"] = []

        if self.rule_delivery == RULE_DELIVERY_NONE:
            return results

        # A resolution failure upstream must never present as "deliver nothing".
        # Delivering nothing to a directory harness PRUNES every module already
        # installed, so a transient unreadable rules/ would silently uninstall
        # the whole ruleset and report success.
        error = self._context.get("rule_delivery_error")
        if error:
            return [
                InstallResult(
                    component="rule_modules",
                    platform=self.platform_id,
                    success=False,
                    action="failed",
                    message=f"rule modules: {error}; refusing to modify delivered rules",
                )
            ]

        selected = self.selected_rule_modules()
        if not selected:
            return [
                InstallResult(
                    component="rule_modules",
                    platform=self.platform_id,
                    success=False,
                    action="failed",
                    message=(
                        "rule modules: resolved to an empty module set; "
                        "refusing to modify delivered rules"
                    ),
                )
            ]

        if self.rule_delivery == RULE_DELIVERY_DIRECTORY:
            target = self.rule_module_dir()
            if target is None:
                return results
            outcome = install_module_symlinks(
                get_rules_dir(self.spellbook_dir),
                target,
                selected,
                dry_run=self.dry_run,
            )
            results.append(
                InstallResult(
                    component="rule_modules",
                    platform=self.platform_id,
                    success=outcome.success,
                    action=outcome.action,
                    message=outcome.message,
                )
            )
            if outcome.success:
                results.extend(
                    self.on_rule_modules_installed(outcome.installed, outcome.removed)
                )

        elif self.rule_delivery == RULE_DELIVERY_FLAT:
            path = self.rule_bundle_path()
            if path is None:
                return results
            try:
                bundle = generate_bundle(
                    selected,
                    self.version,
                    self.platform_id,
                    cap=self.rule_bundle_cap(),
                )
            except BundleTooLargeError as exc:
                results.append(
                    InstallResult(
                        component="rule_modules",
                        platform=self.platform_id,
                        success=False,
                        action="failed",
                        message=f"rule bundle: {exc}",
                    )
                )
                return results

            outcome = write_bundle(
                path,
                bundle,
                dry_run=self.dry_run,
                preserve_existing=self.rule_bundle_preserve_existing(),
            )
            for note in outcome.notes:
                self._step(note)
            for line in bundle.drop_report():
                self._step(line)
            results.append(
                InstallResult(
                    component="rule_modules",
                    platform=self.platform_id,
                    success=outcome.success,
                    action=outcome.action,
                    message=outcome.message,
                )
            )
        else:
            return results

        removed_legacy = remove_legacy_artifacts(
            self.legacy_rule_paths(), dry_run=self.dry_run
        )
        if removed_legacy:
            results.append(
                InstallResult(
                    component="legacy_rules",
                    platform=self.platform_id,
                    success=True,
                    action="removed",
                    message=(
                        "retired rule sidecar: "
                        + ", ".join(p.name for p in removed_legacy)
                    ),
                )
            )

        return results

    def uninstall_rule_modules(self) -> List["InstallResult"]:
        """Remove every delivered rule artifact, including retired sidecars.

        Uninstall must be complete: ``detect()`` keys on the delivered rules, so
        anything left behind keeps the platform reporting as installed forever.
        """
        from ..core import InstallResult

        results: List["InstallResult"] = []
        removed: List[Path] = []
        failures: List[str] = []

        target = self.rule_module_dir()
        if target is not None:
            removed.extend(
                remove_module_symlinks(
                    target, dry_run=self.dry_run, failures=failures
                )
            )

        bundle_path = self.rule_bundle_path()
        if bundle_path is not None:
            gone = remove_bundle(
                bundle_path,
                dry_run=self.dry_run,
                preserve_existing=self.rule_bundle_preserve_existing(),
            )
            if gone is not None:
                removed.append(gone)

        removed.extend(
            remove_legacy_artifacts(
                self.legacy_rule_paths(), dry_run=self.dry_run, failures=failures
            )
        )

        if failures:
            results.append(
                InstallResult(
                    component="rule_modules",
                    platform=self.platform_id,
                    success=False,
                    action="failed",
                    message=(
                        f"rule modules: {len(removed)} removed, "
                        f"{len(failures)} could not be removed "
                        f"({'; '.join(failures[:3])})"
                    ),
                )
            )
            return results

        if removed:
            results.append(
                InstallResult(
                    component="rule_modules",
                    platform=self.platform_id,
                    success=True,
                    action="removed",
                    message=f"rule modules: {len(removed)} removed",
                )
            )

        return results

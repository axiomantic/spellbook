"""Detection of an existing install, and the legacy upgrade path.

The first platform that reports installed is the source of truth for *what the
user had*. It is deliberately not the source of truth for *what to clean up*:
the harnesses are in inconsistent states relative to each other, so migration
runs on every selected platform independently.

Every probe here uses ``os.path.lexists``. After the monolith's deletion an
upgrading user's sidecar symlinks all dangle, and ``Path.exists()`` follows a
symlink and returns False for a broken one. A detector using ``exists()``
classifies that user as FRESH, skips migration, and leaves the dead link in
place permanently -- reading as "installed" to a human and as nothing at all to
the harness.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Optional, Sequence

from ..demarcation import has_demarcated_section
from .rule_delivery import INSTALLED_GLOB


class InstallState(str, Enum):
    """What shape of spellbook install was found, if any."""

    FRESH = "fresh"
    MODULAR = "modular"
    SYMLINK = "symlink"
    LEGACY = "legacy"


@dataclass
class DetectionResult:
    """The detected state plus the platform it was read from."""

    state: InstallState
    platform: Optional[str] = None
    evidence: List[str] = field(default_factory=list)

    @property
    def needs_migration(self) -> bool:
        """Whether this user has legacy artifacts that must be replaced."""
        return self.state in (InstallState.SYMLINK, InstallState.LEGACY)


def _has_modules(rule_dir: Optional[Path]) -> bool:
    if rule_dir is None or not rule_dir.is_dir():
        return False
    return any(rule_dir.glob(INSTALLED_GLOB))


def detect_platform_state(
    module_dir: Optional[Path],
    bundle_path: Optional[Path],
    legacy_paths: Sequence[Path],
    context_files: Sequence[Path],
    version: str,
) -> tuple[InstallState, List[str]]:
    """Classify one platform's install state.

    Ordering matters: a modular install is checked first so a user who has
    already migrated but still has a stale backup lying around is not dragged
    back through migration.
    """
    evidence: List[str] = []

    if _has_modules(module_dir):
        evidence.append(f"module files present in {module_dir}")
        return InstallState.MODULAR, evidence

    if bundle_path is not None and os.path.lexists(bundle_path):
        try:
            from .rule_bundle import DELIVERY_MARKER_PREFIX

            if DELIVERY_MARKER_PREFIX in bundle_path.read_text(encoding="utf-8"):
                evidence.append(f"generated bundle present at {bundle_path}")
                return InstallState.MODULAR, evidence
        except OSError:
            pass

    for path in legacy_paths:
        if os.path.lexists(path):
            dangling = not path.exists()
            evidence.append(
                f"legacy sidecar at {path}" + (" (dangling)" if dangling else "")
            )
            return InstallState.SYMLINK, evidence

    for path in context_files:
        if path.exists() and has_demarcated_section(path):
            evidence.append(f"legacy demarcated block in {path}")
            return InstallState.LEGACY, evidence

    return InstallState.FRESH, evidence


def detect_existing_install(installers: Sequence[object]) -> DetectionResult:
    """Return the state of the first platform that reports installed.

    ``installers`` are PlatformInstaller instances, walked in the caller's
    order, which is ``SUPPORTED_PLATFORMS`` order.
    """
    for installer in installers:
        state, evidence = detect_platform_state(
            module_dir=installer.rule_module_dir(),
            bundle_path=installer.rule_bundle_path(),
            legacy_paths=installer.legacy_rule_paths(),
            context_files=installer.legacy_context_files(),
            version=getattr(installer, "version", ""),
        )
        if state is not InstallState.FRESH:
            return DetectionResult(
                state=state,
                platform=getattr(installer, "platform_id", None),
                evidence=evidence,
            )

    return DetectionResult(state=InstallState.FRESH)

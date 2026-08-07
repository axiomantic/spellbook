"""Post-install verification that rules actually reach the harness.

A symlink existing is not evidence of delivery. The installer previously
reported success on five of seven harnesses for files nothing read. This module
turns "verify the artifact, not the signal" into a mechanical check: it looks
for the delivery marker in the harness's own assembled prompt where that is
obtainable, and reports an honest degradation where it is not.

Three result classes, and the third is the point. A harness whose prompt cannot
be dumped without an interactive login or a GUI is never recorded as verified.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import List, Optional

from .rule_bundle import delivery_marker
from .rule_delivery import CORE_MODULE_GLOB

PROBE_TIMEOUT_SEC = 20


class TripwireStatus(str, Enum):
    """How much a platform's delivery could actually be proven."""

    VERIFIED = "verified"
    """The marker was observed in the harness's assembled prompt."""

    DEGRADED = "degraded"
    """A weaker property was asserted, and the report says which."""

    FAILED = "failed"
    """The probe ran and the marker was absent. Delivery is broken."""

    SKIPPED = "skipped"
    """Nothing was delivered to this platform, so there is nothing to check."""


@dataclass
class TripwireResult:
    """One platform's delivery verification outcome."""

    platform: str
    status: TripwireStatus
    method: str
    message: str

    @property
    def ok(self) -> bool:
        return self.status is not TripwireStatus.FAILED

    def render(self) -> str:
        return f"{self.platform}: {self.status.value} ({self.method}) - {self.message}"


def _content_has_marker(path: Optional[Path], marker: str) -> Optional[bool]:
    """Whether a written artifact contains the marker. None if unreadable."""
    if path is None or not os.path.lexists(path):
        return None
    try:
        return marker in path.read_text(encoding="utf-8")
    except OSError:
        return None


def _probe_codex(config_dir: Path, marker: str) -> tuple[TripwireStatus, str, str]:
    """Render the model-visible prompt and grep it.

    ``codex debug prompt-input`` needs no auth and makes no API call, so this is
    the one harness where the assembled prompt is obtainable for free.
    """
    if shutil.which("codex") is None:
        return (
            TripwireStatus.DEGRADED,
            "path-asserted",
            "codex CLI not on PATH; prompt could not be rendered",
        )

    env = dict(os.environ)
    env["CODEX_HOME"] = str(config_dir)
    try:
        proc = subprocess.run(
            ["codex", "debug", "prompt-input"],
            capture_output=True,
            text=True,
            timeout=PROBE_TIMEOUT_SEC,
            env=env,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return (
            TripwireStatus.DEGRADED,
            "path-asserted",
            f"codex prompt dump unavailable: {exc}",
        )

    if proc.returncode != 0:
        return (
            TripwireStatus.DEGRADED,
            "path-asserted",
            f"codex prompt dump exited {proc.returncode}",
        )

    if marker in proc.stdout:
        return (
            TripwireStatus.VERIFIED,
            "prompt-asserted",
            "delivery marker found in the rendered prompt",
        )

    return (
        TripwireStatus.FAILED,
        "prompt-asserted",
        "delivery marker absent from the rendered prompt",
    )


def verify_platform(
    platform_id: str,
    version: str,
    module_dir: Optional[Path] = None,
    bundle_path: Optional[Path] = None,
    config_dir: Optional[Path] = None,
    registered: Optional[bool] = None,
) -> TripwireResult:
    """Verify that one platform will actually load the delivered rules.

    Args:
        platform_id: Platform identifier.
        version: Spellbook version, which the marker carries.
        module_dir: Rules directory for a directory-capable harness.
        bundle_path: Generated artifact for a flat harness.
        config_dir: Harness config dir, used by probes that need to be pointed
            at the install under test.
        registered: For opencode, whether every installed module path is listed
            in ``opencode.json``. Registration is the only load mechanism there,
            so an unregistered file is a non-delivery.
    """
    marker = delivery_marker(version)

    if platform_id == "codex" and config_dir is not None:
        status, method, message = _probe_codex(config_dir, marker)
        return TripwireResult(platform_id, status, method, message)

    if bundle_path is not None:
        found = _content_has_marker(bundle_path, marker)
        if found is None:
            return TripwireResult(
                platform_id,
                TripwireStatus.FAILED,
                "content-asserted",
                f"no artifact at {bundle_path}",
            )
        if not found:
            return TripwireResult(
                platform_id,
                TripwireStatus.FAILED,
                "content-asserted",
                f"delivery marker absent from {bundle_path}",
            )
        return TripwireResult(
            platform_id,
            TripwireStatus.DEGRADED,
            "content-asserted",
            (
                f"marker present in {bundle_path.name}; the harness's assembled "
                "prompt cannot be dumped without an interactive session"
            ),
        )

    if module_dir is not None:
        core = sorted(module_dir.glob(CORE_MODULE_GLOB)) if module_dir.is_dir() else []
        if not core:
            return TripwireResult(
                platform_id,
                TripwireStatus.FAILED,
                "path-asserted",
                f"mandatory core module missing from {module_dir}",
            )
        if not core[0].exists():
            return TripwireResult(
                platform_id,
                TripwireStatus.FAILED,
                "path-asserted",
                f"core module link at {core[0]} is dangling",
            )
        if registered is False:
            return TripwireResult(
                platform_id,
                TripwireStatus.FAILED,
                "registration-asserted",
                "module files are present but not registered, so none of them load",
            )
        method = "registration-asserted" if registered else "path-asserted"
        return TripwireResult(
            platform_id,
            TripwireStatus.DEGRADED,
            method,
            (
                "module files resolve at the harness's rule path; the assembled "
                "prompt is not obtainable without an interactive session"
            ),
        )

    return TripwireResult(
        platform_id,
        TripwireStatus.SKIPPED,
        "not-applicable",
        "no rule modules delivered to this platform",
    )


def render_report(results: List[TripwireResult]) -> List[str]:
    """Format the per-harness tripwire report for installer output.

    "Installed" and "verified" are different words, and this report never uses
    the second when it means the first.
    """
    if not results:
        return []
    lines = ["Rule delivery verification:"]
    lines.extend(f"  {result.render()}" for result in results)
    return lines
